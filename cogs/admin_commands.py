import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger('deadside_bot.admin')

# Create a SlashCommandGroup for admin commands
admin_group = discord.SlashCommandGroup(
    name="admin",
    description="Administrative commands for bot management",
    default_member_permissions=discord.Permissions(administrator=True)
)

class AdminCommands(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Admin commands cog loaded")
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [admin_group]
    
    @admin_group.command(
        name="sync",
        description="Force sync commands with Discord (Admin only, contexts=[discord.InteractionContextType.guild],)",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def admin_sync(self, ctx):
        """Force synchronize all commands with Discord"""
        await ctx.defer()
        
        try:
            # Attempt to use the advanced sync retry module
            try:
                from utils.sync_retry import safe_command_sync
                
                # Force a sync with all commands
                await ctx.respond("🔄 Syncing commands with Discord... This may take a while due to rate limits.")
                
                sync_result = await safe_command_sync(self.bot, force=True)
                
                if sync_result:
                    await ctx.followup.send("✅ Command sync completed successfully!")
                else:
                    await ctx.followup.send("⚠️ Command sync was partially successful. Some commands may take time to appear due to Discord rate limits.")
                    
            except ImportError:
                # Fallback to traditional sync
                await ctx.respond("🔄 Syncing commands with Discord...")
                await self.bot.sync_commands()
                await ctx.followup.send("✅ Commands synced successfully!")
                
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await ctx.followup.send(f"❌ Error syncing commands: {e}")
            
    @admin_group.command(
        name="set_home_guild",
        description="Set the current guild as the bot's home guild", 
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def set_home_guild(self, ctx):
        """Set the current guild as the bot's home guild"""
        await ctx.defer()
        
        if not self.bot.db:
            await ctx.respond("❌ Database not initialized")
            return
            
        try:
            config_collection = await self.bot.db.get_collection("bot_config")
            
            # Set this guild as the home guild
            await config_collection.update_one(
                {"_id": "home_guild"},
                {"$set": {"guild_id": str(ctx.guild.id)}},
                upsert=True
            )
            
            # Store in bot memory
            self.bot.home_guild_id = ctx.guild.id
            
            await ctx.respond(f"✅ Set {ctx.guild.name} as the bot's home guild!")
            logger.info(f"Home guild set to {ctx.guild.name} (ID: {ctx.guild.id})")
            
            # Sync commands to this guild immediately
            # This uses the new guild-specific registration to bypass rate limits
            try:
                await ctx.followup.send("⏳ Syncing commands to this guild...")
                
                # Collect all commands from cogs
                commands_payload = []
                
                # Process each cog to collect commands
                for cog_name, cog in self.bot.cogs.items():
                    if hasattr(cog, "get_commands") and callable(cog.get_commands):
                        try:
                            cog_commands = cog.get_commands()
                            if cog_commands:
                                for cmd in cog_commands:
                                    if hasattr(cmd, 'to_dict'):
                                        cmd_payload = cmd.to_dict()
                                        commands_payload.append(cmd_payload)
                        except Exception as cog_err:
                            logger.error(f"Error processing commands from cog {cog_name}: {cog_err}")
                
                # Add base commands (ping, commands)
                ping_cmd = {
                    "name": "ping",
                    "description": "Check bot response time",
                    "type": 1
                }
                commands_payload.append(ping_cmd)
                
                help_cmd = {
                    "name": "commands",
                    "description": "Show available commands and help information",
                    "type": 1
                }
                commands_payload.append(help_cmd)
                
                # Register commands directly to this guild
                try:
                    result = await self.bot.http.request(
                        'PUT',
                        f"/applications/{self.bot.application_id}/guilds/{ctx.guild.id}/commands",
                        json=commands_payload
                    )
                    
                    await ctx.followup.send(f"✅ Successfully registered {len(commands_payload)} commands to this guild")
                except Exception as api_err:
                    await ctx.followup.send(f"❌ Command registration failed: {api_err}")
                    
                    # Try the old method as fallback
                    if hasattr(self.bot, "sync_application_commands"):
                        await ctx.followup.send("Trying alternative sync method...")
                        try:
                            await self.bot.sync_application_commands(guild_id=ctx.guild.id)
                            await ctx.followup.send("✅ Commands synced successfully using alternative method")
                        except Exception as e:
                            await ctx.followup.send(f"❌ All sync methods failed: {e}")
            except Exception as e:
                await ctx.followup.send(f"❌ Error syncing commands: {e}")
            
        except Exception as e:
            logger.error(f"Error setting home guild: {e}")
            await ctx.followup.send(f"❌ Error setting home guild: {e}")
            
    @admin_group.command(
        name="status",
        description="Check bot status and statistics",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def status(self, ctx):
        """Display bot status and statistics"""
        await ctx.defer()
        
        if not self.bot.db:
            await ctx.respond("❌ Database not initialized")
            return
            
        try:
            # Get database stats
            servers_collection = await self.bot.db.get_collection("servers")
            server_count = await servers_collection.count_documents({})
            
            # Count guilds
            guild_count = len(self.bot.guilds)
            total_members = sum(guild.member_count for guild in self.bot.guilds)
            
            # Get player stats
            players_collection = await self.bot.db.get_collection("players")
            player_count = await players_collection.count_documents({})
            
            # Count command usage if available
            command_count = 0
            try:
                command_stats = await self.bot.db.get_collection("command_stats")
                pipeline = [{"$group": {"_id": None, "total": {"$sum": "$count"}}}]
                result = await command_stats.aggregate(pipeline).to_list(1)
                if result:
                    command_count = result[0].get("total", 0)
            except Exception as e:
                logger.error(f"Error getting command stats: {e}")
            
            # Create embed
            embed = discord.Embed(
                title="🛡️ Bot Status",
                description="Current operational statistics",
                color=discord.Color.green()
            )
            
            # Add fields
            embed.add_field(
                name="🤖 Bot Info",
                value=f"Name: {self.bot.user.name}\nID: {self.bot.user.id}\nPing: {round(self.bot.latency * 1000)}ms",
                inline=True
            )
            
            embed.add_field(
                name="📊 Discord Stats",
                value=f"Guilds: {guild_count}\nMembers: {total_members}",
                inline=True
            )
            
            embed.add_field(
                name="🎮 Game Stats",
                value=f"Servers: {server_count}\nPlayers: {player_count}",
                inline=True
            )
            
            # Add version info if available
            if hasattr(self.bot, 'version'):
                embed.set_footer(text=f"Bot Version: {self.bot.version} | Discord.py Version: {discord.__version__}")
            else:
                embed.set_footer(text=f"Discord.py Version: {discord.__version__}")
            
            # Send the embed
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error retrieving bot status: {e}")
            await ctx.respond(f"❌ Error retrieving bot status: {e}")
    
    @admin_group.command(
        name="version",
        description="Check bot version information",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install],
    )
    async def version(self, ctx):
        """Display bot version information"""
        version = getattr(self.bot, 'version', "1.0.0")
        await ctx.respond(f"🤖 **Emerald Servers Bot v{version}**\n📚 Discord.py Version: {discord.__version__}")