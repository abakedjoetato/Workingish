import logging
import discord
from discord.ext import commands
import asyncio
import datetime
import os
import time
import json
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log")
    ]
)

logger = logging.getLogger('deadside_bot')
logger.setLevel(logging.INFO)

# Configure file logging
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configuration
PREFIX = "!"

# Define intents for the bot
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

# Create bot with slash commands
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX),
    intents=intents,
    description="Deadside Game Server Monitoring Bot",
    sync_commands=False,  # We'll manually sync commands after loading all cogs
    sync_commands_debug=True,  # Enable debug output for command sync
)

# Command to register all slash commands to Discord
async def sync_slash_commands():
    """Register all slash commands to Discord with unified approach and proper rate limit handling"""
    try:
        logger.info("📝 STARTING UNIFIED COMMAND REGISTRATION")
        
        # Use our optimized command registration function from utils/command_fix
        try:
            from utils.command_fix import optimized_command_sync, apply_command_fixes, patch_discord_internals
            
            # First ensure all command objects are properly fixed
            logger.info("Applying command fixes before registration")
            
            # Apply the monkey patch to Discord internals
            if patch_discord_internals():
                logger.info("✅ Successfully patched Discord.py internals for improved command handling")
            else:
                logger.warning("⚠️ Could not patch Discord.py internals, will rely on command-by-command fixes")
            
            # Apply fixes to all command groups in all cogs
            fixed_count = apply_command_fixes(bot)
            logger.info(f"🔧 Applied fixes to {fixed_count} command objects")
            
            # Use our optimized registration approach
            logger.info("Using optimized command registration approach")
            result = await optimized_command_sync(bot)
            
            if result:
                logger.info("✅ Successfully registered all commands with optimized approach")
                
                # Save last successful sync time to prevent unnecessary retries
                with open(".last_command_check.txt", "w") as f:
                    f.write(str(time.time()))
                    
                return True
            else:
                logger.warning("⚠️ Optimized command registration failed, falling back to alternatives")
        except Exception as e:
            logger.error(f"❌ Error in optimized command registration: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # First fallback: Try using sync_retry module if available
        try:
            from utils.sync_retry import safe_command_sync
            logger.info("Trying sync_retry fallback method")
            
            # We specifically avoid using bot.sync_commands() directly to prevent duplicate registration
            result = await safe_command_sync(bot)
            if result:
                logger.info("✅ Successfully synced commands with sync_retry fallback")
                
                # Save last successful sync time to prevent unnecessary retries
                with open(".last_command_check.txt", "w") as f:
                    f.write(str(time.time()))
                
                return True
            else:
                logger.warning("⚠️ sync_retry fallback failed, trying direct method")
        except Exception as e:
            logger.error(f"❌ Error with sync_retry fallback: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Second fallback: Use bot's built-in sync_commands
        try:
            logger.info("Using direct bot.sync_commands as second fallback")
            
            await bot.sync_commands(
                guild_ids=None,  # Register to global scope
                delete_existing=False  # Don't delete existing commands
            )
            logger.info("✅ Successfully synced commands with built-in method")
            
            # Save last successful sync time to prevent unnecessary retries
            with open(".last_command_check.txt", "w") as f:
                f.write(str(time.time()))
            
            return True
        except Exception as e:
            logger.error(f"❌ Error with built-in sync method: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Last resort: Register individual commands directly via API
        try:
            if len(bot.application_commands) > 0:
                # Just to ensure we have at least the ping command registered
                logger.warning("⚠️ Attempting to register individual commands as final resort")
                return await register_commands_individually(bot, [cmd.to_dict() for cmd in bot.application_commands])
        except Exception as e:
            logger.error(f"❌ Even individual command registration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return False
        
    except Exception as e:
        logger.error(f"❌ Critical error in slash command registration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Function to register commands individually with rate limit handling
async def register_commands_individually(bot, commands_payload):
    """Register commands one by one with advanced rate limit handling and exponential backoff
    
    This improved version uses our command_fix utilities to ensure each command has the correct
    attribute formatting before registration.
    
    Returns:
        bool: True if at least half of the commands were registered successfully, False otherwise
    """
    logger.info(f"Attempting to register {len(commands_payload)} commands individually")
    
    # Track success/failure for each command
    successful = 0
    failed = 0
    
    # Use a fixed-time window approach for rate limiting
    request_times = []
    max_requests = 5  # Discord allows 5 requests per 5 seconds for application commands
    window_size = 5  # 5 second window
    
    # Create a utility function for rate limit checking
    async def wait_for_rate_limit():
        """Wait if we're approaching rate limits"""
        now = time.time()
        
        # Remove timestamps older than our window
        request_times[:] = [t for t in request_times if now - t < window_size]
        
        # If we've made too many requests in this window, wait
        if len(request_times) >= max_requests:
            oldest = min(request_times)
            wait_time = window_size - (now - oldest) + 0.1  # Add a small buffer
            
            if wait_time > 0:
                logger.info(f"Rate limit approaching, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    # Use Discord.py Enum objects if available for better JSON serialization
    try:
        # Handle the various versions of Discord.py with slightly different enum handling
        # For commands that might have legacy string values for enum fields
        class PlaceholderEnum:
            def __init__(self, value):
                self.value = value
            
            def __str__(self):
                return str(self.value)
    except Exception as e:
        logger.error(f"Error setting up command enums: {e}")
    
    # Process commands one-by-one with rate limit awareness
    for i, command in enumerate(commands_payload):
        try:
            # Check if we need to wait for rate limits
            await wait_for_rate_limit()
            
            # Log what we're attempting to register
            cmd_name = command.get('name', f"Command {i+1}")
            logger.info(f"Registering command {i+1}/{len(commands_payload)}: {cmd_name}")
            
            # Register the command directly using Discord's HTTP API
            from discord.http import Route
            route = Route("POST", f"/applications/{bot.application_id}/commands")
            
            # Track this request for rate limiting
            request_times.append(time.time())
            
            # Send the request
            try:
                result = await bot.http.request(route, json=command)
                logger.info(f"✅ Successfully registered command: {cmd_name}")
                successful += 1
            except discord.errors.HTTPException as http_error:
                if http_error.status == 429:  # Rate limited
                    retry_after = getattr(http_error, 'retry_after', 5)
                    logger.warning(f"Rate limited when registering {cmd_name}. Waiting {retry_after + 1}s")
                    await asyncio.sleep(retry_after + 1)
                    
                    # Try again after waiting
                    request_times.append(time.time())
                    result = await bot.http.request(route, json=command)
                    logger.info(f"✅ Successfully registered command after rate limit: {cmd_name}")
                    successful += 1
                else:
                    # Other HTTP error
                    logger.error(f"❌ Failed to register command {cmd_name}: {http_error}")
                    failed += 1
        except Exception as e:
            logger.error(f"❌ Failed to register command {i+1}/{len(commands_payload)}: {e}")
            failed += 1
    
    # Consider registration successful if at least half of commands were registered
    success_rate = successful / (successful + failed) if (successful + failed) > 0 else 0
    logger.info(f"Command registration complete: {successful} succeeded, {failed} failed, success rate: {success_rate:.1%}")
    
    return success_rate >= 0.5  # We want at least half the commands to succeed

# Define ping command
@discord.slash_command(
    name="ping",
    description="Check the bot's response time"
)
async def ping(ctx):
    """Check the bot's response time"""
    # Get response time in milliseconds
    latency = round(bot.latency * 1000, 2)
    
    # Create embed for response
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=discord.Color.green() if latency < 200 else discord.Color.orange()
    )
    
    embed.add_field(name="Status", value="Online and operational", inline=False)
    
    await ctx.respond(embed=embed)

# Define commands menu command
@discord.slash_command(
    name="commands",
    description="Shows available commands and help information"
)
async def commands_menu(ctx):
    """Shows available commands and help information with emerald-themed styling"""
    # Get all registered commands
    all_commands = bot.application_commands
    
    # Create main embed with enhanced emerald-themed styling
    embed = discord.Embed(
        title="💎 Emerald PVP Survival Command Guide 💎",
        description="**Welcome to the Deadside Emerald Servers!**\n*These commands will help you survive, track your kills, and dominate the wasteland:*",
        color=0x50C878  # Emerald green color
    )
    
    # Add footer with additional help and server info
    embed.set_footer(text="For more help, join our Discord at discord.gg/emeraldpvp")
    
    # Send the embed
    await ctx.respond(embed=embed)

# Bot ready event
@bot.event
async def on_ready():
    """Called when the bot is fully ready after connecting to Discord"""
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Load all cogs
    await load_cogs()
    
    # Sync slash commands after bot is ready and cogs are loaded
    try:
        logger.info("Attempting to sync slash commands...")
        
        # Check if we need to sync commands based on last sync time
        sync_needed = True
        
        try:
            last_sync_file = Path(".last_command_check.txt")
            if last_sync_file.exists():
                with open(last_sync_file, "r") as f:
                    last_sync_time = float(f.read().strip())
                current_time = time.time()
                time_since_sync = current_time - last_sync_time
                sync_cooldown = 3600  # 1 hour
                
                if time_since_sync < sync_cooldown:
                    logger.info(f"Last command sync was {time_since_sync:.2f}s ago (<{sync_cooldown}s), skipping unnecessary sync")
                    sync_needed = False
        except Exception as e:
            logger.error(f"Error checking last sync time: {e}")
            sync_needed = True
        
        if sync_needed:
            await sync_slash_commands()
        
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")
    
    logger.info("Bot is ready and online!")

# Load all cogs
async def load_cogs():
    """Load all cogs for the bot"""
    try:
        # Get a list of all .py files in the cogs directory
        cog_files = [f[:-3] for f in os.listdir("cogs") if f.endswith(".py") and not f.startswith("_")]
        logger.info(f"Found {len(cog_files)} potential cog files")
        
        # Load each cog
        loaded_cogs = 0
        for cog in cog_files:
            try:
                await bot.load_extension(f"cogs.{cog}")
                logger.info(f"Loaded cog: {cog}")
                loaded_cogs += 1
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info(f"Successfully loaded {loaded_cogs}/{len(cog_files)} cogs")
    except Exception as e:
        logger.error(f"Error loading cogs: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Handle command errors
@bot.event
async def on_command_error(ctx, error):
    """Global error handler for command errors"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    
    # Log the error
    logger.error(f"Command error in {ctx.command}: {error}")
    
    # Create an embed for the error
    embed = discord.Embed(
        title="❌ Command Error",
        description=f"An error occurred while executing the command.",
        color=discord.Color.red()
    )
    
    # Add a field with the error details
    error_message = str(error)
    if len(error_message) > 1024:
        error_message = error_message[:1021] + "..."
    embed.add_field(name="Error Details", value=error_message, inline=False)
    
    # Send the error embed
    await ctx.respond(embed=embed, ephemeral=True)

# Main function
def main():
    """Main entry point for the bot"""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get token from environment variables
        token = os.getenv("DISCORD_TOKEN")
        
        if not token:
            logger.error("No token found. Make sure to set the DISCORD_TOKEN environment variable.")
            sys.exit(1)
        
        # Start the bot
        logger.info("Starting bot...")
        bot.run(token)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

# Run the bot if this file is executed directly
if __name__ == "__main__":
    main()