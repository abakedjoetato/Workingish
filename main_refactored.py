import os
import discord
import asyncio
import logging
import sys
from discord.ext import commands, tasks
import traceback
import json
import motor.motor_asyncio
from datetime import datetime, timedelta
import importlib
import inspect
import copy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('deadside_bot')

# Create intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DeadsideBot(commands.Bot):
    """Main bot class with enhanced features for command handling and database connection"""
    
    def __init__(self):
        super().__init__(
            command_prefix="!",  # Fallback prefix, we primarily use slash commands
            intents=intents,
            enable_debug_events=True,
            auto_sync_commands=False  # We handle this manually for better control
        )
        
        # MongoDB connection
        self.db_client = None
        self.db = None
        
        # Module loading trackers
        self.loaded_extensions = set()
        self.loaded_cogs = set()
        
        # Status indicators
        self.is_ready = False
        self.last_command_sync = None
        
        # Register event handlers
        self.before_invoke(self.before_command)
        
    async def before_command(self, ctx):
        """Called before any command is executed"""
        logger.info(f"Command {ctx.command.name} executed by {ctx.author} ({ctx.author.id}) in guild {ctx.guild.name if ctx.guild else 'DM'} ({ctx.guild.id if ctx.guild else 'N/A'})")
    
    async def setup_hook(self):
        """Called when the bot is setting up"""
        logger.info("Bot is setting up")
        
        # Connect to MongoDB
        await self.setup_database()
        
        # Load extensions and cogs
        await self.load_all_extensions()
    
    async def setup_database(self):
        """Set up the database connection"""
        if not MONGODB_URI:
            logger.error("No MONGODB_URI environment variable found. Database functionality will be disabled.")
            return
            
        try:
            logger.info("Connecting to MongoDB...")
            self.db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
            self.db = self.db_client.deadside_bot
            
            # Ping the database to verify connection
            await self.db.command("ping")
            logger.info("Connected to MongoDB successfully")
            
            # Start database maintenance task
            self.db_maintenance_task.start()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.db_client = None
            self.db = None
    
    @tasks.loop(hours=24)
    async def db_maintenance_task(self):
        """Periodic database maintenance task"""
        if not self.db:
            return
            
        try:
            logger.info("Running database maintenance")
            
            # Expire old logs 
            logs_collection = await self.db.get_collection("logs")
            one_month_ago = datetime.utcnow() - timedelta(days=30)
            result = await logs_collection.delete_many({"timestamp": {"$lt": one_month_ago}})
            if result.deleted_count:
                logger.info(f"Deleted {result.deleted_count} old log entries")
                
        except Exception as e:
            logger.error(f"Error during database maintenance: {e}")
    
    @db_maintenance_task.before_loop
    async def before_db_maintenance(self):
        """Wait until the bot is ready before starting database maintenance"""
        await self.wait_until_ready()
    
    async def load_all_extensions(self):
        """Load all extensions/cogs"""
        # Load core extensions first
        core_extensions = [
            'utils.sync_retry'
        ]
        
        for extension in core_extensions:
            try:
                await self.load_extension(extension)
                self.loaded_extensions.add(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
                traceback.print_exc()
        
        # Load all cogs
        cogs = [
            'cogs.server_commands_refactored',
            'cogs.stats_commands_refactored',
            'cogs.mission_commands_refactored',
            'cogs.killfeed_commands_refactored',
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                self.loaded_cogs.add(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
                traceback.print_exc()
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Bot is ready. Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Set the bot as ready
        self.is_ready = True
        
        # Sync commands if needed
        try:
            # Import here to avoid circular imports
            from command_fix_implementation import safe_command_sync
            await safe_command_sync()
            logger.info("Commands synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
        
        # Set status
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for server statistics"
        ))
    
    async def on_application_command_error(self, ctx, error):
        """Handle errors from application commands"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.", ephemeral=True)
            return
            
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond("You don't have the required permissions to use this command.", ephemeral=True)
            return
            
        if isinstance(error, commands.errors.ApplicationCommandInvokeError):
            error = error.original
        
        # Log the error
        logger.error(f"Error in command {ctx.command.name if ctx.command else 'unknown'}: {str(error)}")
        logger.error("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        
        # Notify the user
        await ctx.respond(f"❌ An error occurred while executing the command: {str(error)}", ephemeral=True)
    
    async def on_error(self, event, *args, **kwargs):
        """Handle other errors"""
        logger.error(f"Error in event {event}: {sys.exc_info()[1]}")
        logger.error("".join(traceback.format_exception(*sys.exc_info())))

async def main():
    """Main entry point for the bot"""
    bot = DeadsideBot()
    
    if not DISCORD_TOKEN:
        logger.error("No DISCORD_TOKEN environment variable found")
        return
    
    try:
        logger.info("Starting bot...")
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.error("Invalid token provided")
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated")
        await bot.close()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())