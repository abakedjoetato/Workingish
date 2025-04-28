import discord
from discord.ext import commands
import logging
import asyncio
from database.connection import Database
from parsers.parser_memory import ParserMemory
from database.models import Player
from utils.premium import (
    get_premium_tiers, 
    get_guild_premium_tier,
    set_premium_tier, 
    is_home_guild, 
    is_home_guild_admin, 
    is_bot_owner,
    set_home_guild
)
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.cogs.admin')

# Define the slash command group outside the class first
admin_group = discord.SlashCommandGroup(
    name="admin",
    description="Administrative commands for bot management",
    default_member_permissions=discord.Permissions(administrator=True)
)

class AdminCommands(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("AdminCommands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            logger.debug("Set database for AdminCommands cog from bot")
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [admin_group]
    
    @admin_group.command(name="stats", description="View bot statistics and performance metrics")
    async def show_stats(self, ctx):
        """View bot statistics and performance metrics"""
        try:
            db = await Database.get_instance()
            
            # Get counts of various collections
            servers_coll = await db.get_collection("servers")
            players_coll = await db.get_collection("players")
            kills_coll = await db.get_collection("kills")
            events_coll = await db.get_collection("server_events")
            connections_coll = await db.get_collection("connection_events")
            
            # Determine if we should show global stats or guild-specific stats
            is_admin_in_home = await is_home_guild_admin(ctx)
            
            # Filter for guild-specific stats if not a home guild admin
            if is_admin_in_home:
                guild_filter = {}
                stats_scope = "Global"
            else:
                guild_filter = {"guild_id": ctx.guild.id}
                stats_scope = "Guild"
            
            # Get guild-filtered server count
            servers_count = await servers_coll.count_documents(guild_filter)
            
            # Get server IDs for this guild/filter to filter related collections
            cursor = servers_coll.find(guild_filter)
            servers = await cursor.to_list(None)
            server_ids = [server["_id"] for server in servers]
            
            # Filter for server-specific data using the server IDs
            if server_ids:
                server_filter = {"server_id": {"$in": server_ids}}
                
                # Count related data
                kills_count = await kills_coll.count_documents(server_filter)
                events_count = await events_coll.count_documents(server_filter)
                connections_count = await connections_coll.count_documents(server_filter)
            else:
                # No servers for this guild
                kills_count = 0
                events_count = 0
                connections_count = 0
            
            # Players are global, but can limit to those seen on guild servers if desired
            players_count = await players_coll.count_documents({})
            
            # Guild count and uptime are shown for all admins
            guilds_count = len(self.bot.guilds)
            uptime = datetime.utcnow() - datetime.fromtimestamp(self.bot.launch_time)
            
            # Create embed with scope-appropriate title
            embed = discord.Embed(
                title=f"Bot Statistics ({stats_scope})",
                description="Current statistics and metrics",
                color=discord.Color.blue()
            )
            
            # Discord stats field - show guild count only for home guild admins
            discord_stats = f"Latency: {round(self.bot.latency * 1000)}ms\n"
            discord_stats += f"Uptime: {str(uptime).split('.')[0]}"
            
            if is_admin_in_home:
                discord_stats = f"Guilds: {guilds_count}\n" + discord_stats
            
            embed.add_field(
                name="Discord Stats",
                value=discord_stats
            )
            
            # Database stats field
            db_stats = f"Servers: {servers_count}\n"
            db_stats += f"Players: {players_count}\n"
            db_stats += f"Kills: {kills_count}\n"
            db_stats += f"Events: {events_count}\n"
            db_stats += f"Connections: {connections_count}"
            
            embed.add_field(
                name=f"Database Stats ({stats_scope})",
                value=db_stats
            )
            
            # Parser memory usage - filter by guild servers if not home admin
            if is_admin_in_home:
                # Show all parsers
                csv_parsers = await ParserMemory.get_parsers_by_type("csv")
                log_parsers = await ParserMemory.get_parsers_by_type("log")
            else:
                # Filter parsers by guild's servers
                csv_parsers = [p for p in await ParserMemory.get_parsers_by_type("csv") 
                              if any(p.server_id == server_id for server_id in server_ids)]
                log_parsers = [p for p in await ParserMemory.get_parsers_by_type("log")
                              if any(p.server_id == server_id for server_id in server_ids)]
            
            memory_parsers = len(csv_parsers) + len(log_parsers)
            
            embed.add_field(
                name="Parser Stats",
                value=f"Active Parsers: {memory_parsers}"
            )
            
            # Add home guild and premium tier info
            if await is_home_guild(ctx.guild.id):
                embed.add_field(name="Home Guild", value="Yes ✅", inline=True)
                embed.add_field(name="Premium Tier", value="Enterprise", inline=True)
            else:
                tier = await db.get_guild_premium_tier(ctx.guild.id)
                embed.add_field(name="Premium Tier", value=tier, inline=True)
            
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @admin_group.command(name="premium", description="View or set the premium tier for a guild")
    async def set_premium(self, ctx, 
                         guild_id: discord.Option(int, "Guild ID to set premium for", required=False) = None, 
                         tier: discord.Option(str, "Tier to set (survivor, warlord, overseer)", required=False) = None):
        """
        View or set the premium tier for a guild
        
        Usage: !admin premium [guild_id] [tier]
        
        Available tiers: survivor, warlord, overseer
        If no tier is provided, the current tier will be shown.
        If no guild_id is provided, the current guild will be used.
        
        Note: Only home guild admins can set premium tiers for other guilds.
        """
        try:
            db = await Database.get_instance()
            
            # Only home guild admins can set premium tiers for other guilds
            if guild_id is not None and guild_id != ctx.guild.id:
                if not await is_home_guild_admin(ctx):
                    await ctx.respond("⚠️ Only home guild administrators can set premium tiers for other guilds.")
                    return
            
            # If no guild_id provided, use current guild
            if guild_id is None:
                guild_id = ctx.guild.id
            
            # If this is the home guild, always show overseer tier
            if await db.is_home_guild(guild_id):
                if tier is not None:
                    await ctx.respond("⚠️ Home guild always has Overseer tier and cannot be changed.")
                    return
                
                # Show home guild tier info
                tiers = await get_premium_tiers()
                limits = tiers.get("overseer", {})
                
                embed = discord.Embed(
                    title="Premium Tier Information",
                    description=f"Home Guild - Tier: **Overseer** ✅",
                    color=discord.Color.gold()
                )
                
                for feature, value in limits.items():
                    embed.add_field(name=feature.replace('_', ' ').title(), 
                                   value=str(value) if value is not None else "Unlimited", 
                                   inline=True)
                
                await ctx.respond(embed=embed)
                return
            
            # If no tier is provided, show current tier
            if tier is None:
                current_tier = await db.get_guild_premium_tier(guild_id)
                tiers = await get_premium_tiers()
                limits = tiers.get(current_tier, {})
                
                embed = discord.Embed(
                    title="Premium Tier Information",
                    description=f"Guild ID: {guild_id}\nCurrent tier: **{current_tier}**",
                    color=discord.Color.blue()
                )
                
                for feature, value in limits.items():
                    embed.add_field(name=feature.replace('_', ' ').title(), 
                                   value=str(value) if value is not None else "Unlimited", 
                                   inline=True)
                
                await ctx.respond(embed=embed)
                return
            
            # Set new tier (only if in home guild with admin permissions)
            if not await is_home_guild_admin(ctx):
                await ctx.respond("⚠️ Only administrators in the home guild can change premium tiers.")
                return
            
            # Validate and set the tier
            success = await set_premium_tier(guild_id, tier, ctx)
            if success:
                # If successful, the set_premium_tier function will already send a confirmation message
                pass
            else:
                await ctx.respond(f"⚠️ Failed to set premium tier '{tier}' for guild {guild_id}")
                
        except Exception as e:
            logger.error(f"Error in premium command: {e}")
            await ctx.respond(f"Error updating premium tier: {e}")
    
    @admin_group.command(name="link", description="Link a Discord member to a game player")
    async def link_player(self, ctx, 
                         member: discord.Option(discord.Member, "Discord member to link", required=True),
                         player_name: discord.Option(str, "Player name to link to the member", required=True)):
        """
        Link a Discord member to a game player
        
        Usage: !admin link @user <player_name>
        
        This allows users to see their own stats with !stats me
        """
        try:
            db = await Database.get_instance()
            
            # Find player by name
            collection = await db.get_collection("players")
            cursor = collection.find({
                "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
            })
            players = await cursor.to_list(None)
            
            if not players:
                await ctx.respond(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
                return
            
            # Update player with Discord ID
            player = Player(**{**players[0], "_id": players[0]["_id"]})
            player.discord_id = str(member.id)
            await player.update(db)
            
            await ctx.respond(f"✅ Linked player '{player.player_name}' to Discord user {member.mention}")
            
            # Send DM to user
            try:
                await member.send(f"Your Deadside game account '{player.player_name}' has been linked to your Discord account. "
                                 f"You can now use `!stats me` to view your in-game statistics.")
            except:
                # User might have DMs disabled
                pass
        
        except Exception as e:
            logger.error(f"Error linking player: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @admin_group.command(name="unlink", description="Unlink a Discord member from a game player")
    async def unlink_player(self, ctx, 
                           member: discord.Option(discord.Member, "Discord member to unlink", required=True),
                           player_name: discord.Option(str, "Player name to unlink (leave empty to unlink all)", required=False) = None):
        """
        Unlink a Discord member from a game player
        
        Usage: !admin unlink @user [player_name]
        
        If player_name is provided, only that specific link is removed.
        Otherwise, all player links for the user are removed.
        """
        try:
            db = await Database.get_instance()
            
            if player_name:
                # Find specific player
                collection = await db.get_collection("players")
                cursor = collection.find({
                    "player_name": {"$regex": f"^{player_name}$", "$options": "i"},
                    "discord_id": str(member.id)
                })
                players = await cursor.to_list(None)
                
                if not players:
                    await ctx.respond(f"⚠️ Player '{player_name}' not found or not linked to {member.mention}.")
                    return
                
                # Update player to remove Discord ID
                player = Player(**{**players[0], "_id": players[0]["_id"]})
                player.discord_id = None
                await player.update(db)
                
                await ctx.respond(f"✅ Unlinked player '{player.player_name}' from Discord user {member.mention}")
            else:
                # Remove all links for this user
                collection = await db.get_collection("players")
                result = await collection.update_many(
                    {"discord_id": str(member.id)},
                    {"$set": {"discord_id": None}}
                )
                
                await ctx.send(f"✅ Unlinked {result.modified_count} players from Discord user {member.mention}")
        
        except Exception as e:
            logger.error(f"Error unlinking player: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @admin_group.command(name="cleanup", description="Clean up old data from the database")
    async def cleanup_data(self, ctx, 
                          data_type: discord.Option(str, "Type of data to clean (parsers, connections, kills)", 
                                                   choices=["parsers", "connections", "kills"], required=False) = "parsers",
                          days: discord.Option(int, "Age of data to remove (in days)", min_value=1, required=False) = 30):
        """
        Clean up old data from the database
        
        Usage: !admin cleanup [data_type] [days]
        
        data_type: Type of data to clean up (parsers, connections, kills)
        days: Age of data to remove (in days)
        """
        try:
            if days < 1:
                await ctx.send("⚠️ Days must be at least 1.")
                return
            
            db = await Database.get_instance()
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = None
            
            if data_type.lower() == "parsers":
                # Clean old parser states
                collection = await db.get_collection("parser_state")
                result = await collection.delete_many({
                    "updated_at": {"$lt": cutoff_date}
                })
                message = f"Cleaned up {result.deleted_count} old parser states."
            
            elif data_type.lower() == "connections":
                # Clean old connection events
                collection = await db.get_collection("connection_events")
                result = await collection.delete_many({
                    "timestamp": {"$lt": cutoff_date}
                })
                message = f"Cleaned up {result.deleted_count} old connection events."
            
            elif data_type.lower() == "kills":
                # Clean old kill events
                collection = await db.get_collection("kills")
                result = await collection.delete_many({
                    "timestamp": {"$lt": cutoff_date}
                })
                message = f"Cleaned up {result.deleted_count} old kill events."
            
            else:
                await ctx.send("⚠️ Invalid data type. Available types: parsers, connections, kills")
                return
            
            logger.info(message)
            await ctx.send(f"✅ {message}")
        
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @admin_group.command(name="home", description="Set or view the home guild (bot owner only)")
    async def set_home_guild_command(self, ctx, 
                                    guild_id: discord.Option(int, "Guild ID to set as home", required=False) = None):
        """
        Set or view the home guild
        
        Usage: !admin home [guild_id]
        
        If no guild_id is provided, the current home guild info will be shown.
        This command can only be used by the bot owner.
        """
        try:
            db = await Database.get_instance()
            
            # If no guild_id provided, show current home guild
            if guild_id is None:
                home_guild_id = await db.get_home_guild_id()
                
                if home_guild_id is None:
                    await ctx.send("⚠️ No home guild is currently set.")
                    return
                
                home_guild = self.bot.get_guild(home_guild_id)
                home_name = home_guild.name if home_guild else f"Unknown Guild ({home_guild_id})"
                
                embed = discord.Embed(
                    title="Home Guild Information",
                    description=f"Current home guild: **{home_name}**\nID: {home_guild_id}",
                    color=discord.Color.gold()
                )
                
                await ctx.send(embed=embed)
                return
            
            # Set new home guild
            success = await set_home_guild(guild_id, ctx)
            if not success:
                await ctx.send(f"⚠️ Failed to set guild {guild_id} as home guild.")
        
        except Exception as e:
            logger.error(f"Error in home guild command: {e}")
            await ctx.send(f"Error setting home guild: {e}")
    
    @admin_group.command(name="purge", description="Purge all data for this guild (requires confirmation)")
    async def purge_guild_data(self, ctx):
        """
        Purge all data for this guild (requires confirmation)
        
        Usage: !admin purge
        
        This will remove ALL servers, parser states, and guild configuration.
        Player data and statistics will NOT be removed.
        """
        try:
            # Confirm deletion
            confirm_msg = await ctx.send("⚠️ **DANGER!** This will delete ALL server configurations, parser states, and guild settings for this guild. "
                                        "Player data and statistics will be preserved. This action cannot be undone!\n\n"
                                        "Type `confirm` to proceed or `cancel` to abort.")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["confirm", "cancel"]
            
            try:
                # Wait for confirmation
                response = await self.bot.wait_for('message', timeout=30.0, check=check)
                
                if response.content.lower() == "cancel":
                    await ctx.send("Purge operation cancelled.")
                    return
                
                # Proceed with purge
                db = await Database.get_instance()
                
                # Get servers for this guild
                collection = await db.get_collection("servers")
                cursor = collection.find({"guild_id": ctx.guild.id})
                servers = await cursor.to_list(None)
                server_ids = [server["_id"] for server in servers]
                
                # Delete servers
                servers_collection = await db.get_collection("servers")
                result_servers = await servers_collection.delete_many({"guild_id": ctx.guild.id})
                
                # Delete parser states for those servers
                parser_collection = await db.get_collection("parser_state")
                result_parsers = await parser_collection.delete_many({"server_id": {"$in": server_ids}})
                
                # Delete guild config
                config_collection = await db.get_collection("guild_configs")
                result_config = await config_collection.delete_many({"guild_id": ctx.guild.id})
                
                # Send summary
                await ctx.send(f"✅ Purge completed:\n"
                              f"- Deleted {result_servers.deleted_count} servers\n"
                              f"- Deleted {result_parsers.deleted_count} parser states\n"
                              f"- Deleted {result_config.deleted_count} guild configurations\n\n"
                              f"Player data and statistics have been preserved.")
                
            except asyncio.TimeoutError:
                await ctx.send("Purge operation timed out.")
                
        except Exception as e:
            logger.error(f"Error purging guild data: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
            
    @admin_group.command(name="features", description="Display all available features by premium tier")
    async def show_features(self, ctx):
        """
        Display all available features by premium tier
        
        Usage: !admin features
        
        Shows a comparison of features available in each premium tier.
        """
        try:
            db = await Database.get_instance()
            tiers = await get_premium_tiers()
            
            # Create feature comparison embed
            embed = discord.Embed(
                title="Premium Features Comparison",
                description="Features available in each premium tier",
                color=discord.Color.gold()
            )
            
            # Group features into categories for better organization
            feature_categories = {
                "🔢 Server Limits": ["max_servers", "max_history_days"],
                "🔧 Core Features": ["basic_stats", "leaderboard", "killfeed", "connection_tracking", "mission_tracking", "player_linking"],
                "✨ Advanced Features": ["advanced_stats", "historical_parsing", "custom_embeds", "csv_parsing", "log_parsing"],
                "⭐ Premium Features": ["faction_system", "rivalry_tracking"]
            }
            
            # Display current tier
            current_tier = await db.get_guild_premium_tier(ctx.guild.id)
            embed.add_field(
                name="Your Current Tier",
                value=f"**{current_tier.title()}**",
                inline=False
            )
            
            # Add a comparison table for each feature category
            for category, features in feature_categories.items():
                # Build feature table for this category
                table = "```\n"
                table += f"{'Feature':<20} | {'Free':<8} | {'Premium':<8} | {'Enterprise':<10}\n"
                table += f"{'-' * 20} | {'-' * 8} | {'-' * 8} | {'-' * 10}\n"
                
                for feature in features:
                    feature_name = feature.replace('_', ' ').title()
                    feature_name = feature_name[:18] + ".." if len(feature_name) > 18 else feature_name
                    
                    # Get values for each tier
                    free_val = self._format_feature_value(tiers["free"].get(feature, "N/A"))
                    premium_val = self._format_feature_value(tiers["premium"].get(feature, "N/A"))
                    enterprise_val = self._format_feature_value(tiers["enterprise"].get(feature, "N/A"))
                    
                    table += f"{feature_name:<20} | {free_val:<8} | {premium_val:<8} | {enterprise_val:<10}\n"
                
                table += "```"
                
                embed.add_field(
                    name=category,
                    value=table,
                    inline=False
                )
            
            # Add feature descriptions
            descriptions = {
                "faction_system": "Create and manage player factions with Discord role integration",
                "rivalry_tracking": "Track player rivalries (nemesis/prey) for enhanced stats",
                "custom_embeds": "Customize embed colors and appearance",
                "advanced_stats": "View detailed player performance metrics and trends",
                "historical_parsing": "Process historical log files for complete data"
            }
            
            desc_text = "__Premium Feature Descriptions:__\n\n"
            for feature, desc in descriptions.items():
                desc_text += f"**{feature.replace('_', ' ').title()}**: {desc}\n"
            
            embed.add_field(
                name="Feature Details",
                value=desc_text,
                inline=False
            )
            
            embed.set_footer(text="Use !admin premium to view your current tier details")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in features command: {e}")
            await ctx.send(f"Error displaying features: {e}")
    
    def _format_feature_value(self, value):
        """Helper method to format feature values for the comparison table"""
        if isinstance(value, bool):
            return "✓" if value else "✗"
        elif value is None:
            return "∞"  # infinity symbol for unlimited
        else:
            return str(value)

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_application_command(admin_group)
    bot.add_cog(AdminCommands(bot))
