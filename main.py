import os
import discord
import asyncio
import logging
import json
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import traceback
import sys
import motor.motor_asyncio
from pathlib import Path
import time

# Import all cog classes to avoid circular imports
from cogs.admin_commands import AdminCommands
from cogs.server_commands_refactored import ServerCommands
from cogs.stats_commands_refactored import StatsCommands
from cogs.killfeed_commands_refactored import KillfeedCommands
from cogs.mission_commands_refactored import MissionCommands
from cogs.connection_commands import ConnectionCommands
from cogs.faction_commands import FactionCommands
from cogs.notification_cog import NotificationCog
from cogs.rivalry_commands import RivalryCommands
from cogs.analytics_cog import AnalyticsCog

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get variables from .env file
PREFIX = os.getenv("PREFIX", "!")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGODB_NAME = os.getenv("MONGODB_NAME", "deadside_bot")
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Import Flask app for Gunicorn
from app import app

# Helper function for individual command registration with rate limit handling
async def register_commands_individually(bot, commands_payload):
    """Register commands one by one with advanced rate limit handling and exponential backoff
    
    This improved version uses our command_fix utilities to ensure each command has the correct
    attribute formatting before registration.
    
    Returns:
        bool: True if at least half of the commands were registered successfully, False otherwise
    """
    # Preemptively fix command attributes with our utility
    try:
        from utils.command_fix import INTEGRATION_TYPE_GUILD, COMMAND_CONTEXT_GUILD
        logger.info("Using improved command registration with proper enum objects")
    except ImportError:
        logger.warning("Cannot import command_fix utilities, using raw integer values")
        # Create simple placeholder objects
        class PlaceholderEnum:
            def __init__(self, value):
                self.value = value
        INTEGRATION_TYPE_GUILD = PlaceholderEnum(1)
        COMMAND_CONTEXT_GUILD = PlaceholderEnum(2)
    import random
    from pathlib import Path
    import time
    import json
    
    logger = logging.getLogger('deadside_bot')
    logger.info(f"Attempting to register {len(commands_payload)} commands individually...")
    
    # Create a marker file to track the last full refresh
    last_refresh_file = Path(".last_command_refresh")
    start_time = time.time()
    
    # Create a rate limit state file to persist across restarts
    rate_limit_file = Path(".rate_limit_state.json")
    
    success_count = 0
    # Keep track of critical commands for success metric
    critical_commands = ["server", "stats", "missions", "ping", "commands", "faction", "killfeed", "connections"]
    critical_success = 0
    
    # Load any existing rate limit state
    global_rate_limit_reset = 0
    command_rate_limits = {}
    
    if rate_limit_file.exists():
        try:
            with open(rate_limit_file, "r") as f:
                rate_limit_data = json.load(f)
                global_rate_limit = rate_limit_data.get('global', 0)
                command_limits = rate_limit_data.get('commands', {})
                
                # Only use rate limits that are still in the future
                current_time = time.time()
                if global_rate_limit > current_time:
                    global_rate_limit_reset = global_rate_limit
                    logger.info(f"Loaded global rate limit reset time: {global_rate_limit_reset}")
                
                for cmd, reset_time in command_limits.items():
                    if reset_time > current_time:
                        command_rate_limits[cmd] = reset_time
                        logger.info(f"Loaded rate limit for '{cmd}': {reset_time}")
        except Exception as e:
            logger.error(f"Error loading rate limit data: {e}")
    
    # Organize commands by priority to ensure critical ones get registered first
    # Also deduplicate commands by name to avoid conflicts
    prioritized_payload = []
    command_names_seen = set()
    
    # First add all critical commands
    for cmd in commands_payload:
        cmd_name = cmd.get('name', '')
        if cmd_name in critical_commands and cmd_name not in command_names_seen:
            prioritized_payload.append(cmd)
            command_names_seen.add(cmd_name)
    
    # Then add all remaining commands
    for cmd in commands_payload:
        cmd_name = cmd.get('name', '')
        if cmd_name not in command_names_seen:
            prioritized_payload.append(cmd)
            command_names_seen.add(cmd_name)
    
    # Save a copy of the original description for each command
    # This helps detect if a command was modified during processing
    original_descriptions = {}
    for cmd in prioritized_payload:
        cmd_name = cmd.get('name', '')
        original_descriptions[cmd_name] = cmd.get('description', '')
    
    # Process commands with advanced rate limit handling
    for i, cmd in enumerate(prioritized_payload):
        cmd_name = cmd.get('name', f'Command {i}')
        is_critical = cmd_name in critical_commands
        
        # Double-check command integrity
        if not cmd.get('description'):
            logger.warning(f"Command {cmd_name} is missing a description! Adding generic description.")
            cmd['description'] = f"Command for {cmd_name} functionality"
        
        # Implement exponential backoff for retries
        max_retries = 5 if is_critical else 3
        base_delay = 2.0  # Increased from 1.0 to be more conservative
        
        # Check if we need to wait for global rate limit
        current_time = time.time()
        if global_rate_limit_reset > current_time:
            wait_time = global_rate_limit_reset - current_time + 1
            logger.warning(f"Waiting for global rate limit to reset ({wait_time:.2f}s)...")
            await asyncio.sleep(wait_time)
        
        # Check if this specific command has a rate limit
        if cmd_name in command_rate_limits and command_rate_limits[cmd_name] > current_time:
            wait_time = command_rate_limits[cmd_name] - current_time + 1
            logger.warning(f"Waiting for command-specific rate limit to reset for {cmd_name} ({wait_time:.2f}s)...")
            await asyncio.sleep(wait_time)
        
        success = False
        for retry in range(max_retries):
            if retry > 0:
                # Calculate exponential backoff with jitter
                backoff_delay = base_delay * (2 ** retry) + random.uniform(0, 2.0)  # Increased jitter
                logger.info(f"Retry {retry+1}/{max_retries} for {cmd_name} after {backoff_delay:.2f}s backoff...")
                await asyncio.sleep(backoff_delay)
            
            try:
                logger.info(f"Registering command {i+1}/{len(prioritized_payload)}: {cmd_name}")
                
                # Use named endpoint and format for more reliable tracking
                cmd_endpoint = f"/applications/{bot.application_id}/commands"
                logger.info(f"Using endpoint: {cmd_endpoint}")
                
                # Use raw HTTP request to have more control
                await bot.http.request(
                    'POST', 
                    cmd_endpoint,
                    json=cmd
                )
                
                logger.info(f"✅ Successfully registered command: {cmd_name}")
                success_count += 1
                if is_critical:
                    critical_success += 1
                
                # Mark success and update the timestamp
                success = True
                with open(last_refresh_file, "w") as f:
                    f.write(str(time.time()))
                
                # Break out of retry loop on success
                break
                
            except discord.errors.HTTPException as rate_err:
                if hasattr(rate_err, 'status'):
                    if rate_err.status == 429:
                        # If rate limited, extract details and wait accordingly
                        retry_after = getattr(rate_err, 'retry_after', 5)
                        is_global = False
                        
                        # Try to get more specific rate limit info if available
                        if hasattr(rate_err, 'response') and hasattr(rate_err.response, 'json'):
                            try:
                                error_data = await rate_err.response.json()
                                logger.info(f"Rate limit error data: {error_data}")
                                retry_after = error_data.get('retry_after', retry_after)
                                is_global = error_data.get('global', False)
                            except Exception as json_err:
                                logger.error(f"Error parsing rate limit response: {json_err}")
                        
                        # Add a safety margin to retry_after
                        retry_after = retry_after * 1.2  # Add 20% buffer
                        
                        if is_global:
                            # Update global rate limit
                            global_rate_limit_reset = time.time() + retry_after
                            logger.warning(f"Global rate limit hit! Waiting {retry_after:.2f}s before retrying any commands.")
                            
                            # Save global rate limit to file for persistence
                            try:
                                rate_limit_data = {
                                    'global': global_rate_limit_reset,
                                    'commands': {k: v for k, v in command_rate_limits.items() if v > time.time()}
                                }
                                with open(rate_limit_file, "w") as f:
                                    json.dump(rate_limit_data, f)
                            except Exception as e:
                                logger.error(f"Error saving rate limit data: {e}")
                        else:
                            # Update command-specific rate limit
                            command_rate_limits[cmd_name] = time.time() + retry_after
                            logger.warning(f"Rate limited for {cmd_name}. Waiting {retry_after:.2f}s")
                            
                            # Save command-specific rate limit to file
                            try:
                                rate_limit_data = {
                                    'global': global_rate_limit_reset if global_rate_limit_reset > time.time() else 0,
                                    'commands': {k: v for k, v in command_rate_limits.items() if v > time.time()}
                                }
                                with open(rate_limit_file, "w") as f:
                                    json.dump(rate_limit_data, f)
                            except Exception as e:
                                logger.error(f"Error saving rate limit data: {e}")
                        
                        # Add a bit of jitter to avoid slamming the API when many bots restart at once
                        await asyncio.sleep(retry_after + random.uniform(1.0, 3.0))
                        # Continue to next retry
                        continue
                    elif rate_err.status == 400:
                        # Bad request - might be an issue with command format
                        logger.error(f"Bad request error for {cmd_name}: {rate_err}")
                        if hasattr(rate_err, 'response') and hasattr(rate_err.response, 'json'):
                            try:
                                error_data = await rate_err.response.json()
                                logger.error(f"Error details: {error_data}")
                                
                                # Try to fix common issues
                                if 'description' in str(error_data):
                                    logger.warning(f"Description issue detected for {cmd_name}, fixing...")
                                    cmd['description'] = f"Command for {cmd_name} functionality"
                            except:
                                pass
                    else:
                        logger.error(f"HTTP error registering {cmd_name}: {rate_err.status} - {rate_err}")
                        if retry < max_retries - 1:
                            continue
                else:
                    logger.error(f"HTTP error registering {cmd_name} (no status): {rate_err}")
                    if retry < max_retries - 1:
                        continue
            except Exception as e:
                logger.error(f"Failed to register command {cmd_name}: {e}")
                if retry < max_retries - 1:
                    continue
        
        # If we didn't succeed after all retries
        if not success and is_critical:
            logger.error(f"⚠️ Failed to register critical command {cmd_name} after {max_retries} retries")
            
            # Try alternative approach as last resort for critical commands
            if is_critical:
                try:
                    logger.warning(f"Attempting alternative registration for critical command {cmd_name}...")
                    
                    # Simplify the command to basic structure
                    simplified_cmd = {
                        "name": cmd_name,
                        "description": f"Commands for {cmd_name} functionality",
                        "type": 1
                    }
                    
                    # Try direct registration
                    await bot.http.request(
                        'POST', 
                        f"/applications/{bot.application_id}/commands",
                        json=simplified_cmd
                    )
                    
                    logger.info(f"✅ Successfully registered simplified version of {cmd_name}")
                    success = True
                    success_count += 1
                    critical_success += 1
                except Exception as last_err:
                    logger.error(f"Last resort also failed for {cmd_name}: {last_err}")
        
        # Add progressive delay between commands to avoid rate limits
        delay = 2.0 + (i * 0.1)  # Increased delay between commands
        logger.info(f"Waiting {delay:.2f}s before next command...")
        await asyncio.sleep(delay)
        
        # Add a longer pause after groups of commands
        if (i + 1) % 3 == 0:
            pause = 8.0 + (i * 0.2)  # Longer pauses as we progress
            logger.info(f"Pausing for {pause:.2f}s after registering batch of commands...")
            await asyncio.sleep(pause)
    
    # Success metric: Either most commands registered, or all critical commands
    total_success = success_count >= len(prioritized_payload) / 2
    critical_success_rate = critical_success / len(critical_commands) if critical_commands else 1.0
    critical_success_bool = critical_success_rate >= 0.75  # At least 75% of critical commands
    overall_success = total_success or critical_success_bool
    
    # Set final timestamp
    with open(last_refresh_file, "w") as f:
        f.write(str(time.time()))
    
    # Log detailed stats
    elapsed_time = time.time() - start_time
    logger.info(f"Individual registration completed in {elapsed_time:.2f}s")
    logger.info(f"Results: {success_count}/{len(prioritized_payload)} commands registered ({success_count/len(prioritized_payload)*100:.1f}%)")
    logger.info(f"Critical commands: {critical_success}/{len(critical_commands)} ({critical_success_rate*100:.1f}%)")
    
    # Verify rate limit state before finishing
    try:
        current_time = time.time()
        # Clean up expired rate limits
        active_command_limits = {k: v for k, v in command_rate_limits.items() if v > current_time}
        
        if global_rate_limit_reset > current_time or active_command_limits:
            logger.warning("Rate limits still active at end of registration:")
            if global_rate_limit_reset > current_time:
                logger.warning(f"Global rate limit resets in {global_rate_limit_reset - current_time:.2f}s")
            
            for cmd, reset in active_command_limits.items():
                logger.warning(f"Command '{cmd}' rate limit resets in {reset - current_time:.2f}s")
            
            # Save final rate limit state
            rate_limit_data = {
                'global': global_rate_limit_reset if global_rate_limit_reset > current_time else 0,
                'commands': active_command_limits
            }
            with open(rate_limit_file, "w") as f:
                json.dump(rate_limit_data, f)
    except Exception as e:
        logger.error(f"Error handling final rate limit state: {e}")
    
    if overall_success:
        logger.info("✅ Registration considered successful enough to proceed")
    else:
        logger.warning("⚠️ Registration did not meet success criteria")
        
    return overall_success

# Set up logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOGGING_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/deadside_bot.log')
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

# Command to register all slash commands to Discord without clearing first
async def sync_slash_commands():
    """Register all slash commands to Discord with detailed error handling"""
    try:
        logger.info("📝 STARTING COMMAND REGISTRATION")
        
        # First, fix any issues with command objects using our command_fix utilities
        try:
            from utils.command_fix import patch_discord_internals, apply_command_fixes
            
            # Apply the monkey patch to Discord internals
            if patch_discord_internals():
                logger.info("✅ Successfully patched Discord.py internals for improved command handling")
            else:
                logger.warning("⚠️ Could not patch Discord.py internals, will rely on command-by-command fixes")
            
            # Apply fixes to all command groups in all cogs
            fixed_count = apply_command_fixes(bot)
            logger.info(f"🔧 Applied fixes to {fixed_count} command objects")
        except Exception as e:
            logger.error(f"❌ Error applying command fixes: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Check if we can use the enhanced sync_retry module
        try:
            from utils.sync_retry import safe_command_sync
            logger.info("Enhanced command sync available via sync_retry module")
            use_enhanced_sync = True
        except ImportError:
            logger.warning("Enhanced command sync not available, falling back to standard approach")
            use_enhanced_sync = False
        
        # Import all command groups to make sure they're available
        logger.info("Step 1: Importing all command groups")
        from cogs.server_commands_refactored import server_group 
        from cogs.connection_commands import connection_group
        from cogs.killfeed_commands_refactored import killfeed_group
        from cogs.mission_commands_refactored import mission_group
        from cogs.faction_commands import faction_group
        from cogs.stats_commands_refactored import stats_group
        
        # Register all command groups to the bot - without clearing existing ones first
        logger.info("Step 2: Registering all command groups to bot")
        command_groups = [
            (server_group, "server"),
            (connection_group, "connections"),
            (killfeed_group, "killfeed"),
            (mission_group, "missions"),
            (faction_group, "faction"),
            (stats_group, "stats")
        ]
        
        # First clear the duplicates that might be causing our issues
        logger.info("Removing any duplicate command registrations first")
        unique_names = set()
        kept_commands = []
        
        for cmd in bot.application_commands:
            if cmd.name not in unique_names:
                unique_names.add(cmd.name)
                kept_commands.append(cmd)
            else:
                logger.warning(f"Removing duplicate command: {cmd.name}")
        
        # Replace application_commands with deduplicated list
        # We can't modify bot.application_commands directly, so we'll clear and re-add
        bot.application_commands.clear()
        for cmd in kept_commands:
            bot.application_commands.append(cmd)
        
        # Register each command group directly to the application commandment tree
        for group, name in command_groups:
            try:
                # First, ensure the group has the correct name
                if hasattr(group, 'name') and group.name != name:
                    logger.warning(f"🔄 Correcting command group name from '{group.name}' to '{name}'")
                    group.name = name
                
                # Check if already registered
                existing = next((cmd for cmd in bot.application_commands if cmd.name == name), None)
                if not existing:
                    try:
                        # Add it directly to the bot's command list
                        bot.add_application_command(group)
                        # Verify it was added
                        if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                            logger.info(f"✅ Successfully registered {name} command group to bot")
                        else:
                            logger.error(f"❌ Failed to register {name} command group - not found after adding")
                            # Try alternative method
                            logger.info(f"Attempting alternative registration for {name}")
                            bot.application_commands.append(group)
                            # Verify again
                            if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                                logger.info(f"✅ Successfully registered {name} using alternative method")
                            else:
                                logger.error(f"❌ All methods failed to register {name}")
                    except Exception as add_err:
                        logger.error(f"Error adding {name} via main method: {add_err}")
                        # Try alternative method
                        try:
                            logger.info(f"Trying alternative registration for {name}")
                            bot.application_commands.append(group)
                            # Verify it worked
                            if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                                logger.info(f"✅ Successfully registered {name} using alternative method")
                            else:
                                logger.error(f"❌ Alternative method also failed for {name}")
                        except Exception as alt_err:
                            logger.error(f"Alternative method also failed: {alt_err}")
                else:
                    logger.info(f"⏩ {name} command group already registered (skipping)")
            except Exception as e:
                logger.error(f"❌ Failed to register {name} command group: {e}")
                # Try a more direct approach as last resort
                try:
                    bot.application_commands.append(group)
                    logger.info(f"✅ Last resort registration attempt for {name}")
                except Exception as e2:
                    logger.error(f"All registration methods failed for {name}: {e2}")
        
        # Add utility commands
        logger.info("Step 3: Adding utility commands")
        
        # Add ping command if needed
        try:
            ping_cmd = next((cmd for cmd in bot.application_commands if cmd.name == "ping"), None)
            if not ping_cmd:
                bot.add_application_command(ping)
                logger.info("✅ Added ping command")
            else:
                logger.info("⏩ ping command already registered (skipping)")
        except Exception as e:
            logger.error(f"Failed to add ping command: {e}")
            
        # Add commands command if needed
        try:
            commands_cmd = next((cmd for cmd in bot.application_commands if cmd.name == "commands"), None)
            if not commands_cmd:
                bot.add_application_command(commands_menu)
                logger.info("✅ Added commands menu command")
            else:
                logger.info("⏩ commands menu command already registered (skipping)")
        except Exception as e:
            logger.error(f"Failed to add commands menu command: {e}")
            
        # Log what we have registered locally before sync
        logger.info("Local command state before sync:")
        local_cmds = bot.application_commands
        logger.info(f"Bot has {len(local_cmds)} local commands registered")
        
        if local_cmds:
            cmd_names = [cmd.name for cmd in local_cmds]
            logger.info(f"Local commands: {', '.join(cmd_names)}")
            
            # Log group commands and their subcommands
            for cmd in local_cmds:
                if hasattr(cmd, 'subcommands') and cmd.subcommands:
                    subcmd_names = [subcmd.name for subcmd in cmd.subcommands]
                    logger.info(f"• '{cmd.name}' subcommands: {', '.join(subcmd_names)}")
                    
        # Double-check we have all our main command groups before sync
        key_commands = ["server", "stats", "connections", "killfeed", "missions", "faction", "ping", "commands"]
        missing = []
        
        for key in key_commands:
            if not next((cmd for cmd in bot.application_commands if cmd.name == key), None):
                missing.append(key)
                
        if missing:
            logger.warning(f"⚠️ Missing commands before sync: {', '.join(missing)}")
        else:
            logger.info("✅ All key commands are registered locally")
        
        # NEW APPROACH: Direct JSON registration to bypass duplicate issues
        logger.info("Step 6: Using direct API registration approach")
        logger.info("This will make all commands available in Discord via direct registration")
        
        # Prepare a complete list of commands to register in raw JSON format
        # This bypasses the local application_commands list and works directly with Discord's API
        logger.info("Preparing direct command registration payload")
        
        try:
            # Get the list of all existing global commands
            existing_cmds = await bot.http.get_global_commands(bot.application_id)
            existing_cmd_names = [cmd.get('name') for cmd in existing_cmds]
            logger.info(f"Current commands on Discord: {', '.join(existing_cmd_names)}")
            
            # Register missing commands directly via HTTP
            # For simplicity, we'll just use what bot.sync_commands() would use
            # But we'll check each command group to ensure it's registered
            
            # NEW APPROACH: Register commands one by one via direct JSON payload
            logger.info("Attempting to register command groups directly via Discord API")
            
            # First check what's currently registered
            registered_cmds = await bot.http.get_global_commands(bot.application_id)
            registered_cmd_names = [cmd.get('name') for cmd in registered_cmds]
            logger.info(f"Current commands on Discord: {', '.join(registered_cmd_names)}")
            
            # If we don't have stats, server and other key commands, clear all and start fresh
            key_command_count = sum(1 for cmd in key_commands if cmd in registered_cmd_names)
            
            # Determine if we need a full command refresh using a cooldown system
            from pathlib import Path
            import time
            
            # Create a marker file to track the last full refresh
            last_refresh_file = Path(".last_command_refresh")
            current_time = time.time()
            refresh_interval = 3600 * 6  # 6 hours in seconds
            
            # Check if we've done a full refresh recently
            needs_refresh = True
            if last_refresh_file.exists():
                try:
                    # Read the timestamp from file
                    with open(last_refresh_file, "r") as f:
                        last_refresh = float(f.read().strip())
                    
                    # Check if we're still within the cooldown period
                    time_since_refresh = current_time - last_refresh
                    if time_since_refresh < refresh_interval:
                        # Only refresh if we're missing critical commands
                        if key_command_count >= len(key_commands) - 1:  # Allow one missing command
                            logger.info(f"Last command refresh was {time_since_refresh:.2f}s ago (<{refresh_interval}s). Skipping refresh.")
                            needs_refresh = False
                        else:
                            logger.warning(f"Missing critical commands despite recent refresh ({time_since_refresh:.2f}s ago)")
                    else:
                        logger.info(f"Last command refresh was {time_since_refresh:.2f}s ago (>{refresh_interval}s). Time for a refresh.")
                except Exception as e:
                    logger.error(f"Error reading last refresh timestamp: {e}")
            else:
                logger.info("No previous command refresh data found. Performing initial refresh.")
            
            # Always use the nuclear option to ensure all commands are properly registered
            if needs_refresh:
                
                # Step 1: Clear all commands from Discord with retry logic
                try:
                    # This is the nuclear option - clear ALL commands
                    try:
                        await bot.http.bulk_upsert_global_commands(bot.application_id, [])
                        logger.info("✅ Successfully cleared all global commands")
                    except discord.errors.HTTPException as rate_err:
                        if hasattr(rate_err, 'status') and rate_err.status == 429:
                            # If rate limited, log and wait before continuing
                            retry_after = getattr(rate_err, 'retry_after', 10)
                            logger.warning(f"Rate limited when clearing commands. Waiting {retry_after + 2}s")
                            await asyncio.sleep(retry_after + 2)
                            # Try again after waiting
                            await bot.http.bulk_upsert_global_commands(bot.application_id, [])
                            logger.info("✅ Successfully cleared all global commands after rate limit wait")
                        else:
                            # Other HTTP error
                            raise rate_err
                    
                    # Wait longer for Discord to process
                    logger.info("Waiting for Discord to process command clearing...")
                    await asyncio.sleep(5)
                    
                    # Step 2: Register them all fresh using bulk registration
                    if use_enhanced_sync:
                        logger.info("Using enhanced bulk registration from sync_retry")
                        success = await safe_command_sync(bot, force=True)
                        if success:
                            logger.info("✅ Bulk command registration successful")
                            
                            # Save registration timestamp to prevent frequent re-registration
                            with open(last_refresh_file, "w") as f:
                                f.write(str(time.time()))
                            
                            # Skip the individual registration since we're using bulk
                            return True
                        else:
                            logger.warning("⚠️ Bulk command registration not fully successful")
                    
                    # Fallback to old method if bulk registration failed or isn't available
                    commands_payload = []
                    
                    # Build up the JSON for all the commands we want to register through the old method
                    # Register commands using the individual registration with rate limit handling
                    logger.info(f"Registering {len(commands_payload)} commands individually...")
                    registration_success = await register_commands_individually(bot, commands_payload)
                    
                    if registration_success:
                        logger.info("✅ Command registration completed successfully")
                        
                        # Save registration timestamp to prevent frequent re-registration
                        with open(last_refresh_file, "w") as f:
                            f.write(str(time.time()))
                    else:
                        logger.warning("⚠️ Command registration did not meet success criteria, but some commands may have registered")
                except Exception as e:
                    logger.error(f"Error during command registration: {e}")
            else:
                logger.info("Command registration skipped due to recent successful registration")
        except discord.errors.HTTPException as e:
            logger.error(f"HTTP error during command registration: {e}")
        except Exception as e:
            logger.error(f"General error during command registration: {e}")
    except Exception as e:
        logger.error(f"Error in command registration process: {e}")
        import traceback
        logger.error(traceback.format_exc())

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
    description="Interactive command guide with detailed information"
)
async def commands_menu(ctx):
    """Shows available commands and help information with emerald-themed styling"""
    # Get all registered commands
    all_commands = bot.application_commands
    
    # Create main embed with enhanced emerald-themed styling
    embed = discord.Embed(
        title="💎 Emerald PVP Survival Command Guide 💎",
        description="**Welcome to the Deadside Emerald Servers!**\n*These commands will help you survive, track your kills, and dominate the wasteland:*",
        color=0x50C878  # Emerald green color from COLORS["emerald"]
    )
    
    # Add commands by category
    server_commands = []
    stats_commands = []
    mission_commands = []
    faction_commands = []
    connection_commands = []
    killfeed_commands = []
    utility_commands = []
    
    # Group commands by category based on their names
    for cmd in all_commands:
        cmd_name = cmd.name.lower()
        
        if cmd_name == "server":
            server_commands.append(cmd)
        elif cmd_name == "stats":
            stats_commands.append(cmd)
        elif cmd_name == "missions":
            mission_commands.append(cmd)
        elif cmd_name == "faction":
            faction_commands.append(cmd)
        elif cmd_name == "connections":
            connection_commands.append(cmd)
        elif cmd_name == "killfeed":
            killfeed_commands.append(cmd)
        else:
            utility_commands.append(cmd)
    
    # Add fields for each category with improved descriptions and subcommand hints
    if server_commands:
        server_desc = (
            "**`/server add`** - Add a new game server to track\n"
            "**`/server list`** - View all configured servers\n"
            "**`/server info`** - Get detailed server status\n"
            "**`/server update`** - Modify server settings"
        )
        embed.add_field(
            name="🖥️ Server Management",
            value=server_desc,
            inline=False
        )
    
    if stats_commands:
        stats_desc = (
            "**`/stats player`** - View detailed player statistics\n"
            "**`/stats leaderboard`** - See the top players\n"
            "**`/stats weapons`** - Analyze weapon performance\n"
            "**`/stats link`** - Connect Discord to game identity"
        )
        embed.add_field(
            name="📊 Player Statistics",
            value=stats_desc,
            inline=False
        )
    
    if mission_commands:
        mission_desc = (
            "**`/missions track`** - Follow mission status\n"
            "**`/missions alerts`** - Set up mission notifications\n"
            "**`/missions history`** - View past mission results"
        )
        embed.add_field(
            name="🎯 Mission Tracking",
            value=mission_desc,
            inline=False
        )
    
    if faction_commands:
        faction_desc = (
            "**`/faction create`** - Start a new faction\n"
            "**`/faction join`** - Join an existing faction\n"
            "**`/faction leaderboard`** - View top factions\n"
            "**`/faction manage`** - Adjust faction settings"
        )
        embed.add_field(
            name="👥 Faction System",
            value=faction_desc,
            inline=False
        )
    
    if connection_commands:
        connection_desc = (
            "**`/connections track`** - Monitor server logins\n"
            "**`/connections alerts`** - Set up join/leave notifications\n"
            "**`/connections history`** - View player session logs"
        )
        embed.add_field(
            name="🔌 Connection Tracking",
            value=connection_desc,
            inline=False
        )
    
    if killfeed_commands:
        killfeed_desc = (
            "**`/killfeed channel`** - Set a channel for kill notifications\n"
            "**`/killfeed filter`** - Customize which kills to show\n"
            "**`/killfeed highlights`** - Configure special death alerts"
        )
        embed.add_field(
            name="💀 Killfeed",
            value=killfeed_desc,
            inline=False
        )
    
    # Add utilities with better formatting
    if utility_commands:
        utility_desc = "\n".join([f"**`/{cmd.name}`** - {cmd.description}" for cmd in utility_commands])
        embed.add_field(
            name="🛠️ Utility Commands",
            value=utility_desc,
            inline=False
        )
    
    # Add premium tier information with emerald styling
    embed.add_field(
        name="💎 Premium Tiers",
        value=(
            "**🪓 Survivor (Free):** Basic tracking, 1 server\n"
            "**🗡️ Warlord (Premium):** Factions, rivalries, 3 servers\n"
            "**👑 Overseer (Enterprise):** All features, 10 servers"
        ),
        inline=False
    )
    
    # Footer with styled tip and version info
    bot_version = getattr(bot, "version", "1.0.0")
    embed.set_footer(text=f"⚔️ Emerald Servers Bot v{bot_version} | Type /help [command] for detailed usage")
    
    # Add server count if applicable
    try:
        from database.connection import Database
        db = await Database.get_instance()
        servers_collection = await db.get_collection("servers")
        server_count = await servers_collection.count_documents({})
        
        if server_count > 0:
            embed.add_field(
                name="📡 Status", 
                value=f"Tracking {server_count} servers | Bot latency: {round(bot.latency * 1000)}ms",
                inline=False
            )
    except Exception as e:
        logger.error(f"Error getting server count: {e}")
    
    await ctx.respond(embed=embed)

# Import all cog classes for easier access
# Using refactored commands with proper slash command implementation
from cogs.server_commands_refactored import ServerCommands
from cogs.stats_commands_refactored import StatsCommands
from cogs.killfeed_commands_refactored import KillfeedCommands
from cogs.mission_commands_refactored import MissionCommands
from cogs.connection_commands import ConnectionCommands
from cogs.admin_commands import AdminCommands
from cogs.faction_commands import FactionCommands
from cogs.notification_cog import NotificationCog

# Import database connection
from database.connection import Database

# Store database instance at bot level
bot.db = None

@bot.event
async def on_ready():
    """Called when the bot is fully ready after connecting to Discord"""
    # Set bot version information
    bot.version = "1.5.0"
    
    logger.info(f'Bot logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Running py-cord v{discord.__version__}')
    logger.info(f'Bot version: {bot.version}')
    
    # Log what guilds (servers) the bot is in
    guild_count = len(bot.guilds)
    logger.info(f"Bot is in {guild_count} guilds")
    
    for guild in bot.guilds:
        logger.info(f"Guild: {guild.name} (ID: {guild.id})")
        logger.info(f"  - Member count: {guild.member_count}")
        if guild.owner_id:
            logger.info(f"  - Owner: {guild.owner_id}")
    
    if guild_count == 0:
        logger.warning("⚠️ Bot is not in any guilds! Guild-specific command registration will fail.")
        logger.warning("⚠️ Make sure you've invited the bot to at least one server.")
    
    # Connect to database and store at bot level for cogs to access
    max_retries = 3
    retry_count = 0
    db_connected = False
    
    while not db_connected and retry_count < max_retries:
        try:
            retry_count += 1
            
            # Get database instance
            from database.connection import Database
            db_instance = await Database.get_instance()
            
            # Test the connection with a simple query
            await db_instance.get_collection("guild_configs")
            
            # Store the validated instance
            bot.db = db_instance
            logger.info("Database connection established and validated")
            db_connected = True
        except Exception as e:
            logger.error(f"Database connection attempt {retry_count} failed: {e}")
            await asyncio.sleep(1)  # Short delay between retries
    
    if not db_connected:
        logger.critical("Failed to establish database connection after multiple attempts")
        return
    
    # Load cogs after database is established
    await load_cogs()
    
    # Check for home guild setting
    try:
        config_collection = await bot.db.get_collection("bot_config")
        home_guild_doc = await config_collection.find_one({"_id": "home_guild"})
        
        if home_guild_doc and "guild_id" in home_guild_doc:
            bot.home_guild_id = int(home_guild_doc["guild_id"])
            logger.info(f"Home guild ID set to: {bot.home_guild_id}")
        else:
            logger.warning("No home guild ID found")
    except Exception as e:
        logger.error(f"Error loading home guild: {e}")
    
    # Ensure mission command group has the correct name
    # This fixes the inconsistency between "mission" and "missions"
    try:
        from cogs.mission_commands_refactored import mission_group
        if hasattr(mission_group, 'name') and mission_group.name != "missions":
            logger.warning(f"Fixing mission group name from '{mission_group.name}' to 'missions'")
            mission_group.name = "missions"
    except ImportError:
        logger.warning("Could not import mission_group to check name")
    except Exception as e:
        logger.error(f"Error checking mission group name: {e}")
    
    # Use unified command sync approach with utils/sync_retry.py
    try:
        # First ensure all cog files have the proper get_commands() method
        # This will be handled by the cog_checks below
        
        # Initialize the sync_retry module first
        from utils.sync_retry import setup, safe_command_sync
        # Call setup to initialize the module with our bot instance
        await setup(bot)
        logger.info("Using enhanced command registration with sync_retry module")
        
        # Apply fixes to command groups for issues with integration_types
        try:
            from utils.command_fix import apply_command_fixes
            fixed_count = apply_command_fixes(bot)
            logger.info(f"Applied command fixes to {fixed_count} command groups")
        except Exception as fix_err:
            logger.error(f"Failed to apply command fixes: {fix_err}")
        
        # Check local command registration first
        all_current_commands = [cmd.name for cmd in bot.application_commands]
        desired_commands = ["server", "stats", "connections", "killfeed", "missions", "faction", "ping", "commands"]
        missing_commands = [cmd for cmd in desired_commands if cmd not in all_current_commands]
        
        if missing_commands:
            logger.warning(f"Missing {len(missing_commands)}/{len(desired_commands)} local commands: {', '.join(missing_commands)}")
        else:
            logger.info("All commands are registered locally")
        
        # Always force sync on startup to ensure all commands are registered
        # The sync_retry module will handle rate limits intelligently
        sync_result = await safe_command_sync(bot, force=True)
        
        if sync_result:
            logger.info("✅ Command sync completed successfully")
        else:
            logger.warning("⚠️ Command sync was not fully successful")
            logger.info("Commands will continue to be registered in the background")
    except Exception as e:
        logger.error(f"Error during command registration: {e}")
        logger.error("Continuing with bot startup despite command registration error")
    
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
        FactionCommands,
        NotificationCog,
        RivalryCommands,
        # Add the analytics cog for advanced statistics
        AnalyticsCog
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
        
        # Apply command fixes to fix null attributes and patch Discord internals if needed
        try:
            from utils.command_fix import apply_command_fixes, patch_discord_internals
            
            # First try to patch Discord internals for a more reliable fix
            if patch_discord_internals():
                logger.info("Successfully patched Discord internals for better command handling")
            else:
                logger.info("Could not patch Discord internals, will rely on command-by-command fixes")
            
            # Apply fixes to all command groups
            fixed_count = apply_command_fixes(bot)
            logger.info(f"Applied command fixes to {fixed_count} command groups")
        except Exception as e:
            logger.error(f"Error applying command fixes: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
                    if batch_memory.last_update_timestamp:
                        last_update = datetime.fromtimestamp(batch_memory.last_update_timestamp)
                        time_since_update = (datetime.now() - last_update).total_seconds()
                        
                        if time_since_update > 600:  # 10 minutes
                            logger.warning(f"Batch CSV parser for {server_name} appears to be stalled (no updates in {time_since_update:.1f}s)")
                            logger.warning(f"Resetting batch parser for {server_name}")
                            
                            # Reset the parser status
                            batch_memory.is_running = False
                            batch_memory.status = "Stalled - reset automatically"
                            batch_memory.progress = 0
                            batch_memory.last_update_timestamp = datetime.now().timestamp()
                            await batch_memory.save(bot.db)
            except Exception as e:
                logger.error(f"Error processing server {server.get('name', 'Unknown')}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"Error in parser check task: {e}")
        import traceback
        logger.error(traceback.format_exc())

@check_parsers.before_loop
async def before_check_parsers():
    """Wait until the bot is ready before starting the background task"""
    await bot.wait_until_ready()
    logger.info("Starting background parser task")
    
    # Also wait for database to be initialized
    while not bot.db:
        logger.warning("Waiting for database to be initialized before starting parser task")
        await asyncio.sleep(5)

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for command errors"""
    if isinstance(error, commands.CommandNotFound):
        # Don't respond to unknown commands
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        return
        
    if isinstance(error, commands.BotMissingPermissions):
        permissions = "\n".join(error.missing_permissions)
        await ctx.respond(f"I need the following permissions to run this command:\n{permissions}", ephemeral=True)
        return
        
    # If we get here, it's an unexpected error
    logger.error(f"Command error in {ctx.command}: {error}")
    logger.error(traceback.format_exc())
    
    # Notify the user that something went wrong
    try:
        await ctx.respond("An error occurred while processing your command. The bot owner has been notified.", ephemeral=True)
    except:
        # If we can't respond in the context, we'll just log it
        pass

# Main entry point
def main():
    """Main entry point for the bot"""
    # Check if token is provided
    if not DISCORD_TOKEN:
        logger.critical("No Discord token provided. Please set the DISCORD_TOKEN environment variable.")
        return
    
    try:
        # Run the bot
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("Invalid Discord token. Please check your token and try again.")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()