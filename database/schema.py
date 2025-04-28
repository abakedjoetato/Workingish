"""
MongoDB Schema Validation

This module provides schema validation for MongoDB collections to ensure data integrity.
It includes validation schemas for all collections and functions to apply the schemas.
"""

import logging
from datetime import datetime

logger = logging.getLogger('deadside_bot.database.schema')

# Define schemas for collections
SCHEMAS = {
    "servers": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "guild_id", "ip", "port", "added_at"],
                "properties": {
                    "name": {
                        "bsonType": "string",
                        "description": "Server name"
                    },
                    "guild_id": {
                        "bsonType": "string",
                        "description": "ID of the Discord guild that owns this server"
                    },
                    "description": {
                        "bsonType": ["string", "null"],
                        "description": "Optional server description"
                    },
                    "ip": {
                        "bsonType": "string",
                        "description": "Server IP address"
                    },
                    "port": {
                        "bsonType": "int",
                        "description": "Server port number"
                    },
                    "added_at": {
                        "bsonType": "date",
                        "description": "When the server was added"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "When the server was last updated"
                    },
                    "csv_path": {
                        "bsonType": ["string", "null"],
                        "description": "Path to CSV files on the server"
                    },
                    "log_path": {
                        "bsonType": ["string", "null"],
                        "description": "Path to log files on the server"
                    },
                    "csv_enabled": {
                        "bsonType": "bool",
                        "description": "Whether CSV parsing is enabled"
                    },
                    "log_enabled": {
                        "bsonType": "bool",
                        "description": "Whether log parsing is enabled"
                    },
                    "query_enabled": {
                        "bsonType": "bool",
                        "description": "Whether game querying is enabled"
                    },
                    "auth_type": {
                        "bsonType": "string",
                        "enum": ["none", "password", "key"],
                        "description": "Authentication type for file access"
                    }
                }
            }
        }
    },
    "players": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["player_id", "player_name", "server_id", "first_seen"],
                "properties": {
                    "player_id": {
                        "bsonType": "string",
                        "description": "Unique player ID"
                    },
                    "player_name": {
                        "bsonType": "string",
                        "description": "Player's in-game name"
                    },
                    "server_id": {
                        "bsonType": "string",
                        "description": "ID of the server the player was seen on"
                    },
                    "discord_id": {
                        "bsonType": ["string", "null"],
                        "description": "Discord user ID if linked"
                    },
                    "first_seen": {
                        "bsonType": "date",
                        "description": "When the player was first seen"
                    },
                    "last_seen": {
                        "bsonType": "date",
                        "description": "When the player was last seen"
                    },
                    "total_kills": {
                        "bsonType": "int",
                        "description": "Total number of kills"
                    },
                    "total_deaths": {
                        "bsonType": "int",
                        "description": "Total number of deaths"
                    },
                    "total_suicides": {
                        "bsonType": "int",
                        "description": "Total number of suicides"
                    },
                    "total_damage_dealt": {
                        "bsonType": "double",
                        "description": "Total damage dealt"
                    },
                    "total_damage_taken": {
                        "bsonType": "double",
                        "description": "Total damage taken"
                    },
                    "longest_kill_distance": {
                        "bsonType": "double",
                        "description": "Longest kill distance"
                    }
                }
            }
        }
    },
    "kills": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["killer_id", "victim_id", "server_id", "timestamp"],
                "properties": {
                    "killer_id": {
                        "bsonType": "string",
                        "description": "ID of the killer player"
                    },
                    "victim_id": {
                        "bsonType": "string",
                        "description": "ID of the victim player"
                    },
                    "server_id": {
                        "bsonType": "string",
                        "description": "ID of the server where the kill occurred"
                    },
                    "timestamp": {
                        "bsonType": "date",
                        "description": "When the kill occurred"
                    },
                    "weapon": {
                        "bsonType": ["string", "null"],
                        "description": "Weapon used for the kill"
                    },
                    "distance": {
                        "bsonType": ["double", "null"],
                        "description": "Distance of the kill in meters"
                    },
                    "damage": {
                        "bsonType": ["double", "null"],
                        "description": "Damage dealt in the kill"
                    },
                    "is_headshot": {
                        "bsonType": ["bool", "null"],
                        "description": "Whether the kill was a headshot"
                    },
                    "is_suicide": {
                        "bsonType": "bool",
                        "description": "Whether the kill was a suicide"
                    },
                    "source_file": {
                        "bsonType": ["string", "null"],
                        "description": "Source file where the kill was found"
                    }
                }
            }
        }
    },
    "guild_configs": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["guild_id"],
                "properties": {
                    "guild_id": {
                        "bsonType": "string",
                        "description": "Discord guild ID"
                    },
                    "premium_tier": {
                        "bsonType": "string",
                        "enum": ["free", "survivor", "warlord", "overseer"],
                        "description": "Premium tier for the guild"
                    },
                    "tier_updated_at": {
                        "bsonType": "date",
                        "description": "When the premium tier was last updated"
                    },
                    "killfeed_channel": {
                        "bsonType": ["string", "null"],
                        "description": "Channel ID for killfeed notifications"
                    },
                    "killfeed_enabled": {
                        "bsonType": "bool",
                        "description": "Whether killfeed notifications are enabled"
                    },
                    "mission_channel": {
                        "bsonType": ["string", "null"],
                        "description": "Channel ID for mission notifications"
                    },
                    "mission_enabled": {
                        "bsonType": "bool",
                        "description": "Whether mission notifications are enabled"
                    },
                    "connection_channel": {
                        "bsonType": ["string", "null"],
                        "description": "Channel ID for connection notifications"
                    },
                    "connection_enabled": {
                        "bsonType": "bool",
                        "description": "Whether connection notifications are enabled"
                    }
                }
            }
        }
    },
    "factions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "abbreviation", "guild_id", "leader_id", "created_at"],
                "properties": {
                    "name": {
                        "bsonType": "string",
                        "description": "Faction name"
                    },
                    "abbreviation": {
                        "bsonType": "string",
                        "description": "Faction abbreviation (3 chars or less)"
                    },
                    "guild_id": {
                        "bsonType": "string",
                        "description": "Discord guild ID"
                    },
                    "leader_id": {
                        "bsonType": "string",
                        "description": "Discord user ID of the faction leader"
                    },
                    "members": {
                        "bsonType": "array",
                        "description": "Array of Discord user IDs of faction members",
                        "items": {
                            "bsonType": "string"
                        }
                    },
                    "role_id": {
                        "bsonType": ["string", "null"],
                        "description": "Discord role ID for the faction"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "When the faction was created"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "When the faction was last updated"
                    }
                }
            }
        }
    },
    "parser_memory": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["server_id", "last_run"],
                "properties": {
                    "server_id": {
                        "bsonType": "string", 
                        "description": "ID of server this parser memory belongs to"
                    },
                    "last_run": {
                        "bsonType": "date",
                        "description": "When the parser was last run"
                    },
                    "last_file": {
                        "bsonType": ["string", "null"],
                        "description": "Last file that was processed"
                    },
                    "last_line": {
                        "bsonType": ["int", "null"],
                        "description": "Last line processed in the last file"
                    },
                    "progress": {
                        "bsonType": ["double", "null"],
                        "description": "Progress percentage for batch operations (0-100)"
                    },
                    "status": {
                        "bsonType": ["string", "null"],
                        "description": "Current status message"
                    },
                    "last_update_timestamp": {
                        "bsonType": ["date", "null"],
                        "description": "When the progress was last updated"
                    },
                    "processed_files": {
                        "bsonType": ["array", "null"],
                        "description": "List of files that have been processed",
                        "items": {
                            "bsonType": "string"
                        }
                    },
                    "batch_mode": {
                        "bsonType": "bool",
                        "description": "Whether batch mode is enabled"
                    }
                }
            }
        }
    },
    "rivalries": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["player_id", "server_id", "updated_at"],
                "properties": {
                    "player_id": {
                        "bsonType": "string",
                        "description": "ID of the player"
                    },
                    "server_id": {
                        "bsonType": "string", 
                        "description": "ID of the server"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "When the rivalry was last updated"
                    },
                    "prey": {
                        "bsonType": ["object", "null"],
                        "description": "Player's prey (most killed)",
                        "properties": {
                            "id": {
                                "bsonType": "string",
                                "description": "Player ID of the prey"
                            },
                            "name": {
                                "bsonType": "string",
                                "description": "Name of the prey"
                            },
                            "kills": {
                                "bsonType": "int",
                                "description": "Number of times killed"
                            },
                            "last_kill": {
                                "bsonType": "date",
                                "description": "When the prey was last killed"
                            }
                        }
                    },
                    "nemesis": {
                        "bsonType": ["object", "null"],
                        "description": "Player's nemesis (killed by the most)",
                        "properties": {
                            "id": {
                                "bsonType": "string",
                                "description": "Player ID of the nemesis"
                            },
                            "name": {
                                "bsonType": "string",
                                "description": "Name of the nemesis"
                            },
                            "deaths": {
                                "bsonType": "int",
                                "description": "Number of times killed by nemesis"
                            },
                            "last_death": {
                                "bsonType": "date",
                                "description": "When last killed by the nemesis"
                            }
                        }
                    }
                }
            }
        }
    },
    "connections": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["player_id", "server_id", "type", "timestamp"],
                "properties": {
                    "player_id": {
                        "bsonType": "string",
                        "description": "ID of the player"
                    },
                    "player_name": {
                        "bsonType": "string",
                        "description": "Name of the player at time of connection"
                    },
                    "server_id": {
                        "bsonType": "string", 
                        "description": "ID of the server"
                    },
                    "type": {
                        "bsonType": "string",
                        "enum": ["connect", "disconnect"],
                        "description": "Type of connection event"
                    },
                    "timestamp": {
                        "bsonType": "date",
                        "description": "When the connection/disconnection occurred"
                    },
                    "session_id": {
                        "bsonType": ["string", "null"],
                        "description": "Unique session ID if known"
                    },
                    "ip_address": {
                        "bsonType": ["string", "null"],
                        "description": "Player's IP address if available and privacy settings allow"
                    },
                    "duration": {
                        "bsonType": ["int", "null"],
                        "description": "Session duration in seconds (for disconnect events)"
                    },
                    "reason": {
                        "bsonType": ["string", "null"],
                        "description": "Reason for disconnection if known"
                    },
                    "discord_id": {
                        "bsonType": ["string", "null"],
                        "description": "Discord user ID if player is linked"
                    }
                }
            }
        }
    },
    "player_links": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["discord_id", "created_at"],
                "properties": {
                    "discord_id": {
                        "bsonType": "string",
                        "description": "Discord user ID"
                    },
                    "primary_player_id": {
                        "bsonType": ["string", "null"],
                        "description": "Primary player ID (main character)"
                    },
                    "linked_players": {
                        "bsonType": "array",
                        "description": "Array of linked player IDs",
                        "items": {
                            "bsonType": "string"
                        }
                    },
                    "verified": {
                        "bsonType": "bool",
                        "description": "Whether the link has been verified"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "When the link was created"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "When the link was last updated"
                    },
                    "verification_code": {
                        "bsonType": ["string", "null"],
                        "description": "Verification code for linking"
                    },
                    "verification_expires": {
                        "bsonType": ["date", "null"],
                        "description": "When the verification code expires"
                    }
                }
            }
        }
    },
    "missions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["server_id", "mission_type", "start_time"],
                "properties": {
                    "server_id": {
                        "bsonType": "string",
                        "description": "ID of the server"
                    },
                    "mission_type": {
                        "bsonType": "string",
                        "description": "Type of mission (e.g., 'airdrop', 'convoy')"
                    },
                    "mission_id": {
                        "bsonType": ["string", "null"],
                        "description": "Unique mission ID if available"
                    },
                    "start_time": {
                        "bsonType": "date",
                        "description": "When the mission started"
                    },
                    "end_time": {
                        "bsonType": ["date", "null"],
                        "description": "When the mission ended (null if ongoing)"
                    },
                    "location": {
                        "bsonType": ["string", "null"],
                        "description": "Location name if available"
                    },
                    "coordinates": {
                        "bsonType": ["object", "null"],
                        "description": "Map coordinates",
                        "properties": {
                            "x": {"bsonType": "double"},
                            "y": {"bsonType": "double"},
                            "z": {"bsonType": ["double", "null"]}
                        }
                    },
                    "status": {
                        "bsonType": "string",
                        "enum": ["announced", "active", "completed", "failed", "expired"],
                        "description": "Current mission status"
                    },
                    "rewards": {
                        "bsonType": ["array", "null"],
                        "description": "List of potential rewards",
                        "items": {
                            "bsonType": "string"
                        }
                    },
                    "participants": {
                        "bsonType": ["array", "null"],
                        "description": "List of participating player IDs",
                        "items": {
                            "bsonType": "string"
                        }
                    },
                    "winner_id": {
                        "bsonType": ["string", "null"],
                        "description": "ID of the player who completed/won the mission"
                    }
                }
            }
        }
    },
    "server_status": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["server_id", "timestamp", "status"],
                "properties": {
                    "server_id": {
                        "bsonType": "string",
                        "description": "ID of the server"
                    },
                    "timestamp": {
                        "bsonType": "date",
                        "description": "When the status was recorded"
                    },
                    "status": {
                        "bsonType": "string",
                        "enum": ["online", "offline", "restarting", "maintenance"],
                        "description": "Server status"
                    },
                    "player_count": {
                        "bsonType": ["int", "null"],
                        "description": "Number of players online"
                    },
                    "max_players": {
                        "bsonType": ["int", "null"],
                        "description": "Maximum player capacity"
                    },
                    "uptime": {
                        "bsonType": ["int", "null"],
                        "description": "Server uptime in seconds"
                    },
                    "performance": {
                        "bsonType": ["object", "null"],
                        "description": "Performance metrics",
                        "properties": {
                            "cpu_usage": {"bsonType": ["double", "null"]},
                            "memory_usage": {"bsonType": ["double", "null"]},
                            "tick_rate": {"bsonType": ["double", "null"]}
                        }
                    },
                    "response_time": {
                        "bsonType": ["double", "null"],
                        "description": "Server response time in milliseconds"
                    },
                    "version": {
                        "bsonType": ["string", "null"],
                        "description": "Server version"
                    }
                }
            }
        }
    }
}

async def apply_schema_validations(db):
    """
    Apply schema validations to all collections
    
    Args:
        db: Database instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Applying schema validations to collections")
        
        results = {}
        
        for collection_name, schema in SCHEMAS.items():
            try:
                # Check if collection exists, create it if it doesn't
                collection_names = await db._db.list_collection_names()
                if collection_name not in collection_names:
                    logger.info(f"Creating collection {collection_name}")
                    await db._db.create_collection(collection_name)
                
                # Apply validation schema
                logger.info(f"Applying schema validation to {collection_name}")
                await db._db.command({
                    "collMod": collection_name,
                    "validator": schema["validator"],
                    "validationLevel": "moderate"  # Only validate on inserts and updates
                })
                
                results[collection_name] = True
                logger.info(f"Successfully applied schema validation to {collection_name}")
            except Exception as e:
                results[collection_name] = False
                logger.error(f"Failed to apply schema validation to {collection_name}: {e}")
        
        # Log summary
        success_count = sum(1 for result in results.values() if result)
        logger.info(f"Applied schema validations to {success_count}/{len(SCHEMAS)} collections")
        
        return all(results.values())
    except Exception as e:
        logger.error(f"Error applying schema validations: {e}")
        return False

async def validate_collection_data(db, collection_name):
    """
    Validate existing data in a collection against its schema
    
    Args:
        db: Database instance
        collection_name: Name of the collection to validate
        
    Returns:
        tuple: (valid_count, invalid_count, invalid_docs)
    """
    try:
        logger.info(f"Validating data in collection {collection_name}")
        
        if collection_name not in SCHEMAS:
            logger.error(f"No schema defined for collection {collection_name}")
            return 0, 0, []
        
        collection = await db.get_collection(collection_name)
        cursor = collection.find({})
        
        valid_count = 0
        invalid_count = 0
        invalid_docs = []
        
        schema = SCHEMAS[collection_name]["validator"]["$jsonSchema"]
        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})
        
        async for doc in cursor:
            is_valid = True
            
            # Check required fields
            for field in required_fields:
                if field not in doc:
                    is_valid = False
                    invalid_docs.append({
                        "_id": str(doc.get("_id")),
                        "reason": f"Missing required field: {field}"
                    })
                    break
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
        
        logger.info(f"Validation results for {collection_name}: {valid_count} valid, {invalid_count} invalid")
        return valid_count, invalid_count, invalid_docs
    except Exception as e:
        logger.error(f"Error validating collection {collection_name}: {e}")
        return 0, 0, [{"_id": "error", "reason": str(e)}]