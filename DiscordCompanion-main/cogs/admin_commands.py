import discord
from discord.ext import commands
import logging
import asyncio
from database.connection import Database
from database.models import GuildConfig, Player
from parsers.parser_memory import ParserMemory
from utils.premium import get_premium_tiers, set_premium_tier
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.cogs.admin')

class AdminCommands(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="admin", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def admin(self, ctx):
        """Admin commands for bot management (requires Administrator permission)"""
        await ctx.send("Available commands: `stats`, `premium`, `link`, `unlink`, `cleanup`, `purge`")
    
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
            
            servers_count = await servers_coll.count_documents({})
            players_count = await players_coll.count_documents({})
            kills_count = await kills_coll.count_documents({})
            events_count = await events_coll.count_documents({})
            connections_count = await connections_coll.count_documents({})
            
            # Get guilds using the bot
            guilds_count = len(self.bot.guilds)
            
            # Get uptime
            uptime = datetime.utcnow() - datetime.fromtimestamp(self.bot.launch_time)
            
            # Create embed
            embed = discord.Embed(
                title="Deadside Bot Stats",
                description="Current statistics and metrics",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Discord Stats",
                value=f"Guilds: {guilds_count}\n"
                      f"Latency: {round(self.bot.latency * 1000)}ms\n"
                      f"Uptime: {str(uptime).split('.')[0]}"
            )
            
            embed.add_field(
                name="Database Stats",
                value=f"Servers: {servers_count}\n"
                      f"Players: {players_count}\n"
                      f"Kills: {kills_count}\n"
                      f"Events: {events_count}\n"
                      f"Connections: {connections_count}"
            )
            
            # Memory usage
            csv_parsers = await ParserMemory.get_parsers_by_type("csv")
            log_parsers = await ParserMemory.get_parsers_by_type("log")
            memory_parsers = len(csv_parsers) + len(log_parsers)
            
            embed.add_field(
                name="Parser Stats",
                value=f"Active Parsers: {memory_parsers}"
            )
            
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @admin.command(name="premium")
    @commands.has_permissions(administrator=True)
    async def set_premium(self, ctx, tier: str = None):
        """
        View or set the premium tier for this guild
        
        Usage: !admin premium [tier]
        
        Available tiers: free, premium, enterprise
        If no tier is provided, the current tier will be shown.
        """
        try:
            db = await Database.get_instance()
            guild_config = await GuildConfig.get_or_create(db, ctx.guild.id)
            
            # Get available tiers
            premium_tiers = await get_premium_tiers()
            
            if tier is None:
                # Show current tier and limits
                current_tier = guild_config.premium_tier
                limits = premium_tiers.get(current_tier, premium_tiers["free"])
                
                embed = discord.Embed(
                    title=f"Premium Status - {current_tier.title()}",
                    description="Current premium tier and limits",
                    color=discord.Color.gold() if current_tier != "free" else discord.Color.light_grey()
                )
                
                embed.add_field(
                    name="Limits",
                    value=f"Max Servers: {limits['max_servers']}\n"
                          f"Historical Parsing: {'✅' if limits['historical_parsing'] else '❌'}\n"
                          f"Max History Days: {limits['max_history_days']}\n"
                          f"Custom Embeds: {'✅' if limits['custom_embeds'] else '❌'}\n"
                          f"Advanced Stats: {'✅' if limits['advanced_stats'] else '❌'}"
                )
                
                embed.set_footer(text="Use !admin premium <tier> to upgrade")
                
                await ctx.send(embed=embed)
            else:
                # Set new tier
                tier = tier.lower()
                if tier not in premium_tiers:
                    await ctx.send(f"⚠️ Invalid tier. Available tiers: {', '.join(premium_tiers.keys())}")
                    return
                
                # Update tier
                previous_tier = guild_config.premium_tier
                await set_premium_tier(guild_config, tier)
                
                await ctx.send(f"✅ Premium tier updated from '{previous_tier}' to '{tier}'.")
        
        except Exception as e:
            logger.error(f"Error handling premium command: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
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
            players = await db.get_collection("players").find({
                "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
            }).to_list(None)
            
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
                players = await db.get_collection("players").find({
                    "player_name": {"$regex": f"^{player_name}$", "$options": "i"},
                    "discord_id": str(member.id)
                }).to_list(None)
                
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
                result = await db.get_collection("players").update_many(
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
                result = await db.get_collection("parser_state").delete_many({
                    "updated_at": {"$lt": cutoff_date}
                })
                message = f"Cleaned up {result.deleted_count} old parser states."
            
            elif data_type.lower() == "connections":
                # Clean old connection events
                result = await db.get_collection("connection_events").delete_many({
                    "timestamp": {"$lt": cutoff_date}
                })
                message = f"Cleaned up {result.deleted_count} old connection events."
            
            elif data_type.lower() == "kills":
                # Clean old kill events
                result = await db.get_collection("kills").delete_many({
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
                servers = await db.get_collection("servers").find({"guild_id": ctx.guild.id}).to_list(None)
                server_ids = [server["_id"] for server in servers]
                
                # Delete servers
                result_servers = await db.get_collection("servers").delete_many({"guild_id": ctx.guild.id})
                
                # Delete parser states for those servers
                result_parsers = await db.get_collection("parser_state").delete_many({"server_id": {"$in": server_ids}})
                
                # Delete guild config
                result_config = await db.get_collection("guild_configs").delete_many({"guild_id": ctx.guild.id})
                
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

