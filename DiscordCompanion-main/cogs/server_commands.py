import discord
from discord.ext import commands, tasks
import logging
from database.connection import Database
from database.models import Server, GuildConfig
from utils.embeds import create_server_embed
from parsers.parser_memory import ParserMemory

logger = logging.getLogger('deadside_bot.cogs.server')

class ServerCommands(commands.Cog):
    """Commands for managing Deadside game servers"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="server", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def server(self, ctx):
        """Server management commands. Use !server add to add a new server"""
        await ctx.send("Available commands: `add`, `list`, `remove`, `info`, `update`")
    
    @server.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def add_server(self, ctx, name: str, ip: str, port: int, log_path: str, 
                         access_method: str = "local"):
        """
        Add a new server to monitor
        
        Usage: !server add <name> <ip> <port> <log_path> [access_method]
        
        Arguments:
          name: A name for the server
          ip: Server IP address
          port: Server port
          log_path: Path to log files directory
          access_method: How to access logs (local/sftp), default: local
        
        Example:
          !server add "My Server" 192.168.1.100 15000 /path/to/logs sftp
        """
        try:
            # Check if access_method is valid
            if access_method not in ["local", "sftp"]:
                await ctx.send("⚠️ Invalid access method. Choose either 'local' or 'sftp'.")
                return
            
            db = await Database.get_instance()
            
            # Check if we have reached server limit
            guild_config = await GuildConfig.get_or_create(db, ctx.guild.id)
            existing_servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Import premium tier info
            from utils.premium import get_premium_limits
            premium_limits = await get_premium_limits(guild_config.premium_tier)
            
            if len(existing_servers) >= premium_limits["max_servers"]:
                await ctx.send(f"⚠️ You have reached the maximum number of servers for your plan ({premium_limits['max_servers']}). "
                              f"Upgrade to add more servers or remove an existing server.")
                return
            
            # Create new server
            server = await Server.create(db,
                name=name,
                ip=ip,
                port=port,
                log_path=log_path,
                guild_id=ctx.guild.id,
                access_method=access_method
            )
            
            # If it's SFTP, we'll need to follow up for credentials
            if access_method == "sftp":
                await ctx.send("Server added! Since you selected SFTP access, please set up credentials using:\n"
                              f"`!server credentials {name} <username> [password] [key_path]`")
            else:
                await ctx.send(f"✅ Server '{name}' added successfully! Use `!server info {name}` to view details.")
                
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="list")
    async def list_servers(self, ctx):
        """List all configured servers for this guild"""
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            if not servers:
                await ctx.send("No servers have been configured yet. Use `!server add` to add a server.")
                return
            
            embed = discord.Embed(
                title="Configured Deadside Servers",
                description=f"Found {len(servers)} servers",
                color=discord.Color.blue()
            )
            
            for server in servers:
                embed.add_field(
                    name=server.name,
                    value=f"IP: {server.ip}:{server.port}\n"
                          f"Access: {server.access_method}\n"
                          f"Added: {server.added_at.strftime('%Y-%m-%d')}",
                    inline=True
                )
            
            await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="info")
    async def server_info(self, ctx, *, name: str):
        """
        Show detailed information about a server
        
        Usage: !server info <name>
        """
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.send(f"⚠️ Server '{name}' not found. Use `!server list` to see all configured servers.")
                return
            
            # Get parser status
            parser_status = await ParserMemory.get_parser_status(server._id)
            
            embed = await create_server_embed(server, parser_status)
            await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def remove_server(self, ctx, *, name: str):
        """
        Remove a server from monitoring
        
        Usage: !server remove <name>
        """
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.send(f"⚠️ Server '{name}' not found. Use `!server list` to see all configured servers.")
                return
            
            # Confirm deletion
            confirm_msg = await ctx.send(f"Are you sure you want to remove server '{server.name}'? This will delete all parser state but NOT the collected statistics. React with ✅ to confirm.")
            await confirm_msg.add_reaction("✅")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) == "✅" and reaction.message.id == confirm_msg.id
            
            try:
                # Wait for confirmation reaction
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                # Delete server
                await server.delete(db)
                
                # Also clean up related parser states
                await db.get_collection("parser_state").delete_many({"server_id": server._id})
                
                await ctx.send(f"✅ Server '{server.name}' has been removed.")
                
            except TimeoutError:
                await ctx.send("Server removal cancelled.")
                
        except Exception as e:
            logger.error(f"Error removing server: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="update")
    @commands.has_permissions(manage_guild=True)
    async def update_server(self, ctx, name: str, setting: str, *, value: str):
        """
        Update server settings
        
        Usage: !server update <name> <setting> <value>
        
        Settings:
          name: New server name
          ip: Server IP address
          port: Server port
          log_path: Path to log files
          csv_enabled: Enable CSV parsing (true/false)
          log_enabled: Enable log parsing (true/false)
        
        Example:
          !server update "My Server" name "New Server Name"
          !server update "My Server" log_enabled false
        """
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.send(f"⚠️ Server '{name}' not found. Use `!server list` to see all configured servers.")
                return
            
            # Update based on setting
            if setting.lower() == "name":
                server.name = value
            elif setting.lower() == "ip":
                server.ip = value
            elif setting.lower() == "port":
                try:
                    server.port = int(value)
                except ValueError:
                    await ctx.send("⚠️ Port must be a number.")
                    return
            elif setting.lower() == "log_path":
                server.log_path = value
            elif setting.lower() == "csv_enabled":
                server.csv_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            elif setting.lower() == "log_enabled":
                server.log_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            else:
                await ctx.send(f"⚠️ Unknown setting '{setting}'. Valid settings are: name, ip, port, log_path, csv_enabled, log_enabled")
                return
            
            # Save changes
            await server.update(db)
            await ctx.send(f"✅ Server '{server.name}' updated successfully.")
                
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="credentials")
    @commands.has_permissions(manage_guild=True)
    async def set_credentials(self, ctx, name: str, username: str, password: str = None, key_path: str = None):
        """
        Set SFTP credentials for a server (for SFTP access method)
        
        Usage: !server credentials <name> <username> [password] [key_path]
        
        Note: For security, this command will be deleted after processing.
        """
        # Try to delete the command message for security
        try:
            await ctx.message.delete()
        except:
            pass
        
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.send(f"⚠️ Server '{name}' not found. Use `!server list` to see all configured servers.")
                return
            
            if server.access_method != "sftp":
                await ctx.send(f"⚠️ Server '{name}' is not configured for SFTP access. Change the access method first.")
                return
            
            # Update credentials
            server.ssh_user = username
            server.ssh_password = password
            server.ssh_key_path = key_path
            
            # Save changes
            await server.update(db)
            await ctx.send(f"✅ SFTP credentials for server '{server.name}' updated successfully.")
                
        except Exception as e:
            logger.error(f"Error setting credentials: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @server.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def reset_parsers(self, ctx, *, name: str):
        """
        Reset parsers for a server (to re-read logs from beginning)
        
        Usage: !server reset <name>
        """
        try:
            db = await Database.get_instance()
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.send(f"⚠️ Server '{name}' not found. Use `!server list` to see all configured servers.")
                return
            
            # Reset all parsers
            modified_count = await ParserMemory.reset_all_parsers(server._id)
            
            await ctx.send(f"✅ Reset {modified_count} parsers for server '{server.name}'. The next parsing cycle will read logs from the beginning.")
                
        except Exception as e:
            logger.error(f"Error resetting parsers: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
