"""
Guild Isolation Utilities

These functions ensure that each Discord guild can only access its own data,
preventing cross-guild data access.
"""

import logging
from bson.objectid import ObjectId

logger = logging.getLogger('deadside_bot.utils.guild_isolation')

async def get_servers_for_guild(db, guild_id):
    """
    Get all servers for a specific guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        list: List of server documents
    """
    
    # Alias for backward compatibility
    return await get_guild_servers(db, guild_id)

async def get_guild_servers(db, guild_id):
    """
    Get all servers for a specific guild (original implementation)
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        list: List of server documents
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in get_guild_servers")
        return []
        
    try:
        servers_collection = await db.get_collection("servers")
        cursor = servers_collection.find({"guild_id": guild_id})
        servers = await cursor.to_list(None)
        return servers
    except Exception as e:
        logger.error(f"Error in get_guild_servers: {e}")
        return []

async def get_server_by_name(db, server_name, guild_id):
    """
    Get a server by name, ensuring it belongs to the specified guild
    
    Args:
        db: Database connection
        server_name: Name of the server
        guild_id: Discord guild ID
        
    Returns:
        dict: Server document or None if not found
    """
    if not db or not server_name or not guild_id:
        logger.error("Missing parameters in get_server_by_name")
        return None
        
    try:
        # Use case-insensitive search
        servers_collection = await db.get_collection("servers")
        query = {
            "name": {"$regex": f"^{server_name}$", "$options": "i"},
            "guild_id": guild_id
        }
        server = await servers_collection.find_one(query)
        return server
    except Exception as e:
        logger.error(f"Error in get_server_by_name: {e}")
        return None

async def get_server_by_id(db, server_id, guild_id=None):
    """
    Get a server by ID, optionally verifying it belongs to the specified guild
    
    Args:
        db: Database connection
        server_id: Server ID
        guild_id: Optional Discord guild ID for verification
        
    Returns:
        dict: Server document or None if not found
    """
    if not db or not server_id:
        logger.error("Missing parameters in get_server_by_id")
        return None
        
    try:
        servers_collection = await db.get_collection("servers")
        
        # Try to convert string ID to ObjectId if needed
        if isinstance(server_id, str):
            try:
                obj_id = ObjectId(server_id)
                query = {"$or": [{"_id": obj_id}, {"_id": server_id}]}
            except:
                query = {"_id": server_id}
        else:
            query = {"_id": server_id}
        
        # Add guild verification if specified
        if guild_id:
            query["guild_id"] = guild_id
            
        server = await servers_collection.find_one(query)
        return server
    except Exception as e:
        logger.error(f"Error in get_server_by_id: {e}")
        return None

async def count_guild_servers(db, guild_id):
    """
    Count how many servers a guild has
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        int: Number of servers
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in count_guild_servers")
        return 0
        
    try:
        servers_collection = await db.get_collection("servers")
        count = await servers_collection.count_documents({"guild_id": guild_id})
        return count
    except Exception as e:
        logger.error(f"Error in count_guild_servers: {e}")
        return 0

async def can_add_server(db, guild_id):
    """
    Check if a guild can add another server
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        bool: True if the guild can add another server, False otherwise
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in can_add_server")
        return False
        
    try:
        # Import here to avoid circular imports
        from utils.premium import get_max_servers
        
        # Get the current count of servers
        current_count = await count_guild_servers(db, guild_id)
        
        # Get the maximum number of servers for this guild's tier
        max_servers = await get_max_servers(db, guild_id)
        
        # Check if the guild can add another server
        return current_count < max_servers
    except Exception as e:
        logger.error(f"Error in can_add_server: {e}")
        return False

async def verify_guild_access(db, server_id, guild_id):
    """
    Verify that a guild has access to a server
    
    Args:
        db: Database connection
        server_id: Server ID
        guild_id: Discord guild ID
        
    Returns:
        bool: True if the guild has access, False otherwise
    """
    if not db or not server_id or not guild_id:
        return False
        
    try:
        server = await get_server_by_id(db, server_id, guild_id)
        return server is not None
    except Exception as e:
        logger.error(f"Error in verify_guild_access: {e}")
        return False

async def get_guild_config(db, guild_id):
    """
    Get the configuration for a guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        dict: Guild configuration document
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in get_guild_config")
        return None
        
    try:
        configs_collection = await db.get_collection("guild_configs")
        config = await configs_collection.find_one({"guild_id": guild_id})
        return config
    except Exception as e:
        logger.error(f"Error in get_guild_config: {e}")
        return None

async def update_guild_config(db, guild_id, updates):
    """
    Update the configuration for a guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        updates: Dictionary of updates to apply
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not db or not guild_id or not updates:
        logger.error("Missing parameters in update_guild_config")
        return False
        
    try:
        configs_collection = await db.get_collection("guild_configs")
        result = await configs_collection.update_one(
            {"guild_id": guild_id},
            {"$set": updates},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error in update_guild_config: {e}")
        return False