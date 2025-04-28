import discord
from discord.ext import commands
import logging
import asyncio
from database.connection import Database
from database.models import Server, GuildConfig, ServerEvent
from utils.embeds import create_mission_embed

logger = logging.getLogger('deadside_bot.cogs.mission')

# Create slash command group for mission commands
mission_group = discord.SlashCommandGroup(
    name="missions",
    description="Commands for managing mission and server event notifications",
    default_member_permissions=discord.Permissions(manage_channels=True)
)

class MissionCommands(commands.Cog):
    """Commands for managing mission and server event notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        self.server_trackers = {}
        # We'll initialize trackers after the cog is fully loaded, not during __init__
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        # Start tracking after a short delay to ensure everything is ready
        self.bot.loop.create_task(self.initialize_mission_trackers())
    
    async def initialize_mission_trackers(self):
        """Initialize mission trackers for all configured servers"""
        await self.bot.wait_until_ready()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in initialize_mission_trackers")
                return
                
            # Get all guild configs with mission channels
            collection = await self.db.get_collection("guild_configs")
            cursor = collection.find({}) # Get all configs, we'll filter in Python
            all_configs = await cursor.to_list(None)
            # Filter configs with a mission channel
            configs = [config for config in all_configs if config.get("mission_channel") is not None]
            
            for config in configs:
                guild_id = config["guild_id"]
                channel_id = config["mission_channel"]
                
                # Get servers for this guild
                servers = await Server.get_by_guild(self.db, guild_id)
                
                for server in servers:
                    self.server_trackers[str(server._id)] = {
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                        "last_event_id": None
                    }
                    
                    # Start the tracker
                    self.bot.loop.create_task(self.track_server_events(server._id, channel_id))
            
            logger.info(f"Initialized mission trackers for {len(self.server_trackers)} servers")
                
        except Exception as e:
            logger.error(f"Error initializing mission trackers: {e}")
    
    @mission_group.command(name="channel", description="Set the channel for mission notifications")
    async def set_channel(self, ctx, 
                      channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=False) = None):
        """
        Set the channel for mission notifications
        
        Usage: /missions channel [#channel]
        
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
            guild_config.mission_channel = channel.id
            await guild_config.update(self.db)
            
            # Update trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            for server in servers:
                # Update tracker info
                self.server_trackers[str(server._id)] = {
                    "guild_id": ctx.guild.id,
                    "channel_id": channel.id,
                    "last_event_id": None
                }
                
                # Start the tracker if not already running
                if not any(task.get_name() == f"mission_tracker_{server._id}" 
                          for task in asyncio.all_tasks()):
                    self.bot.loop.create_task(
                        self.track_server_events(server._id, channel.id),
                        name=f"mission_tracker_{server._id}"
                    )
            
            await ctx.respond(f"✅ Mission and event notifications will now be sent to {channel.mention}")
                
        except Exception as e:
            logger.error(f"Error setting mission channel: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @mission_group.command(name="disable", description="Disable mission notifications for this guild")
    async def disable_missions(self, ctx):
        """Disable mission notifications for this guild"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in disable_missions command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Update guild config
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            guild_config.mission_channel = None
            await guild_config.update(self.db)
            
            # Remove trackers for all servers in this guild
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            for server in servers:
                if str(server._id) in self.server_trackers:
                    del self.server_trackers[str(server._id)]
            
            await ctx.respond("✅ Mission and event notifications have been disabled.")
                
        except Exception as e:
            logger.error(f"Error disabling missions: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @mission_group.command(name="list", description="List recent server events")
    async def list_missions(self, ctx, 
                          server_name: discord.Option(str, "Server name to show events for", required=False) = None,
                          event_type: discord.Option(str, "Type of event to filter", 
                                                      choices=["mission", "helicrash", "airdrop", "trader", "server_start", "server_stop"], 
                                                      required=False) = None,
                          limit: discord.Option(int, "Number of events to show (max: 20)", min_value=1, max_value=20, required=False) = 10):
        """
        List recent server events
        
        Usage: /missions list [server_name] [event_type] [limit]
        
        If no server name is provided, events for all servers will be shown.
        Event types: mission, helicrash, airdrop, trader, server_start, server_stop
        Default limit is 10, max limit is 20.
        """
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in list_missions command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Limit the number of events
            if limit > 20:
                limit = 20
            
            # Validate event type if provided
            valid_event_types = ["mission", "helicrash", "airdrop", "trader", "server_start", "server_stop"]
            if event_type and event_type.lower() not in valid_event_types:
                await ctx.respond(f"⚠️ Invalid event type. Valid types are: {', '.join(valid_event_types)}")
                return
            
            if server_name:
                # Get events for specific server
                servers = await Server.get_by_guild(self.db, ctx.guild.id)
                server = next((s for s in servers if s.name.lower() == server_name.lower()), None)
                
                if not server:
                    await ctx.respond(f"⚠️ Server '{server_name}' not found. Use `/server list` to see all configured servers.")
                    return
                
                # Build query
                query = {"server_id": server._id}
                if event_type:
                    query["event_type"] = event_type.lower()
                
                # Get recent events
                collection = await self.db.get_collection("server_events")
                cursor = collection.find(query)
                events = await cursor.to_list(limit)
                
                # Create embed
                embed = discord.Embed(
                    title=f"Recent Events for {server.name}",
                    description=f"Last {len(events)} events" + (f" of type '{event_type}'" if event_type else ""),
                    color=discord.Color.blue()
                )
                
                for event in events:
                    event_type = event["event_type"].replace("_", " ").title()
                    timestamp = event["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Format details based on event type
                    details = ""
                    if event["event_type"] == "mission":
                        details = f"Mission: {event['details'].get('name')}\nLevel: {event['details'].get('level')}"
                    elif event["event_type"] in ["helicrash", "airdrop", "trader"]:
                        details = f"Location: {event['details'].get('location')}"
                    
                    embed.add_field(
                        name=f"{event_type} at {timestamp}",
                        value=details if details else "No additional details",
                        inline=False
                    )
                
                await ctx.respond(embed=embed)
            else:
                # Get events for all servers
                servers = await Server.get_by_guild(self.db, ctx.guild.id)
                
                if not servers:
                    await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                    return
                
                # Create a single embed with all server events
                embed = discord.Embed(
                    title="Recent Events for All Servers",
                    description=f"Last events" + (f" of type '{event_type}'" if event_type else ""),
                    color=discord.Color.blue()
                )
                
                for server in servers:
                    # Build query
                    query = {"server_id": server._id}
                    if event_type:
                        query["event_type"] = event_type.lower()
                    
                    # Get recent events
                    collection = await self.db.get_collection("server_events")
                    cursor = collection.find(query)
                    events = await cursor.to_list(limit)
                    
                    if events:
                        # Add server as a header field
                        embed.add_field(
                            name=f"__Server: {server.name}__",
                            value=f"Found {len(events)} events",
                            inline=False
                        )
                        
                        for event in events:
                            event_type = event["event_type"].replace("_", " ").title()
                            timestamp = event["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Format details based on event type
                            details = ""
                            if event["event_type"] == "mission":
                                details = f"Mission: {event['details'].get('name')}\nLevel: {event['details'].get('level')}"
                            elif event["event_type"] in ["helicrash", "airdrop", "trader"]:
                                details = f"Location: {event['details'].get('location')}"
                            
                            embed.add_field(
                                name=f"{event_type} at {timestamp}",
                                value=details if details else "No additional details",
                                inline=False
                            )
                    
                # Send a single embed with all events from all servers
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error listing missions: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    async def track_server_events(self, server_id, channel_id):
        """
        Background task to track new server events and send to channel
        
        Args:
            server_id: MongoDB ObjectId of the server
            channel_id: Discord channel ID to send event messages
        """
        # Ensure we don't start multiple trackers for the same server
        task_name = f"mission_tracker_{server_id}"
        for task in asyncio.all_tasks():
            if task.get_name() == task_name and task != asyncio.current_task():
                logger.debug(f"Mission tracker for server {server_id} already running")
                return
        
        # Set task name for identification
        asyncio.current_task().set_name(task_name)
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error(f"Database instance not available in track_server_events for server {server_id}")
                return
                
            # Get initial last event ID
            if str(server_id) in self.server_trackers and self.server_trackers[str(server_id)]["last_event_id"]:
                last_event_id = self.server_trackers[str(server_id)]["last_event_id"]
            else:
                # Get the most recent event for this server
                collection = await self.db.get_collection("server_events")
                cursor = collection.find({"server_id": server_id})
                latest_event = await cursor.to_list(1)
                
                if latest_event:
                    last_event_id = latest_event[0]["_id"]
                else:
                    last_event_id = None
                
                # Update tracker
                if str(server_id) in self.server_trackers:
                    self.server_trackers[str(server_id)]["last_event_id"] = last_event_id
            
            while True:
                try:
                    # Check if tracker still exists (could be removed if disabled)
                    if str(server_id) not in self.server_trackers:
                        logger.debug(f"Mission tracker for server {server_id} was disabled")
                        return
                    
                    # Get channel
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        logger.warning(f"Could not find channel {channel_id} for missions")
                        await asyncio.sleep(60)
                        continue
                    
                    # Get new events
                    query = {"server_id": server_id}
                    # We can't use MongoDB-style operators in PostgreSQL
                    # We'll filter results in Python after fetching
                    
                    # Get the collection and execute the query
                    collection = await self.db.get_collection("server_events")
                    cursor = collection.find(query)
                    all_events = await cursor.to_list(100)  # Limit to avoid flooding
                    
                    # Filter events that are newer than last_event_id if needed
                    if last_event_id:
                        new_events = [
                            event for event in all_events 
                            if event.get("id", 0) > last_event_id or event.get("_id", 0) > last_event_id
                        ]
                    else:
                        new_events = all_events
                    
                    for event_data in new_events:
                        # Create a ServerEvent object
                        event = ServerEvent(**{**event_data, "_id": event_data["_id"]})
                        
                        # Get server info for the embed
                        server = await Server.get_by_id(self.db, event.server_id)
                        server_name = server.name if server else "Unknown Server"
                        
                        # Create and send embed
                        embed = await create_mission_embed(event, server_name)
                        await channel.send(embed=embed)
                        
                        # Update last event ID
                        last_event_id = event._id
                        if str(server_id) in self.server_trackers:
                            self.server_trackers[str(server_id)]["last_event_id"] = last_event_id
                    
                    # Log the number of events processed
                    if new_events:
                        logger.debug(f"Processed {len(new_events)} new events for server {server_id}")
                    
                    # Sleep before next check
                    await asyncio.sleep(15)
                
                except Exception as e:
                    logger.error(f"Error in mission tracker for server {server_id}: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
        
        except asyncio.CancelledError:
            logger.info(f"Mission tracker for server {server_id} was cancelled")
            return
        except Exception as e:
            logger.error(f"Fatal error in mission tracker for server {server_id}: {e}")

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_cog(MissionCommands(bot))
    bot.add_application_command(mission_group)
    logger.info("Loaded MissionCommands cog and registered missions command group")
