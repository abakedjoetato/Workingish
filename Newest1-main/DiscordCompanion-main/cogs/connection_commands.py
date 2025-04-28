import discord
from discord.ext import commands
import logging
import asyncio
from database.connection import Database
from database.models import Server, GuildConfig, ConnectionEvent
from utils.embeds import create_connection_embed

logger = logging.getLogger('deadside_bot.cogs.connection')

class ConnectionCommands(commands.Cog):
    """Commands for managing connection notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.server_trackers = {}
        self.bot.loop.create_task(self.initialize_connection_trackers())
    
    async def initialize_connection_trackers(self):
        """Initialize connection trackers for all configured servers"""
        await self.bot.wait_until_ready()
        
        try:
            db = await Database.get_instance()
            
            # Get all guild configs with connection channels
            collection = await db.get_collection("guild_configs")
            cursor = await collection.find(
                # PostgreSQL doesn't support MongoDB-style $ne operator directly
                # Instead, we need to use IS NOT NULL in SQL
                {} # Get all configs, we'll filter in Python
            )
            configs = await cursor.to_list(None)
            # Filter configs with a connection channel
            configs = [config for config in configs if config.get("connection_channel") is not None]
            
            for config in configs:
                guild_id = config["guild_id"]
                channel_id = config["connection_channel"]
                
                # Get servers for this guild
                servers = await Server.get_by_guild(db, guild_id)
                
                for server in servers:
                    self.server_trackers[str(server._id)] = {
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                        "last_connection_id": None
                    }
                    
                    # Start the tracker
                    self.bot.loop.create_task(self.track_server_connections(server._id, channel_id))
            
            logger.info(f"Initialized connection trackers for {len(self.server_trackers)} servers")
                
        except Exception as e:
            logger.error(f"Error initializing connection trackers: {e}")
    
    @commands.group(name="connections", aliases=["connection"], invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def connections(self, ctx):
        """Commands for managing connection notifications"""
        await ctx.send("Available commands: `channel`, `disable`")
    
    @connections.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set the channel for connection notifications
        
        Usage: !connections channel [#channel]
        
        If no channel is provided, the current channel will be used.
        """
        try:
            db = await Database.get_instance()
            
            # Use current channel if none specified
            if not channel:
                channel = ctx.channel
            
            # Update guild config
            guild_config = await GuildConfig.get_or_create(db, ctx.guild.id)
            guild_config.connection_channel = channel.id
            await guild_config.update(db)
            
            # Update trackers for all servers in this guild
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            for server in servers:
                # Update tracker info
                self.server_trackers[str(server._id)] = {
                    "guild_id": ctx.guild.id,
                    "channel_id": channel.id,
                    "last_connection_id": None
                }
                
                # Start the tracker if not already running
                if not any(task.get_name() == f"connection_tracker_{server._id}" 
                          for task in asyncio.all_tasks()):
                    self.bot.loop.create_task(
                        self.track_server_connections(server._id, channel.id),
                        name=f"connection_tracker_{server._id}"
                    )
            
            await ctx.send(f"✅ Connection notifications will now be sent to {channel.mention}")
                
        except Exception as e:
            logger.error(f"Error setting connection channel: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @connections.command(name="disable")
    @commands.has_permissions(manage_channels=True)
    async def disable_connections(self, ctx):
        """Disable connection notifications for this guild"""
        try:
            db = await Database.get_instance()
            
            # Update guild config
            guild_config = await GuildConfig.get_or_create(db, ctx.guild.id)
            guild_config.connection_channel = None
            await guild_config.update(db)
            
            # Remove trackers for all servers in this guild
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            for server in servers:
                if str(server._id) in self.server_trackers:
                    del self.server_trackers[str(server._id)]
            
            await ctx.send("✅ Connection notifications have been disabled.")
                
        except Exception as e:
            logger.error(f"Error disabling connections: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @connections.command(name="list")
    async def list_connections(self, ctx, *, server_name: str = None, limit: int = 10):
        """
        List recent player connections for a server
        
        Usage: !connections list [server_name] [limit]
        
        If no server name is provided, connections for all servers will be shown.
        Default limit is 10, max limit is 20.
        """
        try:
            db = await Database.get_instance()
            
            # Limit the number of connections
            if limit > 20:
                limit = 20
            
            if server_name:
                # Get connections for specific server
                servers = await Server.get_by_guild(db, ctx.guild.id)
                server = next((s for s in servers if s.name.lower() == server_name.lower()), None)
                
                if not server:
                    await ctx.send(f"⚠️ Server '{server_name}' not found. Use `!server list` to see all configured servers.")
                    return
                
                # Get recent connections
                collection = await db.get_collection("connection_events")
                cursor = await collection.find({"server_id": server._id})
                connections = await cursor.to_list(limit)
                
                # Create embed
                embed = discord.Embed(
                    title=f"Recent Connections for {server.name}",
                    description=f"Last {len(connections)} connection events",
                    color=discord.Color.blue()
                )
                
                for conn in connections:
                    event_type = conn["event_type"].capitalize()
                    timestamp = conn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    player_name = conn["player_name"]
                    
                    if conn["event_type"] == "kick":
                        embed.add_field(
                            name=f"{event_type}: {player_name}",
                            value=f"Time: {timestamp}\nReason: {conn.get('reason', 'Unknown')}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name=f"{event_type}: {player_name}",
                            value=f"Time: {timestamp}",
                            inline=True
                        )
                
                await ctx.send(embed=embed)
            else:
                # Get connections for all servers
                servers = await Server.get_by_guild(db, ctx.guild.id)
                
                if not servers:
                    await ctx.send("No servers have been configured yet. Use `!server add` to add a server.")
                    return
                
                # Get recent connections for each server
                for server in servers:
                    collection = await db.get_collection("connection_events")
                    cursor = await collection.find({"server_id": server._id})
                    connections = await cursor.to_list(limit)
                    
                    # Create embed
                    embed = discord.Embed(
                        title=f"Recent Connections for {server.name}",
                        description=f"Last {len(connections)} connection events",
                        color=discord.Color.blue()
                    )
                    
                    for conn in connections:
                        event_type = conn["event_type"].capitalize()
                        timestamp = conn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        player_name = conn["player_name"]
                        
                        if conn["event_type"] == "kick":
                            embed.add_field(
                                name=f"{event_type}: {player_name}",
                                value=f"Time: {timestamp}\nReason: {conn.get('reason', 'Unknown')}",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name=f"{event_type}: {player_name}",
                                value=f"Time: {timestamp}",
                                inline=True
                            )
                    
                    await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error listing connections: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    async def track_server_connections(self, server_id, channel_id):
        """
        Background task to track new connections for a server and send to channel
        
        Args:
            server_id: MongoDB ObjectId of the server
            channel_id: Discord channel ID to send connection messages
        """
        # Ensure we don't start multiple trackers for the same server
        task_name = f"connection_tracker_{server_id}"
        for task in asyncio.all_tasks():
            if task.get_name() == task_name and task != asyncio.current_task():
                logger.debug(f"Connection tracker for server {server_id} already running")
                return
        
        # Set task name for identification
        asyncio.current_task().set_name(task_name)
        
        try:
            db = await Database.get_instance()
            
            # Get initial last connection ID
            if str(server_id) in self.server_trackers and self.server_trackers[str(server_id)]["last_connection_id"]:
                last_connection_id = self.server_trackers[str(server_id)]["last_connection_id"]
            else:
                # Get the most recent connection for this server
                collection = await db.get_collection("connection_events")
                cursor = await collection.find({"server_id": server_id})
                latest_connection = await cursor.to_list(1)
                
                if latest_connection:
                    last_connection_id = latest_connection[0]["_id"]
                else:
                    last_connection_id = None
                
                # Update tracker
                if str(server_id) in self.server_trackers:
                    self.server_trackers[str(server_id)]["last_connection_id"] = last_connection_id
            
            while True:
                try:
                    # Check if tracker still exists (could be removed if disabled)
                    if str(server_id) not in self.server_trackers:
                        logger.debug(f"Connection tracker for server {server_id} was disabled")
                        return
                    
                    # Get channel
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        logger.warning(f"Could not find channel {channel_id} for connections")
                        await asyncio.sleep(60)
                        continue
                    
                    # Get new connections
                    query = {"server_id": server_id}
                    # We can't use MongoDB-style operators in PostgreSQL
                    # We'll filter results in Python after fetching
                    
                    # Get the collection and execute the query
                    collection = await db.get_collection("connection_events")
                    cursor = await collection.find(query)
                    all_connections = await cursor.to_list(100)  # Limit to avoid flooding
                    
                    # Filter connections that are newer than last_connection_id if needed
                    if last_connection_id:
                        new_connections = [
                            conn for conn in all_connections 
                            if conn.get("id", 0) > last_connection_id or conn.get("_id", 0) > last_connection_id
                        ]
                    else:
                        new_connections = all_connections
                    
                    for conn_data in new_connections:
                        # Create a ConnectionEvent object
                        connection = ConnectionEvent(**{**conn_data, "_id": conn_data["_id"]})
                        
                        # Get server info for the embed
                        server = await Server.get_by_id(db, connection.server_id)
                        server_name = server.name if server else "Unknown Server"
                        
                        # Create and send embed
                        embed = await create_connection_embed(connection, server_name)
                        await channel.send(embed=embed)
                        
                        # Update last connection ID
                        last_connection_id = connection._id
                        if str(server_id) in self.server_trackers:
                            self.server_trackers[str(server_id)]["last_connection_id"] = last_connection_id
                    
                    # Log the number of connections processed
                    if new_connections:
                        logger.debug(f"Processed {len(new_connections)} new connections for server {server_id}")
                    
                    # Sleep before next check
                    await asyncio.sleep(15)
                
                except Exception as e:
                    logger.error(f"Error in connection tracker for server {server_id}: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
        
        except asyncio.CancelledError:
            logger.info(f"Connection tracker for server {server_id} was cancelled")
            return
        except Exception as e:
            logger.error(f"Fatal error in connection tracker for server {server_id}: {e}")
