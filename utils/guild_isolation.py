import logging
from database.connection import Database
from utils.premium import get_guild_premium_tier, get_premium_limits, is_home_guild

logger = logging.getLogger('deadside_bot.utils.guild_isolation')

async def get_servers_for_guild(guild_id):
    """
    Get all game servers for a specific guild
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        list: List of server documents for the guild
    """
    db = await Database.get_instance()
    collection = await db.get_collection("servers")
    cursor = collection.find({"guild_id": guild_id})
    servers = await cursor.to_list(None)
    return servers

async def get_server_ids_for_guild(guild_id):
    """
    Get all server IDs for a specific guild
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        list: List of server ObjectIds
    """
    servers = await get_servers_for_guild(guild_id)
    return [server["_id"] for server in servers]

async def check_server_ownership(guild_id, server_id):
    """
    Check if a server belongs to a guild
    
    Args:
        guild_id: Discord guild ID
        server_id: Server ObjectId
        
    Returns:
        bool: True if server belongs to the guild
    """
    db = await Database.get_instance()
    collection = await db.get_collection("servers")
    server = await collection.find_one({
        "_id": server_id,
        "guild_id": guild_id
    })
    return server is not None

async def get_guild_config(guild_id):
    """
    Get guild configuration
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        dict: Guild configuration document
    """
    db = await Database.get_instance()
    collection = await db.get_collection("guild_configs")
    config = await collection.find_one({"guild_id": guild_id})
    
    if not config:
        # Create default configuration
        config = {
            "guild_id": guild_id,
            "premium_tier": "free",
            "killfeed_channel": None,
            "connection_channel": None,
            "mission_channel": None
        }
        await collection.insert_one(config)
    
    return config

async def update_guild_config(guild_id, update_dict):
    """
    Update guild configuration
    
    Args:
        guild_id: Discord guild ID
        update_dict: Dictionary of fields to update
        
    Returns:
        bool: True if successful
    """
    try:
        db = await Database.get_instance()
        collection = await db.get_collection("guild_configs")
        await collection.update_one(
            {"guild_id": guild_id},
            {"$set": update_dict},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update guild config: {e}")
        return False

async def get_guild_server_limit(guild_id):
    """
    Get maximum servers allowed for a guild based on premium tier
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        int or None: Maximum servers allowed, None for unlimited
    """
    tier = await get_guild_premium_tier(guild_id)
    limits = await get_premium_limits(tier)
    return limits.get("max_servers", 1)

async def can_add_server(guild_id):
    """
    Check if a guild can add another server based on premium tier limits
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        tuple: (bool, int, int or None) - (Can add, current count, max allowed)
    """
    # Get server count
    servers = await get_servers_for_guild(guild_id)
    current_count = len(servers)
    
    # Get max allowed
    max_allowed = await get_guild_server_limit(guild_id)
    
    # Return if the guild can add a server
    if max_allowed is None:  # Unlimited
        return (True, current_count, None)
    return (current_count < max_allowed, current_count, max_allowed)

async def get_isolated_events(guild_id, collection_name, limit=100, query_filter=None):
    """
    Get events isolated to a specific guild's servers
    
    Args:
        guild_id: Discord guild ID
        collection_name: Collection to query (kills, server_events, connection_events)
        limit: Maximum number of events to return
        query_filter: Additional query filter
        
    Returns:
        list: List of events
    """
    # Get server IDs for this guild
    server_ids = await get_server_ids_for_guild(guild_id)
    
    # If no servers, return empty list
    if not server_ids:
        return []
    
    # Base query
    base_query = {"server_id": {"$in": server_ids}}
    
    # Merge with additional filter if provided
    query = {**base_query, **(query_filter or {})}
    
    # Get database instance
    db = await Database.get_instance()
    
    # Get collection and find events
    collection = await db.get_collection(collection_name)
    cursor = collection.find(query).sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(limit)
    
    return events