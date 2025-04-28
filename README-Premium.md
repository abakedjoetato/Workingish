# Premium Tier System Documentation

This document provides information about the premium tier system and its features.

## Overview

The Discord bot offers three premium tiers:

1. **Survivor (Free Tier)** - Basic functionality for small communities
2. **Warlord (Premium Tier)** - Advanced features for medium-sized communities 
3. **Overseer (Enterprise Tier)** - All features with highest limits for large communities

## Tier Features

### Survivor Tier (Free)
- Track 1 game server
- Basic player statistics 
- Kill feed notifications
- Player linking (main/alt characters)
- Basic leaderboard
- CSV/Log parsing
- No historical data processing

### Warlord Tier (Premium)
- Track up to 3 game servers
- All Survivor features
- Advanced player statistics
- Faction system
- Rivalry tracking
- Connection event notifications
- Mission alerts
- Historical data processing (7 days)
- Advanced kill feed with highlights
- Event tracking

### Overseer Tier (Enterprise)
- Track up to 10 game servers
- All Warlord features
- Extended historical data (30 days)
- Priority support
- Custom branding
- Special server optimizations

## Feature Details

### Basic Player Statistics
- Kills, deaths, and K/D ratio
- Total playtime
- Server-specific statistics

### Advanced Player Statistics
- Weapon usage and proficiency
- Kill distances and accuracy metrics
- Damage dealt and received
- Heatmaps of activity
- Trend analysis over time

### Faction System
- Create and manage player factions
- Automatic role assignment in Discord
- Faction leaderboards
- Faction vs. faction statistics
- Custom faction titles and abbreviations in nicknames

### Rivalry Tracking
- Track prey (players you kill often)
- Track nemesis (players who kill you often)
- Revenge tracking
- Rivalry history and statistics

### Connection Events
- Player join/leave notifications
- Session length tracking
- Connection pattern analysis

### Mission Alerts
- Notifications for in-game missions
- Mission success/failure tracking
- Player participation in missions

### Historical Data Processing
- Process past server logs
- Analyze trends over time
- Access to historical statistics
- Data archiving

## Upgrading Tiers

To upgrade your server to a higher tier:

1. Contact the bot administrator
2. Request the desired tier
3. Complete payment (if applicable)
4. Await confirmation of upgrade

## Tier Limits

| Feature | Survivor (Free) | Warlord (Premium) | Overseer (Enterprise) |
|---------|-----------------|-------------------|------------------------|
| Max Servers | 1 | 3 | 10 |
| History Days | 1 | 7 | 30 |
| Max Factions | 0 | 5 | 15 |
| Max Rivals | 0 | 3 | 10 |
| Batch Processing | No | Yes | Yes |
| Advanced Stats | No | Yes | Yes |
| Faction System | No | Yes | Yes |
| Rivalry Tracking | No | Yes | Yes |

## Commands by Tier

### Survivor Tier Commands
- `/stats player <name>` - View player statistics
- `/stats leaderboard` - View server leaderboard
- `/stats link <player_name>` - Link a player to your Discord account
- `/killfeed channel <channel>` - Set kill feed notification channel
- `/killfeed toggle <enabled>` - Enable/disable kill feed
- `/server add <name> <ip> <port>` - Add a server (limit: 1)
- `/server list` - List tracked servers
- `/server info <name>` - View server information

### Warlord Tier Commands
All Survivor commands, plus:
- `/stats activity <player_name>` - View player activity over time
- `/stats weapons <player_name>` - View player weapon statistics
- `/faction create <name> <abbreviation>` - Create a faction
- `/faction invite <member>` - Invite a member to your faction
- `/faction info` - View faction information
- `/faction list` - List all factions
- `/rivals add <player_name>` - Add a player to your rivals list
- `/rivals list` - View your rivals
- `/connections channel <channel>` - Set connection notification channel
- `/missions channel <channel>` - Set mission notification channel
- `/server reset <name>` - Reprocess historical data

### Overseer Tier Commands
All Warlord commands, plus:
- `/stats extended <player_name>` - View extended statistics
- `/server batch <name>` - Process all historical data
- `/server settings <name>` - Configure advanced server settings
- `/branding set <option> <value>` - Set custom branding options

## Using Premium Features

Each premium feature is automatically available once your server is upgraded to the appropriate tier. Commands that require premium tiers will display an appropriate error message if you attempt to use them without the required tier.

For example:
```
⚠️ This command requires Warlord (Premium) tier, but this server is on Survivor (Free) tier.
Please upgrade to access this feature.
```

## Technical Implementation

The premium tier system is implemented using decorators that check the guild's premium status before executing commands:

```python
@premium_tier_required(tier=1)  # Requires Warlord (Premium) tier
async def premium_command(self, ctx):
    # Command implementation
```

Tier values are mapped as follows:
- 0: Survivor (Free)
- 1: Warlord (Premium)
- 2: Overseer (Enterprise)

The decorator will automatically check the guild's tier from the database and compare it with the required tier. If the guild's tier is lower than required, the command will be rejected with an appropriate message.

The premium tier enforcement is implemented across all feature areas:
- Faction system commands
- Advanced statistical analysis
- Rivalry tracking
- Multiple server management
- Historical data processing

## Support

If you encounter any issues with premium features or have questions about upgrading, please contact the bot administrator.