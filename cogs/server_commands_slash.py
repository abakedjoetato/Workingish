import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime
from database.connection import Database
from database.models import Server, GuildConfig, ParserState, ParserMemory
from utils.embeds import create_server_embed, create_batch_progress_embed
from utils.guild_isolation import get_servers_for_guild, can_add_server
from utils.premium import check_premium_feature

logger = logging.getLogger('deadside_bot.cogs.server')

# Define the slash command group outside the class first
server_group = discord.SlashCommandGroup(
    name="server",
    description="Server management commands",
    default_member_permissions=discord.Permissions(manage_guild=True)
)

class ServerCommands(commands.Cog):
    """Commands for managing Deadside game servers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("ServerCommands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            logger.debug("Set database for ServerCommands cog from bot")
            
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [server_group]
    
    @server_group.command(name="add", description="Add a new server to monitor")
    async def add_server(self, ctx,
                       name: discord.Option(str, "A name for the server", required=True),
                       host: discord.Option(str, "Server host/IP address", required=True),
                       port: discord.Option(int, "Server port", required=True),
                       server_id: discord.Option(str, "Server ID (used in log directory structure)", required=True),
                       username: discord.Option(str, "Login username", required=True),
                       password: discord.Option(str, "Login password", required=True)):
        """Add a new server to monitor"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in add_server command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
            
            # Check if we have reached server limit
            guild_config = await GuildConfig.get_or_create(self.db, ctx.guild.id)
            existing_servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            # Import premium tier info
            from utils.premium import get_premium_limits
            premium_limits = await get_premium_limits(guild_config.premium_tier)
            
            if len(existing_servers) >= premium_limits["max_servers"]:
                await ctx.respond(f"⚠️ You have reached the maximum number of servers for your plan ({premium_limits['max_servers']}). "
                                f"Upgrade to add more servers or remove an existing server.")
                return
            
            # Derive the root log path based on the provided info
            # The first directory is always {ip}_{ServerID}
            root_log_path = f"{host}_{server_id}"
            
            # Create new server
            server = await Server.create(self.db,
                name=name,
                ip=host,
                port=port,
                server_id=server_id,
                log_path=root_log_path,
                guild_id=ctx.guild.id,
                access_method="sftp",
                ssh_user=username,
                ssh_password=password
            )
            
            # Disable auto-parsing initially while batch processing runs
            auto_parser_state = await ParserState.get_or_create(self.db, server._id, "csv", False)
            auto_parser_state.auto_parsing_enabled = False
            await auto_parser_state.update(self.db)
            
            # Send initial response
            initial_message = await ctx.respond(f"✅ Server '{name}' added successfully! When connecting via SFTP, the system will:\n"
                             f"1. Connect to {host} using the provided credentials\n"
                             f"2. Navigate to the `{root_log_path}` directory\n" 
                             f"3. Search for Deadside.log and killfeed.csv files\n\n"
                             f"Starting historical data processing... Please wait.")
            
            # Get the message to update later
            message = await initial_message.original_response()
            
            # Schedule delayed batch processing to allow connection testing first
            import asyncio
            
            # Create progress embed
            progress_memory = await ParserMemory.get_or_create(self.db, server._id, "batch_csv")
            progress_memory.status = "Initializing (starts in 30 seconds)"
            progress_memory.start_time = datetime.utcnow()
            await progress_memory.update(self.db)
            
            embed = await create_batch_progress_embed(server.name, progress_memory)
            await message.edit(content="", embed=embed)
            
            # Schedule the batch parser to run after 30 seconds
            async def run_batch_parser():
                try:
                    from parsers.batch_csv_parser import BatchCSVParser
                    
                    # Wait 30 seconds before starting
                    await asyncio.sleep(30)
                    
                    # Initialize batch parser with message to update
                    batch_parser = BatchCSVParser(
                        server_id=server._id,
                        server_name=server.name,
                        channel=ctx.channel,
                        guild_id=ctx.guild.id,
                        message=message
                    )
                    
                    # Start batch parsing
                    await batch_parser.parse_batch(server)
                    
                    # Re-enable auto parsing after batch processing completes
                    auto_parser_state = await ParserState.get_or_create(self.db, server._id, "csv", False)
                    auto_parser_state.auto_parsing_enabled = True
                    await auto_parser_state.update(self.db)
                    
                    logger.info(f"Batch processing completed for server {server.name}")
                except Exception as e:
                    logger.error(f"Error in batch processing for server {server.name}: {e}")
            
            # Run batch parser in the background
            self.bot.loop.create_task(run_batch_parser())
                
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="list", description="List all configured servers for this guild")
    async def list_servers(self, ctx):
        """List all configured servers for this guild"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in list_servers command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            if not servers:
                await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
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
                          f"Server ID: {server.server_id}\n"
                          f"Added: {server.added_at.strftime('%Y-%m-%d')}",
                    inline=True
                )
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="info", description="Show detailed information about a server")
    async def server_info(self, ctx, 
                        name: discord.Option(str, "Name of the server to show information about", required=True)):
        """Show detailed information about a server"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in server_info command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.respond(f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Get parser status
            parser_status = await ParserMemory.get_parser_status(self.db, server._id)
            
            embed = await create_server_embed(server, parser_status)
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="remove", description="Remove a server from monitoring")
    async def remove_server(self, ctx, 
                          name: discord.Option(str, "Name of the server to remove", required=True)):
        """Remove a server from monitoring"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in remove_server command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.respond(f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Delete server
            await server.delete(self.db)
            
            # Also clean up related parser states
            parser_collection = await self.db.get_collection("parser_state")
            await parser_collection.delete_many({"server_id": server._id})
            
            await ctx.respond(f"✅ Server '{server.name}' has been removed.")
                
        except Exception as e:
            logger.error(f"Error removing server: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="update", description="Update server settings")
    async def update_server(self, ctx, 
                          name: discord.Option(str, "Name of the server to update", required=True),
                          setting: discord.Option(str, "Setting to update", 
                                               choices=["name", "ip", "port", "server_id", "username", "password", "csv_enabled", "log_enabled"], 
                                               required=True),
                          value: discord.Option(str, "New value for the setting", required=True)):
        """Update server settings"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in update_server command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.respond(f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Update based on setting
            if setting.lower() == "name":
                server.name = value
            elif setting.lower() == "ip":
                server.ip = value
                # Update the log path to follow the {ip}_{server_id} pattern
                if server.server_id:
                    server.log_path = f"{value}_{server.server_id}"
            elif setting.lower() == "port":
                try:
                    server.port = int(value)
                except ValueError:
                    await ctx.respond("⚠️ Port must be a number.")
                    return
            elif setting.lower() == "server_id":
                server.server_id = value
                # Update the log path to follow the {ip}_{server_id} pattern
                server.log_path = f"{server.ip}_{value}"
            elif setting.lower() == "username":
                server.ssh_user = value
            elif setting.lower() == "password":
                server.ssh_password = value
            elif setting.lower() == "csv_enabled":
                server.csv_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            elif setting.lower() == "log_enabled":
                server.log_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            
            # Save changes
            await server.update(self.db)
            await ctx.respond(f"✅ Server '{server.name}' updated successfully.")
                
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    

    
    @server_group.command(name="reset", description="Reset parsers for a server")
    async def reset_parsers(self, ctx, 
                          name: discord.Option(str, "Name of the server to reset parsers for", required=True)):
        """Reset parsers for a server (to re-read logs from beginning)"""
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in reset_parsers command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            servers = await Server.get_by_guild(self.db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await ctx.respond(f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Reset all parsers
            modified_count = await ParserMemory.reset_all_parsers(self.db, server._id)
            
            await ctx.respond(f"✅ Reset {modified_count} parsers for server '{server.name}'. The next parsing cycle will read logs from the beginning.")
                
        except Exception as e:
            logger.error(f"Error resetting parsers: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_application_command(server_group)
    bot.add_cog(ServerCommands(bot))
    return True