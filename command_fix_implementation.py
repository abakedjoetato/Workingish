"""
Comprehensive Discord Bot Command System Fix

This script implements all the necessary fixes for the Discord bot's command registration system.
It can be run in standalone mode to manually force command registration.
"""

import os
import json
import asyncio
import time
import logging
import discord
import sys
from datetime import datetime, timedelta
import importlib
import inspect
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deadside_bot.command_fix')

# Constants
LAST_SYNC_FILE = ".last_command_check.txt"
SYNC_COOLDOWN = 60 * 60  # 1 hour in seconds

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

async def get_application_id():
    """Get the application ID using the bot token"""
    if not DISCORD_TOKEN:
        logger.error("No Discord token found in environment")
        return None
        
    try:
        # Create a temp client to get the application ID
        intents = discord.Intents.none()
        client = discord.Client(intents=intents)
        await client.login(DISCORD_TOKEN)
        app_id = client.application_id
        await client.close()
        return app_id
    except Exception as e:
        logger.error(f"Error getting application ID: {e}")
        return None

async def load_rate_limits():
    """Load saved rate limit information"""
    try:
        if os.path.exists("command_rate_limits.json"):
            with open("command_rate_limits.json", "r") as f:
                rate_limits = json.load(f)
                
                # Convert timestamps back to datetime
                for path in rate_limits:
                    if "reset_at" in rate_limits[path]:
                        timestamp = rate_limits[path]["reset_at"]
                        rate_limits[path]["reset_at"] = datetime.fromtimestamp(timestamp)
                        
                return rate_limits
    except Exception as e:
        logger.error(f"Error loading rate limits: {e}")
    return {}

async def save_rate_limits(rate_limits):
    """Save rate limit information for future use"""
    try:
        # Convert datetime objects to timestamps for serialization
        serializable_limits = {}
        for path in rate_limits:
            serializable_limits[path] = rate_limits[path].copy()
            if "reset_at" in serializable_limits[path]:
                if isinstance(serializable_limits[path]["reset_at"], datetime):
                    serializable_limits[path]["reset_at"] = serializable_limits[path]["reset_at"].timestamp()
        
        with open("command_rate_limits.json", "w") as f:
            json.dump(serializable_limits, f)
    except Exception as e:
        logger.error(f"Error saving rate limits: {e}")

async def handle_rate_limit(error, command=None):
    """Handle a rate limit error by extracting info and saving state"""
    if not hasattr(error, "response") or not error.response:
        return
        
    try:
        # Extract rate limit info
        response = error.response
        data = json.loads(await response.text())
        retry_after = data.get("retry_after", 5)
        
        # Load current rate limits
        rate_limits = await load_rate_limits()
        
        # Update with new info
        path = str(response.url)
        logger.warning(f"Rate limited on {path} - retry after {retry_after}s")
        
        rate_limits[path] = {
            "retry_after": retry_after,
            "reset_at": datetime.now() + timedelta(seconds=retry_after)
        }
        
        # Save updated rate limits
        await save_rate_limits(rate_limits)
        
        # Log command info if provided
        if command:
            logger.info(f"Rate limited while registering command: {command}")
    except Exception as e:
        logger.error(f"Error handling rate limit: {e}")

async def register_commands_safely(commands_payload):
    """Register commands with careful rate limit handling"""
    app_id = await get_application_id()
    if not app_id:
        logger.error("Failed to get application ID")
        return False
        
    try:
        from discord.http import Route
        
        # Create HTTP client for Discord API requests
        http = discord.http.HTTPClient()
        await http.static_login(DISCORD_TOKEN)
        
        # Get route for registering global commands
        route = Route("PUT", f"/applications/{app_id}/commands")
        
        # Load rate limits and check if we're rate limited
        rate_limits = await load_rate_limits()
        path = str(route.url)
        
        if path in rate_limits:
            limit_info = rate_limits[path]
            now = datetime.now()
            
            if "reset_at" in limit_info and isinstance(limit_info["reset_at"], datetime):
                if now < limit_info["reset_at"]:
                    wait_time = (limit_info["reset_at"] - now).total_seconds()
                    logger.info(f"Still rate limited for {wait_time:.1f}s, waiting...")
                    await asyncio.sleep(wait_time)
        
        # Make the request
        try:
            response = await http.request(route, json=commands_payload)
            logger.info(f"Commands registered successfully: {len(commands_payload)} commands")
            
            # Update last sync timestamp
            try:
                with open(LAST_SYNC_FILE, "w") as f:
                    f.write(str(time.time()))
            except Exception as ts_err:
                logger.error(f"Error saving sync timestamp: {ts_err}")
                
            return True
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limit
                await handle_rate_limit(e)
                return False
            else:
                logger.error(f"HTTP error registering commands: {e}")
                return False
        finally:
            await http.close()
    except Exception as e:
        logger.error(f"Error registering commands: {e}")
        return False

def generate_minimal_commands():
    """Generate minimal command structures for critical functionality"""
    minimal_commands = [
        {
            "name": "server",
            "description": "Server management commands",
            "options": [
                {
                    "name": "add",
                    "description": "Add a new server to monitor",
                    "type": 1,  # SUB_COMMAND
                    "options": [
                        {"name": "name", "description": "Server name", "type": 3, "required": True},
                        {"name": "host", "description": "Server host/IP", "type": 3, "required": True},
                        {"name": "port", "description": "Server port", "type": 4, "required": True}
                    ]
                },
                {
                    "name": "list",
                    "description": "List all registered servers",
                    "type": 1  # SUB_COMMAND
                }
            ]
        },
        {
            "name": "stats",
            "description": "View server statistics",
            "options": [
                {
                    "name": "player",
                    "description": "View player statistics",
                    "type": 1,  # SUB_COMMAND
                    "options": [
                        {"name": "player_name", "description": "Player name", "type": 3, "required": True}
                    ]
                },
                {
                    "name": "leaderboard",
                    "description": "View server leaderboard",
                    "type": 1  # SUB_COMMAND
                }
            ]
        }
    ]
    
    return minimal_commands

async def is_recent_sync():
    """Check if we've successfully synced commands recently"""
    try:
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, "r") as f:
                timestamp = float(f.read().strip())
                last_sync = datetime.fromtimestamp(timestamp)
                
                # Check if it's been less than the cooldown period
                now = datetime.now()
                time_since_sync = (now - last_sync).total_seconds()
                return time_since_sync < SYNC_COOLDOWN
    except Exception as e:
        logger.error(f"Error checking last sync time: {e}")
    return False

async def safe_command_sync(force=False):
    """
    Safely synchronize commands with advanced rate limit handling
        
    Args:
        force: Force a full sync even if recent
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    # Check if we've recently synced
    if not force and await is_recent_sync():
        logger.info("Commands were synced recently, skipping")
        return True
    
    try:
        # Generate minimal commands
        commands = generate_minimal_commands()
        
        # Register commands
        return await register_commands_safely(commands)
    except Exception as e:
        logger.error(f"Error in safe_command_sync: {e}")
        return False

async def main():
    """Main entry point for the command registration script"""
    logger.info("Starting command registration fix")
    
    # Force command registration
    try:
        # Clear last sync time to force a registration
        if os.path.exists(LAST_SYNC_FILE):
            os.remove(LAST_SYNC_FILE)
            logger.info("Cleared sync timestamp to force registration")
            
        result = await safe_command_sync(force=True)
        
        if result:
            logger.info("Command registration completed successfully")
        else:
            logger.error("Command registration failed")
    except Exception as e:
        logger.error(f"Error executing command fix: {e}")
    
    logger.info("Command registration process complete")

if __name__ == "__main__":
    asyncio.run(main())