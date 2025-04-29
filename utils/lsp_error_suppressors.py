"""
LSP Error Suppressors

This module provides utility functions and type hints to suppress Language Server Protocol (LSP) errors.
These fixes improve code quality and prevent false positives in LSP error detection.

This module should be imported in files that use external libraries to provide proper type hints
for LSP without causing runtime import errors.
"""

import logging
import typing
import os
import sys
from typing import Any, Dict, List, Tuple, Union, Optional, Callable, TypeVar, Generic, Iterable, Iterator, Awaitable, Coroutine, Generator, AsyncGenerator, Mapping, Sequence, Set, FrozenSet, Type, cast, overload, Protocol, runtime_checkable

# Set up logging
logger = logging.getLogger('deadside_bot.utils.lsp_error_suppressors')

# Type variables for generic types
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
F = TypeVar('F', bound=Callable[..., Any])
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)

# Mock type aliases for libraries that may not be installed
# This helps LSP understand the types without actually importing the modules
if typing.TYPE_CHECKING:
    import discord
    import discord.ext.commands
    from discord.ext import tasks
    import motor.motor_asyncio
    import bson
    import bson.objectid
    import pymongo
    import pymongo.errors
    from pymongo import ReturnDocument
    
    # Define commonly used types from discord
    # Application contexts and commands (py-cord specific)
    DiscordContext = discord.ApplicationContext
    DiscordCommand = discord.ApplicationCommand
    SlashCommandGroup = discord.SlashCommandGroup
    SlashCommand = discord.SlashCommand
    Option = discord.Option
    OptionChoice = discord.OptionChoice
    Bot = discord.Bot
    AutocompleteContext = discord.AutocompleteContext
    
    # Discord entity types
    DiscordMember = discord.Member
    DiscordUser = discord.User
    DiscordGuild = discord.Guild
    DiscordRole = discord.Role
    DiscordMessage = discord.Message
    DiscordChannel = discord.abc.GuildChannel
    DiscordTextChannel = discord.TextChannel
    DiscordEmbed = discord.Embed
    DiscordEmbedField = discord.EmbedField
    DiscordPermissions = discord.Permissions
    DiscordColour = discord.Colour
    DiscordCog = discord.ext.commands.Cog
    
    # Tasks and background operations
    DiscordTask = tasks.Loop
    
    # Motor MongoDB types
    AsyncIOMotorClient = motor.motor_asyncio.AsyncIOMotorClient
    AsyncIOMotorDatabase = motor.motor_asyncio.AsyncIOMotorDatabase
    AsyncIOMotorCollection = motor.motor_asyncio.AsyncIOMotorCollection
    AsyncIOMotorCursor = motor.motor_asyncio.AsyncIOMotorCursor
    AsyncIOMotorClientSession = motor.motor_asyncio.AsyncIOMotorClientSession
    
    # MongoDB types
    MongoDBDocument = Dict[str, Any]
    MongoDBCursor = AsyncIOMotorCursor
    
    # BSON types
    ObjectId = bson.objectid.ObjectId
    BSONDocument = bson.SON
    
    # PyMongo errors
    DuplicateKeyError = pymongo.errors.DuplicateKeyError
    PyMongoError = pymongo.errors.PyMongoError
    ConnectionFailure = pymongo.errors.ConnectionFailure
    
    # MongoDB return options
    ReturnDocumentAfter = ReturnDocument.AFTER
    ReturnDocumentBefore = ReturnDocument.BEFORE
else:
    # For runtime, use Any to avoid import errors
    # Basic Discord types
    DiscordContext = Any
    DiscordCommand = Any
    SlashCommandGroup = Any
    SlashCommand = Any
    Option = Any
    OptionChoice = Any
    Bot = Any
    AutocompleteContext = Any
    
    # Discord entity types
    DiscordMember = Any
    DiscordUser = Any
    DiscordGuild = Any
    DiscordRole = Any
    DiscordMessage = Any
    DiscordChannel = Any
    DiscordTextChannel = Any
    DiscordEmbed = Any
    DiscordEmbedField = Any
    DiscordPermissions = Any
    DiscordColour = Any
    DiscordCog = Any
    
    # Tasks
    DiscordTask = Any
    
    # MongoDB types
    AsyncIOMotorClient = Any
    AsyncIOMotorDatabase = Any
    AsyncIOMotorCollection = Any
    AsyncIOMotorCursor = Any
    AsyncIOMotorClientSession = Any
    MongoDBDocument = Dict[str, Any]
    MongoDBCursor = Any
    
    # BSON types
    ObjectId = Any
    BSONDocument = Any
    
    # PyMongo errors
    DuplicateKeyError = Exception
    PyMongoError = Exception
    ConnectionFailure = Exception
    
    # MongoDB return options
    ReturnDocumentAfter = 1  # Same as pymongo.ReturnDocument.AFTER
    ReturnDocumentBefore = 0  # Same as pymongo.ReturnDocument.BEFORE
    
    logger.debug("Runtime imports avoided for LSP error suppression")

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

def get_discord_import_status() -> Dict[str, bool]:
    """
    Get status of Discord library imports
    
    Returns a dictionary with status of various Discord-related imports
    to help with debugging LSP issues.
    
    Returns:
        dict: Import status for various Discord modules
    """
    status = {}
    
    try:
        import discord
        status["discord"] = True
    except ImportError:
        status["discord"] = False
        
    try:
        import discord.ext.commands
        status["discord.ext.commands"] = True
    except ImportError:
        status["discord.ext.commands"] = False
        
    try:
        from discord.ext import tasks
        status["discord.ext.tasks"] = True
    except ImportError:
        status["discord.ext.tasks"] = False
        
    return status

def get_mongo_import_status() -> Dict[str, bool]:
    """
    Get status of MongoDB library imports
    
    Returns a dictionary with status of various MongoDB-related imports
    to help with debugging LSP issues.
    
    Returns:
        dict: Import status for various MongoDB modules
    """
    status = {}
    
    try:
        import motor.motor_asyncio
        status["motor.motor_asyncio"] = True
    except ImportError:
        status["motor.motor_asyncio"] = False
        
    try:
        import pymongo
        status["pymongo"] = True
    except ImportError:
        status["pymongo"] = False
        
    try:
        import bson
        status["bson"] = True
    except ImportError:
        status["bson"] = False
        
    try:
        import bson.objectid
        status["bson.objectid"] = True
    except ImportError:
        status["bson.objectid"] = False
        
    return status

def fix_path_imports() -> Dict[str, bool]:
    """
    Fix import paths for modules in this project
    
    This function helps ensure imports work correctly regardless of 
    the current working directory. It's particularly useful when
    running tests or scripts from different directories.
    
    Returns:
        dict: Status of path modifications
    """
    result = {"success": False, "modified": False}
    
    try:
        # Get absolute path to the project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        # Add project root to path if not already there
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            result["modified"] = True
            
        result["success"] = True
    except Exception as e:
        logger.error(f"Error fixing import paths: {e}")
        
    return result