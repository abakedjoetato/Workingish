import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timedelta
from database.connection import Database
from database.models import Server, GuildConfig
from utils.guild_isolation import get_guild_servers, get_server_by_name
from utils.premium import check_feature_access

logger = logging.getLogger('deadside_bot.cogs.killfeed')

# Create slash command group for killfeed commands
killfeed_group = discord.SlashCommandGroup(
    name="killfeed",
    description="Commands for managing killfeed notifications",
    default_member_permissions=discord.Permissions(manage_channels=True)
)

class KillfeedCommands(commands.Cog):
    """Commands for managing killfeed notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        # We'll store active tracking settings here
        self.killfeed_enabled = {}  # guild_id -> enabled boolean
        self.killfeed_channels = {}  # guild_id -> channel_id
        self.killfeed_filters = {}  # guild_id -> filter settings
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Killfeed commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
        
        # Load existing killfeed settings
        await self.load_killfeed_settings()
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        """Return all commands this cog provides"""
        return [killfeed_group]
    
    async def load_killfeed_settings(self):
        """Load killfeed settings from the database"""
        if not self.db:
            logger.error("Database not available for loading killfeed settings")
            return
            
        try:
            # Get all guild configs
            guild_configs = await self.db.get_collection("guild_configs")
            cursor = guild_configs.find({})
            configs = await cursor.to_list(None)
            
            # Process each config
            for config in configs:
                guild_id = config.get("guild_id")
                if not guild_id:
                    continue
                    
                # Get killfeed settings
                killfeed_channel = config.get("killfeed_channel")
                killfeed_enabled = config.get("killfeed_enabled", False)
                killfeed_filters = config.get("killfeed_filters", {})
                
                # Store in memory for quick access
                if killfeed_enabled is not None:
                    self.killfeed_enabled[guild_id] = killfeed_enabled
                    
                if killfeed_channel:
                    self.killfeed_channels[guild_id] = killfeed_channel
                    
                if killfeed_filters:
                    self.killfeed_filters[guild_id] = killfeed_filters
                    
            logger.info(f"Loaded killfeed settings for {len(self.killfeed_enabled)} guilds")
        except Exception as e:
            logger.error(f"Error loading killfeed settings: {e}")
    
    @killfeed_group.command(
        name="channel",
        description="Set a channel for killfeed notifications"
    )
    async def killfeed_channel(
        self, 
        ctx,
        channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=True)
    ):
        """Set the channel for killfeed notifications"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Verify that the bot has permissions to send messages in the channel
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                await ctx.respond(f"❌ I don't have permission to send messages in {channel.mention}")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            result = await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"killfeed_channel": str(channel.id)}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.killfeed_channels[guild_id] = str(channel.id)
            
            # Enable killfeed if it wasn't already
            if guild_id not in self.killfeed_enabled or not self.killfeed_enabled[guild_id]:
                await guild_configs.update_one(
                    {"guild_id": guild_id},
                    {"$set": {"killfeed_enabled": True}},
                    upsert=True
                )
                self.killfeed_enabled[guild_id] = True
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Killfeed Channel Set",
                description=f"Killfeed notifications will be sent to {channel.mention}",
                color=discord.Color.green()
            )
            
            # Add note about enabling if needed
            if result.upserted_id:
                embed.add_field(
                    name="Notifications Enabled",
                    value="Killfeed notifications have been automatically enabled",
                    inline=False
                )
            
            # Add command help
            embed.add_field(
                name="📝 Related Commands",
                value="`/killfeed toggle` - Enable/disable notifications\n"
                      "`/killfeed filter` - Customize which kills to show\n"
                      "`/killfeed status` - Check notification settings",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting killfeed channel: {e}")
            await ctx.respond(f"❌ Error setting killfeed channel: {e}")
    
    @killfeed_group.command(
        name="toggle",
        description="Enable or disable killfeed notifications"
    )
    async def killfeed_toggle(
        self,
        ctx,
        enabled: discord.Option(bool, "Enable or disable notifications", required=True)
    ):
        """Enable or disable killfeed notifications"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Check if killfeed channel is set
            if enabled and guild_id not in self.killfeed_channels:
                embed = discord.Embed(
                    title="⚠️ No Killfeed Channel Set",
                    description="You need to set a killfeed channel first",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="Set a Channel",
                    value="Use `/killfeed channel #channel` to set a notification channel first",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"killfeed_enabled": enabled}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.killfeed_enabled[guild_id] = enabled
            
            # Create response embed
            if enabled:
                embed = discord.Embed(
                    title="✅ Killfeed Notifications Enabled",
                    description="You will now receive notifications for kills",
                    color=discord.Color.green()
                )
                
                # Add channel information if available
                if guild_id in self.killfeed_channels:
                    channel_id = self.killfeed_channels[guild_id]
                    try:
                        channel = ctx.guild.get_channel(int(channel_id))
                        if channel:
                            embed.add_field(
                                name="Notification Channel",
                                value=f"Notifications will be sent to {channel.mention}",
                                inline=False
                            )
                    except:
                        pass
            else:
                embed = discord.Embed(
                    title="Killfeed Notifications Disabled",
                    description="You will no longer receive notifications for kills",
                    color=discord.Color.red()
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error toggling killfeed notifications: {e}")
            await ctx.respond(f"❌ Error toggling killfeed notifications: {e}")
    
    @killfeed_group.command(
        name="filter",
        description="Customize which kills to show in killfeed"
    )
    async def killfeed_filter(
        self,
        ctx,
        minimum_distance: discord.Option(int, "Minimum kill distance to show (0 to show all)", min_value=0, max_value=2000, required=False) = None,
        show_suicides: discord.Option(bool, "Show suicides in killfeed", required=False) = None,
        show_melee: discord.Option(bool, "Show melee kills in killfeed", required=False) = None,
        show_ai_kills: discord.Option(bool, "Show AI kills in killfeed", required=False) = None
    ):
        """Customize which kills to show in the killfeed"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Get current filters
            current_filters = self.killfeed_filters.get(guild_id, {})
            if not current_filters:
                # Set defaults if none exist
                current_filters = {
                    "minimum_distance": 0,
                    "show_suicides": False,
                    "show_melee": True,
                    "show_ai_kills": True
                }
            
            # Update any specified filters
            updates = {}
            if minimum_distance is not None:
                updates["minimum_distance"] = minimum_distance
                current_filters["minimum_distance"] = minimum_distance
                
            if show_suicides is not None:
                updates["show_suicides"] = show_suicides
                current_filters["show_suicides"] = show_suicides
                
            if show_melee is not None:
                updates["show_melee"] = show_melee
                current_filters["show_melee"] = show_melee
                
            if show_ai_kills is not None:
                updates["show_ai_kills"] = show_ai_kills
                current_filters["show_ai_kills"] = show_ai_kills
            
            # If no updates specified, just show current settings
            if not updates:
                embed = discord.Embed(
                    title="Current Killfeed Filters",
                    description="Current filter settings for killfeed notifications",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="Minimum Kill Distance",
                    value=f"{current_filters.get('minimum_distance', 0)} meters",
                    inline=True
                )
                
                embed.add_field(
                    name="Show Suicides",
                    value="✅ Enabled" if current_filters.get('show_suicides', False) else "❌ Disabled",
                    inline=True
                )
                
                embed.add_field(
                    name="Show Melee Kills",
                    value="✅ Enabled" if current_filters.get('show_melee', True) else "❌ Disabled",
                    inline=True
                )
                
                embed.add_field(
                    name="Show AI Kills",
                    value="✅ Enabled" if current_filters.get('show_ai_kills', True) else "❌ Disabled",
                    inline=True
                )
                
                embed.add_field(
                    name="Change Settings",
                    value="Use this command with parameters to change filter settings",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                return
            
            # Update the database
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"killfeed_filters": current_filters}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.killfeed_filters[guild_id] = current_filters
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Killfeed Filters Updated",
                description="Your killfeed filter settings have been updated",
                color=discord.Color.green()
            )
            
            # Add fields for each filter
            embed.add_field(
                name="Minimum Kill Distance",
                value=f"{current_filters.get('minimum_distance', 0)} meters",
                inline=True
            )
            
            embed.add_field(
                name="Show Suicides",
                value="✅ Enabled" if current_filters.get('show_suicides', False) else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Show Melee Kills",
                value="✅ Enabled" if current_filters.get('show_melee', True) else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Show AI Kills",
                value="✅ Enabled" if current_filters.get('show_ai_kills', True) else "❌ Disabled",
                inline=True
            )
            
            # Add note about enabling if needed
            if guild_id not in self.killfeed_enabled or not self.killfeed_enabled[guild_id]:
                embed.add_field(
                    name="⚠️ Notifications Disabled",
                    value="Killfeed notifications are currently disabled. Use `/killfeed toggle true` to enable them.",
                    inline=False
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating killfeed filters: {e}")
            await ctx.respond(f"❌ Error updating killfeed filters: {e}")
    
    @killfeed_group.command(
        name="status",
        description="Check killfeed notification settings"
    )
    async def killfeed_status(self, ctx):
        """Check the current killfeed notification settings"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Get current settings
            enabled = self.killfeed_enabled.get(guild_id, False)
            channel_id = self.killfeed_channels.get(guild_id)
            filters = self.killfeed_filters.get(guild_id, {})
            
            # Create status embed
            if enabled:
                embed = discord.Embed(
                    title="Killfeed Notification Status",
                    description="✅ Notifications are **enabled**",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="Killfeed Notification Status",
                    description="❌ Notifications are **disabled**",
                    color=discord.Color.red()
                )
            
            # Add channel information if available
            if channel_id:
                try:
                    channel = ctx.guild.get_channel(int(channel_id))
                    if channel:
                        embed.add_field(
                            name="Notification Channel",
                            value=f"Notifications will be sent to {channel.mention}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="⚠️ Channel Not Found",
                            value="The configured channel no longer exists. Please set a new one.",
                            inline=False
                        )
                except:
                    embed.add_field(
                        name="⚠️ Channel Error",
                        value="Could not verify the channel. Please set a new one.",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="No Channel Set",
                    value="Use `/killfeed channel #channel` to set a notification channel",
                    inline=False
                )
            
            # Add filter information if available
            if filters:
                embed.add_field(
                    name="Filter Settings",
                    value=f"Minimum Distance: {filters.get('minimum_distance', 0)} meters\n"
                          f"Show Suicides: {'✅' if filters.get('show_suicides', False) else '❌'}\n"
                          f"Show Melee Kills: {'✅' if filters.get('show_melee', True) else '❌'}\n"
                          f"Show AI Kills: {'✅' if filters.get('show_ai_kills', True) else '❌'}",
                    inline=False
                )
            
            # Get recent killfeed entries if available
            if enabled and channel_id:
                try:
                    # Get servers for this guild
                    servers = await get_guild_servers(self.db, guild_id)
                    server_ids = [str(server["_id"]) for server in servers]
                    
                    if server_ids:
                        # Get recent kills
                        kills_collection = await self.db.get_collection("kills")
                        recent_query = {
                            "server_id": {"$in": server_ids},
                            "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=1)}
                        }
                        recent_cursor = kills_collection.find(recent_query).sort("timestamp", -1).limit(5)
                        recent_kills = await recent_cursor.to_list(None)
                        
                        if recent_kills:
                            kills_text = []
                            for kill in recent_kills:
                                killer = kill.get("killer_name", "Unknown")
                                victim = kill.get("victim_name", "Unknown")
                                weapon = kill.get("weapon", "Unknown")
                                distance = kill.get("distance", 0)
                                
                                kills_text.append(f"• {killer} → {victim} ({weapon}, {distance}m)")
                            
                            # Add to embed
                            embed.add_field(
                                name="Recent Kills (1h)",
                                value="\n".join(kills_text)[:1024],  # Limit to 1024 chars
                                inline=False
                            )
                except Exception as kills_error:
                    logger.error(f"Error getting recent kills: {kills_error}")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking killfeed status: {e}")
            await ctx.respond(f"❌ Error checking killfeed status: {e}")
    
    @killfeed_group.command(
        name="highlights",
        description="Configure special kill notifications"
    )
    async def killfeed_highlights(
        self,
        ctx,
        highlight_long_distance: discord.Option(int, "Minimum distance for highlighting long-distance kills (0 to disable)", min_value=0, max_value=2000, required=False) = None,
        highlight_streaks: discord.Option(bool, "Highlight kill streaks", required=False) = None,
        highlight_faction_kills: discord.Option(bool, "Highlight faction vs faction kills", required=False) = None
    ):
        """Configure special kill notifications for highlights"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Check premium status for advanced features
            is_premium = await check_feature_access(self.db, guild_id, "advanced_killfeed")
            
            if not is_premium:
                embed = discord.Embed(
                    title="💎 Premium Feature",
                    description="Advanced killfeed highlights are a premium feature",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="Upgrade to Premium",
                    value="Upgrade to Warlord tier or higher to access advanced killfeed features",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                return
                
            # Get current highlight settings
            current_highlights = self.killfeed_filters.get(guild_id, {}).get("highlights", {})
            if not current_highlights:
                # Set defaults if none exist
                current_highlights = {
                    "long_distance": 100,  # Highlight kills over 100m
                    "streaks": True,       # Highlight kill streaks
                    "faction_kills": True  # Highlight faction vs faction kills
                }
            
            # Update any specified highlights
            updates = {}
            if highlight_long_distance is not None:
                current_highlights["long_distance"] = highlight_long_distance
                updates["highlights"] = current_highlights
                
            if highlight_streaks is not None:
                current_highlights["streaks"] = highlight_streaks
                updates["highlights"] = current_highlights
                
            if highlight_faction_kills is not None:
                current_highlights["faction_kills"] = highlight_faction_kills
                updates["highlights"] = current_highlights
            
            # If no updates specified, just show current settings
            if not updates:
                embed = discord.Embed(
                    title="Current Killfeed Highlights",
                    description="Current highlight settings for killfeed notifications",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="Long Distance Kills",
                    value=f"Highlight kills over {current_highlights.get('long_distance', 100)} meters",
                    inline=True
                )
                
                embed.add_field(
                    name="Kill Streaks",
                    value="✅ Enabled" if current_highlights.get('streaks', True) else "❌ Disabled",
                    inline=True
                )
                
                embed.add_field(
                    name="Faction vs Faction",
                    value="✅ Enabled" if current_highlights.get('faction_kills', True) else "❌ Disabled",
                    inline=True
                )
                
                embed.add_field(
                    name="Change Settings",
                    value="Use this command with parameters to change highlight settings",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                return
            
            # Update the database with the new highlights
            # Merge with existing filters
            current_filters = self.killfeed_filters.get(guild_id, {})
            current_filters["highlights"] = current_highlights
            
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"killfeed_filters": current_filters}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.killfeed_filters[guild_id] = current_filters
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Killfeed Highlights Updated",
                description="Your killfeed highlight settings have been updated",
                color=discord.Color.green()
            )
            
            # Add fields for each highlight setting
            embed.add_field(
                name="Long Distance Kills",
                value=f"Highlight kills over {current_highlights.get('long_distance', 100)} meters",
                inline=True
            )
            
            embed.add_field(
                name="Kill Streaks",
                value="✅ Enabled" if current_highlights.get('streaks', True) else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Faction vs Faction",
                value="✅ Enabled" if current_highlights.get('faction_kills', True) else "❌ Disabled",
                inline=True
            )
            
            # Add note about enabling if needed
            if guild_id not in self.killfeed_enabled or not self.killfeed_enabled[guild_id]:
                embed.add_field(
                    name="⚠️ Notifications Disabled",
                    value="Killfeed notifications are currently disabled. Use `/killfeed toggle true` to enable them.",
                    inline=False
                )
            
            # Add premium badge
            embed.set_footer(text="Premium Feature")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating killfeed highlights: {e}")
            await ctx.respond(f"❌ Error updating killfeed highlights: {e}")
    
    async def should_send_kill_notification(self, kill, server):
        """
        Check if a kill should be sent as a notification based on filters
        
        Args:
            kill: Kill document
            server: Server document
            
        Returns:
            bool: True if the kill should be sent, False otherwise
        """
        guild_id = server.get("guild_id")
        if not guild_id:
            return False
            
        # Check if killfeed is enabled for this guild
        if guild_id not in self.killfeed_enabled or not self.killfeed_enabled[guild_id]:
            return False
            
        # Check if channel is set
        if guild_id not in self.killfeed_channels:
            return False
            
        # Get filters for this guild
        filters = self.killfeed_filters.get(guild_id, {})
        
        # Apply filters
        
        # Check minimum distance
        min_distance = filters.get("minimum_distance", 0)
        kill_distance = kill.get("distance", 0)
        if kill_distance < min_distance:
            return False
            
        # Check if suicides should be shown
        is_suicide = kill.get("is_suicide", False)
        if is_suicide and not filters.get("show_suicides", False):
            return False
            
        # Check if melee kills should be shown
        weapon = kill.get("weapon", "").lower()
        is_melee = "knife" in weapon or "axe" in weapon or "fist" in weapon or "melee" in weapon
        if is_melee and not filters.get("show_melee", True):
            return False
            
        # Check if AI kills should be shown
        killer_id = kill.get("killer_id", "")
        victim_id = kill.get("victim_id", "")
        is_ai_involved = (killer_id.startswith("ai_") or victim_id.startswith("ai_"))
        if is_ai_involved and not filters.get("show_ai_kills", True):
            return False
            
        # All filters passed, should send notification
        return True
    
    async def format_kill_notification(self, kill, server, guild_id):
        """
        Format a kill notification message
        
        Args:
            kill: Kill document
            server: Server document
            guild_id: Discord guild ID
            
        Returns:
            dict: Formatted message with content, embed, etc.
        """
        # Get highlight settings
        highlights = self.killfeed_filters.get(guild_id, {}).get("highlights", {})
        
        # Basic info
        killer_name = kill.get("killer_name", "Unknown")
        victim_name = kill.get("victim_name", "Unknown")
        weapon = kill.get("weapon", "Unknown")
        distance = kill.get("distance", 0)
        is_suicide = kill.get("is_suicide", False)
        server_name = server.get("name", "Unknown Server")
        
        # Check if this is a highlighted kill
        is_highlighted = False
        highlight_reason = None
        
        # Check for long distance kill
        long_distance_threshold = highlights.get("long_distance", 100)
        if distance >= long_distance_threshold and long_distance_threshold > 0:
            is_highlighted = True
            highlight_reason = f"Long distance kill ({distance}m)"
        
        # Create the embed
        if is_highlighted:
            embed = discord.Embed(
                title=f"⭐ Highlighted Kill - {server_name}",
                description=highlight_reason,
                color=discord.Color.gold()
            )
        else:
            # Use color based on distance
            if distance > 100:
                color = discord.Color.blue()  # Long range
            elif is_suicide:
                color = discord.Color.red()  # Suicide
            else:
                color = discord.Color.green()  # Regular kill
                
            embed = discord.Embed(
                title=f"Kill Feed - {server_name}",
                color=color
            )
        
        # Format the kill message
        if is_suicide:
            kill_message = f"**{victim_name}** died by suicide"
            if weapon != "Unknown":
                kill_message += f" ({weapon})"
        else:
            kill_message = f"**{killer_name}** killed **{victim_name}** with {weapon}"
            if distance > 0:
                kill_message += f" at {distance}m"
                
        embed.description = kill_message
        
        # Add timestamp
        if "timestamp" in kill and isinstance(kill["timestamp"], datetime):
            embed.timestamp = kill["timestamp"]
        
        return {
            "embed": embed
        }
    
    async def send_kill_notification(self, kill, server):
        """
        Send a kill notification to the appropriate channel
        
        Args:
            kill: Kill document
            server: Server document
        """
        try:
            guild_id = server.get("guild_id")
            if not guild_id:
                return
                
            # Check if we should send this notification
            should_send = await self.should_send_kill_notification(kill, server)
            if not should_send:
                return
                
            # Get the channel
            channel_id = self.killfeed_channels[guild_id]
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
                
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return
                
            # Format the notification
            notification = await self.format_kill_notification(kill, server, guild_id)
            
            # Send the notification
            await channel.send(embed=notification["embed"])
            
        except Exception as e:
            logger.error(f"Error sending kill notification: {e}")
    
    # Management methods
    async def update_killfeed_settings(self, guild_id, enabled=None, channel_id=None, filters=None):
        """Update killfeed settings for a guild"""
        if not self.db:
            logger.error("Database not available for updating killfeed settings")
            return False
            
        try:
            update_data = {}
            
            if enabled is not None:
                update_data["killfeed_enabled"] = enabled
                self.killfeed_enabled[guild_id] = enabled
                
            if channel_id is not None:
                update_data["killfeed_channel"] = channel_id
                self.killfeed_channels[guild_id] = channel_id
                
            if filters is not None:
                update_data["killfeed_filters"] = filters
                self.killfeed_filters[guild_id] = filters
                
            if update_data:
                guild_configs = await self.db.get_collection("guild_configs")
                await guild_configs.update_one(
                    {"guild_id": guild_id},
                    {"$set": update_data},
                    upsert=True
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating killfeed settings: {e}")
            
        return False