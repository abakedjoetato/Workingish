"""
Direct command registration script for Discord bot.
Run this separately from the main bot to register commands when needed.
"""

import asyncio
import os
import logging
import json
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
    """Register slash commands directly with Discord API"""
    global APPLICATION_ID
    
    # Get application ID if not already set
    if not APPLICATION_ID:
        APPLICATION_ID = get_application_id()
        if not APPLICATION_ID:
            logger.error("Could not retrieve application ID. Exiting.")
            return
    
    # Define the command structure
    commands = [
        # Root ping command
        {
            "name": "ping",
            "description": "Check the bot's response time",
            "type": 1  # CHAT_INPUT
        },
        
        # Root commands menu
        {
            "name": "commands",
            "description": "Interactive command guide with detailed information",
            "type": 1  # CHAT_INPUT
        },
        
        # Stats command group with subcommands
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
                        },
                        {
                            "name": "server",
                            "description": "Server to filter stats by (optional)",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                },
                {
                    "name": "me",
                    "description": "View your own player statistics",
                    "type": 1  # Subcommand
                },
                {
                    "name": "link",
                    "description": "Link your Discord account to a player name",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "player_name",
                            "description": "Your in-game player name",
                            "type": 3,  # STRING
                            "required": True
                        }
                    ]
                },
                {
                    "name": "unlink",
                    "description": "Unlink your Discord account from a player name",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "player_name",
                            "description": "Player name to unlink (leave empty to unlink all)",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                },
                {
                    "name": "server",
                    "description": "View server-wide statistics",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Server name to view stats for",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                },
                {
                    "name": "leaderboard",
                    "description": "View player leaderboard",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "category",
                            "description": "Stat category to rank by",
                            "type": 3,  # STRING
                            "required": False,
                            "choices": [
                                {"name": "Kills", "value": "kills"},
                                {"name": "Deaths", "value": "deaths"},
                                {"name": "K/D Ratio", "value": "kd"},
                                {"name": "Playtime", "value": "playtime"},
                                {"name": "Headshots", "value": "headshots"}
                            ]
                        },
                        {
                            "name": "limit",
                            "description": "Number of players to show (default: 10)",
                            "type": 4,  # INTEGER
                            "required": False,
                            "min_value": 3,
                            "max_value": 25
                        }
                    ]
                },
                {
                    "name": "weapons",
                    "description": "View weapon usage statistics",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "player",
                            "description": "Player to view weapon stats for (leave empty for all players)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "server",
                            "description": "Server to filter stats by",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                }
            ]
        },
        
        # Server command group with subcommands
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
                    "name": "info",
                    "description": "View detailed information about a server",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Server name to show info for",
                            "type": 3,  # STRING
                            "required": True
                        }
                    ]
                },
                {
                    "name": "status",
                    "description": "Check the online status and player count of a server",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Server name to check (leave empty for all servers)",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                },
                {
                    "name": "add",
                    "description": "Add a new game server to track",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "A unique name for the server",
                            "type": 3,  # STRING
                            "required": True
                        },
                        {
                            "name": "host",
                            "description": "Server hostname or IP address",
                            "type": 3,  # STRING
                            "required": True
                        },
                        {
                            "name": "game_port",
                            "description": "Game server port (default: 27015)",
                            "type": 4,  # INTEGER
                            "required": True
                        },
                        {
                            "name": "query_port",
                            "description": "Query port (default: same as game_port)",
                            "type": 4,  # INTEGER
                            "required": False
                        },
                        {
                            "name": "rcon_port",
                            "description": "RCON port (default: none)",
                            "type": 4,  # INTEGER
                            "required": False
                        },
                        {
                            "name": "rcon_password",
                            "description": "RCON password (optional)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "ftp_host",
                            "description": "FTP host for log access (optional)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "ftp_port",
                            "description": "FTP port (default: 21)",
                            "type": 4,  # INTEGER
                            "required": False
                        },
                        {
                            "name": "ftp_user",
                            "description": "FTP username (optional)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "ftp_password",
                            "description": "FTP password (optional)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "csv_path",
                            "description": "Path to CSV files on FTP server (optional)",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "log_path",
                            "description": "Path to log files on FTP server (optional)",
                            "type": 3,  # STRING
                            "required": False
                        }
                    ]
                },
                {
                    "name": "remove",
                    "description": "Remove a server from tracking",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Server name to remove",
                            "type": 3,  # STRING
                            "required": True
                        },
                        {
                            "name": "confirm",
                            "description": "Type the server name again to confirm deletion",
                            "type": 3,  # STRING
                            "required": True
                        }
                    ]
                },
                {
                    "name": "edit",
                    "description": "Edit server connection settings",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "name",
                            "description": "Server name to edit",
                            "type": 3,  # STRING
                            "required": True
                        },
                        {
                            "name": "setting",
                            "description": "Setting to change",
                            "type": 3,  # STRING
                            "required": True,
                            "choices": [
                                {"name": "Host Address", "value": "host"},
                                {"name": "Game Port", "value": "game_port"},
                                {"name": "Query Port", "value": "query_port"},
                                {"name": "RCON Port", "value": "rcon_port"},
                                {"name": "RCON Password", "value": "rcon_password"},
                                {"name": "FTP Host", "value": "ftp_host"},
                                {"name": "FTP Port", "value": "ftp_port"},
                                {"name": "FTP Username", "value": "ftp_user"},
                                {"name": "FTP Password", "value": "ftp_password"},
                                {"name": "CSV Path", "value": "csv_path"},
                                {"name": "Log Path", "value": "log_path"}
                            ]
                        },
                        {
                            "name": "value",
                            "description": "New value for the setting",
                            "type": 3,  # STRING
                            "required": True
                        }
                    ]
                }
            ]
        },
        
        # Killfeed command group with subcommands
        {
            "name": "killfeed",
            "description": "Configure and manage killfeed notifications",
            "type": 1,  # CHAT_INPUT
            "options": [
                {
                    "name": "channel",
                    "description": "Set the channel for killfeed notifications",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "channel",
                            "description": "Channel to send notifications to",
                            "type": 7,  # CHANNEL
                            "required": False
                        }
                    ]
                },
                {
                    "name": "disable",
                    "description": "Disable killfeed notifications for this guild",
                    "type": 1  # Subcommand
                }
            ]
        },
        
        # Connections command group with subcommands
        {
            "name": "connections",
            "description": "Configure and view player connection notifications",
            "type": 1,  # CHAT_INPUT
            "options": [
                {
                    "name": "channel",
                    "description": "Set the channel for connection notifications",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "channel",
                            "description": "Channel to send notifications to",
                            "type": 7,  # CHANNEL
                            "required": False
                        }
                    ]
                },
                {
                    "name": "disable",
                    "description": "Disable connection notifications for this guild",
                    "type": 1  # Subcommand
                },
                {
                    "name": "list",
                    "description": "List recent player connections for a server",
                    "type": 1,  # Subcommand
                    "options": [
                        {
                            "name": "server_name",
                            "description": "Server name to show connections for",
                            "type": 3,  # STRING
                            "required": False
                        },
                        {
                            "name": "limit",
                            "description": "Number of connections to show (max: 20)",
                            "type": 4,  # INTEGER
                            "required": False,
                            "min_value": 1,
                            "max_value": 20
                        }
                    ]
                }
            ]
        }
    ]
    
    # Register the commands
    # We're going to use a more efficient approach by registering all at once
    
    logger.info(f"Registering all {len(commands)} global commands in a single request...")
    
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    url = f"{API_BASE}/applications/{APPLICATION_ID}/commands"
    
    # Just register all commands in one go using PUT
    # This replaces all existing commands with the new set, avoiding the need to clear first
    try:
        # Register all commands in a single bulk request
        response = requests.put(url, headers=headers, json=commands)
        
        if response.status_code == 429:
            # Handle rate limit
            retry_data = response.json()
            retry_after = retry_data.get("retry_after", 60)
            logger.warning(f"Rate limited! Waiting {retry_after} seconds before retry...")
            
            # Sleep and try again
            import time
            time.sleep(float(retry_after) + 1)
            
            # Try again
            response = requests.put(url, headers=headers, json=commands)
        
        if response.status_code in (200, 201):
            logger.info("✅ Successfully registered all commands in a single request!")
            
            # Log the registered commands
            registered = response.json()
            logger.info(f"Registered {len(registered)} commands with Discord:")
            for cmd in registered:
                name = cmd.get("name", "Unknown")
                cmd_type = cmd.get("type", 1)
                
                if cmd.get("options"):
                    subcmds = [opt.get("name") for opt in cmd.get("options") if opt.get("type") == 1]
                    if subcmds:
                        logger.info(f"• Command Group '{name}' with subcommands: {', '.join(subcmds)}")
                    else:
                        logger.info(f"• Command '{name}'")
                else:
                    logger.info(f"• Command '{name}'")
        else:
            logger.error(f"❌ Failed to register commands: {response.status_code}")
            logger.error(response.text)
        
        logger.info("Command registration complete!")
        logger.info("Note: It may take up to an hour for commands to appear in Discord")
        
    except Exception as e:
        logger.error(f"Error registering commands: {str(e)}")


if __name__ == "__main__":
    register_commands()