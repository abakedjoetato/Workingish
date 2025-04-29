"""
Notification Cog Module

This module provides automatic notifications for the Discord bot:
- Killfeed notifications to a specified channel
- Player join/leave notifications to a specified channel 
- Voice channel renaming with player counts
"""

import asyncio
import datetime
import logging
import time
from typing import Dict, List, Any, Optional, Union

import discord
from discord.ext import commands, tasks

from database.connection import Database
from utils.decorators import guild_only, premium_tier_required
from utils.embeds import create_basic_embed
from utils.error_handler import ErrorLogger

logger = logging.getLogger('deadside_bot.cogs.notification_cog')

class NotificationCog(commands.Cog):
    """Commands and tasks for server notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        
        # Cache for config settings
        self.killfeed_channels = {}  # guild_id -> channel_id
        self.killfeed_enabled = {}   # guild_id -> bool
        self.killfeed_filters = {}   # guild_id -> filter_config

        self.join_leave_channels = {}  # guild_id -> channel_id
        self.join_leave_enabled = {}   # guild_id -> bool
        
        self.player_count_channels = {}  # guild_id -> channel_id
        self.player_count_enabled = {}   # guild_id -> bool
        
        # Cache for last seen players
        self.last_seen_players = {}  # server_id -> {player_id -> bool}
        
        # Cache for last processed kills
        self.last_processed_kills = {}  # server_id -> kill_id
        
        # Start background tasks when the cog is loaded
        self.load_configs.start()
        
    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.process_killfeed_updates.cancel()
        self.process_player_changes.cancel()
        self.update_player_count_channels.cancel()
        self.load_configs.cancel()
    
    async def initialize_db(self):
        """Initialize the database connection"""
        if self.db is None:
            self.db = await Database.get_instance()
    
    @tasks.loop(minutes=5.0)
    async def load_configs(self):
        """Load notification configurations from the database"""
        await self.initialize_db()
        if not self.db:
            return
            
        try:
            # Get all guild configs
            guild_configs = await self.db.get_collection("guild_configs")
            configs = await guild_configs.find({}).to_list(length=None)
            
            # Process each guild's config
            for config in configs:
                guild_id = str(config.get("guild_id"))
                if not guild_id:
                    continue
                
                # Killfeed settings
                if "killfeed_channel" in config and "killfeed_enabled" in config:
                    self.killfeed_channels[guild_id] = str(config["killfeed_channel"])
                    self.killfeed_enabled[guild_id] = bool(config["killfeed_enabled"])
                    
                    # Load filters if available
                    if "killfeed_filters" in config:
                        self.killfeed_filters[guild_id] = config["killfeed_filters"]
                    else:
                        # Default filters
                        self.killfeed_filters[guild_id] = {
                            "minimum_distance": 0,
                            "show_suicides": True,
                            "show_melee": True,
                            "show_ai_kills": True
                        }
                
                # Join/leave notification settings
                if "join_leave_channel" in config and "join_leave_enabled" in config:
                    self.join_leave_channels[guild_id] = str(config["join_leave_channel"])
                    self.join_leave_enabled[guild_id] = bool(config["join_leave_enabled"])
                
                # Player count settings
                if "player_count_channel" in config and "player_count_enabled" in config:
                    self.player_count_channels[guild_id] = str(config["player_count_channel"])
                    self.player_count_enabled[guild_id] = bool(config["player_count_enabled"])
            
            # Start the notification tasks after config is loaded (if not already running)
            if not self.process_killfeed_updates.is_running():
                self.process_killfeed_updates.start()
                
            if not self.process_player_changes.is_running():
                self.process_player_changes.start()
                
            if not self.update_player_count_channels.is_running():
                self.update_player_count_channels.start()
                
            logger.info(f"Loaded notification configs for {len(configs)} guilds")
            
        except Exception as e:
            logger.error(f"Error loading notification configs: {e}")
    
    @load_configs.before_loop
    async def before_load_configs(self):
        """Wait for the bot to be ready before loading configs"""
        await self.bot.wait_until_ready()
    
    async def create_killfeed_embed(self, kill: Dict[str, Any], server_name: str) -> discord.Embed:
        """
        Create an embed for a killfeed entry
        
        Args:
            kill: The kill data
            server_name: The name of the server
            
        Returns:
            discord.Embed: The formatted embed
        """
        # Extract kill data
        killer_name = kill.get("killer_name", "Unknown")
        victim_name = kill.get("victim_name", "Unknown")
        weapon = kill.get("weapon", "Unknown")
        distance = kill.get("distance", 0)
        timestamp = kill.get("timestamp", datetime.datetime.now())
        is_suicide = kill.get("is_suicide", False)
        is_headshot = kill.get("is_headshot", False)
        
        # Format the title based on whether it's a suicide
        if is_suicide:
            title = f"💀 {victim_name} died"
        else:
            title = f"☠️ {killer_name} killed {victim_name}"
            
        # Create the embed
        embed = discord.Embed(
            title=title,
            description=f"**Server:** {server_name}",
            color=discord.Color.red(),
            timestamp=timestamp
        )
        
        # Add fields with details
        if not is_suicide:
            embed.add_field(name="Weapon", value=weapon, inline=True)
            embed.add_field(name="Distance", value=f"{distance}m", inline=True)
            if is_headshot:
                embed.add_field(name="Headshot", value="Yes", inline=True)
        else:
            embed.add_field(name="Cause", value=weapon, inline=True)
            
        # Set footer with timestamp
        embed.set_footer(text=f"Kill ID: {kill.get('kill_id', 'Unknown')}")
        
        return embed
    
    async def create_player_join_embed(self, player: Dict[str, Any], server_name: str) -> discord.Embed:
        """
        Create an embed for a player join notification
        
        Args:
            player: The player data
            server_name: The name of the server
            
        Returns:
            discord.Embed: The formatted embed
        """
        # Extract player data
        player_name = player.get("name", "Unknown")
        player_id = player.get("player_id", "Unknown")
        steam_id = player.get("steam_id", "Unknown")
        timestamp = player.get("last_seen", datetime.datetime.now())
        
        # Create the embed
        embed = discord.Embed(
            title=f"👋 {player_name} joined the server",
            description=f"**Server:** {server_name}",
            color=discord.Color.green(),
            timestamp=timestamp
        )
        
        # Add player info
        embed.add_field(name="Player ID", value=player_id, inline=True)
        embed.add_field(name="Steam ID", value=steam_id, inline=True)
        
        # Add play time if available
        if "play_time" in player:
            play_time = player["play_time"]
            hours = play_time // 3600
            minutes = (play_time % 3600) // 60
            embed.add_field(name="Total Play Time", value=f"{hours}h {minutes}m", inline=True)
            
        # Set footer with timestamp
        embed.set_footer(text=f"Joined at {timestamp.strftime('%H:%M:%S')}")
        
        return embed
    
    async def create_player_leave_embed(self, player: Dict[str, Any], server_name: str) -> discord.Embed:
        """
        Create an embed for a player leave notification
        
        Args:
            player: The player data
            server_name: The name of the server
            
        Returns:
            discord.Embed: The formatted embed
        """
        # Extract player data
        player_name = player.get("name", "Unknown")
        player_id = player.get("player_id", "Unknown")
        steam_id = player.get("steam_id", "Unknown")
        timestamp = player.get("last_seen", datetime.datetime.now())
        
        # Create the embed
        embed = discord.Embed(
            title=f"👋 {player_name} left the server",
            description=f"**Server:** {server_name}",
            color=discord.Color.orange(),
            timestamp=timestamp
        )
        
        # Add player info
        embed.add_field(name="Player ID", value=player_id, inline=True)
        embed.add_field(name="Steam ID", value=steam_id, inline=True)
        
        # Add play time if available
        if "play_time" in player:
            play_time = player["play_time"]
            hours = play_time // 3600
            minutes = (play_time % 3600) // 60
            embed.add_field(name="Total Play Time", value=f"{hours}h {minutes}m", inline=True)
            
        # Set footer with timestamp
        embed.set_footer(text=f"Left at {timestamp.strftime('%H:%M:%S')}")
        
        return embed
    
    @tasks.loop(seconds=15.0)
    async def process_killfeed_updates(self):
        """Process new kills and send killfeed updates"""
        await self.initialize_db()
        if not self.db:
            return
            
        try:
            # Get all servers
            servers_collection = await self.db.get_collection("servers")
            servers = await servers_collection.find({}).to_list(None)
            
            # Get killfeed collection
            killfeed_collection = await self.db.get_collection("killfeed")
            
            # Process each server
            for server_data in servers:
                server_id = str(server_data.get("_id"))
                guild_id = server_data.get("guild_id")
                
                # Skip if killfeed not enabled for this guild
                if not guild_id or not self.killfeed_enabled.get(guild_id, False):
                    continue
                    
                # Get channel for killfeed
                channel_id = self.killfeed_channels.get(guild_id)
                if not channel_id:
                    continue
                    
                # Get the Discord channel
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    logger.warning(f"Could not find channel {channel_id} for killfeed")
                    continue
                
                # Get filters for this guild
                filters = self.killfeed_filters.get(guild_id, {})
                min_distance = filters.get("minimum_distance", 0)
                show_suicides = filters.get("show_suicides", True)
                show_melee = filters.get("show_melee", True)
                show_ai_kills = filters.get("show_ai_kills", True)
                
                # Get last processed kill ID for this server
                last_kill_id = self.last_processed_kills.get(server_id)
                
                # Query for new kills
                query = {"server_id": server_id}
                if last_kill_id:
                    # Only get kills after the last processed one
                    # This requires kills to have an ObjectId or some timestamp-based ID
                    query["_id"] = {"$gt": last_kill_id}
                
                # Sort by ID (assuming it's timestamp-based) or explicitly by timestamp
                new_kills = await killfeed_collection.find(query).sort("timestamp", 1).to_list(None)
                
                if not new_kills:
                    continue
                    
                # Update the last processed kill ID
                if new_kills:
                    self.last_processed_kills[server_id] = new_kills[-1]["_id"]
                
                # Process each new kill
                for kill in new_kills:
                    # Apply distance filter
                    if kill.get("distance", 0) < min_distance:
                        continue
                        
                    # Apply suicide filter
                    if not show_suicides and kill.get("is_suicide", False):
                        continue
                        
                    # Apply weapon filter
                    if not show_melee and kill.get("weapon", "").lower() in ["melee", "fists", "knife", "hands"]:
                        continue
                        
                    # Apply AI filter
                    if not show_ai_kills and (
                        not kill.get("killer_id") or 
                        kill.get("killer_name", "").startswith("AI_") or 
                        kill.get("victim_name", "").startswith("AI_")
                    ):
                        continue
                    
                    # Create embed for kill
                    embed = await self.create_killfeed_embed(kill, server_data.get("name", "Unknown Server"))
                    
                    # Send to channel
                    await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error processing killfeed updates: {e}")
    
    @tasks.loop(seconds=30.0)
    async def process_player_changes(self):
        """Process player join/leave events and send notifications"""
        await self.initialize_db()
        if not self.db:
            return
            
        try:
            # Get all servers
            servers_collection = await self.db.get_collection("servers")
            servers = await servers_collection.find({}).to_list(None)
            
            # Get players collection
            players_collection = await self.db.get_collection("players")
            
            # Process each server
            for server_data in servers:
                server_id = str(server_data.get("_id"))
                guild_id = server_data.get("guild_id")
                
                # Skip if join/leave notifications not enabled for this guild
                if not guild_id or not self.join_leave_enabled.get(guild_id, False):
                    continue
                    
                # Get channel for join/leave notifications
                channel_id = self.join_leave_channels.get(guild_id)
                if not channel_id:
                    continue
                    
                # Get the Discord channel
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    logger.warning(f"Could not find channel {channel_id} for join/leave notifications")
                    continue
                
                # Get all current online players
                online_players = await players_collection.find({
                    "server_id": server_id,
                    "is_online": True
                }).to_list(None)
                
                # Convert to dictionary for faster lookups
                current_online = {str(player["_id"]): player for player in online_players}
                
                # Get the last seen players for this server
                last_seen = self.last_seen_players.get(server_id, {})
                
                # Find players who joined (in current_online but not in last_seen)
                for player_id, player_data in current_online.items():
                    if player_id not in last_seen:
                        # New player joined
                        embed = await self.create_player_join_embed(
                            player_data, 
                            server_data.get("name", "Unknown Server")
                        )
                        await channel.send(embed=embed)
                
                # Find players who left (in last_seen but not in current_online)
                for player_id in last_seen:
                    if player_id not in current_online:
                        # Get player data from database
                        player_data = await players_collection.find_one({"_id": player_id})
                        if player_data:
                            embed = await self.create_player_leave_embed(
                                player_data, 
                                server_data.get("name", "Unknown Server")
                            )
                            await channel.send(embed=embed)
                
                # Update the last seen players for this server
                self.last_seen_players[server_id] = current_online
                
        except Exception as e:
            logger.error(f"Error processing player changes: {e}")
    
    @tasks.loop(minutes=5.0)
    async def update_player_count_channels(self):
        """Update voice channel names with player counts"""
        await self.initialize_db()
        if not self.db:
            return
            
        try:
            # Get all servers
            servers_collection = await self.db.get_collection("servers")
            servers = await servers_collection.find({}).to_list(None)
            
            # Process each server
            for server_data in servers:
                server_id = str(server_data.get("_id"))
                guild_id = server_data.get("guild_id")
                
                # Skip if player count not enabled for this guild
                if not guild_id or not self.player_count_enabled.get(guild_id, False):
                    continue
                    
                # Get channel for player count
                channel_id = self.player_count_channels.get(guild_id)
                if not channel_id:
                    continue
                    
                # Get the Discord voice channel
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                    if not isinstance(channel, discord.VoiceChannel):
                        logger.warning(f"Channel {channel_id} is not a voice channel")
                        continue
                except discord.NotFound:
                    logger.warning(f"Could not find voice channel {channel_id} for player count")
                    continue
                
                # Get current player count
                players_online = server_data.get("players_online", 0)
                max_players = server_data.get("max_players", 0)
                
                # Format new channel name
                server_name = server_data.get("name", "Unknown Server")
                new_name = f"🎮 {server_name}: {players_online}/{max_players}"
                
                # Update channel name if different
                if channel.name != new_name:
                    try:
                        await channel.edit(name=new_name)
                        logger.info(f"Updated player count channel for {server_name}: {players_online}/{max_players}")
                    except discord.errors.Forbidden:
                        logger.warning(f"Missing permissions to edit channel {channel_id}")
                    except discord.errors.HTTPException as e:
                        # Handle rate limiting
                        if e.status == 429:
                            logger.warning(f"Rate limited when updating channel name. Retry after {e.retry_after}s")
                        else:
                            logger.error(f"HTTP error when updating channel name: {e}")
        
        except Exception as e:
            logger.error(f"Error updating player count channels: {e}")
    
    @process_killfeed_updates.before_loop
    @process_player_changes.before_loop
    @update_player_count_channels.before_loop
    async def before_notification_tasks(self):
        """Wait for the bot to be ready before starting notification tasks"""
        await self.bot.wait_until_ready()
    
    # Define the slash command group
    notifications_group = discord.SlashCommandGroup(
        name="notifications",
        description="Configure notification settings for this server",
        guild_only=True  # Using guild_only=True for maximum compatibility
    )
    
    @notifications_group.command(
        name="killfeed",
        description="Configure automatic killfeed notifications for this server"
    )
    @commands.has_permissions(manage_channels=True)
    @guild_only()
    async def setup_killfeed(
        self,
        ctx,
        channel: discord.Option(discord.TextChannel, "Channel to send killfeed notifications", required=True),
        enabled: discord.Option(bool, "Enable or disable killfeed notifications", required=False, default=True)
    ):
        """Set up automatic killfeed notifications"""
        await ctx.defer()
        await self.initialize_db()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Verify that the bot has permissions to send messages in the channel
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                await ctx.respond(f"❌ I don't have permission to send messages in {channel.mention}")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {
                    "killfeed_channel": str(channel.id),
                    "killfeed_enabled": enabled
                }},
                upsert=True
            )
          
            # Update the in-memory cache
            self.killfeed_channels[guild_id] = str(channel.id)
            self.killfeed_enabled[guild_id] = enabled
            
            # Create success embed
            embed = discord.Embed(
                title=f"{'✅ Killfeed Notifications Enabled' if enabled else '❌ Killfeed Notifications Disabled'}",
                description=f"Killfeed notifications will {'now' if enabled else 'no longer'} be sent to {channel.mention}",
                color=discord.Color.green() if enabled else discord.Color.red()
            )
            
            # Add related commands
            embed.add_field(
                name="📝 Related Commands",
                value="`/notifications killfeed-filter` - Customize which kills to show\n"
                      "`/notifications status` - Check notification settings",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting up killfeed: {e}")
            await ctx.respond(f"❌ An error occurred: {str(e)}")
    
    @notifications_group.command(
        name="killfeed_filter",
        description="Customize killfeed notification filters"
    )
    @commands.has_permissions(manage_channels=True)
    @guild_only()
    async def killfeed_filter(
        self,
        ctx,
        minimum_distance: discord.Option(int, "Minimum kill distance to show (in meters)", required=False, min_value=0, default=0),
        show_suicides: discord.Option(bool, "Show suicide events", required=False, default=True),
        show_melee: discord.Option(bool, "Show melee/fist kills", required=False, default=True),
        show_ai_kills: discord.Option(bool, "Show AI kills and deaths", required=False, default=True)
    ):
        """Customize killfeed notification filters"""
        await ctx.defer()
        await self.initialize_db()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Make sure killfeed is set up
            if guild_id not in self.killfeed_channels:
                await ctx.respond("❌ Killfeed notifications are not set up. Use `/notifications killfeed` first.")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            
            filters = {
                "minimum_distance": minimum_distance,
                "show_suicides": show_suicides,
                "show_melee": show_melee,
                "show_ai_kills": show_ai_kills
            }
            
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"killfeed_filters": filters}},
                upsert=True
            )
          
            # Update the in-memory cache
            self.killfeed_filters[guild_id] = filters
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Killfeed Filters Updated",
                description="Your killfeed notification filters have been updated.",
                color=discord.Color.green()
            )
            
            # Add filter details
            embed.add_field(
                name="📊 Filter Settings",
                value=f"Minimum Distance: {minimum_distance}m\n"
                      f"Show Suicides: {'✓' if show_suicides else '✗'}\n"
                      f"Show Melee Kills: {'✓' if show_melee else '✗'}\n"
                      f"Show AI Kills: {'✓' if show_ai_kills else '✗'}",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting killfeed filters: {e}")
            await ctx.respond(f"❌ An error occurred: {str(e)}")
    
    @notifications_group.command(
        name="join_leave",
        description="Configure player join/leave notifications"
    )
    @commands.has_permissions(manage_channels=True)
    @guild_only()
    @premium_tier_required(tier=1)  # Premium feature
    async def setup_join_leave(
        self,
        ctx,
        channel: discord.Option(discord.TextChannel, "Channel to send join/leave notifications", required=True),
        enabled: discord.Option(bool, "Enable or disable join/leave notifications", required=False, default=True)
    ):
        """Set up player join/leave notifications"""
        await ctx.defer()
        await self.initialize_db()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Verify that the bot has permissions to send messages in the channel
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                await ctx.respond(f"❌ I don't have permission to send messages in {channel.mention}")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {
                    "join_leave_channel": str(channel.id),
                    "join_leave_enabled": enabled
                }},
                upsert=True
            )
          
            # Update the in-memory cache
            self.join_leave_channels[guild_id] = str(channel.id)
            self.join_leave_enabled[guild_id] = enabled
            
            # Create success embed
            embed = discord.Embed(
                title=f"{'✅ Join/Leave Notifications Enabled' if enabled else '❌ Join/Leave Notifications Disabled'}",
                description=f"Player join/leave notifications will {'now' if enabled else 'no longer'} be sent to {channel.mention}",
                color=discord.Color.green() if enabled else discord.Color.red()
            )
            
            # Add related commands
            embed.add_field(
                name="📝 Related Commands",
                value="`/notifications status` - Check notification settings",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting up join/leave notifications: {e}")
            await ctx.respond(f"❌ An error occurred: {str(e)}")
    
    @notifications_group.command(
        name="player_count",
        description="Configure voice channel player count updates"
    )
    @commands.has_permissions(manage_channels=True)
    @guild_only()
    @premium_tier_required(tier=1)  # Premium feature
    async def setup_player_count(
        self,
        ctx,
        channel: discord.Option(discord.VoiceChannel, "Voice channel to update with player count", required=True),
        enabled: discord.Option(bool, "Enable or disable player count updates", required=False, default=True)
    ):
        """Set up voice channel player count updates"""
        await ctx.defer()
        await self.initialize_db()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Verify that the bot has permissions to manage the channel
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).manage_channels:
                await ctx.respond(f"❌ I don't have permission to edit {channel.mention}")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {
                    "player_count_channel": str(channel.id),
                    "player_count_enabled": enabled
                }},
                upsert=True
            )
          
            # Update the in-memory cache
            self.player_count_channels[guild_id] = str(channel.id)
            self.player_count_enabled[guild_id] = enabled
            
            # Create success embed
            embed = discord.Embed(
                title=f"{'✅ Player Count Updates Enabled' if enabled else '❌ Player Count Updates Disabled'}",
                description=f"The voice channel {channel.mention} will {'now' if enabled else 'no longer'} be updated with player counts.",
                color=discord.Color.green() if enabled else discord.Color.red()
            )
            
            # Add info about update frequency
            embed.add_field(
                name="⏱️ Update Frequency",
                value="The channel name will update every 5 minutes with the current player count.",
                inline=False
            )
            
            # Add related commands
            embed.add_field(
                name="📝 Related Commands",
                value="`/notifications status` - Check notification settings",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting up player count updates: {e}")
            await ctx.respond(f"❌ An error occurred: {str(e)}")
    
    @notifications_group.command(
        name="status",
        description="Check current notification settings"
    )
    @commands.has_permissions(manage_channels=True)
    @guild_only()
    async def notification_status(self, ctx):
        """Check current notification settings"""
        await ctx.defer()
        await self.initialize_db()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Create status embed
            embed = discord.Embed(
                title="🔔 Notification Settings",
                description="Current notification settings for this server",
                color=discord.Color.blue()
            )
            
            # Add killfeed status
            killfeed_enabled = self.killfeed_enabled.get(guild_id, False)
            killfeed_channel_id = self.killfeed_channels.get(guild_id)
            
            if killfeed_channel_id:
                killfeed_channel = ctx.guild.get_channel(int(killfeed_channel_id))
                killfeed_status = f"{'✅ Enabled' if killfeed_enabled else '❌ Disabled'}\nChannel: {killfeed_channel.mention if killfeed_channel else 'Unknown'}"
            else:
                killfeed_status = "❌ Not configured"
                
            embed.add_field(
                name="☠️ Killfeed Notifications",
                value=killfeed_status,
                inline=False
            )
            
            # Add killfeed filter status if configured
            if killfeed_channel_id and guild_id in self.killfeed_filters:
                filters = self.killfeed_filters[guild_id]
                filter_text = (
                    f"Minimum Distance: {filters.get('minimum_distance', 0)}m\n"
                    f"Show Suicides: {'✓' if filters.get('show_suicides', True) else '✗'}\n"
                    f"Show Melee Kills: {'✓' if filters.get('show_melee', True) else '✗'}\n"
                    f"Show AI Kills: {'✓' if filters.get('show_ai_kills', True) else '✗'}"
                )
                embed.add_field(
                    name="📊 Killfeed Filters",
                    value=filter_text,
                    inline=False
                )
            
            # Add join/leave status
            join_leave_enabled = self.join_leave_enabled.get(guild_id, False)
            join_leave_channel_id = self.join_leave_channels.get(guild_id)
            
            if join_leave_channel_id:
                join_leave_channel = ctx.guild.get_channel(int(join_leave_channel_id))
                join_leave_status = f"{'✅ Enabled' if join_leave_enabled else '❌ Disabled'}\nChannel: {join_leave_channel.mention if join_leave_channel else 'Unknown'}"
            else:
                join_leave_status = "❌ Not configured"
                
            embed.add_field(
                name="👋 Join/Leave Notifications",
                value=join_leave_status,
                inline=False
            )
            
            # Add player count status
            player_count_enabled = self.player_count_enabled.get(guild_id, False)
            player_count_channel_id = self.player_count_channels.get(guild_id)
            
            if player_count_channel_id:
                player_count_channel = ctx.guild.get_channel(int(player_count_channel_id))
                player_count_status = f"{'✅ Enabled' if player_count_enabled else '❌ Disabled'}\nChannel: {player_count_channel.mention if player_count_channel else 'Unknown'}"
            else:
                player_count_status = "❌ Not configured"
                
            embed.add_field(
                name="🎮 Player Count Updates",
                value=player_count_status,
                inline=False
            )
            
            # Add setup commands
            embed.add_field(
                name="⚙️ Setup Commands",
                value="`/notifications killfeed` - Configure killfeed notifications\n"
                      "`/notifications killfeed_filter` - Customize killfeed filters\n"
                      "`/notifications join_leave` - Configure join/leave notifications\n"
                      "`/notifications player_count` - Configure player count updates",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking notification status: {e}")
            await ctx.respond(f"❌ An error occurred: {str(e)}")

def setup(bot):
    """Add the cog to the bot"""
    bot.add_cog(NotificationCog(bot))