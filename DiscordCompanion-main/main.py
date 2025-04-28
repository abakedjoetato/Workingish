import os
import discord
import logging
import asyncio
from discord.ext import commands, tasks
from config import TOKEN, PREFIX, LOGGING_LEVEL
from database.connection import Database
from cogs.server_commands import ServerCommands
from cogs.stats_commands import StatsCommands
from cogs.killfeed_commands import KillfeedCommands
from cogs.connection_commands import ConnectionCommands
from cogs.mission_commands import MissionCommands
from cogs.admin_commands import AdminCommands

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
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Running py-cord v{discord.__version__}')
    
    # Connect to database
    try:
        db = await Database.get_instance()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return
    
    # Load cogs
    await load_cogs()
    
    # Start background tasks
    check_parsers.start()
    
    # Set bot activity
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Deadside Servers | {PREFIX}help"
        )
    )
    
    logger.info("Bot is fully ready")

async def load_cogs():
    """Load all cogs for the bot"""
    cog_classes = [
        ServerCommands,
        StatsCommands,
        KillfeedCommands,
        ConnectionCommands,
        MissionCommands,
        AdminCommands
    ]
    
    for cog_class in cog_classes:
        try:
            # Initialize and add the cog
            cog = cog_class(bot)
            await bot.add_cog(cog)
            logger.info(f"Loaded cog: {cog_class.__name__}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog_class.__name__}: {e}")

@tasks.loop(minutes=5)
async def check_parsers():
    """Background task to check and run parsers for all servers"""
    try:
        db = await Database.get_instance()
        servers_collection = await db.get_collection("servers")
        cursor = await servers_collection.find({})
        
        # We need to convert _id to a string if it exists
        servers = []
        async for server in cursor:
            if "_id" in server and server["_id"] is not None:
                server["_id"] = str(server["_id"])
            elif "id" in server and server["id"] is not None:
                server["_id"] = str(server["id"])
            servers.append(server)
        
        for server in servers:
            try:
                # Import and run parsers here to avoid circular imports
                from parsers.csv_parser import CSVParser
                from parsers.log_parser import LogParser
                from utils.log_access import get_log_file
                
                server_id = server.get("_id")
                
                if server.get("csv_enabled", True):
                    csv_path = await get_log_file(server, "csv")
                    if csv_path:
                        csv_parser = CSVParser(server_id)
                        await csv_parser.parse_file(csv_path)
                        logger.debug(f"Parsed CSV logs for server {server.get('name')}")
                
                if server.get("log_enabled", True):
                    log_path = await get_log_file(server, "log")
                    if log_path:
                        log_parser = LogParser(server_id)
                        await log_parser.parse_file(log_path)
                        logger.debug(f"Parsed deadside.log for server {server.get('name')}")
                        
            except Exception as e:
                logger.error(f"Error parsing logs for server {server.get('name')}: {e}")
    
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
