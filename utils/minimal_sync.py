"""
Minimal command synchronization with Discord's API.

This module provides a stripped-down approach to command registration
that works reliably by using native Discord.py functionality and proper
rate limit handling.
"""

import logging
import asyncio
import random
import json
from datetime import datetime

logger = logging.getLogger('deadside_bot.utils.minimal_sync')

async def sync_commands_to_discord(bot, force=False):
    """
    Sync commands to Discord with intelligent rate limit handling
    
    This function uses the built-in Discord.py sync mechanism
    but adds proper rate limit handling and retries.
    
    Args:
        bot: The bot instance
        force: Force sync even if recent
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Starting command synchronization")
        
        # Try to use built-in command sync with smart retry
        # This is the most compatible method
        try:
            # First check if we need to sync
            if not force and hasattr(bot, 'last_sync_time'):
                last_sync = bot.last_sync_time
                now = datetime.now()
                hours_since_sync = (now - last_sync).total_seconds() / 3600
                
                if hours_since_sync < 1:  # Less than 1 hour since last sync
                    logger.info(f"Skipping command sync - last sync was {hours_since_sync:.1f} hours ago")
                    return True
            
            # Delete possible duplicate commands
            commands_by_name = {}
            for cmd in bot.application_commands:
                if cmd.name in commands_by_name:
                    logger.warning(f"Found duplicate command: {cmd.name}, keeping newest version")
                else:
                    commands_by_name[cmd.name] = cmd
            
            # If we found duplicates, replace the commands list
            if len(commands_by_name) < len(bot.application_commands):
                logger.info(f"Cleaned up {len(bot.application_commands) - len(commands_by_name)} duplicate commands")
                bot.application_commands.clear()
                for cmd in commands_by_name.values():
                    bot.application_commands.append(cmd)
            
            # Use built-in sync with retry for rate limits
            max_retries = 5
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Syncing commands, attempt {attempt}/{max_retries}")
                    
                    # Use try-except without modifying built-in sync
                    # This is safer than modifying the internal sync method
                    await bot.sync_commands()
                    
                    # If we get here, sync succeeded
                    logger.info("✅ Command sync successful")
                    bot.last_sync_time = datetime.now()
                    return True
                    
                except Exception as e:
                    logger.error(f"Error in sync attempt {attempt}: {e}")
                    
                    # Check if it's a rate limit error
                    if "rate limit" in str(e).lower() or getattr(e, 'status', 0) == 429:
                        # Extract retry_after if possible or use exponential backoff
                        retry_after = 5 * (2 ** (attempt - 1))
                        try:
                            # Try to parse the retry_after value from the error
                            error_text = str(e)
                            if "retry_after" in error_text:
                                import re
                                match = re.search(r'retry_after[\'"]?: ?([0-9.]+)', error_text)
                                if match:
                                    retry_after = float(match.group(1)) + 1  # Add 1s buffer
                        except:
                            pass
                        
                        # Add some jitter to avoid thundering herd
                        retry_after += random.uniform(1, 5)
                        
                        logger.warning(f"Rate limited. Waiting {retry_after:.1f}s before retry...")
                        await asyncio.sleep(retry_after)
                    else:
                        # If it's not a rate limit error, wait a bit but less
                        await asyncio.sleep(5)
                        
                    # If this was the last attempt, continue to fallback
                    if attempt == max_retries:
                        logger.error("All sync attempts failed, will try fallback approach")
            
            # If built-in sync failed, try direct HTTP API approach
            logger.warning("Attempting direct API call for command registration")
            
            # Get all commands from cogs
            commands_payload = []
            for cog_name, cog in bot.cogs.items():
                if hasattr(cog, "get_commands") and callable(cog.get_commands):
                    try:
                        cog_commands = cog.get_commands()
                        if isinstance(cog_commands, list):
                            for cmd in cog_commands:
                                if hasattr(cmd, 'to_dict'):
                                    try:
                                        cmd_payload = cmd.to_dict()
                                        commands_payload.append(cmd_payload)
                                    except Exception as cmd_err:
                                        logger.error(f"Error converting {cmd.name} to dict: {cmd_err}")
                    except Exception as cog_err:
                        logger.error(f"Error getting commands from {cog_name}: {cog_err}")
            
            # Add basic commands if needed
            if commands_payload and not any(c.get('name') == 'ping' for c in commands_payload):
                commands_payload.append({
                    "name": "ping",
                    "description": "Check bot's response time",
                    "type": 1
                })
            
            if commands_payload and not any(c.get('name') == 'commands' for c in commands_payload):
                commands_payload.append({
                    "name": "commands",
                    "description": "Show available commands",
                    "type": 1
                })
            
            # Try to register via direct API call
            if not commands_payload:
                logger.error("No commands to register")
                return False
            
            logger.info(f"Attempting to register {len(commands_payload)} commands via direct API call")
            try:
                # Use direct HTTP call with proper rate limit handling
                result = await bot.http.request(
                    'PUT',
                    f'/applications/{bot.application_id}/commands',
                    json=commands_payload
                )
                logger.info("✅ Successfully registered commands via direct API call")
                bot.last_sync_time = datetime.now()
                return True
            except Exception as api_err:
                logger.error(f"Direct API registration failed: {api_err}")
                return False
            
        except Exception as sync_err:
            logger.error(f"Error in command sync: {sync_err}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in command sync: {e}")
        return False

async def setup(bot):
    """Called when this extension is loaded"""
    # Store the last sync time
    bot.last_sync_time = datetime.now()
    
    # Add sync command as a method to the bot for easy access
    bot.sync_commands_safely = sync_commands_to_discord
    
    logger.info("Minimal command sync module loaded")