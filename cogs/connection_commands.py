import discord
from discord.ext import commands, tasks
import logging
import asyncio
from database.connection import Database
from database.models import Server, GuildConfig, ConnectionEvent
from utils.embeds import create_connection_embed

logger = logging.getLogger('deadside_bot.cogs.connection')

# Create slash command group
connection_group = discord.SlashCommandGroup(
    name="connections",
    description="Commands for managing connection notifications",
    default_member_permissions=discord.Permissions(manage_channels=True),
    contexts=[discord.InteractionContextType.guild]  # Using contexts for maximum compatibility
)

class ConnectionCommands(commands.Cog):
    """Commands for managing connection notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        self.server_trackers = {}
        # Add the connection command group to this cog
        self.connection_group = connection_group
        # We'll initialize trackers after the cog is fully loaded, not during __init__
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        # Start tracking after a short delay to ensure everything is ready
        self.bot.loop.create_task(self.initialize_connection_trackers())
        
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [connection_group]
    
    async def initialize_connection_trackers(self):
        """Initialize connection trackers for all configured servers"""
        await self.bot.wait_until_ready()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in initialize_connection_trackers")
                return
                
            # Get all guild configs with connection channels
            collection = await self.db.get_collection("guild_configs")
            cursor = collection.find(
                # MongoDB-style query
                {} # Get all configs, we'll filter in Python
            )
            configs = await cursor.to_list(None)
            # Filter configs with a connection channel
            configs = [config for config in configs if config.get("connection_channel") is not None]
            
            for config in configs:
                guild_id = config["guild_id"]
                channel_id = config["connection_channel"]
                
                # Get servers for this guild
                servers = await Server.get_by_guild(self.db, guild_id)
                
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
    
    @connection_group.command(
        name="channel",
        description="Set the channel for connection notifications",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def set_channel(self, ctx, 
                         channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=False) = None):
        """
        Set the channel for connection notifications
        
        Usage: /connections channel [#channel]
        
        If no channel is provided, the current channel will be used.
        """
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in set_channel command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Use current channel if none specified
            if not channel:
                channel = ctx.channel
            
            # Update guild config
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            guild_config.connection_channel = channel.id
            await guild_config.update(self.db)
            
            # Update trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
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
            
            await ctx.respond(f"✅ Connection notifications will now be sent to {channel.mention}")
                
        except Exception as e:
            logger.error(f"Error setting connection channel: {e}")
            await ctx.respond(f"❌ Error setting connection channel: {e}")
            
    @connection_group.command(
        name="disable", 
        description="Disable connection notifications for this guild", 
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def disable_connections(self, ctx):
        """Disable connection notifications for this guild"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in disable_connections command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Update guild config
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            guild_config.connection_channel = None
            await guild_config.update(self.db)
            
            # Remove trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            for server in servers:
                if str(server._id) in self.server_trackers:
                    del self.server_trackers[str(server._id)]
            
            await ctx.respond("✅ Connection notifications have been disabled.")
                
        except Exception as e:
            logger.error(f"Error disabling connections: {e}")
            await ctx.respond(f"❌ Error disabling connections: {e}")
            
    @connection_group.command(
        name="list", 
        description="List recent player connections for a server", 
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def list_connections(self, ctx, 
                               server_name: discord.Option(str, "Server name to show connections for", required=False) = None,
                               limit: discord.Option(int, "Number of connections to show (max: 20)", min_value=1, max_value=20, required=False) = 10):
        """
        List recent player connections for a server
        
        Usage: /connections list [server_name] [limit]
        
        If no server name is provided, connections for all servers will be shown.
        Default limit is 10, max limit is 20.
        """
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in list_connections command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Limit the number of connections
            if limit > 20:
                limit = 20
            
            if server_name:
                # Get connections for specific server
                servers = await Server.get_by_guild(self.db, ctx.guild.id)
                server = next((s for s in servers if s.name.lower() == server_name.lower()), None)
                
                if not server:
                    await ctx.respond(f"⚠️ Server '{server_name}' not found. Use `/server list` to see all configured servers.")
                    return
                
                # Get recent connections
                collection = await self.db.get_collection("connection_events")
                cursor = collection.find({"server_id": server._id})
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
                
                await ctx.respond(embed=embed)
            else:
                # Get connections for all servers
                servers = await Server.get_by_guild(self.db, ctx.guild.id)
                
                if not servers:
                    await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                    return
                
                # Create a combined embed for all servers
                combined_embed = discord.Embed(
                    title="Recent Connections for All Servers",
                    description=f"Last {limit} connection events per server",
                    color=discord.Color.blue()
                )
                
                # Get recent connections for each server
                for server in servers:
                    collection = await self.db.get_collection("connection_events")
                    cursor = collection.find({"server_id": server._id})
                    connections = await cursor.to_list(limit)
                    
                    if connections:
                        combined_embed.add_field(
                            name=f"📊 {server.name} ({len(connections)} events)",
                            value="Server connection events",
                            inline=False
                        )
                        
                        for conn in connections:
                            event_type = conn["event_type"].capitalize()
                            timestamp = conn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                            player_name = conn["player_name"]
                            
                            if conn["event_type"] == "kick":
                                field_value = f"Time: {timestamp}\nReason: {conn.get('reason', 'Unknown')}"
                            else:
                                field_value = f"Time: {timestamp}"
                                
                            combined_embed.add_field(
                                name=f"{event_type}: {player_name}",
                                value=field_value,
                                inline=True
                            )
                
                await ctx.respond(embed=combined_embed)
                
        except Exception as e:
            logger.error(f"Error listing connections: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
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
            # Ensure we have a database instance
            if not self.db:
                logger.error(f"Database instance not available in track_server_connections for server {server_id}")
                return
            
            # Get initial last connection ID
            if str(server_id) in self.server_trackers and self.server_trackers[str(server_id)]["last_connection_id"]:
                last_connection_id = self.server_trackers[str(server_id)]["last_connection_id"]
            else:
                # Get the most recent connection for this server
                collection = await self.db.get_collection("connection_events")
                cursor = collection.find({"server_id": server_id})
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
                    collection = await self.db.get_collection("connection_events")
                    cursor = collection.find(query)
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
                        server = await Server.get_by_id(self.db, connection.server_id)
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

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_cog(ConnectionCommands(bot))
