"""
Enhanced command registration for Discord.py with rate limit handling

This module provides a unified approach to command registration
that works with Discord's rate limits and prevents common issues.
"""

import logging
import asyncio
import random
import os
import json
from datetime import datetime, timedelta
try:
    import aiohttp
except ImportError:
    # If aiohttp is not available, we'll use http.client as fallback
    import http.client
    import urllib.parse
    import ssl
    aiohttp = None

# Import these modules regardless to ensure they're available for fallback
import http.client
import urllib.parse

logger = logging.getLogger('deadside_bot.command_registration_fix')

# Track the last sync time to avoid unnecessary syncs
LAST_SYNC_TIME = None
RATE_LIMIT_RESETS = {}

async def optimized_command_sync(bot):
    """
    Enhanced command registration that properly handles rate limits and context issues
    with a single batch registration approach
    """
    global LAST_SYNC_TIME, RATE_LIMIT_RESETS
    
    # Check if we recently synced commands
    if LAST_SYNC_TIME:
        now = datetime.now()
        hours_since_sync = (now - LAST_SYNC_TIME).total_seconds() / 3600
        if hours_since_sync < 1:  # Less than 1 hour since last sync
            logger.info(f"Skipping command sync - last sync was {hours_since_sync:.2f} hours ago")
            return True
    
    # Collect all commands from application_commands
    all_commands = []
    for cmd in bot.application_commands:
        if hasattr(cmd, 'to_dict'):
            try:
                cmd_dict = cmd.to_dict()
                all_commands.append(cmd_dict)
            except Exception as e:
                logger.error(f"Error serializing command {cmd.name}: {e}")
    
    # Add standard commands if needed
    if not any(c.get('name') == 'ping' for c in all_commands):
        all_commands.append({
            "name": "ping",
            "description": "Check the bot's response time",
            "type": 1  # CHAT_INPUT type
        })
    
    if not any(c.get('name') == 'commands' for c in all_commands):
        all_commands.append({
            "name": "commands",
            "description": "Show available commands and help information",
            "type": 1  # CHAT_INPUT type
        })
        
    # Add core commands that should always be present
    core_commands = [
        "server", "stats", "connections", "killfeed", 
        "missions", "faction"
    ]
    
    # Check for missing core commands and add stubs for them
    for cmd_name in core_commands:
        if not any(c.get('name') == cmd_name for c in all_commands):
            logger.info(f"Adding stub for missing command: {cmd_name}")
            all_commands.append({
                "name": cmd_name,
                "description": f"{cmd_name.capitalize()} management commands",
                "type": 1  # CHAT_INPUT type
            })
    
    # Use direct API approach with aiohttp for reliability
    token = os.getenv('DISCORD_TOKEN')
    app_id = bot.application_id
    
    if not token:
        logger.error("No Discord token available")
        return False
    
    if not app_id:
        logger.error("No application ID available")
        return False
    
    # Endpoint for global command registration
    url = f"https://discord.com/api/v10/applications/{app_id}/commands"
    
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    # Register in small batches to respect rate limits
    batch_size = 3
    batches = [all_commands[i:i+batch_size] for i in range(0, len(all_commands), batch_size)]
    
    logger.info(f"Registering {len(all_commands)} commands in {len(batches)} batches")
    
    success_count = 0
    
    try:
        if aiohttp:
            # Use aiohttp if available (more efficient)
            async with aiohttp.ClientSession() as session:
                for i, batch in enumerate(batches):
                    try:
                        logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} commands")
                        
                        # Check if we need to wait for a rate limit reset
                        if url in RATE_LIMIT_RESETS and RATE_LIMIT_RESETS[url] > datetime.now():
                            wait_time = (RATE_LIMIT_RESETS[url] - datetime.now()).total_seconds()
                            logger.info(f"Waiting {wait_time:.1f}s for rate limit reset")
                            await asyncio.sleep(wait_time + 0.5)  # Add a small buffer
                        
                        # Register commands with PUT method
                        async with session.put(url, headers=headers, json=batch) as response:
                            if response.status == 429:  # Rate limited
                                # Parse the retry_after field
                                data = await response.json()
                                retry_after = data.get('retry_after', 5)
                                
                                logger.warning(f"Rate limited on batch {i+1}. Retry after {retry_after}s")
                                
                                # Store rate limit reset time
                                RATE_LIMIT_RESETS[url] = datetime.now() + timedelta(seconds=retry_after)
                                
                                # Wait and retry this batch
                                await asyncio.sleep(retry_after + 1)
                                
                                # Retry this batch
                                async with session.put(url, headers=headers, json=batch) as retry_response:
                                    if retry_response.status in (200, 201):
                                        logger.info(f"Batch {i+1} succeeded after retry")
                                        success_count += len(batch)
                                    else:
                                        error_text = await retry_response.text()
                                        logger.error(f"Failed to register batch {i+1} after retry: {retry_response.status} - {error_text}")
                            
                            elif response.status in (200, 201):
                                logger.info(f"Batch {i+1} succeeded")
                                success_count += len(batch)
                            else:
                                error_text = await response.text()
                                logger.error(f"Failed to register batch {i+1}: {response.status} - {error_text}")
                        
                        # Wait between batches to respect rate limits
                        if i < len(batches) - 1:  # Don't wait after the last batch
                            await asyncio.sleep(2)
                    
                    except Exception as e:
                        logger.error(f"Error in batch {i+1}: {e}")
                        await asyncio.sleep(3)  # Wait a bit longer after an error
        else:
            # Fallback to standard http module
            logger.info("Using http.client fallback - aiohttp not available")
            
            for i, batch in enumerate(batches):
                try:
                    logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} commands")
                    
                    # Check if we need to wait for a rate limit reset
                    if url in RATE_LIMIT_RESETS and RATE_LIMIT_RESETS[url] > datetime.now():
                        wait_time = (RATE_LIMIT_RESETS[url] - datetime.now()).total_seconds()
                        logger.info(f"Waiting {wait_time:.1f}s for rate limit reset")
                        await asyncio.sleep(wait_time + 0.5)
                    
                    # Parse the URL for http.client
                    parsed_url = urllib.parse.urlparse(url)
                    
                    # Prepare the data
                    data = json.dumps(batch).encode('utf-8')
                    
                    # Create a secure connection
                    conn = http.client.HTTPSConnection(parsed_url.netloc)
                    
                    # Send the request
                    conn.request("PUT", parsed_url.path, body=data, headers=headers)
                    
                    # Get the response
                    response = conn.getresponse()
                    
                    # Handle the response
                    if response.status == 429:  # Rate limited
                        response_data = json.loads(response.read().decode('utf-8'))
                        retry_after = response_data.get('retry_after', 5)
                        
                        logger.warning(f"Rate limited on batch {i+1}. Retry after {retry_after}s")
                        
                        # Store rate limit reset time
                        RATE_LIMIT_RESETS[url] = datetime.now() + timedelta(seconds=retry_after)
                        
                        # Wait and retry this batch
                        await asyncio.sleep(retry_after + 1)
                        
                        # Retry this batch
                        conn = http.client.HTTPSConnection(parsed_url.netloc)
                        conn.request("PUT", parsed_url.path, body=data, headers=headers)
                        retry_response = conn.getresponse()
                        
                        if retry_response.status in (200, 201):
                            logger.info(f"Batch {i+1} succeeded after retry")
                            success_count += len(batch)
                        else:
                            error_text = retry_response.read().decode('utf-8')
                            logger.error(f"Failed to register batch {i+1} after retry: {retry_response.status} - {error_text}")
                    
                    elif response.status in (200, 201):
                        logger.info(f"Batch {i+1} succeeded")
                        success_count += len(batch)
                    else:
                        error_text = response.read().decode('utf-8')
                        logger.error(f"Failed to register batch {i+1}: {response.status} - {error_text}")
                    
                    # Close the connection
                    conn.close()
                    
                    # Wait between batches to respect rate limits
                    if i < len(batches) - 1:  # Don't wait after the last batch
                        await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"Error in batch {i+1}: {e}")
                    await asyncio.sleep(3)  # Wait a bit longer after an error
        
        # Report overall success
        if success_count == len(all_commands):
            logger.info(f"Successfully registered all {success_count} commands")
            LAST_SYNC_TIME = datetime.now()
            return True
        elif success_count > 0:
            logger.warning(f"Registered {success_count}/{len(all_commands)} commands")
            LAST_SYNC_TIME = datetime.now()
            return True
        else:
            logger.error("Failed to register any commands")
            return False
            
    except Exception as e:
        logger.error(f"Error during command registration: {e}")
        return False