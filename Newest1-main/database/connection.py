import motor.motor_asyncio
import logging
import json
import asyncio
from bson import ObjectId
from datetime import datetime
from config import MONGODB_URI, DATABASE_NAME

logger = logging.getLogger('deadside_bot.database')

class Database:
    """
    Singleton class for managing MongoDB database connections.
    Uses motor.motor_asyncio for async MongoDB operations.
    """
    _instance = None
    _client = None
    _db = None
    
    @classmethod
    async def get_instance(cls):
        """Get or create the singleton instance of the Database class"""
        if cls._instance is None:
            cls._instance = cls()
            try:
                # Connect to MongoDB
                cls._client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
                cls._db = cls._client[DATABASE_NAME]
                
                # Test connection
                await cls._db.command({"ping": 1})
                logger.info("Connected to MongoDB")
                
                # Initialize collections and indexes
                await cls._init_collections()
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return cls._instance
    
    @classmethod
    async def _init_collections(cls):
        """Initialize collections and create indexes if they don't exist"""
        try:
            if cls._db is None:
                logger.error("Database not initialized in _init_collections")
                return
                
            # Create indexes for servers collection
            servers = cls._db["servers"]
            await servers.create_index("guild_id")
            await servers.create_index([("name", 1), ("guild_id", 1)], unique=True)
            
            # Create indexes for players collection
            players = cls._db["players"] 
            await players.create_index("player_id", unique=True)
            await players.create_index("discord_id")
            await players.create_index("player_name")
            
            # Create indexes for kills collection
            kills = cls._db["kills"]
            await kills.create_index("timestamp")
            await kills.create_index("server_id")
            await kills.create_index("killer_id")
            await kills.create_index("victim_id")
            
            # Create indexes for server_events collection
            server_events = cls._db["server_events"]
            await server_events.create_index([("timestamp", -1)])
            await server_events.create_index("server_id")
            await server_events.create_index("event_type")
            
            # Create indexes for connection_events collection
            connection_events = cls._db["connection_events"]
            await connection_events.create_index([("timestamp", -1)])
            await connection_events.create_index("server_id")
            await connection_events.create_index("player_id")
            
            # Create indexes for parser_state collection
            parser_state = cls._db["parser_state"]
            await parser_state.create_index([
                ("server_id", 1), 
                ("parser_type", 1), 
                ("is_historical", 1)
            ], unique=True)
            
            # Create indexes for guild_configs collection
            guild_configs = cls._db["guild_configs"]
            await guild_configs.create_index("guild_id", unique=True)
            
            # Create global_config collection for bot-wide settings including home guild
            # Initialize with default values if it doesn't exist
            global_config_collection = cls._db["global_config"]
            global_config = await global_config_collection.find_one({"_id": "settings"})
            if not global_config:
                await global_config_collection.insert_one({
                    "_id": "settings",
                    "home_guild_id": None,
                    "owner_ids": [],
                    "version": "1.0.0",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
            
            logger.info("MongoDB collections and indexes initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB collections: {e}")
            # Don't raise, just log the error and continue
    
    async def get_collection(self, collection_name):
        """Get a MongoDB collection"""
        try:
            if self._db is None:
                logger.error(f"Database not initialized in get_collection for {collection_name}")
                raise Exception("Database not initialized")
            
            if not collection_name:
                logger.error("No collection name provided in get_collection")
                raise ValueError("Collection name is required")
                
            return self._db[collection_name]
        except Exception as e:
            logger.error(f"Error getting collection {collection_name}: {e}")
            raise
    
    async def get_home_guild_id(self):
        """Get the ID of the home guild"""
        try:
            if self._db is None:
                logger.error("Database not initialized in get_home_guild_id")
                return None
            
            try:
                collection = await self.get_collection("global_config")
                global_config = await collection.find_one({"_id": "settings"})
                
                if global_config and "home_guild_id" in global_config:
                    return global_config.get("home_guild_id")
                else:
                    logger.warning("No home guild ID found in global_config")
                    return None
            except Exception as inner_e:
                logger.error(f"Error accessing global_config collection: {inner_e}")
                return None
        except Exception as e:
            logger.error(f"Error in get_home_guild_id: {e}")
            return None
    
    async def set_home_guild_id(self, guild_id):
        """Set the ID of the home guild"""
        if self._db is None:
            raise Exception("Database not initialized")
        
        global_config = await self.get_collection("global_config")
        await global_config.update_one(
            {"_id": "settings"},
            {"$set": {
                "home_guild_id": guild_id,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f"Set home guild ID to {guild_id}")
        
        # Also ensure the guild has enterprise premium tier
        guild_configs = await self.get_collection("guild_configs")
        await guild_configs.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "premium_tier": "enterprise",
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    async def is_home_guild(self, guild_id):
        """Check if a guild is the home guild"""
        try:
            if guild_id is None:
                return False
                
            home_guild_id = await self.get_home_guild_id()
            # Only return True if both values are valid and equal
            if home_guild_id and guild_id:
                return str(home_guild_id) == str(guild_id)
            return False
        except Exception as e:
            logger.error(f"Error in is_home_guild: {e}")
            return False
    
    async def get_guild_premium_tier(self, guild_id):
        """Get the premium tier of a guild"""
        try:
            if self._db is None:
                logger.error("Database not initialized in get_guild_premium_tier")
                return "free"  # Safely fallback to free tier
            
            # If this is the home guild, always return enterprise
            try:
                if await self.is_home_guild(guild_id):
                    return "enterprise"
            except Exception as e:
                logger.error(f"Error checking home guild: {e}")
                # Continue execution to check guild config directly
            
            collection = await self.get_collection("guild_configs")
            guild_config = await collection.find_one({"guild_id": guild_id})
            
            if guild_config and "premium_tier" in guild_config:
                return guild_config.get("premium_tier")
            else:
                return "free"  # Default if no config found or no tier specified
        except Exception as e:
            logger.error(f"Error in get_guild_premium_tier: {e}")
            return "free"  # Safely fallback to free tier
    
    async def set_guild_premium_tier(self, guild_id, tier):
        """Set the premium tier of a guild"""
        if self._db is None:
            raise Exception("Database not initialized")
        
        # Don't allow changing the home guild's tier
        if await self.is_home_guild(guild_id):
            logger.warning(f"Attempted to change home guild tier to {tier}, ignoring")
            return
        
        collection = await self.get_collection("guild_configs")
        await collection.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "premium_tier": tier,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f"Set guild {guild_id} premium tier to {tier}")
    
    async def close(self):
        """Close the MongoDB connection"""
        if self._client is not None:
            self._client.close()
            logger.info("Closed MongoDB connection")
            self._client = None
            self._db = None
            Database._instance = None