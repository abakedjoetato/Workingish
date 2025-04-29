import discord
from discord.ext import commands, tasks
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

class AdminCommands(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
    
    @commands.group(name="admin", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def admin(self, ctx):
        """Admin commands for bot management (requires Administrator permission)"""
        await ctx.send("Available commands: `stats`, `premium`, `link`, `unlink`, `cleanup`, `purge`, `home`")
    
    @admin.command(name="stats")
    @commands.has_permissions(administrator=True)
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
    
    @admin.command(name="premium")
    @commands.has_permissions(administrator=True)
    async def set_premium(self, ctx, guild_id: int = None, tier: str = None):
        """
        View or set the premium tier for a guild
        
        Usage: !admin premium [guild_id] [tier]
        
        Available tiers: free, premium, enterprise
        If no tier is provided, the current tier will be shown.
        If no guild_id is provided, the current guild will be used.
        
        Note: Only home guild admins can set premium tiers for other guilds.
        """
        try:
            db = await Database.get_instance()
            
            # Only home guild admins can set premium tiers for other guilds
            if guild_id is not None and guild_id != ctx.guild.id:
                if not await is_home_guild_admin(ctx):
                    await ctx.send("⚠️ Only home guild administrators can set premium tiers for other guilds.")
                    return
            
            # If no guild_id provided, use current guild
            if guild_id is None:
                guild_id = ctx.guild.id
            
            # If this is the home guild, always show enterprise tier
            if await db.is_home_guild(guild_id):
                if tier is not None:
                    await ctx.send("⚠️ Home guild always has enterprise tier and cannot be changed.")
                    return
                
                # Show home guild tier info
                tiers = await get_premium_tiers()
                limits = tiers.get("enterprise", {})
                
                embed = discord.Embed(
                    title="Premium Tier Information",
                    description=f"Home Guild - Tier: **enterprise** ✅",
                    color=discord.Color.gold()
                )
                
                for feature, value in limits.items():
                    embed.add_field(name=feature.replace('_', ' ').title(), 
                                   value=str(value) if value is not None else "Unlimited", 
                                   inline=True)
                
                await ctx.send(embed=embed)
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
                
                await ctx.send(embed=embed)
                return
            
            # Set new tier (only if in home guild with admin permissions)
            if not await is_home_guild_admin(ctx):
                await ctx.send("⚠️ Only administrators in the home guild can change premium tiers.")
                return
            
            # Validate and set the tier
            success = await set_premium_tier(guild_id, tier, ctx)
            if success:
                # If successful, the set_premium_tier function will already send a confirmation message
                pass
            else:
                await ctx.send(f"⚠️ Failed to set premium tier '{tier}' for guild {guild_id}")
                
        except Exception as e:
            logger.error(f"Error in premium command: {e}")
            await ctx.send(f"Error updating premium tier: {e}")
    
    @admin.command(name="link")
    @commands.has_permissions(administrator=True)
    async def link_player(self, ctx, member: discord.Member, *, player_name: str):
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
                await ctx.send(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
                return
            
            # Update player with Discord ID
            player = Player(**{**players[0], "_id": players[0]["_id"]})
            player.discord_id = str(member.id)
            await player.update(db)
            
            await ctx.send(f"✅ Linked player '{player.player_name}' to Discord user {member.mention}")
            
            # Send DM to user
            try:
                await member.send(f"Your Deadside game account '{player.player_name}' has been linked to your Discord account. "
                                 f"You can now use `!stats me` to view your in-game statistics.")
            except:
                # User might have DMs disabled
                pass
        
        except Exception as e:
            logger.error(f"Error linking player: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @admin.command(name="unlink")
    @commands.has_permissions(administrator=True)
    async def unlink_player(self, ctx, member: discord.Member, *, player_name: str = None):
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
                    await ctx.send(f"⚠️ Player '{player_name}' not found or not linked to {member.mention}.")
                    return
                
                # Update player to remove Discord ID
                player = Player(**{**players[0], "_id": players[0]["_id"]})
                player.discord_id = None
                await player.update(db)
                
                await ctx.send(f"✅ Unlinked player '{player.player_name}' from Discord user {member.mention}")
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
    
    @admin.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup_data(self, ctx, data_type: str = "parsers", days: int = 30):
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
    
    @admin.command(name="home")
    @commands.check(is_bot_owner)
    async def set_home_guild_command(self, ctx, guild_id: int = None):
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
    
    @admin.command(name="purge")
    @commands.has_permissions(administrator=True)
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

