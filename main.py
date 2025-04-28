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
        
        # Get the home guild ID if available for faster testing
        home_guild_id = None
        if bot.db:
            try:
                home_guild_id = await bot.db.get_home_guild_id()
            except:
                pass
                
        if home_guild_id:
            # Sync to home guild first for faster testing (less rate limiting)
            try:
                logger.info(f"Syncing commands to home guild {home_guild_id} first...")
                await bot.sync_commands(guild_ids=[home_guild_id])
                logger.info(f"Commands synced to home guild successfully")
            except Exception as e:
                logger.error(f"Error syncing commands to home guild: {e}")
        
        # This syncs slash commands globally, making them available in all guilds
        # This may take up to an hour to propagate due to Discord's caching
        logger.info("Syncing commands globally (this may be rate-limited by Discord)...")
        await bot.sync_commands()
        logger.info("Global slash commands sync request sent successfully")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")

# Add slash commands for utility functions
@bot.slash_command(name="ping", description="Check bot's response time")
async def ping(ctx):
    """Check the bot's response time"""
    latency = round(bot.latency * 1000)
    await ctx.respond(f"Pong! 🏓 Response time: {latency}ms")

@bot.slash_command(name="premium", description="View available features by premium tier")
async def premium_features(ctx):
    """Shows available features for different premium tiers"""
    # Import needed modules
    from utils.premium import get_premium_tiers
    from database.connection import Database
    
    # Get premium tiers
    tiers = await get_premium_tiers()
    
    # Create premium feature comparison embed with emerald theme
    embed = discord.Embed(
        title="💎 PREMIUM TIER COMPARISON",
        description="Available features at each tier",
        color=0x50C878  # Emerald green
    )
    
    # Group features into categories for better organization
    feature_categories = {
        "🔢 SERVER LIMITS": ["max_servers", "max_history_days"],
        "🔧 CORE FEATURES": ["basic_stats", "leaderboard", "killfeed", "connection_tracking", "mission_tracking", "player_linking"],
        "✨ ADVANCED FEATURES": ["advanced_stats", "historical_parsing", "custom_embeds", "csv_parsing", "log_parsing"],
        "⭐ PREMIUM FEATURES": ["faction_system", "rivalry_tracking"]
    }
    
    # Get database instance
    db = await Database.get_instance()
    
    # Display current tier if possible
    try:
        current_tier = await db.get_guild_premium_tier(ctx.guild.id)
        embed.add_field(
            name="YOUR CURRENT TIER",
            value=f"**{current_tier.title()}**",
            inline=False
        )
    except Exception as e:
        # If we can't get the tier, just continue without showing it
        pass
    
    # Add a comparison table for each feature category
    for category, features in feature_categories.items():
        # Build feature table for this category
        table = "```\n"
        table += f"{'FEATURE':<20} | {'SURVIVOR':<10} | {'WARLORD':<10} | {'OVERSEER':<10}\n"
        table += f"{'-' * 20} | {'-' * 10} | {'-' * 10} | {'-' * 10}\n"
        
        for feature in features:
            feature_name = feature.replace('_', ' ').title()
            feature_name = feature_name[:18] + ".." if len(feature_name) > 18 else feature_name
            
            # Get values for each tier
            survivor_val = _format_feature_value(tiers.get("survivor", {}).get(feature, "N/A"))
            warlord_val = _format_feature_value(tiers.get("warlord", {}).get(feature, "N/A"))
            overseer_val = _format_feature_value(tiers.get("overseer", {}).get(feature, "N/A"))
            
            table += f"{feature_name:<20} | {survivor_val:<10} | {warlord_val:<10} | {overseer_val:<10}\n"
        
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
        name="FEATURE DETAILS",
        value=desc_text,
        inline=False
    )
    
    # Set footer
    embed.set_footer(text="For more details, contact the bot maintainer")
    
    # Send the embed
    await ctx.respond(embed=embed)

def _format_feature_value(value):
    """Helper method to format feature values for the comparison table"""
    if isinstance(value, bool):
        return "✓" if value else "✗"
    elif value is None:
        return "∞"  # infinity symbol for unlimited
    else:
        return str(value)

@bot.slash_command(name="commands", description="Interactive command guide with detailed information")
async def commands_menu(ctx):
    """Shows available commands and help information with pagination"""
    # Import the command helper utilities
    from utils.command_helper import get_all_commands, CommandsView, COLORS
    
    # Gather all commands from the bot and organize them by category
    command_data = await get_all_commands(bot)
    
    # Create the initial embed
    embed = discord.Embed(
        title="💎 DEADSIDE COMMAND CENTER",
        description="Interactive command guide with detailed information.",
        color=COLORS["default"]  # Use emerald green from our theme
    )
    
    # If we successfully gathered command data
    if command_data:
        # Get the first category's information to show initially
        first_category = list(command_data.keys())[0]
        category_commands = command_data[first_category]
        
        # Add the first 5 commands (or fewer if there aren't that many)
        cmd_count = min(5, len(category_commands))
        for i in range(cmd_count):
            cmd = category_commands[i]
            name = cmd.get("name", "Unknown Command")
            description = cmd.get("description", "No description available")
            usage = cmd.get("usage", "")
            examples = cmd.get("examples", [])
            required_permissions = cmd.get("required_permissions", [])
            premium_tier = cmd.get("premium_tier", None)
            
            # Format the value with usage, examples, and requirements
            value = f"{description}\n\n"
            
            if usage:
                value += f"**Usage:** `{usage}`\n"
            
            if examples:
                examples_text = "\n".join([f"• `{ex}`" for ex in examples[:2]])
                value += f"**Examples:**\n{examples_text}\n"
            
            if required_permissions:
                perms = ", ".join(required_permissions)
                value += f"**Required Permissions:** {perms}\n"
            
            if premium_tier:
                value += f"**Premium Tier:** {premium_tier.capitalize()}\n"
            
            embed.add_field(
                name=name,
                value=value,
                inline=False
            )
    else:
        # Fallback if command gathering fails
        embed.add_field(
            name="Commands Not Available",
            value="Command information could not be loaded. Please try again later.",
            inline=False
        )
    
    # Set footer with usage instructions
    embed.set_footer(
        text="Use the dropdown to switch categories and buttons to navigate pages"
    )
    
    # Create the view with interactive components
    view = CommandsView(command_data, ctx.author.id)
    
    # Send the embed with the view
    await ctx.respond(embed=embed, view=view)

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
            name=f"Deadside Servers | /commands"
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
