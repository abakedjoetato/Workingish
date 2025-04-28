import discord
from discord.ext import commands
import logging
import asyncio
from database.connection import Database
from database.models import Server, GuildConfig, Kill
from utils.embeds import create_killfeed_embed

logger = logging.getLogger('deadside_bot.cogs.killfeed')

class KillfeedCommands(commands.Cog):
    """Commands for managing killfeed notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        self.server_trackers = {}
        # We'll initialize trackers after the cog is fully loaded, not during __init__
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        # Start tracking after a short delay to ensure everything is ready
        self.bot.loop.create_task(self.initialize_killfeed_trackers())
    
    async def initialize_killfeed_trackers(self):
        """Initialize kill trackers for all configured servers"""
        await self.bot.wait_until_ready()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in initialize_killfeed_trackers")
                return
                
            # Get all guild configs with killfeed channels
            collection = await self.db.get_collection("guild_configs")
            cursor = collection.find(
                # MongoDB-style query
                {} # Get all configs, we'll filter in Python
            )
            configs = await cursor.to_list(None)
            # Filter configs with a killfeed channel
            configs = [config for config in configs if config.get("killfeed_channel") is not None]
            
            for config in configs:
                guild_id = config["guild_id"]
                channel_id = config["killfeed_channel"]
                
                # Get servers for this guild
                servers = await Server.get_by_guild(self.db, guild_id)
                
                for server in servers:
                    self.server_trackers[str(server._id)] = {
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                        "last_kill_id": None
                    }
                    
                    # Start the tracker
                    self.bot.loop.create_task(self.track_server_kills(server._id, channel_id))
            
            logger.info(f"Initialized killfeed trackers for {len(self.server_trackers)} servers")
                
        except Exception as e:
            logger.error(f"Error initializing killfeed trackers: {e}")
    
    @commands.group(name="killfeed", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def killfeed(self, ctx):
        """Commands for managing killfeed notifications"""
        await ctx.send("Available commands: `channel`, `disable`")
    
    @killfeed.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set the channel for killfeed notifications
        
        Usage: !killfeed channel [#channel]
        
        If no channel is provided, the current channel will be used.
        """
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in set_channel command")
                await ctx.send("⚠️ Database connection not available. Please try again later.")
                return
                
            # Use current channel if none specified
            if not channel:
                channel = ctx.channel
            
            # Update guild config
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            guild_config.killfeed_channel = channel.id
            await guild_config.update(self.db)
            
            # Update trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            for server in servers:
                # Update tracker info
                self.server_trackers[str(server._id)] = {
                    "guild_id": ctx.guild.id,
                    "channel_id": channel.id,
                    "last_kill_id": None
                }
                
                # Start the tracker if not already running
                if not any(task.get_name() == f"killfeed_tracker_{server._id}" 
                          for task in asyncio.all_tasks()):
                    self.bot.loop.create_task(
                        self.track_server_kills(server._id, channel.id),
                        name=f"killfeed_tracker_{server._id}"
                    )
            
            await ctx.send(f"✅ Killfeed notifications will now be sent to {channel.mention}")
                
        except Exception as e:
            logger.error(f"Error setting killfeed channel: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @killfeed.command(name="disable")
    @commands.has_permissions(manage_channels=True)
    async def disable_killfeed(self, ctx):
        """Disable killfeed notifications for this guild"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in disable_killfeed command")
                await ctx.send("⚠️ Database connection not available. Please try again later.")
                return
                
            # Update guild config
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            guild_config.killfeed_channel = None
            await guild_config.update(self.db)
            
            # Remove trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            for server in servers:
                if str(server._id) in self.server_trackers:
                    del self.server_trackers[str(server._id)]
            
            await ctx.send("✅ Killfeed notifications have been disabled.")
                
        except Exception as e:
            logger.error(f"Error disabling killfeed: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    async def track_server_kills(self, server_id, channel_id):
        """
        Background task to track new kills for a server and send to killfeed channel
        
        Args:
            server_id: MongoDB ObjectId of the server
            channel_id: Discord channel ID to send killfeed messages
        """
        # Ensure we don't start multiple trackers for the same server
        task_name = f"killfeed_tracker_{server_id}"
        for task in asyncio.all_tasks():
            if task.get_name() == task_name and task != asyncio.current_task():
                logger.debug(f"Killfeed tracker for server {server_id} already running")
                return
        
        # Set task name for identification
        asyncio.current_task().set_name(task_name)
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error(f"Database instance not available in track_server_kills for server {server_id}")
                return
            
            # Get initial last kill ID
            if str(server_id) in self.server_trackers and self.server_trackers[str(server_id)]["last_kill_id"]:
                last_kill_id = self.server_trackers[str(server_id)]["last_kill_id"]
            else:
                # Get the most recent kill for this server
                collection = await self.db.get_collection("kills")
                cursor = collection.find({"server_id": server_id})
                # Sort and limit in MongoDB
                latest_kill = await cursor.to_list(1)
                
                if latest_kill:
                    last_kill_id = latest_kill[0]["_id"]
                else:
                    last_kill_id = None
                
                # Update tracker
                if str(server_id) in self.server_trackers:
                    self.server_trackers[str(server_id)]["last_kill_id"] = last_kill_id
            
            while True:
                try:
                    # Check if tracker still exists (could be removed if disabled)
                    if str(server_id) not in self.server_trackers:
                        logger.debug(f"Killfeed tracker for server {server_id} was disabled")
                        return
                    
                    # Get channel
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        logger.warning(f"Could not find channel {channel_id} for killfeed")
                        await asyncio.sleep(60)
                        continue
                    
                    # Get new kills
                    query = {"server_id": server_id}
                    # We can't use MongoDB-style operators in PostgreSQL
                    # We'll filter results in Python after fetching
                    
                    # Get the collection and execute the query
                    collection = await self.db.get_collection("kills")
                    cursor = collection.find(query)
                    all_kills = await cursor.to_list(100)  # Limit to avoid flooding
                    
                    # Filter kills that are newer than last_kill_id if needed
                    if last_kill_id:
                        new_kills = [
                            kill for kill in all_kills 
                            if kill.get("id", 0) > last_kill_id or kill.get("_id", 0) > last_kill_id
                        ]
                    else:
                        new_kills = all_kills
                    
                    for kill_data in new_kills:
                        # Create a Kill object
                        kill = Kill(**{**kill_data, "_id": kill_data["_id"]})
                        
                        # Get server info for the embed
                        server = await Server.get_by_id(self.db, kill.server_id)
                        server_name = server.name if server else "Unknown Server"
                        
                        # Create and send embed
                        embed = await create_killfeed_embed(kill, server_name)
                        await channel.send(embed=embed)
                        
                        # Update last kill ID
                        last_kill_id = kill._id
                        if str(server_id) in self.server_trackers:
                            self.server_trackers[str(server_id)]["last_kill_id"] = last_kill_id
                    
                    # Log the number of kills processed
                    if new_kills:
                        logger.debug(f"Processed {len(new_kills)} new kills for server {server_id}")
                    
                    # Sleep before next check
                    await asyncio.sleep(15)
                
                except Exception as e:
                    logger.error(f"Error in killfeed tracker for server {server_id}: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
        
        except asyncio.CancelledError:
            logger.info(f"Killfeed tracker for server {server_id} was cancelled")
            return
        except Exception as e:
            logger.error(f"Fatal error in killfeed tracker for server {server_id}: {e}")
