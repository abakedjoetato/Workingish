import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta
import traceback

from database.connection import Database
from database.models import Server, GuildConfig, AuthCredentials
from utils.embeds import create_server_embed, create_success_embed, create_error_embed, create_info_embed
from parsers.parser_memory import ParserMemory
from utils.guild_isolation import get_servers_for_guild, can_add_server
from utils.premium import check_premium_feature, get_premium_limits
from utils.game_query import query_game_server

logger = logging.getLogger('deadside_bot.cogs.server')

# Create server command group
server_group = discord.SlashCommandGroup(
    name="server",
    description="Commands for managing Deadside game servers"
)

class ServerCommands(commands.Cog):
    """Commands for managing Deadside game servers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
    
    def get_commands(self):
        """Returns the slash command group for this cog"""
        return [server_group]
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("ServerCommands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            logger.debug("Set database for ServerCommands cog from bot")
    
    @server_group.command(name="list", contexts=[discord.InteractionContextType.guild],)
    async def list_servers(self, ctx):
        """List all servers configured for this Discord server"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Use the guild isolation utility to get only servers for this guild
            servers = await get_servers_for_guild(self.db, ctx.guild.id)
            
            if not servers:
                return await ctx.respond("No servers have been added yet. Use `/server add` to add a server.", ephemeral=True)
                
            embed = discord.Embed(
                title="Configured Servers",
                description=f"Found {len(servers)} servers for this Discord server",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Use /server info <name> for details")
            
            for server in servers:
                # Create a field for each server with basic info
                name = server.get("name", "Unnamed")
                ip = server.get("ip", "Unknown")
                port = server.get("port", "Unknown")
                
                embed.add_field(
                    name=name,
                    value=f"IP: {ip}\nPort: {port}",
                    inline=True
                )
                
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond("⚠️ An error occurred while listing servers", ephemeral=True)
    
    @server_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def add_server(
        self, ctx, 
        name: discord.Option(str, "A name for the server"),
        ip: discord.Option(str, "Server IP address"),
        port: discord.Option(int, "Server port"),
        log_path: discord.Option(str, "Path to log files directory"),
        access_method: discord.Option(
            str, 
            "How to access logs (local/sftp)",
            choices=["local", "sftp"],
            default="local"
        )
    ):
        """Add a new server to monitor"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in add_server command")
                return await ctx.respond("⚠️ Database connection not available. Please try again later.", ephemeral=True)
            
            # Check if we have reached server limit
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            
            # Check if user can add a new server based on premium tier
            can_add = await can_add_server(self.db, ctx.guild.id)
            if not can_add['success']:
                return await ctx.respond(can_add['message'], ephemeral=True)
            
            # Create new server
            server = await Server.create(self.db,
                name=name,
                ip=ip,
                port=port,
                log_path=log_path,
                guild_id=str(ctx.guild.id),
                access_method=access_method
            )
            
            # If it's SFTP, we'll need to follow up for credentials
            if access_method == "sftp":
                await ctx.respond("Server added! Since you selected SFTP access, please set up credentials using:\n"
                              f"`/server credentials {name} <username> [password] [key_path]`")
            else:
                embed = create_success_embed(
                    f"Server '{name}' added successfully!",
                    f"Use `/server info {name}` to view details"
                )
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error adding server: {str(e)}", ephemeral=True)
    
    @server_group.command(name="info")
    async def server_info(
        self, ctx, 
        name: discord.Option(str, "Name of the server to get info about")
    ):
        """Get detailed information about a server"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Defer response as we'll be making API calls
            await ctx.defer()
            
            # Get the server document
            server = await Server.get_by_name(self.db, name, ctx.guild.id)
            
            if not server:
                return await ctx.respond(f"Server '{name}' not found. Use `/server list` to see available servers.", ephemeral=True)
                
            # Check server status
            status = None
            try:
                status = await query_game_server(server.get("ip"), server.get("port"))
            except Exception as e:
                logger.error(f"Error querying server status: {e}")
                status = {"online": False, "error": str(e)}
            
            # Create embed with server info
            embed = create_server_embed(server, status)
            
            # Add parser status if available
            try:
                csv_memory = await ParserMemory.get_or_create(self.db, server.get("_id", ""), "batch_csv")
                if csv_memory and csv_memory.is_running:
                    embed.add_field(
                        name="Parser Status",
                        value=f"Batch CSV Parser: {csv_memory.status}\nProgress: {csv_memory.progress}%",
                        inline=False
                    )
            except Exception as e:
                logger.error(f"Error getting parser status: {e}")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error getting server info: {str(e)}", ephemeral=True)
    
    @server_group.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def remove_server(
        self, ctx, 
        name: discord.Option(str, "Name of the server to remove"),
        confirm: discord.Option(
            bool, 
            "Are you sure? This will delete all server data!",
            default=False
        )
    ):
        """Remove a server from monitoring"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get the server document
            server = await Server.get_by_name(self.db, name, ctx.guild.id)
            
            if not server:
                return await ctx.respond(f"Server '{name}' not found. Use `/server list` to see available servers.", ephemeral=True)
                
            # Check confirmation
            if not confirm:
                embed = create_warning_embed(
                    "Confirmation Required",
                    f"Are you sure you want to remove server '{name}'? This will delete **all** related data, "
                    f"including player stats, killfeed, etc. If you're sure, use:\n\n"
                    f"`/server remove {name} confirm:True`"
                )
                return await ctx.respond(embed=embed)
                
            # Remove server
            await Server.delete(self.db, server.get("_id", ""))
            
            embed = create_success_embed(
                f"Server '{name}' removed",
                "All server data has been deleted."
            )
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing server: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error removing server: {str(e)}", ephemeral=True)
    
    @server_group.command(name="update")
    @commands.has_permissions(manage_guild=True)
    async def update_server(
        self, ctx, 
        name: discord.Option(str, "Name of the server to update"),
        new_name: discord.Option(str, "New server name", default=None),
        ip: discord.Option(str, "Server IP address", default=None),
        port: discord.Option(int, "Server port", default=None),
        log_path: discord.Option(str, "Path to log files directory", default=None),
        access_method: discord.Option(
            str, 
            "How to access logs (local/sftp)",
            choices=["local", "sftp"],
            default=None
        )
    ):
        """Update server configuration"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get the server document
            server = await Server.get_by_name(self.db, name, ctx.guild.id)
            
            if not server:
                return await ctx.respond(f"Server '{name}' not found. Use `/server list` to see available servers.", ephemeral=True)
                
            # Update fields
            updates = {}
            if new_name is not None:
                updates["name"] = new_name
            if ip is not None:
                updates["ip"] = ip
            if port is not None:
                updates["port"] = port
            if log_path is not None:
                updates["log_path"] = log_path
            if access_method is not None:
                updates["access_method"] = access_method
                
            if not updates:
                return await ctx.respond("No updates provided. Please specify at least one field to update.", ephemeral=True)
                
            # Apply updates
            await Server.update(self.db, server.get("_id", ""), updates)
            
            display_name = new_name if new_name else name
            embed = create_success_embed(
                f"Server '{display_name}' updated",
                "The server configuration has been updated."
            )
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error updating server: {str(e)}", ephemeral=True)
    
    @server_group.command(name="credentials")
    @commands.has_permissions(manage_guild=True)
    async def set_credentials(
        self, ctx, 
        name: discord.Option(str, "Name of the server to set credentials for"),
        username: discord.Option(str, "SSH/SFTP username"),
        password: discord.Option(str, "SSH/SFTP password (leave empty if using key)", default=None),
        key_path: discord.Option(str, "Path to SSH key file (leave empty if using password)", default=None)
    ):
        """Set SFTP credentials for remote log access"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get the server document
            server = await Server.get_by_name(self.db, name, ctx.guild.id)
            
            if not server:
                return await ctx.respond(f"Server '{name}' not found. Use `/server list` to see available servers.", ephemeral=True)
                
            # Verify access method is SFTP
            if server.get("access_method") != "sftp":
                return await ctx.respond(f"Server '{name}' is not configured for SFTP access. Please update the server first.", ephemeral=True)
                
            # Create or update credentials
            server_id = server.get("_id", "")
            await AuthCredentials.set_credentials(
                self.db,
                server_id,
                username,
                password,
                key_path
            )
            
            await ctx.respond(f"✅ SFTP credentials have been updated.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting credentials: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error setting credentials: {str(e)}", ephemeral=True)

    @server_group.command(name="status")
    async def status(self, ctx):
        """Check status of all configured servers"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Defer response as we'll be making API calls
            await ctx.defer()
            
            # Use the guild isolation utility to get only servers for this guild
            servers = await get_servers_for_guild(self.db, ctx.guild.id)
            
            if not servers:
                return await ctx.respond("No servers have been added yet. Use `/server add` to add a server.", ephemeral=True)
                
            embed = discord.Embed(
                title="Server Status",
                description=f"Status of {len(servers)} configured servers",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            status_emojis = {
                True: "🟢",  # Online
                False: "🔴",  # Offline
                None: "⚪"   # Unknown
            }
            
            for server in servers:
                server_name = server.get("name", "Unnamed")
                server_ip = server.get("ip", "Unknown")
                server_port = server.get("port", "Unknown")
                
                try:
                    # Query server status
                    status = await query_game_server(server_ip, server_port)
                    
                    # Format status message
                    if status.get("online"):
                        players = status.get("players", {})
                        current = players.get("online", 0)
                        maximum = players.get("max", 0)
                        status_text = f"{status_emojis[True]} Online - {current}/{maximum} players"
                        
                        # Add more info if available
                        if "name" in status:
                            status_text += f"\nName: {status.get('name')}"
                        if "map" in status:
                            status_text += f"\nMap: {status.get('map')}"
                    else:
                        status_text = f"{status_emojis[False]} Offline"
                        if "error" in status:
                            status_text += f"\nError: {status.get('error')}"
                except Exception as e:
                    logger.error(f"Error querying server {server_name}: {e}")
                    status_text = f"{status_emojis[None]} Status check failed\nError: {str(e)}"
                
                embed.add_field(
                    name=server_name,
                    value=f"{server_ip}:{server_port}\n{status_text}",
                    inline=True
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"⚠️ Error checking server status: {str(e)}", ephemeral=True)

def setup(bot):
    """Required setup function for cog loading"""
    bot.add_cog(ServerCommands(bot))

# Helper function to create warning embed
def create_warning_embed(title, description=None):
    """Create a warning embed with an orange color"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange()
    )
    return embed