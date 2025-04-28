# Discord Companion Bot

A comprehensive Discord bot for monitoring game servers (primarily Deadside), tracking player statistics, and providing notifications for various game events. Built with Discord.py/py-cord and MongoDB.

## Features

- **Multi-guild Support**: Bot works independently across multiple Discord servers
- **Premium Tiers**: Support for different feature levels based on guild premium status
- **Server Management**: Add/remove/manage multiple game servers
- **Statistics Tracking**: Track player performance, kills, deaths, and more
- **Real-time Notifications**:
  - Player connections
  - Kill feed
  - Server events and missions
  
## Command Structure

The bot uses Discord's slash commands for all functionality. Here are the main command groups:

- `/server` - Server management commands
  - `/server add` - Add a new server to monitor
  - `/server list` - List all configured servers
  - `/server info` - Show details about a specific server
  - `/server remove` - Remove a server from monitoring
  - `/server update` - Update server settings
  - `/server credentials` - Set SFTP credentials for remote log access
  - `/server reset` - Reset parser states for a server

- `/stats` - Statistics commands
  - `/stats player` - View statistics for a specific player
  - `/stats server` - View server statistics
  - `/stats leaderboard` - View top players by various metrics

- `/killfeed` - Killfeed notification commands
  - `/killfeed channel` - Set the channel for killfeed notifications
  - `/killfeed disable` - Disable killfeed notifications

- `/connections` - Connection notification commands
  - `/connections channel` - Set the channel for connection notifications
  - `/connections disable` - Disable connection notifications
  - `/connections list` - List recent player connections

- `/missions` - Mission/event notification commands
  - `/missions channel` - Set the channel for mission notifications
  - `/missions disable` - Disable mission notifications
  - `/missions list` - List recent server events

- `/admin` - Administrative commands (requires permissions)
  - `/admin stats` - View bot statistics
  - `/admin premium` - View/set guild premium tier
  - `/admin link` - Link Discord users to game players
  - `/admin cleanup` - Clean up old data
  - `/admin home` - Set home guild (bot owner only)
  - `/admin purge` - Purge all guild data

## Permissions

- Server Management Commands: Requires `Manage Server` permission
- Administrative Commands: Requires `Administrator` permission
- Regular Commands: Available to all users

## Premium Tiers

- **Free**: Basic functionality with limited servers and features
- **Premium**: More servers, enhanced features
- **Enterprise**: Maximum servers, all features enabled

## Setup

1. Invite the bot to your Discord server
2. Use the `/server add` command to add your first game server
3. Configure notification channels using the channel setup commands
4. Start receiving updates and tracking statistics!

## Technical Details

- Built with py-cord (Discord.py fork)
- MongoDB for database storage
- Async architecture for optimal performance
- Comprehensive error handling and logging
- Remote log parsing via SFTP or local file access