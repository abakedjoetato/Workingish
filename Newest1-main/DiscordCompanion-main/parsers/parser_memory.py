import logging
from datetime import datetime, timedelta
from database.connection import Database
from database.models import ParserState

logger = logging.getLogger('deadside_bot.parsers.memory')

class ParserMemory:
    """
    Utility class to manage parser state and memory across multiple parsers.
    This helps with tracking, resetting, and managing the state for all parsers.
    """
    
    @staticmethod
    async def reset_all_parsers(server_id):
        """Reset all parsers for a specific server"""
        db = await Database.get_instance()
        collection = await db.get_collection("parser_state")
        result = await collection.update_many(
            {"server_id": server_id},
            {"$set": {"last_position": 0, "updated_at": datetime.utcnow()}}
        )
        modified_count = result.get("modified_count", 0)
        logger.info(f"Reset all parsers for server {server_id}, modified {modified_count} states")
        return modified_count
    
    @staticmethod
    async def get_parser_status(server_id):
        """Get the status of all parsers for a specific server"""
        db = await Database.get_instance()
        collection = await db.get_collection("parser_state")
        cursor = await collection.find({"server_id": server_id})
        
        parser_status = []
        async for state in cursor:
            state['_id'] = str(state.get('_id') or state.get('id'))  # Convert ID to string for serialization
            parser_status.append(state)
            
        return parser_status
    
    @staticmethod
    async def clean_old_parsers(days=30):
        """Clean parser states that haven't been updated in a while"""
        db = await Database.get_instance()
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        collection = await db.get_collection("parser_state")
        result = await collection.delete_many({
            "updated_at": {"$lt": cutoff_date}
        })
        
        deleted_count = result.get("deleted_count", 0)
        logger.info(f"Cleaned {deleted_count} old parser states")
        return deleted_count
    
    @staticmethod
    async def get_parsers_by_type(parser_type):
        """Get all parsers of a specific type"""
        db = await Database.get_instance()
        collection = await db.get_collection("parser_state")
        cursor = await collection.find({"parser_type": parser_type})
        
        parsers = []
        async for state in cursor:
            state['_id'] = str(state.get('_id') or state.get('id'))  # Convert ID to string for serialization
            parsers.append(state)
            
        return parsers
