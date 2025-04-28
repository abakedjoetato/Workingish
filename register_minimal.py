"""
Minimal direct command registration script - registers only the most essential commands.
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def get_application_id():
    """Get the application ID using the bot token"""
    headers = {
        "Authorization": f"Bot {TOKEN}"
    }
    
    response = requests.get(
        "https://discord.com/api/v10/applications/@me",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error retrieving application ID: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    return data["id"]

def register_commands():
    """Register only the most essential slash commands directly with Discord API"""
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables")
        return False
    
    # Get application ID
    application_id = get_application_id()
    if not application_id:
        print("Could not retrieve application ID. Exiting.")
        return False
    
    # Minimal commands to register
    commands = [
        # Add ping command
        {
            "name": "ping",
            "description": "Check the bot's response time",
            "type": 1
        },
        
        # Add commands menu
        {
            "name": "commands",
            "description": "Interactive command guide with detailed information",
            "type": 1
        }
    ]
    
    # Set up Discord API request
    url = f"https://discord.com/api/v10/applications/{application_id}/commands"
    
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Register commands
    for command in commands:
        command_name = command["name"]
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=command
            )
            
            if response.status_code == 429:  # Rate limit
                retry_after = response.json().get("retry_after", 60)
                print(f"Rate limited when registering {command_name}, retrying after {retry_after}s")
                time.sleep(retry_after + 1)  # Add 1s buffer
                
                # Try again after waiting
                response = requests.post(
                    url,
                    headers=headers,
                    json=command
                )
            
            if response.status_code in (200, 201):
                print(f"Successfully registered command: {command_name}")
            else:
                print(f"Error registering command {command_name}: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"Exception when registering command {command_name}: {e}")
            
    print("Command registration complete. Check Discord after a few minutes.")
    print("Note: It may take up to an hour for commands to appear due to Discord's caching.")
    return True

if __name__ == "__main__":
    print("Starting minimal command registration")
    register_commands()