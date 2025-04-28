from datetime import datetime

class Server:
    """Model for game server configuration"""
    collection_name = "servers"
    
    def __init__(self, name, ip, port, log_path, guild_id, 
                 access_method="local", ssh_user=None, ssh_password=None, 
                 ssh_key_path=None, csv_enabled=True, log_enabled=True, 
                 _id=None):
        self.name = name
        self.ip = ip
        self.port = port
        self.log_path = log_path
        self.guild_id = guild_id
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
        data = await collection.find_one({"id": server_id})
        if data:
            return cls(**{**data, "_id": data.get("id")})
        return None
    
    @classmethod
    async def get_by_guild(cls, db, guild_id):
        """Get all servers for a specific guild"""
        collection = await db.get_collection(cls.collection_name)
        cursor = await collection.find({"guild_id": guild_id})
        servers = []
        
        # Get the server docs from the cursor
        docs = await cursor.to_list(None)
        for data in docs:
            # Convert the PostgreSQL id to _id for compatibility
            servers.append(cls(**{**data, "_id": data.get("id")}))
        
        return servers
    
    async def update(self, db):
        """Update server in the database"""
        self.updated_at = datetime.utcnow()
        data = self.to_dict()
        collection = await db.get_collection(self.collection_name)
        await collection.update_one(
            {"id": self._id},
            {"$set": data}
        )
        
    async def delete(self, db):
        """Delete server from the database"""
        collection = await db.get_collection(self.collection_name)
        await collection.delete_one({"id": self._id})
        
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
            # Handle either MongoDB-style _id or PostgreSQL-style id
            id_value = data.get("_id") or data.get("id")
            return cls(**{**data, "_id": id_value})
        return None
        
    @classmethod
    async def get_by_discord_id(cls, db, discord_id):
        """Get all players linked to a Discord user"""
        collection = await db.get_collection(cls.collection_name) 
        cursor = await collection.find({"discord_id": discord_id})
        players = []
        
        # Get all matching documents
        docs = await cursor.to_list(None)
        for data in docs:
            players.append(cls(**{**data, "_id": data.get("id")}))
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
                is_historical=False, updated_at=None, _id=None):
        self.server_id = server_id
        self.parser_type = parser_type  # "csv", "log"
        self.last_position = last_position
        self.is_historical = is_historical
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
            # Handle either MongoDB-style _id or PostgreSQL-style id
            id_value = data.get("_id") or data.get("id")
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
        collection = await db.get_collection(cls.collection_name)
        data = await collection.find_one({"guild_id": guild_id})
        
        if data:
            # Handle either MongoDB-style _id or PostgreSQL-style id
            id_value = data.get("_id") or data.get("id")
            return cls(**{**data, "_id": id_value})
        
        # Create new config
        config = cls(guild_id=guild_id)
        collection = await db.get_collection(cls.collection_name)
        result = await collection.insert_one(config.to_dict())
        config._id = result.inserted_id
        return config
    
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
