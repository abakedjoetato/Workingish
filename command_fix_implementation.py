"""
Comprehensive Discord Bot Command System Fix

This script implements all the necessary fixes for the Discord bot's command registration system.
It can be run in standalone mode to manually force command registration.
"""

import os
import sys
import discord
import asyncio
import logging
import json
import time
import random
from dotenv import load_dotenv
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("command_fix")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.error("DISCORD_TOKEN not found in environment variables")
    sys.exit(1)

# Discord API endpoints
API_BASE = "https://discord.com/api/v10"
APPLICATION_ID = None  # Will be retrieved from API

# Files for tracking sync state
LAST_SYNC_FILE = ".last_command_sync"
RATE_LIMIT_FILE = ".discord_rate_limits.json"

# Critical commands that must be registered for basic functionality
CRITICAL_COMMANDS = [
    "server", "stats", "missions", "ping", "commands", 
    "faction", "killfeed", "connections"
]

# Helper function to get application ID
async def get_application_id():
    """Get the application ID using the bot token"""
    global APPLICATION_ID
    
    # If we already have an application ID, return it
    if APPLICATION_ID:
        return APPLICATION_ID
        
    # Create the Discord client
    from discord.http import HTTPClient
    http_client = HTTPClient()
    await http_client.static_login(TOKEN)
    
    # Get the application ID
    my_app = await http_client.application_info()
    APPLICATION_ID = my_app["id"]
    logger.info(f"Retrieved application ID: {APPLICATION_ID}")
    
    # Close the HTTP client
    await http_client.close()
    
    return APPLICATION_ID

async def load_rate_limits():
    """Load saved rate limit information"""
    rate_limit_file = Path(RATE_LIMIT_FILE)
    if not rate_limit_file.exists():
        return {'global': 0, 'endpoint': 0, 'buckets': {}, 'commands': {}}
        
    try:
        with open(rate_limit_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading rate limits: {e}")
        return {'global': 0, 'endpoint': 0, 'buckets': {}, 'commands': {}}

async def save_rate_limits(rate_limits):
    """Save rate limit information for future use"""
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(rate_limits, f)
    except Exception as e:
        logger.error(f"Error saving rate limits: {e}")

async def handle_rate_limit(error, command=None):
    """Handle a rate limit error by extracting info and saving state"""
    retry_after = getattr(error, 'retry_after', 60)
    is_global = False
    bucket = "unknown"
    
    # Try to get more specific rate limit info from headers or response
    if hasattr(error, 'response'):
        if hasattr(error.response, 'headers'):
            # Try to extract the X-RateLimit headers for more precision
            headers = error.response.headers
            retry_after_header = headers.get('Retry-After') or headers.get('retry-after')
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except (ValueError, TypeError):
                    pass
                    
            # Check for global flag in headers
            is_global_header = headers.get('X-RateLimit-Global') or headers.get('x-ratelimit-global')
            if is_global_header and is_global_header.lower() == 'true':
                is_global = True
                
            # Get bucket for more precise tracking
            bucket_header = headers.get('X-RateLimit-Bucket') or headers.get('x-ratelimit-bucket')
            if bucket_header:
                bucket = bucket_header
    
    # If the bucket is in the error message, extract it
    if hasattr(error, 'args') and error.args:
        error_msg = str(error.args[0])
        bucket_index = error_msg.find('bucket "')
        if bucket_index != -1:
            bucket_end = error_msg.find('"', bucket_index + 8)
            if bucket_end != -1:
                bucket = error_msg[bucket_index + 8:bucket_end]
    
    # Add a safety buffer (different for global vs endpoint)
    if is_global:
        retry_after = retry_after * 1.5 + 2  # Longer buffer for global rate limits
    else:
        retry_after = retry_after * 1.2 + 1  # Small buffer for endpoint rate limits
    
    # Save rate limit state
    rate_limits = await load_rate_limits()
    
    # Current time plus retry delay
    expiry_time = time.time() + retry_after
    
    if is_global:
        rate_limits['global'] = expiry_time
        logger.warning(f"Global rate limit hit! Retry after {retry_after:.2f}s (until {time.ctime(expiry_time)})")
    else:
        # Track both general endpoint and specific bucket
        rate_limits['endpoint'] = expiry_time
        
        if bucket != "unknown":
            if 'buckets' not in rate_limits:
                rate_limits['buckets'] = {}
            rate_limits['buckets'][bucket] = expiry_time
            
        # Track command-specific rate limit if provided
        if command:
            if 'commands' not in rate_limits:
                rate_limits['commands'] = {}
            rate_limits['commands'][command] = expiry_time
            
        logger.warning(f"Endpoint rate limit hit for bucket '{bucket}'! " +
                      f"Retry after {retry_after:.2f}s (until {time.ctime(expiry_time)})")
    
    await save_rate_limits(rate_limits)

async def register_commands_safely(commands_payload):
    """Register commands with careful rate limit handling"""
    # Get application ID
    application_id = await get_application_id()
    if not application_id:
        logger.error("Could not retrieve application ID. Exiting.")
        return False
    
    from discord.http import HTTPClient
    http_client = HTTPClient()
    await http_client.static_login(TOKEN)
    
    # Create a flag file to indicate we're in the process of registration
    in_progress_file = Path(".command_registration_in_progress")
    try:
        in_progress_file.touch()
    except Exception:
        pass
    
    success_count = 0
    critical_count = 0
    critical_total = sum(1 for cmd in commands_payload if cmd['name'] in CRITICAL_COMMANDS)
    
    # Prioritize critical commands first
    prioritized_commands = sorted(
        commands_payload, 
        key=lambda c: 0 if c['name'] in CRITICAL_COMMANDS else 1
    )
    
    # Load existing rate limit state
    rate_limits = await load_rate_limits()
    
    # Check for global rate limit first
    if rate_limits.get('global', 0) > time.time():
        wait_time = rate_limits['global'] - time.time() + 1  # Add 1s buffer
        if wait_time > 0:
            logger.warning(f"Waiting for global rate limit: {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
    
    # If endpoint is rate limited, wait it out first
    endpoint_limit = rate_limits.get('endpoint', 0)
    if endpoint_limit > time.time():
        wait_time = endpoint_limit - time.time() + 1  # Add 1s buffer
        if wait_time > 0:
            logger.warning(f"Waiting for endpoint rate limit: {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
    
    try:
        for i, cmd in enumerate(prioritized_commands):
            cmd_name = cmd['name']
            is_critical = cmd_name in CRITICAL_COMMANDS
            max_retries = 5 if is_critical else 3
            
            # Add progressively longer delays between commands
            # This prevents hitting rate limits as aggressively
            if i > 0:
                delay = 3 + random.uniform(0, 2) + (i * 0.5)  # Gradually increase delay
                logger.info(f"Waiting {delay:.2f}s before next command registration")
                await asyncio.sleep(delay)
            
            # Check if this specific command has a rate limit
            cmd_limit = rate_limits.get('commands', {}).get(cmd_name, 0)
            if cmd_limit > time.time():
                wait_time = cmd_limit - time.time() + 1  # Add 1s buffer
                if wait_time > 0:
                    logger.warning(f"Waiting for command-specific rate limit for {cmd_name}: {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            
            for retry in range(max_retries):
                if retry > 0:
                    # Exponential backoff with jitter
                    backoff = 2 * (2 ** retry) + random.uniform(0, 5)
                    logger.info(f"Retry {retry+1}/{max_retries} for {cmd_name} after {backoff:.2f}s")
                    await asyncio.sleep(backoff)
                
                try:
                    logger.info(f"Registering command: {cmd_name}")
                    await http_client.upsert_global_command(application_id, cmd)
                    logger.info(f"✅ Successfully registered {cmd_name}")
                    success_count += 1
                    if is_critical:
                        critical_count += 1
                    
                    # After successful registration, add a pause to be safe
                    await asyncio.sleep(1.5)
                    break
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        retry_after = getattr(e, 'retry_after', 5)
                        logger.warning(f"Rate limited when registering {cmd_name}, retry after {retry_after}s")
                        
                        # Update rate limit info
                        await handle_rate_limit(e, cmd_name)
                        
                        # Wait a bit longer than suggested plus jitter
                        actual_wait = retry_after * 1.2 + random.uniform(0, 2)
                        logger.info(f"Waiting {actual_wait:.2f}s for rate limit to reset")
                        await asyncio.sleep(actual_wait)
                        
                        # If on last retry and it's critical, we'll try one more time with longer wait
                        if retry == max_retries - 1 and is_critical:
                            logger.warning(f"Last retry for critical command {cmd_name}, waiting longer")
                            await asyncio.sleep(10)  # Extra long wait for critical commands
                            try:
                                await http_client.upsert_global_command(application_id, cmd)
                                logger.info(f"✅ Successfully registered {cmd_name} on final attempt")
                                success_count += 1
                                critical_count += 1
                                await asyncio.sleep(2)  # Add a pause after success
                            except Exception as final_e:
                                logger.error(f"Final attempt to register {cmd_name} failed: {final_e}")
                    else:
                        logger.error(f"HTTP error registering {cmd_name}: {e}")
                        if retry == max_retries - 1 and is_critical:
                            logger.warning(f"Command {cmd_name} is critical, adding extra retry")
                            await asyncio.sleep(5)
                            try:
                                await http_client.upsert_global_command(application_id, cmd)
                                logger.info(f"✅ Successfully registered {cmd_name} on emergency retry")
                                success_count += 1
                                critical_count += 1
                            except Exception as emergency_e:
                                logger.error(f"Emergency retry for {cmd_name} failed: {emergency_e}")
                except Exception as e:
                    logger.error(f"Error registering {cmd_name}: {e}")
    finally:
        # Clean up in-progress marker
        if in_progress_file.exists():
            try:
                in_progress_file.unlink()
            except Exception:
                pass
        
        # Close HTTP client
        await http_client.close()
    
    # Verify if we registered enough commands
    if critical_total > 0:
        critical_success_rate = critical_count / critical_total
        logger.info(f"Critical command success rate: {critical_success_rate:.2f}")
        
        # Update the last sync timestamp on success
        if critical_success_rate >= 0.5:  # Lower threshold to 50% for critical commands
            # Update the timestamp file
            try:
                with open(LAST_SYNC_FILE, 'w') as f:
                    f.write(str(time.time()))
                logger.info("Updated sync timestamp")
            except Exception as e:
                logger.error(f"Error updating sync timestamp: {e}")
            return True
    
    # If no critical commands, consider overall success rate
    if len(commands_payload) > 0:
        success_rate = success_count / len(commands_payload)
        logger.info(f"Overall command success rate: {success_rate:.2f}")
        return success_rate >= 0.5
    
    return True

def generate_minimal_commands():
    """Generate minimal command structures for critical functionality"""
    commands = []
    
    # Add ping command
    commands.append({
        "name": "ping",
        "description": "Check the bot's response time",
        "type": 1
    })
    
    # Add commands menu
    commands.append({
        "name": "commands",
        "description": "Interactive command guide with detailed information",
        "type": 1
    })
    
    # Add stats command
    commands.append({
        "name": "stats",
        "description": "View player and server statistics",
        "type": 1
    })
    
    # Add server commands
    commands.append({
        "name": "server",
        "description": "Manage game server connections and settings",
        "type": 1
    })
    
    # Add killfeed commands
    commands.append({
        "name": "killfeed",
        "description": "Configure and view killfeed notifications",
        "type": 1
    })
    
    # Add connections commands
    commands.append({
        "name": "connections",
        "description": "Configure and view player connection notifications",
        "type": 1
    })
    
    # Add missions commands
    commands.append({
        "name": "missions",
        "description": "Configure and view server mission notifications",
        "type": 1
    })
    
    # Add faction commands
    commands.append({
        "name": "faction",
        "description": "Manage player factions and alliances",
        "type": 1
    })
    
    return commands

async def is_recent_sync():
    """Check if we've successfully synced commands recently"""
    sync_file = Path(LAST_SYNC_FILE)
    if not sync_file.exists():
        return False
        
    try:
        with open(sync_file, 'r') as f:
            last_sync = float(f.read().strip())
            
        time_since = time.time() - last_sync
        # Minimum time between full command resyncs (12 hours in seconds)
        min_resync_interval = 3600 * 12  
        
        if time_since < min_resync_interval:
            logger.info(f"Last sync was {time_since:.2f}s ago (< {min_resync_interval}s)")
            return True
    except Exception as e:
        logger.error(f"Error checking last sync: {e}")
        
    return False

async def safe_command_sync(force=False):
    """
    Safely synchronize commands with advanced rate limit handling
        
    Args:
        force: Force a full sync even if recent
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    # Check if we've done a full sync recently
    if not force and await is_recent_sync():
        logger.info("Recent command sync detected, skipping to prevent rate limits")
        return True
    
    # Step 1: Check current state
    try:
        # Get application ID
        application_id = await get_application_id()
        if not application_id:
            logger.error("Could not retrieve application ID. Exiting.")
            return False
            
        # Create Discord HTTP client
        from discord.http import HTTPClient
        http_client = HTTPClient()
        await http_client.static_login(TOKEN)
        
        # Get current commands
        try:
            existing = await http_client.get_global_commands(application_id)
            existing_names = [cmd.get('name') for cmd in existing]
            missing = [cmd for cmd in CRITICAL_COMMANDS if cmd not in existing_names]
            
            if not missing:
                logger.info("All critical commands already registered")
                # Update the timestamp file
                try:
                    with open(LAST_SYNC_FILE, 'w') as f:
                        f.write(str(time.time()))
                    logger.info("Updated sync timestamp")
                except Exception as e:
                    logger.error(f"Error updating sync timestamp: {e}")
                await http_client.close()
                return True
                
            logger.warning(f"Missing critical commands: {', '.join(missing)}")
        except discord.errors.HTTPException as e:
            if e.status == 429:
                logger.error(f"Rate limited while checking commands: {e}")
                await handle_rate_limit(e)
                await http_client.close()
                return False
            logger.error(f"Error checking current commands: {e}")
            await http_client.close()
            return False
        finally:
            # Always close HTTP client
            await http_client.close()
    except Exception as e:
        logger.error(f"Error during command check: {e}")
        return False
    
    # Step 2: Attempt limited command updates if possible
    rate_limits = await load_rate_limits()
    global_limit = rate_limits.get('global', 0)
    
    if global_limit > time.time():
        wait_time = global_limit - time.time()
        logger.warning(f"Global rate limit active for {wait_time:.2f}s, deferring sync")
        return False
    
    # Generate command payloads
    try:
        payloads = generate_minimal_commands()
        
        # Only include missing commands
        filtered_payloads = [p for p in payloads if p['name'] in missing]
        logger.info(f"Attempting to register {len(filtered_payloads)} missing commands")
        
        # Register each command individually with retries
        success = await register_commands_safely(filtered_payloads)
        
        return success
    except Exception as e:
        logger.error(f"Error during command sync: {e}")
        return False

async def main():
    """Main entry point for the command registration script"""
    logger.info("Starting command registration script")
    
    # Check if argument for force sync was provided
    force_sync = len(sys.argv) > 1 and sys.argv[1] == "--force"
    
    # Run the command sync
    success = await safe_command_sync(force=force_sync)
    
    if success:
        logger.info("✅ Command registration successful!")
    else:
        logger.error("❌ Command registration failed.")
    
    # Notify that it might take time for commands to appear
    logger.info("Note: It may take up to an hour for commands to appear in Discord")

if __name__ == "__main__":
    asyncio.run(main())