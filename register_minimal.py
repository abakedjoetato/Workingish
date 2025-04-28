"""
Minimal direct command registration script - registers only the most essential commands.
"""

import os
import logging
import requests
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("command_registrar")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.error("DISCORD_TOKEN not found in environment variables")
    exit(1)

# Discord API endpoints
API_BASE = "https://discord.com/api/v10"
APPLICATION_ID = None  # Will be retrieved from API


def get_application_id():
    """Get the application ID using the bot token"""
    headers = {"Authorization": f"Bot {TOKEN}"}
    
    response = requests.get(f"{API_BASE}/users/@me", headers=headers)
    if response.status_code != 200:
        logger.error(f"Failed to get application info: {response.status_code}")
        logger.error(response.text)
        return None
        
    application_id = response.json().get("id")
    logger.info(f"Retrieved application ID: {application_id}")
    return application_id


def register_commands():
    """Register only the most essential slash commands directly with Discord API"""
    global APPLICATION_ID
    
    # Get application ID if not already set
    if not APPLICATION_ID:
        APPLICATION_ID = get_application_id()
        if not APPLICATION_ID:
            logger.error("Could not retrieve application ID. Exiting.")
            return
    
    # Define minimal core commands - only use the ones that actually matter
    commands = [
        # Root ping command - good for testing the bot is alive
        {
            "name": "ping",
            "description": "Check the bot's response time",
            "type": 1  # CHAT_INPUT
        },
        
        # Server stats command group with subcommands
        {
            "name": "stats",
            "description": "View player and server statistics",
            "type": 1,  # CHAT_INPUT
            "options": [
                {
                    "name": "player",
                    "description": "View detailed statistics for a player",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Player name to search for",
                            "type": 3,  # STRING
                            "required": True
                        }
                    ]
                },
                {
                    "name": "me",
                    "description": "View your own player statistics",
                    "type": 1  # Subcommand
                },
                {
                    "name": "leaderboard",
                    "description": "View player leaderboard",
                    "type": 1  # Subcommand
                }
            ]
        },
        
        # Server command group
        {
            "name": "server",
            "description": "Manage game server connections and settings",
            "type": 1,  # CHAT_INPUT
            "options": [
                {
                    "name": "list",
                    "description": "List all configured servers",
                    "type": 1  # Subcommand
                },
                {
                    "name": "status",
                    "description": "Check the online status and player count of a server",
                    "type": 1  # Subcommand
                }
            ]
        },
        
        # Missions command group (minimal options)
        {
            "name": "missions",
            "description": "View server missions and events",
            "type": 1,  # CHAT_INPUT
            "options": [
                {
                    "name": "list",
                    "description": "List recent server events",
                    "type": 1  # Subcommand
                }
            ]
        }
    ]
    
    # Register the commands
    logger.info(f"Registering {len(commands)} essential commands...")
    
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    url = f"{API_BASE}/applications/{APPLICATION_ID}/commands"
    
    try:
        # Register commands directly via PUT (replaces all existing commands)
        response = requests.put(url, headers=headers, json=commands)
        
        if response.status_code == 429:
            # Handle rate limit
            retry_after = response.json().get("retry_after", 60)
            logger.warning(f"Rate limited! Waiting {retry_after} seconds before retry...")
            
            # Sleep and try again
            import time
            time.sleep(float(retry_after) + 1)
            
            # Try again
            response = requests.put(url, headers=headers, json=commands)
        
        if response.status_code in (200, 201):
            logger.info("✅ Successfully registered essential commands!")
            
            # Log the registered commands
            registered = response.json()
            logger.info(f"Registered {len(registered)} commands with Discord:")
            for cmd in registered:
                name = cmd.get("name", "Unknown")
                logger.info(f"• Command registered: {name}")
        else:
            logger.error(f"❌ Failed to register commands: {response.status_code}")
            logger.error(response.text)
        
        logger.info("Command registration complete!")
        logger.info("Note: It may take up to an hour for commands to appear in Discord")
        
    except Exception as e:
        logger.error(f"Error registering commands: {str(e)}")


if __name__ == "__main__":
    register_commands()