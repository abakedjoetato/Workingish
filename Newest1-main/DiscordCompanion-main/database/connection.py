import asyncpg
import logging
import json
from config import DATABASE_URL

logger = logging.getLogger('deadside_bot.database')

class Database:
    """
    Singleton class for managing PostgreSQL database connections.
    Uses asyncpg for async PostgreSQL operations.
    """
    _instance = None
    _pool = None
    
    @classmethod
    async def get_instance(cls):
        """Get or create the singleton instance of the Database class"""
        if cls._instance is None:
            cls._instance = cls()
            try:
                cls._pool = await asyncpg.create_pool(DATABASE_URL)
                # Test connection
                async with cls._pool.acquire() as conn:
                    await conn.execute('SELECT 1')
                logger.info("Connected to PostgreSQL")
                
                # Initialize tables if they don't exist
                await cls._init_tables()
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise
        return cls._instance
    
    @classmethod
    async def _init_tables(cls):
        """Initialize database tables if they don't exist"""
        async with cls._pool.acquire() as conn:
            # Create servers table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS servers (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    log_path TEXT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    access_method TEXT DEFAULT 'local',
                    ssh_user TEXT,
                    ssh_password TEXT,
                    ssh_key_path TEXT,
                    csv_enabled BOOLEAN DEFAULT TRUE,
                    log_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create players table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    player_id TEXT NOT NULL UNIQUE,
                    player_name TEXT NOT NULL,
                    discord_id BIGINT,
                    total_kills INTEGER DEFAULT 0,
                    total_deaths INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create kills table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS kills (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    killer_id TEXT,
                    killer_name TEXT,
                    victim_id TEXT NOT NULL,
                    victim_name TEXT NOT NULL,
                    weapon TEXT,
                    distance FLOAT,
                    server_id INTEGER REFERENCES servers(id),
                    is_suicide BOOLEAN DEFAULT FALSE,
                    is_menu_suicide BOOLEAN DEFAULT FALSE,
                    is_fall_death BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Create server_events table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    event_type TEXT NOT NULL,
                    server_id INTEGER REFERENCES servers(id),
                    details JSONB
                )
            ''')
            
            # Create connection_events table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS connection_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    player_id TEXT,
                    player_name TEXT NOT NULL,
                    server_id INTEGER REFERENCES servers(id),
                    event_type TEXT NOT NULL,
                    reason TEXT
                )
            ''')
            
            # Create parser_state table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS parser_state (
                    id SERIAL PRIMARY KEY,
                    server_id INTEGER REFERENCES servers(id),
                    parser_type TEXT NOT NULL,
                    last_position BIGINT DEFAULT 0,
                    is_historical BOOLEAN DEFAULT FALSE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create guild_configs table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS guild_configs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL UNIQUE,
                    premium_tier TEXT DEFAULT 'free',
                    killfeed_channel BIGINT,
                    connection_channel BIGINT,
                    mission_channel BIGINT
                )
            ''')
            
            logger.info("Database tables initialized")
    
    async def get_collection(self, collection_name):
        """
        Compatibility method for MongoDB-style collection access.
        Returns a CollectionWrapper that mimics MongoDB collections.
        """
        if not self._pool:
            raise Exception("Database not initialized")
        return CollectionWrapper(self._pool, collection_name)
    
    async def close(self):
        """Close the PostgreSQL connection pool"""
        if self._pool:
            await self._pool.close()
            logger.info("Closed PostgreSQL connection")
            self._pool = None
            Database._instance = None

class CollectionWrapper:
    """
    Wrapper class to provide MongoDB-like collection methods
    for PostgreSQL tables to minimize code changes.
    """
    def __init__(self, pool, table_name):
        self.pool = pool
        self.table_name = table_name
    
    async def find_one(self, query):
        """Find a single document/row"""
        where_clause, values = self._build_where(query)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self.table_name} {where_clause} LIMIT 1",
                *values
            )
            
            if row:
                return dict(row)
            return None
    
    async def find(self, query=None):
        """Find multiple documents/rows"""
        if query is None:
            query = {}
        
        where_clause, values = self._build_where(query)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {self.table_name} {where_clause}",
                *values
            )
            
            # Return direct cursor for compatibility with immediate await
            cursor = CursorWrapper(rows)
            return cursor
    
    async def insert_one(self, document):
        """Insert a single document/row"""
        fields = []
        placeholders = []
        values = []
        
        i = 1
        for key, value in document.items():
            if key != '_id':  # Skip MongoDB ID field
                fields.append(key)
                placeholders.append(f"${i}")
                
                # Convert dictionaries to JSON
                if isinstance(value, dict):
                    value = json.dumps(value)
                
                values.append(value)
                i += 1
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"INSERT INTO {self.table_name} ({fields_str}) VALUES ({placeholders_str}) RETURNING id",
                *values
            )
            
            id_value = await result.fetchval()
            return {"inserted_id": id_value}
    
    async def update_one(self, query, update):
        """Update a single document/row"""
        where_clause, where_values = self._build_where(query)
        
        # Handle MongoDB-style $set operator
        if "$set" in update:
            update_data = update["$set"]
        else:
            update_data = update
        
        set_clauses = []
        values = []
        
        i = len(where_values) + 1
        for key, value in update_data.items():
            # Convert dictionaries to JSON
            if isinstance(value, dict):
                value = json.dumps(value)
                
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
            i += 1
        
        set_clause = ", ".join(set_clauses)
        all_values = where_values + values
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} {where_clause} LIMIT 1",
                *all_values
            )
            
            return {"modified_count": result.split()[1]}
            
    async def update_many(self, query, update):
        """Update multiple documents/rows"""
        where_clause, where_values = self._build_where(query)
        
        # Handle MongoDB-style $set operator
        if "$set" in update:
            update_data = update["$set"]
        else:
            update_data = update
        
        set_clauses = []
        values = []
        
        i = len(where_values) + 1
        for key, value in update_data.items():
            # Convert dictionaries to JSON
            if isinstance(value, dict):
                value = json.dumps(value)
                
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
            i += 1
        
        set_clause = ", ".join(set_clauses)
        all_values = where_values + values
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} {where_clause}",
                *all_values
            )
            
            return {"modified_count": result.split()[1]}
    
    async def delete_one(self, query):
        """Delete a single document/row"""
        where_clause, values = self._build_where(query)
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table_name} {where_clause} LIMIT 1",
                *values
            )
            
            return {"deleted_count": result.split()[1]}
            
    async def delete_many(self, query):
        """Delete multiple documents/rows"""
        where_clause, values = self._build_where(query)
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table_name} {where_clause}",
                *values
            )
            
            return {"deleted_count": result.split()[1]}
    
    async def count_documents(self, query=None):
        """Count documents/rows"""
        if query is None:
            query = {}
            
        where_clause, values = self._build_where(query)
        
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self.table_name} {where_clause}",
                *values
            )
            
            return count
    
    def _build_where(self, query):
        """Build WHERE clause from MongoDB-style query"""
        if not query:
            return "", []
            
        clauses = []
        values = []
        i = 1
        
        for key, value in query.items():
            # Handle MongoDB _id to PostgreSQL id conversion
            if key == "_id":
                key = "id"
                
            # Handle ObjectId as string
            if isinstance(value, str) and key == "id":
                try:
                    value = int(value)
                except ValueError:
                    pass
            
            # For simplicity, we only handle direct equality for now
            clauses.append(f"{key} = ${i}")
            values.append(value)
            i += 1
            
        where_clause = "WHERE " + " AND ".join(clauses) if clauses else ""
        return where_clause, values

class CursorWrapper:
    """Wrapper for result rows to mimic MongoDB cursor"""
    def __init__(self, rows):
        self.rows = rows
        self.index = 0
    
    async def to_list(self, length=None):
        """Convert results to a list"""
        if length is None:
            return [dict(row) for row in self.rows]
        else:
            return [dict(row) for row in self.rows[:length]]
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.rows):
            raise StopAsyncIteration
        
        result = dict(self.rows[self.index])
        self.index += 1
        return result
