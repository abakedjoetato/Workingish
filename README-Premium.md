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

The premium tier system is implemented using advanced decorators that check the guild's premium status before executing commands, with comprehensive error handling, caching, and consistent messaging.

### Premium Tier Decorator

```python
@premium_tier_required(tier=1)  # Requires Warlord (Premium) tier
async def premium_command(self, ctx):
    # Command implementation
```

This decorator performs several functions:
1. Retrieves the guild's premium tier from the database (with caching)
2. Compares the guild's tier with the required tier for the command
3. Either allows the command to proceed or returns a helpful error message
4. Logs the access attempt for analytics
5. Provides consistent user feedback

### Tier Mapping System

Tier values are consistently mapped as follows across the entire application:
- 0: Survivor (Free) - Our base tier with core functionality
- 1: Warlord (Premium) - Mid-tier with enhanced features
- 2: Overseer (Enterprise) - Top tier with all features and limits removed

This consistent naming and numbering convention is maintained throughout the code to ensure stability and readability.

### Premium Tier Enforcement

The premium tier enforcement is robustly implemented across all feature areas:

- **Faction system commands** - All faction creation and management requires Warlord tier or higher
- **Advanced statistical analysis** - Detailed statistics require premium access
- **Rivalry tracking** - Player rivalry management requires Warlord tier
- **Multiple server management** - Limited to a single server in Survivor tier
- **Historical data processing** - Limited retention or disabled in free tier

### Implementation Details

The premium tier system is built with several key design principles:

1. **Centralized logic**: All premium tier checks are handled by the same core functions
2. **Clear messaging**: Users receive specific feedback about the tier requirements
3. **Graceful degradation**: Features are selectively enabled or limited rather than completely failing
4. **Consistent naming**: Tier names and numbering are consistent across all user-facing elements
5. **Optimized performance**: Database lookups for premium status are cached to minimize performance impact
6. **Extensive testing**: Premium tier enforcement is automatically tested with the command testing framework

### Database Schema

Premium tier information is stored in the guild_configs collection with the following structure:

```json
{
  "guild_id": "discord_guild_id",
  "premium_tier": "warlord",
  "tier_updated_at": "2025-04-01T12:00:00Z",
  "tier_expiry": "2026-04-01T12:00:00Z"
}
```

### Upgrade Workflow

When a guild is upgraded:
1. The database record is updated with the new tier and timestamp
2. All caches are immediately invalidated
3. New capabilities become available without requiring restart
4. The upgrade is logged for audit purposes
5. Users are notified of the new capabilities

## Support

If you encounter any issues with premium features or have questions about upgrading, please contact the bot administrator.