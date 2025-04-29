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
from discord.ext import commands, tasks
from discord.http import Route

logger = logging.getLogger('deadside_bot.utils.sync_retry')

# Constants for rate limit handling
SYNC_COOLDOWN = 60 * 60  # 1 hour in seconds between full command syncs
NORMAL_COOLDOWN = 60 * 10  # 10 minutes between normal syncs
STARTUP_COOLDOWN = 60  # 1 minute cooldown on first startup
RATE_LIMIT_BUFFER = 600  # 10 minutes (600 seconds) wait time after rate limit

class CommandSyncManager:
    """Manages command synchronization with Discord API"""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_sync_time = None
        self.first_run = True
        self.rate_limits = {}
        self._load_last_sync()
        self._load_rate_limits()
    
    def _load_last_sync(self):
        """Load the last sync time from file"""
        try:
            if os.path.exists(".last_command_sync.txt"):
                with open(".last_command_sync.txt", "r") as f:
                    timestamp_str = f.read().strip()
                    if timestamp_str:
                        self.last_sync_time = datetime.fromtimestamp(float(timestamp_str))
                        logger.info(f"Last command sync: {self.last_sync_time}")
                    else:
                        self.last_sync_time = None
        except Exception as e:
            logger.error(f"Error loading last sync time: {e}")
            self.last_sync_time = None
    
    def _save_last_sync(self, timestamp=None):
        """Save the last sync time to file"""
        try:
            timestamp = timestamp or datetime.now()
            with open(".last_command_sync.txt", "w") as f:
                f.write(str(timestamp.timestamp()))
        except Exception as e:
            logger.error(f"Error saving last sync time: {e}")
    
    def _load_rate_limits(self):
        """Load rate limit state from file"""
        try:
            if os.path.exists("rate_limit_state.json"):
                with open("rate_limit_state.json", "r") as f:
                    rate_limits_data = json.load(f)
                    
                    # Convert string timestamps back to datetime objects
                    for path, limit_info in rate_limits_data.items():
                        if "reset_time" in limit_info:
                            limit_info["reset_time"] = datetime.fromtimestamp(limit_info["reset_time"])
                    
                    self.rate_limits = rate_limits_data
        except Exception as e:
            logger.error(f"Error loading rate limits: {e}")
            self.rate_limits = {}
    
    def _save_rate_limits(self):
        """Save current rate limit state to file"""
        try:
            # Convert datetime objects to timestamps for JSON serialization
            rate_limits_data = {}
            for path, limit_info in self.rate_limits.items():
                rate_limits_data[path] = limit_info.copy()
                if "reset_time" in limit_info and isinstance(limit_info["reset_time"], datetime):
                    rate_limits_data[path]["reset_time"] = limit_info["reset_time"].timestamp()
            
            with open("rate_limit_state.json", "w") as f:
                json.dump(rate_limits_data, f)
        except Exception as e:
            logger.error(f"Error saving rate limits: {e}")
    
    async def is_recent_sync(self):
        """Check if we've synced commands recently using a smart cooldown system"""
        if not self.last_sync_time:
            return False
        
        now = datetime.now()
        elapsed = (now - self.last_sync_time).total_seconds()
        
        # Different cooldowns for different scenarios
        if self.first_run:
            # Very short cooldown on first run
            return elapsed < STARTUP_COOLDOWN
        
        # Full cooldown for repeat runs
        return elapsed < SYNC_COOLDOWN
    
    async def collect_all_commands(self):
        """Collect all commands from cogs into a payload for registration"""
        commands_payload = []
        
        # Process each cog to collect commands
        for cog_name, cog in self.bot.cogs.items():
            if hasattr(cog, "get_commands") and callable(cog.get_commands):
                try:
                    cog_commands = cog.get_commands()
                    logger.info(f"Cog {cog_name} returned command type: {type(cog_commands)}")
                    
                    # Handle different return types (list or single command)
                    if isinstance(cog_commands, list):
                        for cmd in cog_commands:
                            if hasattr(cmd, "to_dict"):
                                try:
                                    # Apply command fixes if available
                                    if hasattr(cmd, "name"):
                                        logger.info(f"Added slash command group: {cmd.name}")
                                    
                                    cmd_dict = cmd.to_dict()
                                    commands_payload.append(cmd_dict)
                                except Exception as cmd_err:
                                    logger.error(f"Error converting command {getattr(cmd, 'name', 'Unknown')} to dict: {cmd_err}")
                    elif cog_commands and hasattr(cog_commands, "to_dict"):
                        try:
                            cmd_dict = cog_commands.to_dict()
                            if hasattr(cog_commands, "name"):
                                logger.info(f"Added slash command: {cog_commands.name}")
                            commands_payload.append(cmd_dict)
                        except Exception as cmd_err:
                            logger.error(f"Error converting command {getattr(cog_commands, 'name', 'Unknown')} to dict: {cmd_err}")
                except Exception as cog_err:
                    logger.error(f"Error getting commands from cog {cog_name}: {cog_err}")
            elif hasattr(cog, "get_application_commands") and callable(cog.get_application_commands):
                try:
                    app_commands = cog.get_application_commands()
                    if isinstance(app_commands, list):
                        for cmd in app_commands:
                            try:
                                if hasattr(cmd, "to_dict"):
                                    cmd_dict = cmd.to_dict()
                                    logger.info(f"Added application command: {cmd.name}")
                                    commands_payload.append(cmd_dict)
                            except Exception as cmd_err:
                                logger.error(f"Error converting app command to dict: {cmd_err}")
                except Exception as app_err:
                    logger.error(f"Error getting application commands from {cog_name}: {app_err}")
        
        # Add global commands that aren't in cogs
        for cmd in self.bot.application_commands:
            try:
                if not any(c.get("name") == cmd.name for c in commands_payload):
                    cmd_dict = cmd.to_dict()
                    logger.info(f"Added global command: {cmd.name}")
                    commands_payload.append(cmd_dict)
            except Exception as global_err:
                logger.error(f"Error adding global command {cmd.name}: {global_err}")
        
        # Add ping command if not already present
        if not any(c.get("name") == "ping" for c in commands_payload):
            ping_cmd = {
                "name": "ping",
                "description": "Check the bot's response time",
                "type": 1  # CHAT_INPUT
            }
            commands_payload.append(ping_cmd)
            logger.info("Added basic ping command")
        
        # Add help command if not already present
        if not any(c.get("name") == "commands" for c in commands_payload):
            help_cmd = {
                "name": "commands",
                "description": "Show available commands and help information",
                "type": 1  # CHAT_INPUT
            }
            commands_payload.append(help_cmd)
            logger.info("Added basic help command")
        
        return commands_payload
    
    async def handle_rate_limit(self, error, path="commands"):
        """Handle a rate limit error by scheduling retries appropriately"""
        retry_after = 5  # default retry time in seconds
        
        # Try to extract retry_after from the error
        try:
            if hasattr(error, 'response') and error.response:
                data = await error.response.json()
                if 'retry_after' in data:
                    retry_after = data['retry_after']
        except:
            # If we can't extract, use a default with some buffer
            retry_after = 5
        
        # Add a buffer time to be extra cautious
        retry_after = max(retry_after + 2, RATE_LIMIT_BUFFER / 10)
        
        # Store the rate limit information
        now = datetime.now()
        reset_time = now + timedelta(seconds=retry_after)
        
        self.rate_limits[path] = {
            "reset_time": reset_time,
            "retry_after": retry_after
        }
        
        # Save rate limit state for future reference
        self._save_rate_limits()
        
        logger.warning(f"Rate limited on {path}. Will retry after {retry_after:.2f}s (at {reset_time})")
    
    async def should_retry(self, path):
        """Check if we should retry a request to a specific path"""
        if path not in self.rate_limits:
            return True
        
        rate_limit = self.rate_limits[path]
        now = datetime.now()
        
        if "reset_time" in rate_limit and rate_limit["reset_time"] > now:
            # Still rate limited
            return False
        
        # Rate limit has expired, clean up
        self.rate_limits.pop(path, None)
        return True
    
    async def wait_for_rate_limit(self, path):
        """Wait for a rate limit to expire"""
        if path not in self.rate_limits:
            return 0
        
        rate_limit = self.rate_limits[path]
        now = datetime.now()
        
        if "reset_time" in rate_limit and rate_limit["reset_time"] > now:
            # Calculate wait time
            wait_seconds = (rate_limit["reset_time"] - now).total_seconds()
            if wait_seconds > 0:
                logger.info(f"Waiting {wait_seconds:.2f}s for rate limit to expire")
                await asyncio.sleep(wait_seconds)
            
            # Rate limit should be expired now
            self.rate_limits.pop(path, None)
            return wait_seconds
        
        # Clean up the rate limit info
        if path in self.rate_limits:
            del self.rate_limits[path]
    
    async def register_commands_safely(self, commands_payload):
        """Register commands with Discord with rate limit handling and auto-retry"""
        if not self.bot.application_id:
            logger.error("No application ID available")
            return False
        
        max_retries = 5  # Increased from 3 to 5
        batch_size = 3   # Small batch size to respect rate limits
        wait_time = 6    # 6 seconds between batches (Discord allows ~5 requests per 5 seconds)
        
        logger.info(f"🌐 Enhanced GLOBAL command registration with smart rate limit handling")
        logger.info(f"Using batch size of {batch_size} with {wait_time}s delay between batches")
        
        # Define a helper function for rate-limited calls with exponential backoff
        async def register_with_rate_limit(endpoint, method, payload, retry_count=0, max_local_retries=3):
            try:
                # Check for existing rate limits first
                if not await self.should_retry(endpoint):
                    wait_seconds = await self.wait_for_rate_limit(endpoint)
                    logger.info(f"Waiting {wait_seconds}s for rate limit to expire before attempting registration")
                
                # Handle the API call correctly based on Discord.py's requirements
                # The HTTP client expects the method and route as separate arguments
                return await self.bot.http.request(method, endpoint, json=payload)
                
            except Exception as e:
                # Check if it's a rate limit error
                is_rate_limit = False
                retry_after = 5  # default
                
                if hasattr(e, 'status') and e.status == 429:
                    is_rate_limit = True
                elif "rate limit" in str(e).lower():
                    is_rate_limit = True
                
                # Handle rate limit errors with exponential backoff
                if is_rate_limit and retry_count < max_local_retries:
                    # Try to extract retry_after if available
                    try:
                        if hasattr(e, 'response') and hasattr(e.response, 'json'):
                            data = await e.response.json()
                            if 'retry_after' in data:
                                retry_after = data['retry_after']
                                # Add buffer time
                                retry_after += 2
                    except:
                        # Use exponential backoff
                        retry_after = 5 * (2 ** retry_count) + random.uniform(1, 3)
                    
                    # Add to rate limits
                    await self.handle_rate_limit(e, endpoint)
                    
                    logger.warning(f"Rate limited on {endpoint}. Waiting {retry_after:.2f}s before retry {retry_count+1}/{max_local_retries}")
                    await asyncio.sleep(retry_after)
                    return await register_with_rate_limit(endpoint, method, payload, retry_count+1, max_local_retries)
                else:
                    # Not a rate limit or too many retries
                    raise
        
        # IMPLEMENTATION #1: Try batched registration first (most efficient)
        try:
            # Divide commands into smaller batches to respect rate limits
            batches = [commands_payload[i:i+batch_size] for i in range(0, len(commands_payload), batch_size)]
            
            logger.info(f"Divided {len(commands_payload)} commands into {len(batches)} batches of max {batch_size}")
            
            success_count = 0
            for i, batch in enumerate(batches):
                try:
                    logger.info(f"Registering batch {i+1}/{len(batches)} with {len(batch)} commands...")
                    
                    # Set up the endpoint
                    cmd_endpoint = f"/applications/{self.bot.application_id}/commands"
                    
                    # Register this batch
                    result = await register_with_rate_limit(cmd_endpoint, "PUT", batch)
                    success_count += len(batch)
                    logger.info(f"✅ Batch {i+1} successful. {success_count}/{len(commands_payload)} commands registered")
                    
                    # Wait between batches to respect rate limits
                    if i < len(batches) - 1:  # Don't wait after the last batch
                        wait_with_jitter = wait_time + random.uniform(0.5, 2.0)  # Add jitter
                        logger.info(f"Waiting {wait_with_jitter:.2f}s before next batch...")
                        await asyncio.sleep(wait_with_jitter)
                        
                except Exception as batch_err:
                    logger.error(f"❌ Error in batch {i+1}: {batch_err}")
                    
                    # Wait a bit longer after an error
                    logger.info(f"Waiting {wait_time * 2}s after error before continuing...")
                    await asyncio.sleep(wait_time * 2)
                    
                    # Continue with next batch, we'll try IMPLEMENTATION #2 if overall success is low
            
            # Report success based on how many commands were registered
            if success_count >= len(commands_payload):
                logger.info(f"✅ SUCCESS: Registered all {success_count} commands globally")
                # Update last sync time
                self.last_sync_time = datetime.now()
                self._save_last_sync(self.last_sync_time)
                # Save rate limit state
                self._save_rate_limits()
                # Mark first run as complete
                self.first_run = False
                return True
            elif success_count > 0:
                logger.warning(f"⚠️ PARTIAL SUCCESS: Registered {success_count}/{len(commands_payload)} commands globally with batch method")
                # Update last sync time
                self.last_sync_time = datetime.now()
                self._save_last_sync(self.last_sync_time)
                # Save rate limit state
                self._save_rate_limits()
                # Mark first run as complete
                self.first_run = False
                # Still consider this a success to avoid blocking bot startup
                return True
                
            # If we registered none, fall through to IMPLEMENTATION #2
            
        except Exception as batch_approach_err:
            logger.error(f"❌ Error in batch registration approach: {batch_approach_err}")
            # Fall through to IMPLEMENTATION #2
        
        # IMPLEMENTATION #2: Register commands one by one for maximum reliability
        logger.warning("Attempting one-by-one command registration for maximum reliability")
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                # Get the route for registering global commands
                global_endpoint = f"/applications/{self.bot.application_id}/commands"
                
                # Try individual registration
                success_count = 0
                for cmd in commands_payload:
                    try:
                        result = await register_with_rate_limit(global_endpoint, "POST", cmd)
                        success_count += 1
                        logger.info(f"✅ Registered command: {cmd.get('name', 'Unknown')}")
                        
                        # Wait between individual commands
                        await asyncio.sleep(2)
                    except Exception as cmd_err:
                        logger.error(f"❌ Failed to register command {cmd.get('name', 'Unknown')}: {cmd_err}")
                
                if success_count > 0:
                    logger.info(f"✅ Registered {success_count}/{len(commands_payload)} commands individually")
                    # Update last sync time
                    self.last_sync_time = datetime.now()
                    self._save_last_sync(self.last_sync_time)
                    # Save rate limit state
                    self._save_rate_limits()
                    # Mark first run as complete
                    self.first_run = False
                    return True
                else:
                    logger.error("❌ Failed to register any commands")
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        wait_time = 60 * (2 ** (retry_count - 1))  # Exponential backoff
                        logger.warning(f"Retry {retry_count}/{max_retries}: Waiting {wait_time}s before next attempt")
                        await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error in individual registration: {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    wait_time = 60 * (2 ** (retry_count - 1))  # Exponential backoff
                    logger.warning(f"Retry {retry_count}/{max_retries}: Waiting {wait_time}s before next attempt")
                    await asyncio.sleep(wait_time)
        
        # If we get here, all approaches failed
        logger.error(f"❌ All command registration approaches failed after {max_retries} attempts")
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