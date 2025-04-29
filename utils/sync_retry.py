"""
Discord Command Synchronization with Rate Limit Handling

This module provides utilities for safely synchronizing commands with Discord's API,
handling rate limits gracefully and providing retry mechanisms.

Includes both individual command registration and bulk registration approaches.
"""

import logging
import json
import asyncio
import time
import os
import sys
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union

import discord
from discord.ext import commands
from discord.http import Route

logger = logging.getLogger('deadside_bot.utils.sync_retry')

# Constants for rate limit handling
SYNC_COOLDOWN = 60 * 60  # 1 hour in seconds between full command syncs
NORMAL_COOLDOWN = 60 * 10  # 10 minutes between normal syncs
STARTUP_COOLDOWN = 60  # 1 minute cooldown on first startup
LAST_SYNC_FILE = ".last_command_check.txt"
RATE_LIMIT_FILE = "./rate_limit_state.json"  # Stores rate limit state between restarts (without dot prefix to be visible)

class CommandSyncManager:
    """Manages command synchronization with Discord API"""
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limits = self._load_rate_limits()
        self.last_sync_time = self._load_last_sync()
        self.first_run = True  # Track if this is first run after startup
    
    def _load_last_sync(self):
        """Load the last sync time from file"""
        try:
            if os.path.exists(LAST_SYNC_FILE):
                with open(LAST_SYNC_FILE, "r") as f:
                    timestamp = float(f.read().strip())
                    return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.error(f"Error loading last sync time: {e}")
        return None
    
    def _save_last_sync(self, timestamp=None):
        """Save the last sync time to file"""
        try:
            if timestamp is None:
                timestamp = datetime.now().timestamp()
            elif isinstance(timestamp, datetime):
                timestamp = timestamp.timestamp()
                
            with open(LAST_SYNC_FILE, "w") as f:
                f.write(str(timestamp))
        except Exception as e:
            logger.error(f"Error saving last sync time: {e}")
            
    def _load_rate_limits(self):
        """Load rate limit state from file"""
        try:
            if os.path.exists(RATE_LIMIT_FILE):
                with open(RATE_LIMIT_FILE, "r") as f:
                    data = json.load(f)
                    
                    # Convert reset_at strings back to datetime objects
                    rate_limits = {}
                    for path, info in data.items():
                        if 'reset_at' in info:
                            try:
                                info['reset_at'] = datetime.fromtimestamp(info['reset_at'])
                                rate_limits[path] = info
                            except:
                                # Skip any malformed entries
                                pass
                    
                    logger.info(f"Loaded {len(rate_limits)} rate limit states from disk")
                    return rate_limits
        except Exception as e:
            logger.error(f"Error loading rate limit state: {e}")
        return {}
        
    def _save_rate_limits(self):
        """Save current rate limit state to file"""
        try:
            # Convert datetimes to timestamps for JSON serialization
            data_to_save = {}
            for path, info in self.rate_limits.items():
                # Deep copy to avoid modifying the original
                path_data = dict(info)
                if 'reset_at' in path_data and isinstance(path_data['reset_at'], datetime):
                    path_data['reset_at'] = path_data['reset_at'].timestamp()
                data_to_save[path] = path_data
                
            with open(RATE_LIMIT_FILE, "w") as f:
                json.dump(data_to_save, f)
        except Exception as e:
            logger.error(f"Error saving rate limit state: {e}")
    
    async def is_recent_sync(self):
        """Check if we've synced commands recently using a smart cooldown system"""
        if not self.last_sync_time:
            # First run ever, always sync
            logger.info("No previous sync detected - initial sync required")
            return False
        
        # Check if it's been less than the appropriate cooldown period
        now = datetime.now()
        time_since_sync = (now - self.last_sync_time).total_seconds()
        
        # On first run after startup, use a shorter cooldown
        if self.first_run:
            if time_since_sync < STARTUP_COOLDOWN:
                logger.info(f"Recent startup detected. Last sync was {time_since_sync:.1f}s ago (<{STARTUP_COOLDOWN}s startup cooldown)")
                return True
            else:
                logger.info(f"First run after startup, but {time_since_sync:.1f}s since last sync (>{STARTUP_COOLDOWN}s startup cooldown)")
                self.first_run = False
                return False
        
        # For normal operation, use the standard cooldown logic
        if time_since_sync < NORMAL_COOLDOWN:
            logger.info(f"Skipping sync due to recent activity. Last sync was {time_since_sync:.1f}s ago (<{NORMAL_COOLDOWN}s normal cooldown)")
            return True
            
        # For full syncs, we use a longer cooldown to avoid unnecessary API calls
        if time_since_sync < SYNC_COOLDOWN:
            # We still want to do lighter syncs between full syncs
            # Here, we could check if there are new commands that need registration
            # but for now, we'll just log that we're within the cooldown window
            logger.info(f"Performing normal sync. Last full sync was {time_since_sync:.1f}s ago (<{SYNC_COOLDOWN}s full sync cooldown)")
            return False
            
        # If it's been longer than the full sync cooldown, we need to do a full refresh
        logger.info(f"Performing full sync. It's been {time_since_sync:.1f}s since last sync (>{SYNC_COOLDOWN}s full sync cooldown)")
        return False
    
    async def collect_all_commands(self):
        """Collect all commands from cogs into a payload for registration"""
        commands_payload = []
        
        # Process each cog
        for cog_name, cog in self.bot.cogs.items():
            # Check if the cog has a get_commands method
            if hasattr(cog, "get_commands") and callable(cog.get_commands):
                try:
                    # Get commands from the cog
                    cog_commands = cog.get_commands()
                    
                    # Add more verbose debugging
                    logger.info(f"Cog {cog_name} returned command type: {type(cog_commands)}")
                    if cog_commands is None:
                        logger.error(f"Cog {cog_name} returned None instead of a list of commands")
                        continue
                    
                    # Process each command or group
                    for cmd in cog_commands:
                        # Apply command fix for integration_types and contexts
                        if isinstance(cmd, discord.SlashCommandGroup):
                            # Fix command group attributes first
                            try:
                                from utils.command_fix import fix_command_group
                                cmd = fix_command_group(cmd)
                                
                                # For command groups, convert to dict
                                cmd_payload = cmd.to_dict()
                                commands_payload.append(cmd_payload)
                                logger.info(f"Added slash command group: {cmd.name}")
                            except Exception as fix_err:
                                logger.error(f"Error fixing command group {cmd.name}: {fix_err}")
                                import traceback
                                logger.error(traceback.format_exc())
                                continue
                        elif isinstance(cmd, discord.ApplicationCommand):
                            # For regular commands, convert to dict
                            # Attempt to fix command attributes first if needed
                            try:
                                # Use proper command fix function to ensure we have the right types
                                from utils.command_fix import fix_command_group_attributes
                                cmd = fix_command_group_attributes(cmd)
                                    
                                cmd_payload = cmd.to_dict()
                                commands_payload.append(cmd_payload)
                                logger.info(f"Added application command: {cmd.name}")
                            except Exception as fix_err:
                                logger.error(f"Error fixing application command {cmd.name}: {fix_err}")
                                import traceback
                                logger.error(traceback.format_exc())
                                continue
                        else:
                            logger.warning(f"Unknown command type from {cog_name}: {type(cmd)}")
                except Exception as e:
                    logger.error(f"Error getting commands from cog {cog_name}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        return commands_payload
    
    async def handle_rate_limit(self, error, command=None):
        """Handle a rate limit error by scheduling retries appropriately"""
        if not hasattr(error, "response") or not error.response:
            return
            
        try:
            # Extract rate limit info
            response = error.response
            data = json.loads(await response.text())
            retry_after = data.get("retry_after", 5)
            
            # Extract the bucket info from the headers or response if available
            bucket = None
            if hasattr(error, "route") and error.route:
                bucket = error.route.bucket
            
            # Log rate limit info
            path = str(response.url)
            if bucket:
                logger.warning(f"Rate limited on {path} (bucket: {bucket}) - retry after {retry_after}s")
            else:
                logger.warning(f"Rate limited on {path} - retry after {retry_after}s")
            
            # Add an extra buffer to prevent exactly hitting the rate limit
            # Add 0.5-1.5 seconds of extra padding
            buffer_time = 0.5 + (random.random() * 1.0)
            actual_retry = retry_after + buffer_time
            
            # Store rate limit info for this path
            self.rate_limits[path] = {
                "retry_after": actual_retry,
                "reset_at": datetime.now() + timedelta(seconds=actual_retry),
                "bucket": bucket,
                "hit_count": self.rate_limits.get(path, {}).get("hit_count", 0) + 1,
                "last_hit": datetime.now().timestamp()
            }
            
            try:
                # Save rate limit state so it persists across restarts
                self._save_rate_limits()
                logger.info(f"Successfully saved rate limit state to {RATE_LIMIT_FILE}")
            except Exception as save_error:
                logger.error(f"Failed to save rate limit state: {save_error}")
                import traceback
                logger.error(traceback.format_exc())
            
            # If we have command info, log it
            if command:
                logger.info(f"Rate limited while processing command: {command}")
        except Exception as e:
            logger.error(f"Error handling rate limit: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def should_retry(self, path):
        """Check if we should retry a request to a specific path"""
        if path not in self.rate_limits:
            return True
            
        rate_limit = self.rate_limits[path]
        now = datetime.now()
        
        # Check if we're past the reset time
        if now >= rate_limit["reset_at"]:
            del self.rate_limits[path]
            return True
            
        # Otherwise, we need to wait
        return False
    
    async def wait_for_rate_limit(self, path):
        """Wait for a rate limit to expire"""
        if path not in self.rate_limits:
            return
            
        rate_limit = self.rate_limits[path]
        now = datetime.now()
        
        # If we're still rate limited, wait
        if now < rate_limit["reset_at"]:
            wait_time = (rate_limit["reset_at"] - now).total_seconds()
            logger.info(f"Waiting {wait_time:.1f}s for rate limit to expire")
            await asyncio.sleep(wait_time)
            
        # Clean up the rate limit info
        if path in self.rate_limits:
            del self.rate_limits[path]
    
    async def register_commands_safely(self, commands_payload):
        """Register commands with Discord with rate limit handling and auto-retry"""
        if not self.bot.application_id:
            logger.error("No application ID available")
            return False
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Get the route for registering global commands
                route = Route("PUT", f"/applications/{self.bot.application_id}/commands")
                
                # Check for rate limits
                if not await self.should_retry(str(route.url)):
                    logger.info("Waiting for rate limit to expire before attempting command registration")
                    await self.wait_for_rate_limit(str(route.url))
                
                # Make the request with detailed logging
                logger.info(f"Attempting bulk command registration (attempt {retry_count+1}/{max_retries})")
                await self.bot.http.request(route, json=commands_payload)
                
                # Success! Update last sync time
                self.last_sync_time = datetime.now()
                self._save_last_sync(self.last_sync_time)
                
                # Save rate limit state for future use
                self._save_rate_limits()
                
                # Mark first run as complete
                self.first_run = False
                
                logger.info(f"✅ Successfully registered {len(commands_payload)} commands with Discord")
                return True
            
            except discord.HTTPException as e:
                # Handle rate limits with exponential backoff
                if e.status == 429:
                    retry_count += 1
                    await self.handle_rate_limit(e, "register_commands")
                    
                    # Extract retry_after from response if possible
                    retry_after = 1
                    try:
                        if hasattr(e, 'response') and e.response:
                            data = json.loads(await e.response.text())
                            retry_after = data.get('retry_after', 1)
                    except:
                        # Fallback to exponential backoff
                        retry_after = (2 ** retry_count) * 5
                    
                    # Add some jitter to prevent thundering herd
                    retry_after = retry_after * (0.8 + (0.4 * (time.time() % 1)))
                    
                    logger.warning(f"Rate limited on attempt {retry_count}/{max_retries}. "
                                   f"Retrying in {retry_after:.2f}s...")
                    
                    # Wait before retry
                    await asyncio.sleep(retry_after)
                    continue
                
                # Other HTTP errors
                logger.error(f"HTTP error registering commands: {e}")
                return False
                
            except Exception as e:
                logger.error(f"Error registering commands: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
        
        logger.error(f"Failed to register commands after {max_retries} attempts")
        return False
    
    async def sync_commands(self, force=False):
        """Synchronize commands with Discord"""
        # Check if we should sync based on cooldown
        if not force and await self.is_recent_sync():
            logger.info(f"Skipping command sync - last sync was {self.last_sync_time}")
            return True
            
        # Collect all commands
        try:
            logger.info("Collecting commands for synchronization")
            commands_payload = await self.collect_all_commands()
            
            if not commands_payload:
                logger.warning("No commands found to sync")
                return False
                
            logger.info(f"Registering {len(commands_payload)} commands with Discord")
            result = await self.register_commands_safely(commands_payload)
            
            if result:
                logger.info("Command synchronization successful")
            else:
                logger.warning("Command synchronization failed")
                
            return result
        except Exception as e:
            logger.error(f"Error synchronizing commands: {e}")
            return False

# This function is called internally by the extension loader
def add_sync_manager(bot):
    """Add the synchronization manager to the bot"""
    bot.sync_manager = CommandSyncManager(bot)

async def safe_command_sync(bot=None, force=False):
    """
    Safely synchronize commands with Discord
    
    This function can be called from anywhere in the code to trigger
    a command synchronization with built-in rate limit handling.
    
    Args:
        bot: Optional bot instance (if not provided, get from sync_retry)
        force: Force synchronization even if recent
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    try:
        # Get the bot instance
        if not bot and not hasattr(sync_retry, "bot"):
            logger.error("No bot instance available for command sync")
            return False
            
        if not bot:
            bot = sync_retry.bot
            
        # Check if bot has sync manager
        if not hasattr(bot, "sync_manager"):
            logger.error("Bot doesn't have sync_manager - was setup() called?")
            return False
            
        # Sync commands
        return await bot.sync_manager.sync_commands(force)
    except Exception as e:
        logger.error(f"Error in safe_command_sync: {e}")
        return False

async def setup(bot):
    """Called when the extension is loaded"""
    # Store the bot instance for module-level access
    global sync_retry
    sync_retry = sys.modules[__name__]
    sync_retry.bot = bot
    
    # Initialize the sync manager
    bot.sync_manager = CommandSyncManager(bot)
    logger.info("Command sync manager initialized")