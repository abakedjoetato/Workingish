"""
Simple command sync utility for testing Discord command registration
with absolute minimal dependencies to ensure maximum compatibility.

This utility takes a back-to-basics approach that works with all versions
of Discord.py by using only the most fundamental parts of the API.
"""

import logging
import asyncio
from datetime import datetime
import aiohttp
import json
import os

logger = logging.getLogger('deadside_bot.utils.command_test')

# Set up simple rate limit handling
RATE_LIMIT_RESET = {}  # Path -> datetime of reset
LAST_SYNC = None

async def sync_commands(bot, force=False):
    """
    Sync commands to Discord using a very basic approach
    that doesn't rely on Discord.py internal implementations.
    """
    global LAST_SYNC
    
    # Check if we've synced recently
    if not force and LAST_SYNC:
        now = datetime.now()
        hours_since_sync = (now - LAST_SYNC).total_seconds() / 3600
        if hours_since_sync < 1:  # Less than 1 hour since last sync
            logger.info(f"Skipping sync - last sync was {hours_since_sync:.1f} hours ago")
            return True
    
    # Simple approach: use Discord API directly rather than using Discord.py
    # This avoids any Discord.py version incompatibilities
    logger.info("🔄 Using direct Discord API approach for command sync")
    
    # Collect commands manually
    commands = []
    for cmd in bot.application_commands:
        if hasattr(cmd, 'to_dict'):
            try:
                cmd_dict = cmd.to_dict()
                commands.append(cmd_dict)
            except Exception as e:
                logger.error(f"Error converting command {cmd.name}: {e}")
    
    # Add standard commands if not present
    if not any(c.get('name') == 'ping' for c in commands):
        ping_cmd = {
            "name": "ping",
            "description": "Check the bot's response time",
            "type": 1  # CHAT_INPUT
        }
        commands.append(ping_cmd)
        logger.info("Added standard ping command")
    
    if not any(c.get('name') == 'commands' for c in commands):
        help_cmd = {
            "name": "commands",
            "description": "Show available commands and help information",
            "type": 1  # CHAT_INPUT
        }
        commands.append(help_cmd)
        logger.info("Added standard help command")
    
    # Make a direct API request using aiohttp rather than Discord.py's HTTP client
    token = os.getenv('DISCORD_TOKEN') or bot.http.token
    app_id = bot.application_id
    url = f"https://discord.com/api/v10/applications/{app_id}/commands"
    
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Simple batching of 5 commands at a time to respect rate limits
        batch_size = 3
        batches = [commands[i:i+batch_size] for i in range(0, len(commands), batch_size)]
        
        logger.info(f"Syncing {len(commands)} commands in {len(batches)} batches")
        
        success_count = 0
        
        async with aiohttp.ClientSession() as session:
            for i, batch in enumerate(batches):
                try:
                    logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} commands")
                    
                    # Wait for any rate limit reset
                    if url in RATE_LIMIT_RESET:
                        now = datetime.now()
                        if RATE_LIMIT_RESET[url] > now:
                            wait_time = (RATE_LIMIT_RESET[url] - now).total_seconds()
                            logger.info(f"Waiting {wait_time:.1f}s for rate limit reset")
                            await asyncio.sleep(wait_time + 0.5)  # Add a small buffer
                    
                    # Register commands in the current batch
                    async with session.put(url, headers=headers, json=batch) as response:
                        # Handle rate limits properly
                        if response.status == 429:
                            data = await response.json()
                            retry_after = data.get('retry_after', 5)
                            logger.warning(f"Rate limited. Retry after {retry_after}s")
                            
                            # Store rate limit reset
                            reset_time = datetime.now().timestamp() + retry_after
                            RATE_LIMIT_RESET[url] = datetime.fromtimestamp(reset_time)
                            
                            # Wait for rate limit to reset
                            await asyncio.sleep(retry_after + 1)
                            
                            # Try again
                            async with session.put(url, headers=headers, json=batch) as retry_response:
                                if retry_response.status in (200, 201):
                                    logger.info(f"✅ Batch {i+1} registered successfully after retry")
                                    success_count += len(batch)
                                else:
                                    error_text = await retry_response.text()
                                    logger.error(f"❌ Failed to register batch {i+1} after retry: {error_text}")
                        elif response.status in (200, 201):
                            logger.info(f"✅ Batch {i+1} registered successfully")
                            success_count += len(batch)
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Failed to register batch {i+1}: {response.status} - {error_text}")
                    
                    # Wait between batches to respect rate limits
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error processing batch {i+1}: {e}")
                    await asyncio.sleep(5)  # Wait longer after an error
        
        # Report overall success
        if success_count == len(commands):
            logger.info(f"✅ Successfully registered all {success_count} commands")
            LAST_SYNC = datetime.now()
            return True
        elif success_count > 0:
            logger.warning(f"⚠️ Registered {success_count}/{len(commands)} commands")
            LAST_SYNC = datetime.now()
            return True
        else:
            logger.error("❌ Failed to register any commands")
            return False
            
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
        return False

async def setup(bot):
    """Called when this extension is loaded"""
    # Add sync function as a method to the bot
    bot.test_sync_commands = sync_commands
    
    logger.info("Command test module loaded")