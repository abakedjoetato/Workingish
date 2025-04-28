# Discord Bot API Documentation

This document provides detailed information about the Discord bot's API, including database models, command structures, and utility functions.

## Database Models

### Server Model
Represents a game server tracked by the bot.

#### Properties:
- `_id`: MongoDB ObjectId
- `name`: String - Server name
- `guild_id`: String - Discord guild ID
- `description`: String - Optional server description
- `ip`: String - Server IP address
- `port`: Integer - Server port
- `added_at`: Date - When the server was added
- `updated_at`: Date - When the server was last updated
- `csv_path`: String - Path to CSV files
- `log_path`: String - Path to log files
- `csv_enabled`: Boolean - Whether CSV parsing is enabled
- `log_enabled`: Boolean - Whether log parsing is enabled
- `query_enabled`: Boolean - Whether game querying is enabled
- `auth_type`: String (enum: "none", "password", "key") - Authentication type

#### Methods:
- `get_by_name(db, name, guild_id)` - Get a server by name in a guild
- `get_all_for_guild(db, guild_id)` - Get all servers for a guild
- `create(db, name, guild_id, ...)` - Create a new server
- `update(db)` - Save changes to the server
- `delete(db)` - Delete the server

### Player Model
Represents a player in the game.

#### Properties:
- `_id`: MongoDB ObjectId
- `player_id`: String - Unique player ID
- `player_name`: String - Player's in-game name
- `server_id`: String - ID of the server
- `discord_id`: String - Discord user ID if linked
- `first_seen`: Date - When the player was first seen
- `last_seen`: Date - When the player was last seen
- `total_kills`: Integer - Total number of kills
- `total_deaths`: Integer - Total number of deaths
- `total_suicides`: Integer - Total number of suicides
- `total_damage_dealt`: Double - Total damage dealt
- `total_damage_taken`: Double - Total damage taken
- `longest_kill_distance`: Double - Longest kill distance

#### Methods:
- `get_by_id(db, player_id)` - Get a player by ID
- `get_by_name(db, name, server_id)` - Get a player by name on a server
- `get_by_discord_id(db, discord_id)` - Get all players linked to a Discord user
- `create(db, player_id, player_name, server_id, ...)` - Create a new player
- `update(db)` - Save changes to the player
- `link_discord(db, discord_id)` - Link the player to a Discord user
- `unlink_discord(db)` - Unlink the player from Discord

### Kill Model
Represents a kill event in the game.

#### Properties:
- `_id`: MongoDB ObjectId
- `killer_id`: String - ID of the killer player
- `victim_id`: String - ID of the victim player
- `server_id`: String - ID of the server
- `timestamp`: Date - When the kill occurred
- `weapon`: String - Weapon used
- `distance`: Double - Distance of the kill
- `damage`: Double - Damage dealt
- `is_headshot`: Boolean - Whether it was a headshot
- `is_suicide`: Boolean - Whether it was a suicide
- `source_file`: String - Source file where the kill was found

#### Methods:
- `create(db, killer_id, victim_id, server_id, ...)` - Create a new kill
- `get_by_player(db, player_id, as_killer=True, limit=100)` - Get kills by a player
- `get_kills_between(db, player1_id, player2_id)` - Get kills between two players

### Faction Model
Represents a player faction.

#### Properties:
- `_id`: MongoDB ObjectId
- `name`: String - Faction name
- `abbreviation`: String - Faction abbreviation
- `guild_id`: String - Discord guild ID
- `leader_id`: String - Discord user ID of leader
- `members`: Array of Strings - Discord user IDs of members
- `role_id`: String - Discord role ID
- `created_at`: Date - When the faction was created
- `updated_at`: Date - When the faction was last updated

#### Methods:
- `get_by_name(db, name, guild_id)` - Get a faction by name
- `get_by_abbreviation(db, abbreviation, guild_id)` - Get a faction by abbreviation
- `get_by_member(db, member_id, guild_id)` - Get a faction by member
- `get_all_for_guild(db, guild_id)` - Get all factions for a guild
- `create(db, name, abbreviation, guild_id, ...)` - Create a new faction
- `update(db)` - Save changes to the faction
- `delete(db)` - Delete the faction

### GuildConfig Model
Represents Discord guild configuration.

#### Properties:
- `_id`: MongoDB ObjectId
- `guild_id`: String - Discord guild ID
- `premium_tier`: String - Premium tier
- `tier_updated_at`: Date - When the tier was updated
- `killfeed_channel`: String - Channel ID for killfeed
- `killfeed_enabled`: Boolean - Whether killfeed is enabled
- `mission_channel`: String - Channel ID for missions
- `mission_enabled`: Boolean - Whether missions are enabled
- `connection_channel`: String - Channel ID for connections
- `connection_enabled`: Boolean - Whether connections are enabled

#### Methods:
- `get_by_guild_id(db, guild_id)` - Get config for a guild
- `update(db)` - Save changes to the config

## Command Structure

All commands use Discord's slash command system and are organized in command groups.

### Command Groups
- `server` - Commands for managing game servers
- `stats` - Commands for viewing player statistics
- `killfeed` - Commands for managing kill notifications
- `missions` - Commands for mission alerts
- `connections` - Commands for connection notifications
- `faction` - Commands for managing factions
- `admin` - Administrative commands

### Command Examples
```python
@server_group.command(name="add", description="Add a new server")
async def add_server(self, ctx, 
                     name: discord.Option(str, "Server name", required=True),
                     ip: discord.Option(str, "Server IP address", required=True),
                     port: discord.Option(int, "Server port", required=True),
                     description: discord.Option(str, "Server description", required=False) = None):
    # Command implementation
```

## Utility Functions

### Premium Tier System
The `utils/premium.py` module handles premium tier checks.

#### Functions:
- `get_guild_tier(db, guild_id)` - Get the premium tier for a guild
- `check_feature_access(db, guild_id, feature)` - Check if a guild has access to a feature
- `get_max_servers(db, guild_id)` - Get the maximum number of servers a guild can have
- `count_guild_servers(db, guild_id)` - Count the number of servers a guild has
- `update_guild_tier(db, guild_id, tier)` - Update a guild's tier

### Command Decorators
The `utils/decorators.py` module provides decorators for command validation.

#### Decorators:
- `@premium_required(feature)` - Check if a guild has access to a premium feature
- `@server_limit_check()` - Check if a guild has reached its server limit
- `@guild_admin_required()` - Check if a user has administrator permissions
- `@bot_owner_only()` - Check if a user is the bot owner

### Error Handling
The `utils/error_handler.py` module provides error handling utilities.

#### Functions:
- `handle_command_error(ctx, error)` - Handle command errors
- `log_error_to_database(ctx, error, db)` - Log errors to the database
- `format_error_embed(error_message)` - Format error messages as embeds
- `handle_database_error(ctx, error, operation)` - Handle database errors
- `handle_http_error(ctx, error, operation)` - Handle HTTP errors

### Guild Isolation
The `utils/guild_isolation.py` module ensures data isolation between guilds.

#### Functions:
- `get_guild_servers(db, guild_id)` - Get servers for a specific guild
- `get_server_by_name(db, name, guild_id)` - Get a server by name for a guild
- `is_server_in_guild(db, server_id, guild_id)` - Check if a server belongs to a guild

### Embeds
The `utils/embeds.py` module provides standardized embeds for responses.

#### Functions:
- `create_basic_embed(title, description, color)` - Create a basic embed
- `create_server_embed(server)` - Create an embed for server info
- `create_player_embed(player, server)` - Create an embed for player stats
- `create_kill_embed(kill, server)` - Create an embed for a kill
- `create_faction_embed(faction, guild)` - Create an embed for faction info
- `create_leaderboard_embed(players, title)` - Create a leaderboard embed

### Testing
The `utils/command_test.py` module provides utilities for testing commands.

#### Functions:
- `test_database_connection(db)` - Test the database connection
- `test_command_permissions(bot, command_name)` - Test command permissions
- `test_premium_tier_checks(db, guild_id, feature)` - Test premium tier checks
- `verify_command_registration(bot, expected_commands)` - Verify command registration
- `run_command_tests(bot, guild_id)` - Run a comprehensive test suite

## Database Schema Validation

The `database/schema.py` module provides schema validation for MongoDB collections.

#### Functions:
- `apply_schema_validations(db)` - Apply schema validations to collections
- `validate_collection_data(db, collection_name)` - Validate existing data

## Command Registration

The `utils/sync_retry.py` module handles command registration with Discord.

#### Functions:
- `setup(bot)` - Initialize the module with the bot instance
- `safe_command_sync(bot, force=False)` - Sync commands with Discord with retry logic
- `register_commands_individually(bot, commands)` - Register commands one by one

## Command Fix Utilities

The `utils/command_fix.py` module fixes Discord API object attributes.

#### Functions:
- `apply_command_fixes(bot)` - Apply fixes to all commands
- `fix_integration_types(command)` - Fix integration_types attribute
- `fix_contexts(command)` - Fix contexts attribute