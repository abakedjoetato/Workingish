import os
import discord
import logging
import asyncio
from discord.ext import commands, tasks
from config import TOKEN, PREFIX, LOGGING_LEVEL
from database.connection import Database
from cogs.server_commands_slash import ServerCommands, server_group
from cogs.stats_commands import StatsCommands
from cogs.killfeed_commands import KillfeedCommands, killfeed_group
from cogs.connection_commands import ConnectionCommands, connection_group
from cogs.mission_commands import MissionCommands, mission_group
from cogs.admin_commands import AdminCommands
from cogs.faction_commands import FactionCommands, faction_group

# Import Flask app for Gunicorn
from app import app

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOGGING_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('deadside_bot')

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True  # Required for prefix commands to work properly
intents.members = True
intents.guilds = True

# Create bot with slash commands only (no prefix commands)
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX),  # Will be ignored as we're using slash commands only
    intents=intents,
    description="Deadside Game Server Monitoring Bot",
    sync_commands=False,  # We'll manually sync commands after loading all cogs
    sync_commands_debug=True,  # Enable debug output for command sync
)

# Global slash command sync to register application commands
async def sync_slash_commands():
    """Sync slash commands to Discord - call this after all cogs are loaded"""
    try:
        logger.info("Syncing slash commands...")
        # This syncs slash commands globally, making them available in all guilds
        await bot.sync_commands()
        logger.info("Slash commands synced successfully")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")

# Add slash commands for utility functions
@bot.slash_command(name="ping", description="Check bot's response time")
async def ping(ctx):
    """Check the bot's response time"""
    latency = round(bot.latency * 1000)
    await ctx.respond(f"Pong! 🏓 Response time: {latency}ms")

@bot.slash_command(name="help", description="Shows available commands")
async def help_command(ctx):
    """Shows available commands and help information"""
    embed = discord.Embed(
        title="Bot Commands",
        description="This bot uses slash commands. Type `/` to see all available commands.",
        color=0x5865F2
    )
    
    embed.add_field(
        name="Main Command Groups",
        value="- `/server` - Server management commands\n"
              "- `/stats` - Statistics commands\n"
              "- `/faction` - Faction management commands\n"
              "- `/killfeed` - Killfeed notification commands\n"
              "- `/connections` - Connection notification commands\n"
              "- `/missions` - Mission notification commands\n"
              "- `/admin` - Administrative commands",
        inline=False
    )
    
    embed.add_field(
        name="Utility Commands",
        value="- `/ping` - Check bot response time\n"
              "- `/help` - Show this help message",
        inline=False
    )
    
    embed.set_footer(text="For more information, check the README.md file")
    
    await ctx.respond(embed=embed)

# Store database instance at bot level
bot.db = None

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Running py-cord v{discord.__version__}')
    
    # Connect to database and store at bot level for cogs to access
    max_retries = 3
    retry_count = 0
    db_connected = False
    
    while not db_connected and retry_count < max_retries:
        try:
            retry_count += 1
            
            # Get database instance
            db_instance = await Database.get_instance()
            
            # Test the connection with a simple query
            await db_instance.get_collection("guild_configs")
            
            # Store the validated instance
            bot.db = db_instance
            logger.info("Database connection established and validated")
            db_connected = True
            
            # Validate home guild
            try:
                home_id = await bot.db.get_home_guild_id()
                if home_id:
                    logger.info(f"Home guild ID found: {home_id}")
                else:
                    logger.warning("No home guild ID found")
            except Exception as e:
                logger.warning(f"Home guild check failed: {e}")
                
        except Exception as e:
            logger.error(f"Database connection attempt {retry_count} failed: {e}")
            await asyncio.sleep(1)  # Short delay between retries
    
    if not db_connected:
        logger.critical("Failed to establish database connection after multiple attempts")
        return
    
    # Load cogs after database is established
    await load_cogs()
    
    # Manually add command groups
    try:
        # Add server command group
        bot.add_application_command(server_group)
        logger.info(f"Successfully registered server command group")
        
        # Add connection command group
        bot.add_application_command(connection_group)
        logger.info(f"Successfully registered connections command group")
        
        # Add killfeed command group
        bot.add_application_command(killfeed_group)
        logger.info(f"Successfully registered killfeed command group")
        
        # Add mission command group
        bot.add_application_command(mission_group)
        logger.info(f"Successfully registered mission command group")
        
        # Add faction command group
        bot.add_application_command(faction_group)
        logger.info(f"Successfully registered faction command group")
    except Exception as e:
        logger.error(f"Failed to register command groups: {e}")
    
    # Sync slash commands with Discord - MUST happen after cogs are loaded
    await sync_slash_commands()
    
    # Log all registered commands from application_commands 
    # application_commands is the property that contains slash commands
    all_commands = bot.application_commands
    command_count = len(all_commands)
    command_names = [f"{cmd.name}" for cmd in all_commands]
    
    # Debug: Check for SlashCommandGroups in application_commands
    for cmd in all_commands:
        logger.info(f"Command: {cmd.name}, Type: {type(cmd).__name__}")
        # If it's a group, log all subcommands
        if hasattr(cmd, 'subcommands'):
            subcmd_names = [f"{subcmd.name}" for subcmd in cmd.subcommands]
            if subcmd_names:
                logger.info(f" - Subcommands for {cmd.name}: {', '.join(subcmd_names)}")
    
    logger.info(f"Bot is fully ready with {command_count} registered commands")
    if command_count > 0:
        logger.info(f"Available commands: {', '.join(command_names)}")
    
    # Start background tasks
    check_parsers.start()
    
    # Set bot activity
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Deadside Servers | /server"
        )
    )

async def load_cogs():
    """Load all cogs for the bot"""
    # Don't attempt to load cogs if database isn't initialized
    if not bot.db:
        logger.error("Cannot load cogs - database not initialized")
        return
        
    # First, unload any previously loaded cogs to avoid duplicates
    for cog_name in list(bot.cogs.keys()):
        try:
            logger.debug(f"Unloading existing cog: {cog_name}")
            bot.remove_cog(cog_name)
        except Exception as e:
            logger.error(f"Error unloading cog {cog_name}: {e}")
    
    # Define the cog classes to load
    cog_classes = [
        ServerCommands,
        StatsCommands,
        KillfeedCommands,
        ConnectionCommands,
        MissionCommands,
        AdminCommands,
        FactionCommands
    ]
    
    loaded_count = 0
    for cog_class in cog_classes:
        try:
            # Use the safest initialization approach
            cog_name = cog_class.__name__
            
            # Check if cog is already loaded (should be removed above, but just in case)
            if cog_name in bot.cogs:
                logger.warning(f"Cog {cog_name} is already loaded, skipping")
                continue
                
            # More verbose logging to better identify where the issue is
            logger.debug(f"Creating cog instance for {cog_name}")
            
            # Create the cog instance
            cog = cog_class(bot)
            
            if cog is None:
                logger.error(f"Failed to create instance of {cog_name} - constructor returned None")
                continue
                
            # Explicitly set the database reference
            if hasattr(cog, 'db'):
                cog.db = bot.db
                logger.debug(f"Set database for {cog_name}")
                
            # Add a debug log right before adding the cog
            logger.debug(f"About to add cog {cog_name} to bot")
            
            # Add the cog to the bot using synchronous version to avoid NoneType issues
            try:
                # First, try synchronous method which seems more reliable
                bot.add_cog(cog)
                logger.info(f"Successfully loaded cog: {cog_name}")
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing cog {cog_class.__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    if loaded_count > 0:
        logger.info(f"Successfully loaded {loaded_count}/{len(cog_classes)} cogs")
    else:
        logger.error("No cogs were loaded successfully")

@tasks.loop(minutes=5)
async def check_parsers():
    """
    Background task to check and run parsers for all servers.
    
    This function runs every 5 minutes and manages three different parsers:
    
    1. Auto CSV Parser:
       - Downloads only the newest CSV file from each server
       - Processes only new content since the last run
       - Updates player stats and killfeed as it goes
       - Controlled by the csv_enabled server setting
       
    2. Log Parser:
       - Downloads and parses Deadside.log for server events
       - Extracts information about missions, server starts/stops, etc.
       - Only processes new log entries since the last run
       - Controlled by the log_enabled server setting
       
    3. Batch CSV Parser:
       - Only runs when explicitly triggered (not on this schedule)
       - Processes all historical CSV files with progress tracking
       - Reports status and progress through ParserMemory
       - Triggered by adding a new server or using the reset command
       - This function only monitors for stalled batch parsers
    """
    if not bot.db:
        logger.error("Cannot run parsers - database not initialized")
        return
        
    try:
        # Use the bot's database instance
        servers_collection = await bot.db.get_collection("servers")
        cursor = servers_collection.find({})
        
        # We need to convert _id to a string if it exists
        servers = []
        async for server in cursor:
            if "_id" in server and server["_id"] is not None:
                server["_id"] = str(server["_id"])
            elif "id" in server and server["id"] is not None:
                server["_id"] = str(server["id"])
            servers.append(server)
        
        server_count = len(servers)
        if server_count > 0:
            logger.info(f"Checking parsers for {server_count} servers")
        else:
            logger.info("No servers found for parsing")
        
        for server in servers:
            try:
                # Import parsers here to avoid circular imports
                from parsers.csv_parser import CSVParser
                from parsers.log_parser import LogParser
                from parsers.batch_csv_parser import BatchCSVParser
                from utils.log_access import get_log_file, get_newest_csv_file
                from database.models import ParserState, ParserMemory
                from datetime import datetime
                
                server_id = server.get("_id")
                server_name = server.get("name", "Unknown Server")
                
                # Check if auto CSV parsing is enabled
                if server.get("csv_enabled", True):
                    # Get parser state to check if auto parsing is enabled
                    parser_state = await ParserState.get_or_create(
                        bot.db, 
                        server_id, 
                        "csv", 
                        False
                    )
                    
                    # Only run auto parser if enabled
                    if parser_state.auto_parsing_enabled:
                        # Use newest CSV file for auto parser
                        newest_csv = await get_newest_csv_file(server)
                        if newest_csv:
                            # Create and run auto CSV parser
                            csv_parser = CSVParser(server_id)
                            await csv_parser.parse_newest_csv(server)
                            logger.debug(f"Auto-parsed newest CSV logs for server {server_name}")
                
                # Check if log parsing is enabled
                if server.get("log_enabled", True):
                    log_path = await get_log_file(server, "log")
                    if log_path:
                        log_parser = LogParser(server_id)
                        await log_parser.parse_file(log_path)
                        logger.debug(f"Parsed deadside.log for server {server_name}")
                
                # Check if batch CSV parser is currently running
                batch_memory = await ParserMemory.get_or_create(
                    bot.db, 
                    server_id, 
                    "batch_csv"
                )
                
                if batch_memory.is_running:
                    logger.debug(f"Batch CSV parser already running for server {server_name}, status: {batch_memory.status}")
                    
                    # If it's been more than 10 minutes since the last update, reset its status
                    if batch_memory.updated_at:
                        time_diff = datetime.utcnow() - batch_memory.updated_at
                        if time_diff.total_seconds() > 600:  # 10 minutes timeout
                            logger.warning(f"Batch CSV parser for server {server_name} seems to be stuck, resetting status")
                            batch_memory.is_running = False
                            batch_memory.status = "Stalled - reset required"
                            await batch_memory.update(bot.db)
                
            except Exception as e:
                logger.error(f"Error running parsers for server {server.get('name', 'Unknown')}: {e}")
    
    except Exception as e:
        logger.error(f"Error in check_parsers task: {e}")

@check_parsers.before_loop
async def before_check_parsers():
    """Wait until the bot is ready before starting the background task"""
    await bot.wait_until_ready()

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"⚠️ Bad argument: {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f"⚠️ You don't have the required permissions to use this command.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(f"⚠️ I don't have the required permissions to execute this command.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⚠️ This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
    else:
        logger.error(f"Unhandled command error: {error}")
        await ctx.send(f"⚠️ An error occurred: {error}")

def main():
    """Main entry point for the bot"""
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
