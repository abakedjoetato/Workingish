import os

# Bot configuration
TOKEN = os.getenv("DISCORD_TOKEN", "")
PREFIX = os.getenv("COMMAND_PREFIX", "!")
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

# Database configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/discord_bot")
DATABASE_NAME = os.getenv("MONGODB_DB", "discord_bot")
DATABASE_URL = os.getenv("DATABASE_URL")

# Parser configuration
PARSER_INTERVAL = int(os.getenv("PARSER_INTERVAL", "300"))  # 5 minutes in seconds

# Default premium tiers
PREMIUM_TIERS = {
    "free": {
        "max_servers": 1,
        "historical_parsing": False,
        "max_history_days": 0,
        "custom_embeds": False,
        "advanced_stats": False,
        "faction_system": False,
        "rivalry_tracking": False,
        "connection_tracking": False,  # Changed to premium
        "killfeed": True,
        "basic_stats": False,  # Changed to premium
        "player_linking": True,
        "mission_tracking": False,  # Changed to premium
        "leaderboard": True,
        "csv_parsing": True,
        "log_parsing": True
    },
    "premium": {
        "max_servers": 3,
        "historical_parsing": True,
        "max_history_days": 7,
        "custom_embeds": True,
        "advanced_stats": True,
        "faction_system": True,
        "rivalry_tracking": True,
        "connection_tracking": True,
        "killfeed": True,
        "basic_stats": True,
        "player_linking": True,
        "mission_tracking": True,
        "leaderboard": True,
        "csv_parsing": True,
        "log_parsing": True
    },
    "enterprise": {
        "max_servers": 10,
        "historical_parsing": True,
        "max_history_days": 30,
        "custom_embeds": True,
        "advanced_stats": True,
        "faction_system": True,
        "rivalry_tracking": True,
        "connection_tracking": True,
        "killfeed": True,
        "basic_stats": True,
        "player_linking": True,
        "mission_tracking": True,
        "leaderboard": True,
        "csv_parsing": True,
        "log_parsing": True
    }
}

# File access defaults
DEFAULT_PORT = 22
SSH_TIMEOUT = 10

# Default embed colors
COLORS = {
    "primary": 0x5865F2,     # Discord Blurple
    "success": 0x57F287,     # Green
    "danger": 0xED4245,      # Red
    "warning": 0xFEE75C,     # Yellow
    "info": 0x5865F2,        # Light Blue
    "neutral": 0x99AAB5      # Gray
}

# Default messages
MESSAGES = {
    "no_servers": "No servers configured. Use `!server add` to add a server.",
    "no_permission": "You don't have permission to use this command.",
    "command_success": "Command executed successfully.",
    "command_error": "An error occurred while executing the command.",
    "server_added": "Server added successfully.",
    "server_removed": "Server removed successfully.",
    "server_updated": "Server updated successfully.",
    "parser_started": "Parser started successfully.",
    "parser_stopped": "Parser stopped successfully.",
    "parser_error": "An error occurred while parsing logs.",
    "player_linked": "Player linked to Discord account successfully.",
    "player_unlinked": "Player unlinked from Discord account successfully."
}
