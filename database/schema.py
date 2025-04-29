"""
Database Schema Validation Module

This module provides schema validation functions for MongoDB documents.
It ensures data consistency and validation before saving to the database.
"""

import re
import logging
import datetime
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, cast

# Set up logging
logger = logging.getLogger('deadside_bot.database.schema')

# Type for validators and schema definitions
T = TypeVar('T')
SchemaDefinition = Dict[str, Dict[str, Any]]
ValidatorFunc = Callable[[Any], bool]

class SchemaValidationError(Exception):
    """Exception raised when a document fails schema validation"""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(message)

def validate_type(value: Any, expected_type: Any) -> bool:
    """
    Validate that a value is of the expected type
    
    Args:
        value: The value to check
        expected_type: The expected type or list of types
        
    Returns:
        bool: True if value is of the expected type, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    # Handle union types (list of allowed types)
    if isinstance(expected_type, list):
        return any(isinstance(value, t) for t in expected_type)
        
    return isinstance(value, expected_type)

def validate_required(value: Any) -> bool:
    """
    Validate that a required value is not None or empty
    
    Args:
        value: The value to check
        
    Returns:
        bool: True if value is not None or empty, False otherwise
    """
    if value is None:
        return False
        
    # For strings, check if empty
    if isinstance(value, str) and not value.strip():
        return False
        
    # For lists and dicts, check if empty
    if (isinstance(value, (list, dict)) and not value):
        return False
        
    return True

def validate_min_length(value: Any, min_length: int) -> bool:
    """
    Validate that a value has a minimum length
    
    Args:
        value: The value to check
        min_length: The minimum length required
        
    Returns:
        bool: True if value meets the minimum length requirement, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if hasattr(value, '__len__'):
        return len(value) >= min_length
        
    return True  # Non-iterable values always pass

def validate_max_length(value: Any, max_length: int) -> bool:
    """
    Validate that a value has a maximum length
    
    Args:
        value: The value to check
        max_length: The maximum length allowed
        
    Returns:
        bool: True if value meets the maximum length requirement, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if hasattr(value, '__len__'):
        return len(value) <= max_length
        
    return True  # Non-iterable values always pass

def validate_min_value(value: Any, min_value: Union[int, float, datetime.datetime]) -> bool:
    """
    Validate that a value is at least a minimum value
    
    Args:
        value: The value to check
        min_value: The minimum value required
        
    Returns:
        bool: True if value meets the minimum value requirement, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if isinstance(value, (int, float, datetime.datetime)) and isinstance(min_value, type(value)):
        return value >= min_value
        
    return True  # Non-comparable values always pass

def validate_max_value(value: Any, max_value: Union[int, float, datetime.datetime]) -> bool:
    """
    Validate that a value is at most a maximum value
    
    Args:
        value: The value to check
        max_value: The maximum value allowed
        
    Returns:
        bool: True if value meets the maximum value requirement, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if isinstance(value, (int, float, datetime.datetime)) and isinstance(max_value, type(value)):
        return value <= max_value
        
    return True  # Non-comparable values always pass

def validate_regex(value: Any, pattern: str) -> bool:
    """
    Validate that a value matches a regex pattern
    
    Args:
        value: The value to check
        pattern: The regex pattern to match
        
    Returns:
        bool: True if value matches the pattern, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if isinstance(value, str):
        return bool(re.match(pattern, value))
        
    return False  # Non-string values fail regex validation

def validate_enum(value: Any, allowed_values: List[Any]) -> bool:
    """
    Validate that a value is one of a set of allowed values
    
    Args:
        value: The value to check
        allowed_values: List of allowed values
        
    Returns:
        bool: True if value is in the allowed values, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    return value in allowed_values

def validate_subdocument(value: Any, schema: SchemaDefinition) -> bool:
    """
    Validate a nested document against a schema
    
    Args:
        value: The document to validate
        schema: The schema definition
        
    Returns:
        bool: True if document is valid, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if not isinstance(value, dict):
        return False
        
    # Validate each field in the schema
    try:
        validate_document(value, schema)
        return True
    except SchemaValidationError:
        return False

def validate_array(value: Any, item_schema: Dict[str, Any]) -> bool:
    """
    Validate that each item in an array matches a schema
    
    Args:
        value: The array to validate
        item_schema: The schema for each item
        
    Returns:
        bool: True if all items are valid, False otherwise
    """
    if value is None:
        return True  # None is allowed unless required=True is specified
        
    if not isinstance(value, list):
        return False
        
    # Empty arrays are valid
    if not value:
        return True
        
    # Validate each item
    for item in value:
        # If item_schema has a type key, it's a simple schema
        if 'type' in item_schema:
            if not validate_field(item, item_schema):
                return False
        # Otherwise, it's a document schema
        else:
            if not validate_subdocument(item, item_schema):
                return False
                
    return True

def validate_field(value: Any, field_schema: Dict[str, Any]) -> bool:
    """
    Validate a field value against its schema
    
    Args:
        value: The value to validate
        field_schema: The schema for the field
        
    Returns:
        bool: True if field is valid, False otherwise
    """
    # Check if required
    if field_schema.get('required', False) and not validate_required(value):
        return False
        
    # If value is None and not required, it's valid
    if value is None:
        return True
        
    # Check type
    if 'type' in field_schema and not validate_type(value, field_schema['type']):
        return False
        
    # Check length constraints
    if 'min_length' in field_schema and not validate_min_length(value, field_schema['min_length']):
        return False
        
    if 'max_length' in field_schema and not validate_max_length(value, field_schema['max_length']):
        return False
        
    # Check value constraints
    if 'min_value' in field_schema and not validate_min_value(value, field_schema['min_value']):
        return False
        
    if 'max_value' in field_schema and not validate_max_value(value, field_schema['max_value']):
        return False
        
    # Check regex
    if 'pattern' in field_schema and not validate_regex(value, field_schema['pattern']):
        return False
        
    # Check enum
    if 'enum' in field_schema and not validate_enum(value, field_schema['enum']):
        return False
        
    # Check subdocument
    if 'schema' in field_schema and not validate_subdocument(value, field_schema['schema']):
        return False
        
    # Check array
    if 'items' in field_schema and not validate_array(value, field_schema['items']):
        return False
        
    # Custom validator
    if 'validator' in field_schema:
        validator_func = cast(ValidatorFunc, field_schema['validator'])
        if not validator_func(value):
            return False
            
    return True

def validate_document(document: Dict[str, Any], schema: SchemaDefinition) -> None:
    """
    Validate a document against a schema
    
    Args:
        document: Document to validate
        schema: Schema definition
        
    Raises:
        SchemaValidationError: If document does not match schema
    """
    if not document:
        raise SchemaValidationError("Document is empty")
        
    if not schema:
        raise SchemaValidationError("Schema is empty")
        
    # Validate each field in the schema
    for field_name, field_schema in schema.items():
        # Get the field value (or None if field is missing)
        value = document.get(field_name)
        
        # Validate the field
        if not validate_field(value, field_schema):
            error_message = f"Invalid value for field '{field_name}'"
            
            # Include specific validation error if available
            if 'type' in field_schema and not validate_type(value, field_schema['type']):
                expected_type = field_schema['type']
                type_name = expected_type.__name__ if not isinstance(expected_type, list) else [t.__name__ for t in expected_type]
                error_message = f"Field '{field_name}' should be of type {type_name}, got {type(value).__name__}"
                
            elif field_schema.get('required', False) and not validate_required(value):
                error_message = f"Field '{field_name}' is required but missing or empty"
                
            elif 'min_length' in field_schema and not validate_min_length(value, field_schema['min_length']):
                error_message = f"Field '{field_name}' should have a minimum length of {field_schema['min_length']}"
                
            elif 'max_length' in field_schema and not validate_max_length(value, field_schema['max_length']):
                error_message = f"Field '{field_name}' should have a maximum length of {field_schema['max_length']}"
                
            elif 'min_value' in field_schema and not validate_min_value(value, field_schema['min_value']):
                error_message = f"Field '{field_name}' should be at least {field_schema['min_value']}"
                
            elif 'max_value' in field_schema and not validate_max_value(value, field_schema['max_value']):
                error_message = f"Field '{field_name}' should be at most {field_schema['max_value']}"
                
            elif 'pattern' in field_schema and not validate_regex(value, field_schema['pattern']):
                error_message = f"Field '{field_name}' should match pattern {field_schema['pattern']}"
                
            elif 'enum' in field_schema and not validate_enum(value, field_schema['enum']):
                error_message = f"Field '{field_name}' should be one of {field_schema['enum']}"
                
            raise SchemaValidationError(error_message, field_name, value)

# Schema definitions for commonly used documents

# Guild schema
GUILD_SCHEMA = {
    'guild_id': {'required': True, 'type': str, 'min_length': 1},
    'name': {'required': False, 'type': str, 'max_length': 100},
    'premium_tier': {'required': False, 'type': str, 'enum': ['survivor', 'warlord', 'overseer', 'free', 'premium', 'enterprise']},
    'created_at': {'required': False, 'type': datetime.datetime},
    'updated_at': {'required': False, 'type': datetime.datetime},
    'settings': {'required': False, 'type': dict}
}

# Server schema
SERVER_SCHEMA = {
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'guild_id': {'required': True, 'type': str, 'min_length': 1},
    'name': {'required': True, 'type': str, 'min_length': 1, 'max_length': 100},
    'address': {'required': True, 'type': str, 'min_length': 1, 'max_length': 100},
    'port': {'required': True, 'type': int, 'min_value': 1, 'max_value': 65535},
    'query_port': {'required': False, 'type': int, 'min_value': 1, 'max_value': 65535},
    'rcon_port': {'required': False, 'type': int, 'min_value': 1, 'max_value': 65535},
    'rcon_password': {'required': False, 'type': str},
    'ftp_username': {'required': False, 'type': str},
    'ftp_password': {'required': False, 'type': str},
    'ftp_port': {'required': False, 'type': int, 'min_value': 1, 'max_value': 65535},
    'sftp': {'required': False, 'type': bool},
    'csv_path': {'required': False, 'type': str},
    'log_path': {'required': False, 'type': str},
    'is_default': {'required': False, 'type': bool},
    'csv_enabled': {'required': False, 'type': bool},
    'log_enabled': {'required': False, 'type': bool},
    'last_poll': {'required': False, 'type': datetime.datetime},
    'status': {'required': False, 'type': str, 'enum': ['online', 'offline', 'unknown']},
    'players_online': {'required': False, 'type': int, 'min_value': 0},
    'max_players': {'required': False, 'type': int, 'min_value': 0},
    'created_at': {'required': False, 'type': datetime.datetime},
    'updated_at': {'required': False, 'type': datetime.datetime}
}

# Player schema
PLAYER_SCHEMA = {
    'player_id': {'required': True, 'type': str, 'min_length': 1},
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'steam_id': {'required': True, 'type': str, 'min_length': 1, 'pattern': r'^[0-9]+$'},
    'name': {'required': True, 'type': str, 'min_length': 1, 'max_length': 100},
    'last_seen': {'required': False, 'type': datetime.datetime},
    'first_seen': {'required': False, 'type': datetime.datetime},
    'play_time': {'required': False, 'type': int, 'min_value': 0},
    'kills': {'required': False, 'type': int, 'min_value': 0},
    'deaths': {'required': False, 'type': int, 'min_value': 0},
    'suicides': {'required': False, 'type': int, 'min_value': 0},
    'longest_kill': {'required': False, 'type': int, 'min_value': 0},
    'favorite_weapon': {'required': False, 'type': str},
    'nemesis': {'required': False, 'type': str},
    'prey': {'required': False, 'type': str},
    'is_online': {'required': False, 'type': bool},
    'faction_id': {'required': False, 'type': str},
    'linked_ids': {'required': False, 'type': list},
    'stats': {'required': False, 'type': dict}
}

# Faction schema
FACTION_SCHEMA = {
    'faction_id': {'required': True, 'type': str, 'min_length': 1},
    'guild_id': {'required': True, 'type': str, 'min_length': 1},
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'name': {'required': True, 'type': str, 'min_length': 1, 'max_length': 50},
    'tag': {'required': False, 'type': str, 'max_length': 10},
    'color': {'required': False, 'type': str, 'pattern': r'^#[0-9a-fA-F]{6}$'},
    'icon_url': {'required': False, 'type': str},
    'leader_id': {'required': True, 'type': str, 'min_length': 1},
    'members': {'required': True, 'type': list},
    'created_at': {'required': False, 'type': datetime.datetime},
    'updated_at': {'required': False, 'type': datetime.datetime},
    'description': {'required': False, 'type': str, 'max_length': 1000},
    'discord_role_id': {'required': False, 'type': str}
}

# Killfeed entry schema
KILLFEED_SCHEMA = {
    'kill_id': {'required': True, 'type': str, 'min_length': 1},
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'killer_id': {'required': False, 'type': str},
    'killer_name': {'required': False, 'type': str},
    'victim_id': {'required': True, 'type': str, 'min_length': 1},
    'victim_name': {'required': True, 'type': str, 'min_length': 1},
    'weapon': {'required': False, 'type': str},
    'distance': {'required': False, 'type': int, 'min_value': 0},
    'timestamp': {'required': True, 'type': datetime.datetime},
    'is_suicide': {'required': False, 'type': bool},
    'is_headshot': {'required': False, 'type': bool},
    'killer_faction': {'required': False, 'type': str},
    'victim_faction': {'required': False, 'type': str}
}

# Mission schema
MISSION_SCHEMA = {
    'mission_id': {'required': True, 'type': str, 'min_length': 1},
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'name': {'required': True, 'type': str, 'min_length': 1},
    'type': {'required': False, 'type': str},
    'location': {'required': False, 'type': str},
    'start_time': {'required': True, 'type': datetime.datetime},
    'end_time': {'required': False, 'type': datetime.datetime},
    'status': {'required': False, 'type': str, 'enum': ['active', 'completed', 'failed', 'unknown']},
    'participants': {'required': False, 'type': list}
}

# Parser memory schema
PARSER_MEMORY_SCHEMA = {
    'memory_id': {'required': True, 'type': str, 'min_length': 1},
    'server_id': {'required': True, 'type': str, 'min_length': 1},
    'parser_type': {'required': True, 'type': str, 'enum': ['csv', 'log', 'batch']},
    'last_position': {'required': False, 'type': int, 'min_value': 0},
    'last_file': {'required': False, 'type': str},
    'last_timestamp': {'required': False, 'type': datetime.datetime},
    'batch_files_total': {'required': False, 'type': int, 'min_value': 0},
    'batch_files_processed': {'required': False, 'type': int, 'min_value': 0},
    'batch_lines_processed': {'required': False, 'type': int, 'min_value': 0},
    'progress': {'required': False, 'type': float, 'min_value': 0, 'max_value': 100},
    'status': {'required': False, 'type': str, 'enum': ['idle', 'running', 'completed', 'error']},
    'error': {'required': False, 'type': str},
    'created_at': {'required': False, 'type': datetime.datetime},
    'updated_at': {'required': False, 'type': datetime.datetime},
    'last_update_timestamp': {'required': False, 'type': datetime.datetime}
}

# Map of collection names to schemas
COLLECTION_SCHEMAS = {
    'guilds': GUILD_SCHEMA,
    'servers': SERVER_SCHEMA,
    'players': PLAYER_SCHEMA,
    'factions': FACTION_SCHEMA,
    'killfeed': KILLFEED_SCHEMA,
    'missions': MISSION_SCHEMA,
    'parser_memory': PARSER_MEMORY_SCHEMA
}

def validate_for_collection(document: Dict[str, Any], collection_name: str) -> None:
    """
    Validate a document against the schema for a specific collection
    
    Args:
        document: Document to validate
        collection_name: Name of the collection
        
    Raises:
        SchemaValidationError: If document does not match schema
    """
    if collection_name not in COLLECTION_SCHEMAS:
        raise ValueError(f"No schema defined for collection '{collection_name}'")
        
    validate_document(document, COLLECTION_SCHEMAS[collection_name])