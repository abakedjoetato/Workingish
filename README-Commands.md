# Discord Bot Command Registration System

## Command System Overview

This bot uses Discord's slash commands system with global command registration. This document explains how the command registration system works and how to troubleshoot any issues.

## Key Components

### 1. Bot Command Structure

The bot uses a modular design with commands organized by function:

- **Server Commands** - Manage game server connections and settings
- **Stats Commands** - View player and server statistics 
- **Killfeed Commands** - Configure kill notifications
- **Connection Commands** - Configure player connection notifications
- **Mission Commands** - Configure mission notifications
- **Faction Commands** - Manage player factions and alliances
- **Admin Commands** - Administrative functionality
- **Rivalry Commands** - View and manage player rivalries and relationships
- **Analytics Commands** - Access detailed statistical analytics for servers, players, and factions

Each command category is implemented as a Discord.py "cog" in the `cogs/` directory.

### 2. Command Registration Process

When the bot starts:

1. All cogs are loaded via `load_cogs()` function
2. Each cog's `get_commands()` method is called to collect command definitions
3. Commands are registered globally via `sync_slash_commands()`
4. The bot handles any rate limits during registration

### 3. Rate Limit Handling

Discord imposes strict rate limits on command registration. The bot handles this with:

- Rate limit tracking between restarts
- Exponential backoff with jitter
- Prioritization of critical commands
- Smart retry mechanisms

### 4. Recovery Mechanisms

If command registration fails:

1. The bot will retry on subsequent restarts
2. Manual registration is possible via dedicated scripts
3. A minimum set of essential commands will always be tried first

## Common Issues and Solutions

### Missing Commands

If commands are missing in Discord:

1. **Wait for propagation** - Discord can take up to an hour to propagate global commands
2. **Check rate limits** - The bot may have hit Discord's rate limits
3. **Manually register** - Use `python register_minimal.py` for essential commands

### Rate Limit Errors

If you see rate limit errors in logs:

1. **Wait and retry** - Discord's rate limits typically reset within an hour
2. **Use minimal registration** - Register only essential commands with `register_minimal.py`
3. **Check .discord_rate_limits.json** - This file tracks current rate limit state

### Command Sync Failed

If command sync fails completely:

1. **Run the fixer** - `python unified_command_fix.py` will repair all command-related issues
2. **Verify the fix** - `python verify_commands.py` checks if all components are working
3. **Restart the bot** - After fixes are applied, restart to attempt registration again

## Manual Registration Tools

Several scripts are provided for manual intervention:

- **unified_command_fix.py** - One-step solution to fix all command-related issues
- **verify_commands.py** - Verifies that command fixes have been properly implemented
- **register_commands.py** - Full command registration script
- **register_minimal.py** - Registers only essential commands when rate limited
- **fix_all_commands.py** - Forces a full command sync regardless of rate limits

## Adding New Commands

When adding new commands:

1. Implement your command in the appropriate cog
2. Ensure the cog's `get_commands()` method returns the command
3. Restart the bot to register the new command

Note that global commands can take up to an hour to propagate to all Discord servers.

## Premium Tier Commands 

The bot implements a tiered permission system:

- **Survivor (Free)** - Basic commands for server tracking, killfeed, and player stats
- **Warlord (Premium)** - Adds faction system, rivalry tracking, and advanced features
- **Overseer (Enterprise)** - Adds expanded server limits and all premium features

Commands automatically adjust their behavior based on the guild's subscription tier.

## Analytics Commands

The Analytics command group provides advanced statistical insights for servers, players, and factions. These commands are only available with Warlord (Premium) tier or higher.

### /analytics server

**Description:** Get detailed server analytics and statistics  
**Premium Tier:** Warlord (Premium)  
**Options:**
- `time_period`: Time period in days [1, 7, 14, 30] (default: 7)
- `server_index`: Index of server to use (default: 1)

This command provides comprehensive server statistics including player count trends, peak hours, kill distribution, most active players, and weapon usage.

### /analytics player

**Description:** Get detailed player analytics and statistics  
**Premium Tier:** Warlord (Premium)  
**Options:**
- `player_name`: Player name to search for (partial name search supported)
- `time_period`: Time period in days [1, 7, 14, 30] (default: 7)
- `server_index`: Index of server to use (default: 1)

This command provides in-depth player statistics including K/D ratio trends, favorite weapons, activity patterns, and performance metrics.

### /analytics player_by_id

**Description:** Get detailed player analytics and statistics using exact Steam ID  
**Premium Tier:** Warlord (Premium)  
**Options:**
- `player_id`: Steam ID of the player
- `time_period`: Time period in days [1, 7, 14, 30] (default: 7)

Use this command when you need to look up a specific player by their Steam ID rather than name.

### /analytics leaderboard

**Description:** Get server leaderboard with various sorting options  
**Premium Tier:** Warlord (Premium)  
**Options:**
- `sort_by`: Stat to sort by ["kills", "kd", "distance"] (default: "kills")
- `time_period`: Time period in days [0, 1, 7, 14, 30] (default: 7, 0 = all-time)
- `server_index`: Index of server to use (default: 1)

Shows the top players on your server with customizable sorting options.

### /analytics faction

**Description:** Get detailed analytics for a specific faction  
**Premium Tier:** Warlord (Premium)  
**Options:**
- `faction_id`: ID of the faction
- `time_period`: Time period in days [1, 7, 14, 30] (default: 7)

Provides faction-level statistics including total kills, K/D ratio, active members, and faction rivalries.

### /analytics factions

**Description:** List all factions for easy reference  
**Premium Tier:** Warlord (Premium)

Shows a list of all factions on the server with their IDs for use with other faction commands.