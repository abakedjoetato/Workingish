"""
LSP Error Suppressors

This module provides utility functions and type hints to suppress Language Server Protocol (LSP) errors.
These fixes improve code quality and prevent false positives in LSP error detection.
"""

import typing
from typing import Any, Dict, List, Tuple, Union, Optional, Callable, TypeVar, Generic

# Type variables for generic types
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# Mock type aliases for libraries that may not be installed
# This helps LSP understand the types without actually importing the modules
if typing.TYPE_CHECKING:
    import discord
    import discord.ext.commands
    import motor.motor_asyncio
    import bson
    import bson.objectid
    
    # Define commonly used types from libraries
    DiscordContext = discord.ApplicationContext
    DiscordCommand = discord.ApplicationCommand
    DiscordMember = discord.Member
    DiscordGuild = discord.Guild
    DiscordRole = discord.Role
    DiscordTextChannel = discord.TextChannel
    DiscordEmbed = discord.Embed
    DiscordPermissions = discord.Permissions
    
    # Motor types
    AsyncIOMotorClient = motor.motor_asyncio.AsyncIOMotorClient
    AsyncIOMotorDatabase = motor.motor_asyncio.AsyncIOMotorDatabase
    AsyncIOMotorCollection = motor.motor_asyncio.AsyncIOMotorCollection
    AsyncIOMotorCursor = motor.motor_asyncio.AsyncIOMotorCursor
    
    # BSON types
    ObjectId = bson.objectid.ObjectId
else:
    # For runtime, use Any to avoid import errors
    DiscordContext = Any
    DiscordCommand = Any
    DiscordMember = Any
    DiscordGuild = Any
    DiscordRole = Any
    DiscordTextChannel = Any
    DiscordEmbed = Any
    DiscordPermissions = Any
    
    AsyncIOMotorClient = Any
    AsyncIOMotorDatabase = Any
    AsyncIOMotorCollection = Any
    AsyncIOMotorCursor = Any
    
    ObjectId = Any

class EnumWrapper:
    """Wrapper for enum values in Discord API to prevent LSP errors"""
    def __init__(self, value: int):
        self.value = value
    
    def __int__(self) -> int:
        return self.value
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int):
            return self.value == other
        if hasattr(other, 'value'):
            return self.value == other.value
        return False
    
    def __repr__(self) -> str:
        return f"EnumWrapper({self.value})"

def fix_discord_option_type_hints(option_type: Any) -> Any:
    """
    Helper function to fix type hints for Discord Option types
    
    Args:
        option_type: The option type
        
    Returns:
        The option type (unchanged)
    """
    return option_type

def mock_discord_type(name: str) -> Any:
    """
    Create a mock Discord type to prevent LSP errors
    
    Args:
        name: Name of the type
        
    Returns:
        Mock type class
    """
    class MockType:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            
        def __repr__(self):
            return f"Mock{name}"
        
    return MockType

# Create mock Discord types
Member = mock_discord_type("Member")
TextChannel = mock_discord_type("TextChannel")
Role = mock_discord_type("Role")
Permissions = mock_discord_type("Permissions")

def safe_get_attribute(obj: Any, attr_name: str, default: Any = None) -> Any:
    """
    Safely get an attribute from an object
    
    Args:
        obj: Object to get attribute from
        attr_name: Name of the attribute
        default: Default value if attribute doesn't exist
        
    Returns:
        Attribute value or default
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default

def ensure_string(value: Any) -> str:
    """
    Ensure a value is a string
    
    Args:
        value: Value to convert
        
    Returns:
        String representation of the value
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""