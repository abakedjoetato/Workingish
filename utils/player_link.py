"""
Player Linking Utility

This module provides functions to link Discord users with their in-game player profiles,
allowing users to use commands without specifying their player name each time.
"""

import logging
from typing import Optional, List, Dict, Any, Union
import asyncio
from datetime import datetime

from database.connection import Database
from database.models import Player

logger = logging.getLogger(__name__)

async def get_linked_player_for_user(discord_id: Union[int, str]) -> Optional[Player]:
    """
    Get the player linked to a Discord user
    
    Args:
        discord_id: Discord user ID (either as int or string)
        
    Returns:
        Player: The linked player or None if not found
    """
    discord_id_str = str(discord_id)
    
    try:
        db = await Database.get_instance()
        player = await Player.get_by_discord_id(db, discord_id_str)
        return player
    except Exception as e:
        logger.error(f"Error getting linked player for {discord_id}: {e}")
        return None
        
async def link_player_to_user(discord_id: Union[int, str], player_id: str) -> bool:
    """
    Link a player to a Discord user
    
    Args:
        discord_id: Discord user ID
        player_id: In-game player ID (SteamID)
        
    Returns:
        bool: True if successful, False otherwise
    """
    discord_id_str = str(discord_id)
    
    try:
        db = await Database.get_instance()
        
        # Get the player
        player = await Player.get_by_player_id(db, player_id)
        if not player:
            logger.warning(f"Attempted to link non-existent player {player_id}")
            return False
            
        # Check if this Discord user already has a linked player
        existing_link = await Player.get_by_discord_id(db, discord_id_str)
        if existing_link:
            # If same player, consider it a success
            if existing_link.player_id == player_id:
                return True
                
            # Otherwise, unlink the existing player first
            existing_link.discord_id = None
            await existing_link.update(db)
            
        # Link the new player
        player.discord_id = discord_id_str
        await player.update(db)
        
        logger.info(f"Linked Discord user {discord_id} to player {player.player_name} ({player_id})")
        return True
        
    except Exception as e:
        logger.error(f"Error linking player {player_id} to Discord user {discord_id}: {e}")
        return False
        
async def unlink_player_from_user(discord_id: Union[int, str]) -> bool:
    """
    Unlink a player from a Discord user
    
    Args:
        discord_id: Discord user ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    discord_id_str = str(discord_id)
    
    try:
        db = await Database.get_instance()
        
        # Find the linked player
        player = await Player.get_by_discord_id(db, discord_id_str)
        if not player:
            # No linked player, so technically already unlinked
            return True
            
        # Unlink the player
        player.discord_id = None
        await player.update(db)
        
        logger.info(f"Unlinked Discord user {discord_id} from player {player.player_name} ({player.player_id})")
        return True
        
    except Exception as e:
        logger.error(f"Error unlinking player from Discord user {discord_id}: {e}")
        return False
        
async def get_player_by_name(name: str, partial_match: bool = False) -> Optional[Player]:
    """
    Find a player by name
    
    Args:
        name: Player name to search for
        partial_match: Whether to allow partial matches
        
    Returns:
        Player: The found player or None if not found
    """
    try:
        db = await Database.get_instance()
        
        if partial_match:
            # Use regex for partial matching
            players_collection = db.get_collection("players")
            player_doc = await players_collection.find_one({"player_name": {"$regex": name, "$options": "i"}})
            
            if player_doc:
                return Player.from_dict(player_doc)
        else:
            # Exact match (case-insensitive)
            players_collection = db.get_collection("players")
            player_doc = await players_collection.find_one({"player_name": {"$regex": f"^{name}$", "$options": "i"}})
            
            if player_doc:
                return Player.from_dict(player_doc)
                
        return None
        
    except Exception as e:
        logger.error(f"Error finding player by name {name}: {e}")
        return None
        
async def search_players(query: str, limit: int = 10) -> List[Player]:
    """
    Search for players matching a query
    
    Args:
        query: Search query
        limit: Maximum number of results
        
    Returns:
        List[Player]: List of matching players
    """
    try:
        db = await Database.get_instance()
        players_collection = db.get_collection("players")
        
        # Use regex for partial matching
        cursor = players_collection.find({"player_name": {"$regex": query, "$options": "i"}}).limit(limit)
        player_docs = await cursor.to_list(length=limit)
        
        return [Player.from_dict(doc) for doc in player_docs]
        
    except Exception as e:
        logger.error(f"Error searching players with query {query}: {e}")
        return []