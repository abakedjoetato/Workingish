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

# Helper functions for command handling
async def safe_defer(ctx):
    """Safely defer a context response with error handling"""
    if ctx is None:
        logger.error("Context is None in safe_defer")
        return False
        
    try:
        await ctx.defer()
        return True
    except Exception as e:
        logger.error(f"Error deferring response: {e}")
        return False
        
async def safe_send(ctx, content=None, embed=None, followup=True):
    """Safely send a message with fallback to channel send if followup fails"""
    if ctx is None:
        logger.error("Context is None in safe_send")
        return None
        
    try:
        if followup:
            return await ctx.followup.send(content=content, embed=embed)
        else:
            return await ctx.respond(content=content, embed=embed)
    except Exception as e:
        logger.error(f"Error sending followup response: {e}")
        # Fallback to channel send if possible
        try:
            if ctx.channel:
                return await ctx.channel.send(content=content, embed=embed)
        except Exception as e2:
            logger.error(f"Error sending fallback message: {e2}")
        return None

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
    
    @server_group.command(
        name="add", 
        description="Add a new server to monitor",
        options=[
            discord.Option(
                name="name",
                description="A name for the server",
                type=str,
                required=True
            ),
            discord.Option(
                name="host",
                description="Server host/IP address",
                type=str,
                required=True
            ),
            discord.Option(
                name="port",
                description="Server port",
                type=int,
                required=True
            ),
            discord.Option(
                name="server_id",
                description="Server ID (used in log directory structure)",
                type=str,
                required=True
            ),
            discord.Option(
                name="username",
                description="Login username (SFTP/SSH)",
                type=str,
                required=True
            ),
            discord.Option(
                name="password",
                description="Login password (SFTP/SSH)",
                type=str,
                required=True
            )
        ]
    )
    async def add_server(self, ctx,
                       name: str,
                       host: str,
                       port: int,
                       server_id: str,
                       username: str,
                       password: str):
        """Add a new server to monitor"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in add_server command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in add_server")
        
        try:
            # Always fetch the database instance directly from the bot, not from self
            # This fixes the 'ApplicationContext' has no attribute 'db' error
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in add_server command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
            
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in add_server command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
            
            # Check for duplicate server names 
            existing_servers = await Server.get_by_guild(db, ctx.guild.id)
            for existing in existing_servers:
                if existing.name.lower() == name.lower():
                    await safe_send(ctx, f"⚠️ A server with the name '{name}' already exists. Please use a different name.")
                    return
            
            # Check if we have reached server limit
            guild_config = await GuildConfig.get_or_create(db, ctx.guild.id)
            
            # Import premium tier info
            from utils.premium import get_premium_limits
            premium_limits = await get_premium_limits(guild_config.premium_tier)
            
            if len(existing_servers) >= premium_limits["max_servers"]:
                await safe_send(ctx, f"⚠️ You have reached the maximum number of servers for your plan ({premium_limits['max_servers']}). "
                                f"Upgrade to add more servers or remove an existing server.")
                return
            
            # Derive the root log path based on the provided info
            # The first directory is always {ip}_{ServerID}
            root_log_path = f"{host}_{server_id}"
            
            # Create new server
            server = await Server.create(db,
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
            auto_parser_state = await ParserState.get_or_create(db, server._id, "csv", False)
            auto_parser_state.auto_parsing_enabled = False
            await auto_parser_state.update(db)
            
            # Send initial response
            initial_embed = discord.Embed(
                title="✅ Server Added Successfully",
                description=f"Server '{name}' has been configured with the following settings:",
                color=discord.Color.green()
            )
            
            initial_embed.add_field(name="Connection Details", value=
                f"• Host: `{host}`\n"
                f"• Port: `{port}`\n"
                f"• Server ID: `{server_id}`\n"
                f"• Username: `{username}`\n"
                f"• Password: `{'•' * 8}`\n"
                f"• Log Path: `{root_log_path}`"
            )
            
            initial_embed.add_field(name="Next Steps", value=
                f"1. The system will connect to `{host}` via SFTP\n"
                f"2. Navigate to the `{root_log_path}` directory\n"
                f"3. Search for and process Deadside log files\n"
                f"4. Historical batch processing will begin shortly"
            )
            
            initial_message = await safe_send(ctx, embed=initial_embed)
            if not initial_message:
                # If we couldn't send the message, try via channel
                try:
                    if ctx.channel:
                        initial_message = await ctx.channel.send(embed=initial_embed)
                except Exception as e2:
                    logger.error(f"Failed to send add confirmation via channel: {e2}")
                    # Continue anyway since we've already created the server
            
            # Create progress embed
            progress_memory = await ParserMemory.get_or_create(db, server._id, "batch_csv")
            progress_memory.status = "Initializing (starts in 30 seconds)"
            progress_memory.start_time = datetime.utcnow()
            await progress_memory.update(db)
            
            # Only try to edit if we got a message response
            if initial_message:
                progress_embed = await create_batch_progress_embed(server.name, progress_memory)
                try:
                    await initial_message.edit(embed=progress_embed)
                except Exception as edit_error:
                    logger.error(f"Error updating message with progress embed: {edit_error}")
                    # Continue anyway, the important part is the server was created
            
            # Schedule the batch parser to run after 30 seconds
            async def run_batch_parser():
                try:
                    from parsers.batch_csv_parser import BatchCSVParser
                    
                    # Wait 30 seconds before starting
                    await asyncio.sleep(30)
                    
                    # Safety check to ensure we have a valid message to update
                    if not initial_message:
                        logger.warning("No initial message available for batch parser, progress updates will be limited")
                    
                    # Initialize batch parser with message to update (if we have one)
                    batch_parser = BatchCSVParser(
                        server_id=server._id,
                        server_name=server.name,
                        channel=ctx.channel,
                        guild_id=ctx.guild.id,
                        message=initial_message
                    )
                    
                    # Start batch parsing
                    await batch_parser.parse_batch(server)
                    
                    # Re-enable auto parsing after batch processing completes
                    db = self.bot.db  # Get fresh DB reference
                    if db:
                        auto_parser_state = await ParserState.get_or_create(db, server._id, "csv", False)
                        auto_parser_state.auto_parsing_enabled = True
                        await auto_parser_state.update(db)
                        logger.info(f"Re-enabled auto parsing for server {server.name} after batch processing")
                    else:
                        logger.error("Database not available in batch parser callback")
                    
                    logger.info(f"Batch processing completed for server {server.name}")
                    
                    # Send final message if we couldn't update progress messages
                    if not initial_message and ctx.channel:
                        try:
                            complete_embed = discord.Embed(
                                title="✅ Historical Processing Complete",
                                description=f"Finished processing historical data for '{server.name}'.",
                                color=discord.Color.green()
                            )
                            await ctx.channel.send(embed=complete_embed)
                        except Exception as e2:
                            logger.error(f"Failed to send completion message: {e2}")
                            
                except Exception as e:
                    logger.error(f"Error in batch processing for server {server.name}: {e}")
                    try:
                        if ctx.channel:
                            error_embed = discord.Embed(
                                title="⚠️ Batch Processing Error",
                                description=f"An error occurred during processing for server '{server.name}':\n```{str(e)}```",
                                color=discord.Color.red()
                            )
                            await ctx.channel.send(embed=error_embed)
                    except Exception as e2:
                        logger.error(f"Failed to send error message: {e2}")
            
            # Run batch parser in the background
            self.bot.loop.create_task(run_batch_parser())
            logger.info(f"Scheduled batch parser for server {server.name} (id: {server._id})")
                
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="list", description="List all configured servers for this guild")
    async def list_servers(self, ctx):
        """List all configured servers for this guild"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in list_servers command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in list_servers")
            
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in list_servers command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
            
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in list_servers command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
            
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            if not servers:
                await safe_send(ctx, "No servers have been configured yet. Use `/server add` to add a server.")
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
            
            await safe_send(ctx, embed=embed)
                
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="info", description="Show detailed information about a server")
    async def server_info(self, ctx, 
                        name: discord.Option(str, "Name of the server to show information about", required=True)):
        """Show detailed information about a server"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in server_info command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in server_info")
        
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in server_info command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
            
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in server_info command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
                
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await safe_send(ctx, f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Get parser status
            parser_status = await ParserMemory.get_parser_status(db, server._id)
            
            embed = await create_server_embed(server, parser_status)
            await safe_send(ctx, embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="remove", description="Remove a server from monitoring")
    async def remove_server(self, ctx, 
                          name: discord.Option(str, "Name of the server to remove", required=True)):
        """Remove a server from monitoring"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in remove_server command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in remove_server")
        
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in remove_server command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
                
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in remove_server command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
                
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await safe_send(ctx, f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
                
            # Confirm deletion
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Server Removal",
                description=f"Are you sure you want to remove the server '{server.name}'?\n"
                           f"This will delete all parser states and configuration for this server.",
                color=discord.Color.red()
            )
            await safe_send(ctx, embed=confirm_embed)
            
            # Run server deletion in background task to avoid timeout
            async def delete_server_task():
                try:
                    await asyncio.sleep(3)  # Give user a chance to see the confirmation
                    
                    # Delete server
                    await server.delete(db)
                    
                    # Also clean up related parser states
                    parser_collection = await db.get_collection("parser_state")
                    delete_result = await parser_collection.delete_many({"server_id": server._id})
                    
                    # Clean up parser memory
                    memory_collection = await db.get_collection("parser_memory")
                    memory_result = await memory_collection.delete_many({"server_id": server._id})
                    
                    success_embed = discord.Embed(
                        title="✅ Server Removed",
                        description=f"Server '{server.name}' has been removed successfully.\n"
                                   f"Cleaned up {delete_result.deleted_count} parser states and "
                                   f"{memory_result.deleted_count} parser memory records.",
                        color=discord.Color.green()
                    )
                    
                    # Try to send using ctx.channel first, fallback to direct channel access
                    try:
                        if ctx.channel:
                            await ctx.channel.send(embed=success_embed)
                    except Exception as e2:
                        logger.error(f"Error sending removal completion: {e2}")
                        # We've tried our best, no other fallbacks available
                except Exception as e:
                    logger.error(f"Error in delete_server_task: {e}")
                    # Try to send using ctx.channel
                    try:
                        if ctx.channel:
                            await ctx.channel.send(f"⚠️ An error occurred while removing server: {e}")
                    except Exception as e2:
                        logger.error(f"Error sending error message: {e2}")
            
            # Start the background task
            self.bot.loop.create_task(delete_server_task())
                
        except Exception as e:
            logger.error(f"Error removing server: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")
    
    @server_group.command(name="update", description="Update server settings")
    async def update_server(self, ctx, 
                          name: discord.Option(str, "Name of the server to update", required=True),
                          setting: discord.Option(str, "Setting to update", 
                                               choices=["name", "ip", "port", "server_id", "username", "password", "csv_enabled", "log_enabled"], 
                                               required=True),
                          value: discord.Option(str, "New value for the setting", required=True)):
        """Update server settings"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in update_server command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in update_server")
        
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in update_server command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
                
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in update_server command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
                
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await safe_send(ctx, f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
            
            # Initialize old_value for safety
            old_value = "unknown"
            
            # Update based on setting
            if setting.lower() == "name":
                old_value = server.name
                server.name = value
            elif setting.lower() == "ip":
                old_value = server.ip
                server.ip = value
                # Update the log path to follow the {ip}_{server_id} pattern
                if server.server_id:
                    server.log_path = f"{value}_{server.server_id}"
            elif setting.lower() == "port":
                old_value = str(server.port)
                try:
                    server.port = int(value)
                except ValueError:
                    await safe_send(ctx, "⚠️ Port must be a number.")
                    return
            elif setting.lower() == "server_id":
                old_value = server.server_id
                server.server_id = value
                # Update the log path to follow the {ip}_{server_id} pattern
                server.log_path = f"{server.ip}_{value}"
            elif setting.lower() == "username":
                old_value = server.ssh_user
                server.ssh_user = value
            elif setting.lower() == "password":
                old_value = "********"  # Don't show actual password
                server.ssh_password = value
            elif setting.lower() == "csv_enabled":
                old_value = "enabled" if server.csv_enabled else "disabled"
                server.csv_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            elif setting.lower() == "log_enabled":
                old_value = "enabled" if server.log_enabled else "disabled"
                server.log_enabled = value.lower() in ["true", "yes", "1", "enable", "enabled"]
            
            # First send acknowledgment
            await safe_send(ctx, f"Updating server '{server.name}'...\nChanging {setting} from '{old_value}' to '{value}'")
            
            # Save changes in background task
            async def update_server_task():
                try:
                    await server.update(db)
                    
                    success_embed = discord.Embed(
                        title="✅ Server Updated",
                        description=f"Server '{server.name}' updated successfully.",
                        color=discord.Color.green()
                    )
                    success_embed.add_field(
                        name="Setting Updated",
                        value=f"`{setting}`: `{old_value}` → `{value}`"
                    )
                    
                    # Try to send using ctx.channel first, fallback to direct channel access
                    try:
                        if ctx.channel:
                            await ctx.channel.send(embed=success_embed)
                    except Exception as e2:
                        logger.error(f"Error sending update completion: {e2}")
                        # We've tried our best, no other fallbacks available
                except Exception as e:
                    logger.error(f"Error in update_server_task: {e}")
                    # Try to send using ctx.channel
                    try:
                        if ctx.channel:
                            await ctx.channel.send(f"⚠️ An error occurred while updating server: {e}")
                    except Exception as e2:
                        logger.error(f"Error sending error message: {e2}")
            
            # Start the background task
            self.bot.loop.create_task(update_server_task())
                
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")
    

    
    @server_group.command(name="status", description="Check if a server is online and get player count")
    async def server_status(self, ctx,
                         name: discord.Option(str, "Server name to check (leave empty for all servers)", required=False) = None):
        """Check if a server is online and display current player count"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in server_status command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in server_status")
        
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in server_status command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
                
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in server_status command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
            
            # Get servers for the current guild
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            if not servers:
                await safe_send(ctx, "⚠️ No servers configured for this Discord server. Use `/server add` to add one.")
                return
            
            # Filter by name if provided
            if name:
                server = next((s for s in servers if s.name.lower() == name.lower()), None)
                if not server:
                    await safe_send(ctx, f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                    return
                
                servers = [server]
            
            # Create a status embed
            embed = discord.Embed(
                title="🎮 Server Status",
                description="Current game server status and player counts",
                color=0x00FF00
            )
            
            from utils.game_query import query_game_server
            
            status_tasks = []
            for server in servers:
                status_tasks.append(query_game_server(server.host, server.port))
            
            # Wait for all status checks to complete
            statuses = await asyncio.gather(*status_tasks, return_exceptions=True)
            
            # Add each server to the embed
            for i, server in enumerate(servers):
                status = statuses[i]
                
                if isinstance(status, Exception):
                    # Query failed
                    embed.add_field(
                        name=f"{server.name}",
                        value="⛔ Offline or unreachable",
                        inline=False
                    )
                else:
                    # Query succeeded
                    player_count = status.get("player_count", 0)
                    max_players = status.get("max_players", 0)
                    server_name = status.get("name", "Unknown")
                    
                    embed.add_field(
                        name=f"{server.name}",
                        value=f"✅ Online - {player_count}/{max_players} players\n*{server_name}*",
                        inline=False
                    )
            
            embed.set_footer(text="Last updated just now")
            await safe_send(ctx, embed=embed)
                
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")

    @server_group.command(name="reset", description="Reset parsers for a server")
    async def reset_parsers(self, ctx, 
                          name: discord.Option(str, "Name of the server to reset parsers for", required=True)):
        """Reset parsers for a server (to re-read logs from beginning)"""
        # Check if context is None and handle it gracefully
        if ctx is None:
            logger.error("Context is None in reset_parsers command")
            return
            
        # Send immediate acknowledgment to avoid timeout
        if not await safe_defer(ctx):
            # If defer fails, we should still try to continue
            logger.warning("Failed to defer response in reset_parsers")
        
        try:
            # Always fetch the database instance directly from the bot
            if not hasattr(self.bot, 'db') or not self.bot.db:
                logger.error("Bot database instance not available in reset_parsers command")
                await safe_send(ctx, "⚠️ Database connection not available. Please try again later.")
                return
                
            # Verify ctx.guild is not None (fix for NoneType error)
            if not ctx.guild:
                logger.error(f"Guild context is None in reset_parsers command")
                await safe_send(ctx, "⚠️ Cannot determine which Discord server you're in. Please try again later.")
                return
                
            # Use the bot's db instance directly
            db = self.bot.db
                
            servers = await Server.get_by_guild(db, ctx.guild.id)
            
            # Find server by name
            server = next((s for s in servers if s.name.lower() == name.lower()), None)
            
            if not server:
                await safe_send(ctx, f"⚠️ Server '{name}' not found. Use `/server list` to see all configured servers.")
                return
                
            # Confirm reset with warning about data processing
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Parser Reset",
                description=f"Are you sure you want to reset parsers for server '{server.name}'?\n\n"
                           f"This will cause the next parsing cycle to re-read logs from the beginning, "
                           f"which may result in duplicate data processing. The killfeed will be prevented "
                           f"from showing duplicate messages.",
                color=discord.Color.orange()
            )
            await safe_send(ctx, embed=confirm_embed)
            
            # Run parser reset in background task
            async def reset_parsers_task():
                try:
                    await asyncio.sleep(3)  # Give user time to see the confirmation
                    
                    # Reset all parsers
                    modified_count = await ParserMemory.reset_all_parsers(db, server._id)
                    
                    # Start the batch parser for historical processing
                    from parsers.batch_csv_parser import BatchCSVParser
                    
                    # Create progress memory
                    progress_memory = await ParserMemory.get_or_create(db, server._id, "batch_csv")
                    progress_memory.status = "Initializing batch processing"
                    progress_memory.start_time = datetime.utcnow()
                    await progress_memory.update(db)
                    
                    # Send update message
                    status_embed = discord.Embed(
                        title="✅ Parsers Reset",
                        description=f"Reset {modified_count} parsers for server '{server.name}'.\n\n"
                                  f"Starting historical data processing in the background.",
                        color=discord.Color.green()
                    )
                    
                    # Try to send using ctx.channel first, with fallback handling
                    try:
                        if ctx and ctx.channel:
                            message = await ctx.channel.send(embed=status_embed)
                            
                            # Initialize batch parser with message to update
                            batch_parser = BatchCSVParser(
                                server_id=server._id,
                                server_name=server.name,
                                channel=ctx.channel,
                                guild_id=ctx.guild.id,
                                message=message
                            )
                            
                            # Disable auto-parsing while batch processing runs
                            auto_parser_state = await ParserState.get_or_create(db, server._id, "csv", False)
                            auto_parser_state.auto_parsing_enabled = False
                            await auto_parser_state.update(db)
                            
                            # Start batch parsing
                            await batch_parser.parse_batch(server)
                            
                            # Re-enable auto parsing after batch processing completes
                            auto_parser_state = await ParserState.get_or_create(db, server._id, "csv", False)
                            auto_parser_state.auto_parsing_enabled = True
                            await auto_parser_state.update(db)
                            
                            logger.info(f"Batch processing after reset completed for server {server.name}")
                        else:
                            logger.error("Unable to start batch processing - context or channel is None")
                    except Exception as e2:
                        logger.error(f"Error sending reset completion and starting batch process: {e2}")
                        # We still want to try to enable auto-parsing
                        try:
                            auto_parser_state = await ParserState.get_or_create(db, server._id, "csv", False)
                            auto_parser_state.auto_parsing_enabled = True
                            await auto_parser_state.update(db)
                        except Exception as e3:
                            logger.error(f"Error enabling auto-parsing in fallback: {e3}")
                    
                except Exception as e:
                    logger.error(f"Error in reset_parsers_task: {e}")
                    # Try to send using ctx.channel
                    try:
                        if ctx and ctx.channel:
                            await ctx.channel.send(f"⚠️ An error occurred during parser reset: {e}")
                    except Exception as e2:
                        logger.error(f"Error sending error message: {e2}")
            
            # Start the background task
            self.bot.loop.create_task(reset_parsers_task())
                
        except Exception as e:
            logger.error(f"Error resetting parsers: {e}")
            await safe_send(ctx, f"⚠️ An error occurred: {e}")

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_application_command(server_group)
    bot.add_cog(ServerCommands(bot))
    return True