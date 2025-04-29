"""
LSP Error Suppressors

This module contains type stubs and suppression utilities to fix Language Server Protocol (LSP)
errors without changing the actual functionality of the code.

These suppressors help IDE integration by providing type hints to the language server
while maintaining compatibility with the actual code execution.
"""

from typing import Any, Dict, List, Optional, Union, TypeVar, Generic, Protocol, Callable, Type
import datetime

# ======================================================================
# Discord Type Suppressors
# ======================================================================

# Base DiscordTask class is defined below

class DiscordContext:
    """Type stub for discord.ApplicationContext to suppress LSP errors"""
    author: Any
    guild: Any
    channel: Any
    
    async def defer(self, *args, **kwargs):
        pass
        
    async def respond(self, *args, **kwargs):
        pass
        
    async def send(self, *args, **kwargs):
        pass

class DiscordMember:
    """Type stub for discord.Member to suppress LSP errors"""
    id: int
    name: str
    display_name: str
    guild: Any
    
    def __init__(self, *args, **kwargs):
        pass

class DiscordGuild:
    """Type stub for discord.Guild to suppress LSP errors"""
    id: int
    name: str
    owner_id: int
    
    def __init__(self, *args, **kwargs):
        pass

class DiscordChannel:
    """Type stub for discord.Channel to suppress LSP errors"""
    id: int
    name: str
    
    async def send(self, *args, **kwargs) -> Any:
        pass
    
    async def edit(self, *args, **kwargs) -> Any:
        pass

class DiscordTextChannel(DiscordChannel):
    """Type stub for discord.TextChannel to suppress LSP errors"""
    pass

class DiscordVoiceChannel(DiscordChannel):
    """Type stub for discord.VoiceChannel to suppress LSP errors"""
    pass

class DiscordCategoryChannel(DiscordChannel):
    """Type stub for discord.CategoryChannel to suppress LSP errors"""
    pass

class DiscordMessage:
    """Type stub for discord.Message to suppress LSP errors"""
    id: int
    content: str
    author: Any
    channel: Any
    guild: Any
    
    async def edit(self, *args, **kwargs) -> Any:
        pass
    
    async def delete(self, *args, **kwargs) -> Any:
        pass

class DiscordEmbed:
    """Type stub for discord.Embed to suppress LSP errors"""
    title: str
    description: str
    
    def __init__(self, *args, **kwargs):
        pass
    
    def add_field(self, *args, **kwargs) -> Any:
        pass
    
    def set_footer(self, *args, **kwargs) -> Any:
        pass
    
    def set_thumbnail(self, *args, **kwargs) -> Any:
        pass
    
    def set_image(self, *args, **kwargs) -> Any:
        pass

class DiscordColor:
    """Type stub for discord.Color to suppress LSP errors"""
    @staticmethod
    def red() -> Any:
        pass
    
    @staticmethod
    def green() -> Any:
        pass
    
    @staticmethod
    def blue() -> Any:
        pass
    
    @staticmethod
    def gold() -> Any:
        pass
    
    @staticmethod
    def orange() -> Any:
        pass
    
    @staticmethod
    def purple() -> Any:
        pass

class DiscordOption:
    """Type stub for discord.Option to suppress LSP errors"""
    def __init__(self, *args, **kwargs):
        pass

class DiscordTask:
    """Type stub for discord.ext.tasks.loop to suppress LSP errors"""
    _running_state: bool = False
    
    def __init__(self, *args, **kwargs):
        self._running_state = False
    
    def start(self, *args, **kwargs) -> None:
        self._running_state = True
    
    def stop(self, *args, **kwargs) -> None:
        self._running_state = False
    
    def cancel(self, *args, **kwargs) -> None:
        self._running_state = False
    
    def is_running(self) -> bool:
        return self._running_state
    
    def before_loop(self, func: Callable) -> Callable:
        return func
    
    def after_loop(self, func: Callable) -> Callable:
        return func
    
    def error(self, func: Callable) -> Callable:
        return func
    
    def __call__(self, func: Callable) -> 'DiscordTask':
        return self

# ======================================================================
# MongoDB Type Suppressors
# ======================================================================

class MongoCollection:
    """Type stub for motor.motor_asyncio.AsyncIOMotorCollection to suppress LSP errors"""
    
    async def find_one(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        pass
    
    async def find(self, *args, **kwargs) -> Any:
        pass
    
    async def insert_one(self, *args, **kwargs) -> Any:
        pass
    
    async def insert_many(self, *args, **kwargs) -> Any:
        pass
    
    async def update_one(self, *args, **kwargs) -> Any:
        pass
    
    async def update_many(self, *args, **kwargs) -> Any:
        pass
    
    async def delete_one(self, *args, **kwargs) -> Any:
        pass
    
    async def delete_many(self, *args, **kwargs) -> Any:
        pass
    
    async def count_documents(self, *args, **kwargs) -> int:
        return 0
    
    async def distinct(self, *args, **kwargs) -> List[Any]:
        return []
    
    async def aggregate(self, *args, **kwargs) -> Any:
        return []

class MongoCursor:
    """Type stub for motor.motor_asyncio.AsyncIOMotorCursor to suppress LSP errors"""
    
    def __aiter__(self) -> 'MongoCursor':
        return self
    
    async def __anext__(self) -> Dict[str, Any]:
        return {}
    
    def sort(self, *args, **kwargs) -> 'MongoCursor':
        return self
    
    def skip(self, n: int) -> 'MongoCursor':
        return self
    
    def limit(self, n: int) -> 'MongoCursor':
        return self
    
    async def to_list(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return []
    
    async def count(self) -> int:
        return 0
    
    async def distinct(self, *args, **kwargs) -> List[Any]:
        return []

class MongoDatabase:
    """Type stub for motor.motor_asyncio.AsyncIOMotorDatabase to suppress LSP errors"""
    
    async def get_collection(self, name: str) -> MongoCollection:
        collection = MongoCollection()
        return collection
    
    async def list_collection_names(self) -> List[str]:
        return []

class MongoClient:
    """Type stub for motor.motor_asyncio.AsyncIOMotorClient to suppress LSP errors"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def __getitem__(self, name: str) -> MongoDatabase:
        db = MongoDatabase()
        return db
    
    def get_database(self, name: str) -> MongoDatabase:
        db = MongoDatabase()
        return db
    
    async def list_database_names(self) -> List[str]:
        return []

# ======================================================================
# Type Helpers for Model Classes
# ======================================================================

class MongoModel:
    """Helper for MongoDB model classes to suppress LSP errors"""
    _id: Any
    
    def to_dict(self) -> Dict[str, Any]:
        return {}
    
    async def update(self, db: Any) -> None:
        pass
    
    @classmethod
    async def create(cls, db: Any, **kwargs) -> Any:
        return cls()
    
    @classmethod
    async def get_by_id(cls, db: Any, id: Any) -> Optional[Any]:
        return cls()

class PlayerModel(MongoModel):
    """Helper for Player model to suppress LSP errors"""
    player_id: str
    player_name: str
    discord_id: Optional[str]
    total_kills: int
    total_deaths: int
    first_seen: datetime.datetime
    last_seen: datetime.datetime
    faction_id: Optional[str]
    prey_id: Optional[str]
    prey_name: Optional[str]
    prey_kills: int
    nemesis_id: Optional[str]
    nemesis_name: Optional[str]
    nemesis_deaths: int
    
    async def update_rivalry_data(self, db: Any, kill_event: Any = None, death_event: Any = None) -> None:
        pass
        
    @classmethod
    async def get_by_player_id(cls, db: Any, player_id: str) -> Optional['PlayerModel']:
        return None
        
    @classmethod
    async def get_by_discord_id(cls, db: Any, discord_id: str) -> List['PlayerModel']:
        return []

class KillModel(MongoModel):
    """Helper for Kill model to suppress LSP errors"""
    timestamp: datetime.datetime
    killer_id: str
    killer_name: str
    victim_id: str
    victim_name: str
    weapon: str
    distance: float
    server_id: str
    is_suicide: bool
    is_menu_suicide: bool
    is_fall_death: bool
    from_batch_process: bool

class ServerModel(MongoModel):
    """Helper for Server model to suppress LSP errors"""
    name: str
    ip: str
    port: int
    log_path: str
    guild_id: str
    server_id: Optional[str]
    access_method: str
    ssh_user: Optional[str]
    ssh_password: Optional[str]
    ssh_key_path: Optional[str]
    csv_enabled: bool
    log_enabled: bool
    added_at: datetime.datetime
    updated_at: datetime.datetime

class ParserStateModel(MongoModel):
    """Helper for ParserState model to suppress LSP errors"""
    server_id: str
    parser_type: str
    last_position: int
    is_historical: bool
    last_filename: Optional[str]
    auto_parsing_enabled: bool
    updated_at: datetime.datetime

class ParserMemoryModel(MongoModel):
    """Helper for ParserMemory model to suppress LSP errors"""
    server_id: str
    parser_type: str
    status: str
    total_files: int
    processed_files: int
    total_lines: int
    processed_lines: int
    current_file: str
    percent_complete: int
    is_running: bool
    start_time: Optional[datetime.datetime]
    updated_at: datetime.datetime
    progress: int
    last_update_timestamp: datetime.datetime
    
    async def save(self, db: Any) -> None:
        pass