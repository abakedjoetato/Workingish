from datetime import datetime
import logging

logger = logging.getLogger('deadside_bot.database.models')

class Server:
    """Model for game server configuration"""
    collection_name = "servers"
    
    def __init__(self, name, ip, port, log_path, guild_id, 
                 access_method="local", ssh_user=None, ssh_password=None, 
                 ssh_key_path=None, csv_enabled=True, log_enabled=True, 
                 server_id=None, _id=None):
        self.name = name
        self.ip = ip
        self.port = port
        self.log_path = log_path
        self.guild_id = guild_id
        self.server_id = server_id  # Game server ID used in directory structure
        self.access_method = access_method  # "local", "sftp"
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.ssh_key_path = ssh_key_path
        self.csv_enabled = csv_enabled
        self.log_enabled = log_enabled
        self.added_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._id = _id
        
    @classmethod
    async def create(cls, db, **kwargs):
        """Create a new server in the database"""
        server = cls(**kwargs)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(server.to_dict())
        server._id = result.inserted_id
        return server
    
    @classmethod
    async def get_by_id(cls, db, server_id):
        """Get a server by ID"""
        collection = await db.get_collection(cls.collection_name)
        # Try with MongoDB's _id first
        data = await collection.find_one({"_id": server_id})
        
        # If not found, try with 'id' for backward compatibility
        if not data:
            data = await collection.find_one({"id": server_id})
        
        if data:
            # MongoDB already has _id
            id_value = data.get("_id")
            if id_value:
                return cls(**{**data, "_id": id_value})
        return None
    
    @classmethod
    async def get_by_guild(cls, db, guild_id):
        """Get all servers for a specific guild"""
        servers = []
        
        try:
            if not db:
                logger.error("Database instance is None in Server.get_by_guild")
                return servers
                
            if not guild_id:
                logger.error("guild_id is None in Server.get_by_guild")
                return servers
            
            try:
                collection = await db.get_collection(cls.collection_name)
                cursor = collection.find({"guild_id": guild_id})
                
                # Get the server docs from the cursor
                docs = await cursor.to_list(None)
                
                for data in docs:
                    try:
                        # MongoDB already has _id, but ensure it's used correctly
                        id_value = data.get("_id") 
                        if id_value:
                            servers.append(cls(**{**data, "_id": id_value}))
                    except Exception as e:
                        logger.error(f"Error processing server data: {e}")
                        continue  # Skip this server but continue with others
                
            except Exception as e:
                logger.error(f"Error querying servers collection: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error in Server.get_by_guild: {e}")
        
        return servers
    
    async def update(self, db):
        """Update server in the database"""
        self.updated_at = datetime.utcnow()
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"_id": self._id},
            {"$set": data}
        )
        
    async def delete(self, db):
        """Delete server from the database"""
        collection = await db.get_collection(self.collection_name)
        await collection.delete_one({"_id": self._id})
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class Player:
    """Model for player data"""
    collection_name = "players"
    
    def __init__(self, player_id, player_name, discord_id=None,
                total_kills=0, total_deaths=0, first_seen=None, last_seen=None,
                _id=None):
        self.player_id = player_id
        self.player_name = player_name
        self.discord_id = discord_id
        self.total_kills = total_kills
        self.total_deaths = total_deaths
        self.first_seen = first_seen or datetime.utcnow()
        self.last_seen = last_seen or datetime.utcnow()
        self._id = _id
        
    @classmethod
    async def create(cls, db, **kwargs):
        """Create a new player in the database"""
        player = cls(**kwargs)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(player.to_dict())
        player._id = result.inserted_id
        return player
    
    @classmethod
    async def get_by_player_id(cls, db, player_id):
        """Get a player by game ID"""
        collection = await db.get_collection(cls.collection_name)
        data = await collection.find_one({"player_id": player_id})
        if data:
            # Use MongoDB's _id
            id_value = data.get("_id")
            if id_value:
                return cls(**{**data, "_id": id_value})
        return None
        
    @classmethod
    async def get_by_discord_id(cls, db, discord_id):
        """Get all players linked to a Discord user"""
        collection = await db.get_collection(cls.collection_name) 
        cursor = collection.find({"discord_id": discord_id})
        players = []
        
        # Get all matching documents
        docs = await cursor.to_list(None)
        for data in docs:
            # MongoDB already has _id
            id_value = data.get("_id")
            if id_value:
                players.append(cls(**{**data, "_id": id_value}))
        return players
    
    async def update(self, db):
        """Update player in the database"""
        self.last_seen = datetime.utcnow()
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"_id": self._id},
            {"$set": data}
        )
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class Kill:
    """Model for kill events"""
    collection_name = "kills"
    
    def __init__(self, timestamp, killer_id, killer_name, victim_id, victim_name,
                weapon, distance, server_id, is_suicide=False, is_menu_suicide=False,
                is_fall_death=False, _id=None):
        self.timestamp = timestamp
        self.killer_id = killer_id
        self.killer_name = killer_name
        self.victim_id = victim_id
        self.victim_name = victim_name
        self.weapon = weapon
        self.distance = distance
        self.server_id = server_id
        self.is_suicide = is_suicide
        self.is_menu_suicide = is_menu_suicide
        self.is_fall_death = is_fall_death
        self._id = _id
    
    @classmethod
    async def create(cls, db, **kwargs):
        """Create a new kill record in the database"""
        kill = cls(**kwargs)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(kill.to_dict())
        kill._id = result.inserted_id
        return kill
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class ServerEvent:
    """Model for server events (missions, airdrops, etc.)"""
    collection_name = "server_events"
    
    def __init__(self, timestamp, event_type, server_id, details=None, _id=None):
        self.timestamp = timestamp
        self.event_type = event_type  # "mission", "helicrash", "airdrop", "trader", etc.
        self.server_id = server_id
        self.details = details or {}
        self._id = _id
    
    @classmethod
    async def create(cls, db, **kwargs):
        """Create a new server event in the database"""
        event = cls(**kwargs)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(event.to_dict())
        event._id = result.inserted_id
        return event
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class ConnectionEvent:
    """Model for player connection/disconnection events"""
    collection_name = "connection_events"
    
    def __init__(self, timestamp, player_id, player_name, server_id, 
                event_type, reason=None, _id=None):
        self.timestamp = timestamp
        self.player_id = player_id
        self.player_name = player_name
        self.server_id = server_id
        self.event_type = event_type  # "connect", "disconnect", "kick"
        self.reason = reason
        self._id = _id
    
    @classmethod
    async def create(cls, db, **kwargs):
        """Create a new connection event in the database"""
        event = cls(**kwargs)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(event.to_dict())
        event._id = result.inserted_id
        return event
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class ParserState:
    """Model for tracking parser state"""
    collection_name = "parser_state"
    
    def __init__(self, server_id, parser_type, last_position=0, 
                is_historical=False, last_filename=None, 
                auto_parsing_enabled=True, updated_at=None, _id=None):
        self.server_id = server_id
        self.parser_type = parser_type  # "csv", "log"
        self.last_position = last_position
        self.is_historical = is_historical
        self.last_filename = last_filename
        self.auto_parsing_enabled = auto_parsing_enabled
        self.updated_at = updated_at or datetime.utcnow()
        self._id = _id
    
    @classmethod
    async def get_or_create(cls, db, server_id, parser_type, is_historical=False):
        """Get existing parser state or create a new one"""
        collection = await db.get_collection(cls.collection_name)
        data = await collection.find_one({
            "server_id": server_id,
            "parser_type": parser_type,
            "is_historical": is_historical
        })
        
        if data:
            # Use MongoDB's _id
            id_value = data.get("_id")
            if id_value:
                return cls(**{**data, "_id": id_value})
        
        # Create new state
        state = cls(
            server_id=server_id,
            parser_type=parser_type,
            is_historical=is_historical
        )
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(state.to_dict())
        state._id = result.inserted_id
        return state
    
    async def update(self, db):
        """Update parser state in the database"""
        self.updated_at = datetime.utcnow()
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"_id": self._id},
            {"$set": data}
        )
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class ParserMemory:
    """Model for storing detailed parser progress information"""
    collection_name = "parser_memory"
    
    def __init__(self, server_id, parser_type, status="Not started", total_files=0,
                processed_files=0, total_lines=0, processed_lines=0, current_file="",
                percent_complete=0, is_running=False, start_time=None, 
                updated_at=None, _id=None):
        self.server_id = server_id
        self.parser_type = parser_type  # "batch_csv", "auto_csv", "log"
        self.status = status
        self.total_files = total_files
        self.processed_files = processed_files
        self.total_lines = total_lines
        self.processed_lines = processed_lines
        self.current_file = current_file
        self.percent_complete = percent_complete
        self.is_running = is_running
        self.start_time = start_time
        self.updated_at = updated_at or datetime.utcnow()
        self._id = _id
    
    @classmethod
    async def get_or_create(cls, db, server_id, parser_type):
        """Get existing parser memory or create a new one"""
        collection = await db.get_collection(cls.collection_name)
        data = await collection.find_one({
            "server_id": server_id,
            "parser_type": parser_type
        })
        
        if data:
            # Use MongoDB's _id
            id_value = data.get("_id")
            if id_value:
                return cls(**{**data, "_id": id_value})
        
        # Create new memory
        memory = cls(
            server_id=server_id,
            parser_type=parser_type
        )
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(memory.to_dict())
        memory._id = result.inserted_id
        return memory
    
    @classmethod
    async def get_parser_status(cls, db, server_id):
        """Get parser status for display in embeds"""
        collection = await db.get_collection(cls.collection_name)
        cursor = collection.find({"server_id": server_id})
        
        parser_status = []
        async for doc in cursor:
            # Convert _id to string for serialization
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            parser_status.append(doc)
            
        return parser_status
        
    @classmethod
    async def reset_all_parsers(cls, db, server_id):
        """Reset all parser states and memories for a server"""
        # Reset parser states
        parser_state_collection = await db.get_collection("parser_state")
        await parser_state_collection.update_many(
            {"server_id": server_id},
            {"$set": {
                "last_position": 0,
                "last_filename": None,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Reset parser memories
        memory_collection = await db.get_collection(cls.collection_name)
        await memory_collection.update_many(
            {"server_id": server_id},
            {"$set": {
                "status": "Not started",
                "total_files": 0,
                "processed_files": 0,
                "total_lines": 0,
                "processed_lines": 0,
                "current_file": "",
                "percent_complete": 0,
                "is_running": False,
                "start_time": None,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return True
    
    async def update(self, db):
        """Update parser memory in the database"""
        self.updated_at = datetime.utcnow()
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"_id": self._id},
            {"$set": data}
        )
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result


class GuildConfig:
    """Model for Discord guild configuration"""
    collection_name = "guild_configs"
    
    def __init__(self, guild_id, premium_tier="free", killfeed_channel=None,
                connection_channel=None, mission_channel=None, 
                _id=None):
        self.guild_id = guild_id
        self.premium_tier = premium_tier
        self.killfeed_channel = killfeed_channel
        self.connection_channel = connection_channel
        self.mission_channel = mission_channel
        self._id = _id
    
    @classmethod
    async def get_or_create(cls, db, guild_id):
        """Get existing guild config or create a new one"""
        try:
            if not db:
                logger.error("Database instance is None in GuildConfig.get_or_create")
                # Return a default config without trying to save it
                return cls(guild_id=guild_id)
                
            if not guild_id:
                logger.error("guild_id is None in GuildConfig.get_or_create")
                return cls(guild_id=0)  # Use a safe default
            
            try:
                collection = await db.get_collection(cls.collection_name)
                data = await collection.find_one({"guild_id": guild_id})
                
                if data:
                    # Use MongoDB's _id
                    id_value = data.get("_id")
                    # Create a new config with the data
                    return cls(**{**data, "_id": id_value})
            except Exception as e:
                logger.error(f"Error retrieving guild config: {e}")
                # Continue to create a new config
            
            # Create new config
            config = cls(guild_id=guild_id)
            
            try:
                # Get collection again in case the first attempt failed
                collection = await db.get_collection(cls.collection_name)
                result = await collection.insert_one(config.to_dict())
                config._id = result.inserted_id
            except Exception as e:
                logger.error(f"Error creating guild config: {e}")
                # Return config without an ID
                
            return config
        except Exception as e:
            logger.error(f"Unexpected error in GuildConfig.get_or_create: {e}")
            # Return a default config as fallback
            return cls(guild_id=guild_id)
    
    async def update(self, db):
        """Update guild config in the database"""
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"_id": self._id},
            {"$set": data}
        )
        
    def to_dict(self):
        """Convert instance to dictionary for database storage"""
        result = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return result
