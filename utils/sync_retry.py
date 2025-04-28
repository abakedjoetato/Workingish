"""
Discord Command Synchronization with Rate Limit Handling

This module provides utilities for safely synchronizing commands with Discord's API,
handling rate limits gracefully and providing retry mechanisms.
"""

import logging
import json
import asyncio
import time
import os
import sys
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord.http import Route

logger = logging.getLogger('deadside_bot.utils.sync_retry')

# Constants for rate limit handling
SYNC_COOLDOWN = 60 * 60  # 1 hour in seconds
LAST_SYNC_FILE = ".last_command_check.txt"

class CommandSyncManager:
    """Manages command synchronization with Discord API"""
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limits = {}
        self.last_sync_time = self._load_last_sync()
    
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
    
    async def is_recent_sync(self):
        """Check if we've synced commands recently"""
        if not self.last_sync_time:
            return False
            
        # Check if it's been less than the cooldown period
        now = datetime.now()
        time_since_sync = (now - self.last_sync_time).total_seconds()
        return time_since_sync < SYNC_COOLDOWN
    
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
            
            # Log rate limit info
            path = str(response.url)
            logger.warning(f"Rate limited on {path} - retry after {retry_after}s")
            
            # Store rate limit info for this path
            self.rate_limits[path] = {
                "retry_after": retry_after,
                "reset_at": datetime.now() + timedelta(seconds=retry_after)
            }
            
            # If we have command info, log it
            if command:
                logger.info(f"Rate limited while processing command: {command}")
        except Exception as e:
            logger.error(f"Error handling rate limit: {e}")
    
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
        """Register commands with Discord with rate limit handling"""
        if not self.bot.application_id:
            logger.error("No application ID available")
            return False
            
        try:
            # Get the route for registering global commands
            route = Route("PUT", f"/applications/{self.bot.application_id}/commands")
            
            # Check for rate limits
            if not await self.should_retry(str(route.url)):
                await self.wait_for_rate_limit(str(route.url))
            
            # Make the request
            await self.bot.http.request(route, json=commands_payload)
            
            # Update last sync time
            self.last_sync_time = datetime.now()
            self._save_last_sync(self.last_sync_time)
            
            return True
        except discord.HTTPException as e:
            # Handle rate limits
            if e.status == 429:
                await self.handle_rate_limit(e, "register_commands")
                return False
            logger.error(f"HTTP error registering commands: {e}")
            return False
        except Exception as e:
            logger.error(f"Error registering commands: {e}")
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