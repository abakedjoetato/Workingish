"""
Rivalry Tracking System

This module provides functions for tracking player rivalries (Prey/Nemesis) based on kill data,
and generates relationship graphs and statistics for player interactions.
"""

import logging
from datetime import datetime, timedelta
from database.connection import Database
from database.models import Player, Kill

logger = logging.getLogger(__name__)

async def update_rivalry_data(server_id, days_to_analyze=7, premium_limit=30):
    """
    Update rivalry data for all players in a server based on recent kill history
    
    Args:
        server_id: MongoDB ObjectId of the server
        days_to_analyze: Number of days of kill data to analyze
        premium_limit: Maximum days allowed for premium servers
        
    Returns:
        dict: Summary of updated rivalries
    """
    logger.info(f"Updating rivalry data for server {server_id} using {days_to_analyze} days of data")
    
    # Enforce premium limit
    if days_to_analyze > premium_limit:
        days_to_analyze = premium_limit
        logger.warning(f"Requested days exceeded premium limit, using maximum of {premium_limit} days")
    
    # Connect to database
    db = await Database.get_instance()
    
    # Calculate time window
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_to_analyze)
    
    # Get all kills for the server within the time window
    kills_collection = db.kills
    kill_query = {
        "server_id": server_id,
        "timestamp": {"$gte": start_date, "$lte": end_date},
        "is_suicide": False  # Exclude suicides from rivalry tracking
    }
    
    # Get all players who have kills or deaths on this server
    player_ids = set()
    
    # First, get all unique killer_ids and victim_ids from the kills collection
    async for kill in kills_collection.find(kill_query, {"killer_id": 1, "victim_id": 1}):
        player_ids.add(kill["killer_id"])
        player_ids.add(kill["victim_id"])
    
    # Process each player's kill/death data to identify nemesis and prey
    updated_players = 0
    total_players = len(player_ids)
    
    for player_id in player_ids:
        # Find who this player has killed the most (prey)
        prey_pipeline = [
            {"$match": {
                "server_id": server_id,
                "killer_id": player_id,
                "timestamp": {"$gte": start_date, "$lte": end_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": "$victim_id",
                "count": {"$sum": 1},
                "player_name": {"$first": "$victim_name"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        
        # Find who has killed this player the most (nemesis)
        nemesis_pipeline = [
            {"$match": {
                "server_id": server_id,
                "victim_id": player_id,
                "timestamp": {"$gte": start_date, "$lte": end_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": "$killer_id",
                "count": {"$sum": 1},
                "player_name": {"$first": "$killer_name"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        
        # Execute aggregation pipelines
        prey_results = await kills_collection.aggregate(prey_pipeline).to_list(1)
        nemesis_results = await kills_collection.aggregate(nemesis_pipeline).to_list(1)
        
        # Get the player object
        player = await Player.get_by_player_id(db, player_id)
        if not player:
            # This is unusual, but could happen if a player was deleted or something went wrong
            logger.warning(f"Player {player_id} found in kill data but not in players collection")
            continue
        
        # Update player's prey information
        if prey_results:
            prey = prey_results[0]
            player.prey_id = prey["_id"]
            player.prey_name = prey["player_name"]
            player.prey_kills = prey["count"]
        else:
            # Player has no prey
            player.prey_id = None
            player.prey_name = None
            player.prey_kills = 0
        
        # Update player's nemesis information
        if nemesis_results:
            nemesis = nemesis_results[0]
            player.nemesis_id = nemesis["_id"]
            player.nemesis_name = nemesis["player_name"]
            player.nemesis_deaths = nemesis["count"]
        else:
            # Player has no nemesis
            player.nemesis_id = None
            player.nemesis_name = None
            player.nemesis_deaths = 0
        
        # Save the updated player object
        await player.update(db)
        updated_players += 1
    
    summary = {
        "server_id": server_id,
        "days_analyzed": days_to_analyze,
        "total_players": total_players,
        "updated_players": updated_players,
        "start_date": start_date,
        "end_date": end_date
    }
    
    logger.info(f"Rivalry update complete: {updated_players}/{total_players} players updated")
    return summary

async def get_nemesis_data(player_id, server_id=None):
    """
    Get detailed nemesis data for a player
    
    Args:
        player_id: SteamID of the player
        server_id: Optional server filter
        
    Returns:
        dict: Nemesis data including kill details
    """
    db = await Database.get_instance()
    player = await Player.get_by_player_id(db, player_id)
    
    if not player or not player.nemesis_id:
        return None
    
    # Build match query for kill history
    match_query = {
        "killer_id": player.nemesis_id,
        "victim_id": player_id,
        "is_suicide": False
    }
    
    if server_id:
        match_query["server_id"] = server_id
    
    # Get the most recent kills by the nemesis against the player
    kills_collection = db.kills
    recent_kills = await kills_collection.find(match_query).sort("timestamp", -1).limit(10).to_list(10)
    
    # Get the most used weapons by the nemesis against the player
    weapon_pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$weapon",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 3}
    ]
    
    weapons = await kills_collection.aggregate(weapon_pipeline).to_list(3)
    favorite_weapons = [{"weapon": w["_id"], "count": w["count"]} for w in weapons]
    
    # Calculate kill/death ratio between the two players
    kd_query_player = {
        "killer_id": player_id,
        "victim_id": player.nemesis_id,
        "is_suicide": False
    }
    
    if server_id:
        kd_query_player["server_id"] = server_id
        
    player_kills = await kills_collection.count_documents(kd_query_player)
    
    nemesis = await Player.get_by_player_id(db, player.nemesis_id)
    
    result = {
        "player_id": player_id,
        "player_name": player.player_name,
        "nemesis_id": player.nemesis_id,
        "nemesis_name": player.nemesis_name,
        "nemesis_deaths": player.nemesis_deaths,
        "player_kills": player_kills,
        "kd_ratio": round(player_kills / max(1, player.nemesis_deaths), 2),
        "favorite_weapons": favorite_weapons,
        "recent_kills": [
            {
                "timestamp": k["timestamp"],
                "weapon": k["weapon"],
                "distance": k["distance"]
            } for k in recent_kills
        ],
        "nemesis_total_kills": nemesis.total_kills if nemesis else 0,
        "nemesis_total_deaths": nemesis.total_deaths if nemesis else 0
    }
    
    return result

async def get_prey_data(player_id, server_id=None):
    """
    Get detailed prey data for a player
    
    Args:
        player_id: SteamID of the player
        server_id: Optional server filter
        
    Returns:
        dict: Prey data including kill details
    """
    db = await Database.get_instance()
    player = await Player.get_by_player_id(db, player_id)
    
    if not player or not player.prey_id:
        return None
    
    # Build match query for kill history
    match_query = {
        "killer_id": player_id,
        "victim_id": player.prey_id,
        "is_suicide": False
    }
    
    if server_id:
        match_query["server_id"] = server_id
    
    # Get the most recent kills by the player against their prey
    kills_collection = db.kills
    recent_kills = await kills_collection.find(match_query).sort("timestamp", -1).limit(10).to_list(10)
    
    # Get the most used weapons by the player against their prey
    weapon_pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$weapon",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 3}
    ]
    
    weapons = await kills_collection.aggregate(weapon_pipeline).to_list(3)
    favorite_weapons = [{"weapon": w["_id"], "count": w["count"]} for w in weapons]
    
    # Calculate prey's kills against the player
    prey_kills_query = {
        "killer_id": player.prey_id,
        "victim_id": player_id,
        "is_suicide": False
    }
    
    if server_id:
        prey_kills_query["server_id"] = server_id
        
    prey_kills = await kills_collection.count_documents(prey_kills_query)
    
    prey = await Player.get_by_player_id(db, player.prey_id)
    
    result = {
        "player_id": player_id,
        "player_name": player.player_name,
        "prey_id": player.prey_id,
        "prey_name": player.prey_name,
        "prey_kills": player.prey_kills,
        "prey_revenge_kills": prey_kills,
        "kd_ratio": round(player.prey_kills / max(1, prey_kills), 2),
        "favorite_weapons": favorite_weapons,
        "recent_kills": [
            {
                "timestamp": k["timestamp"],
                "weapon": k["weapon"],
                "distance": k["distance"]
            } for k in recent_kills
        ],
        "prey_total_kills": prey.total_kills if prey else 0,
        "prey_total_deaths": prey.total_deaths if prey else 0
    }
    
    return result

async def get_player_relationships(player_id, server_id=None, limit=10):
    """
    Get a player's kill relationships with other players
    
    Args:
        player_id: SteamID of the player
        server_id: Optional server filter
        limit: Maximum number of relationships to return
        
    Returns:
        dict: Player relationship data
    """
    db = await Database.get_instance()
    player = await Player.get_by_player_id(db, player_id)
    
    if not player:
        return None
    
    # Build match queries
    killed_query = {
        "killer_id": player_id,
        "is_suicide": False
    }
    
    killed_by_query = {
        "victim_id": player_id,
        "is_suicide": False
    }
    
    if server_id:
        killed_query["server_id"] = server_id
        killed_by_query["server_id"] = server_id
    
    # Aggregate players killed by this player
    killed_pipeline = [
        {"$match": killed_query},
        {"$group": {
            "_id": "$victim_id",
            "player_name": {"$first": "$victim_name"},
            "kill_count": {"$sum": 1},
            "most_used_weapon": {"$max": "$weapon"}
        }},
        {"$sort": {"kill_count": -1}},
        {"$limit": limit}
    ]
    
    # Aggregate players who killed this player
    killed_by_pipeline = [
        {"$match": killed_by_query},
        {"$group": {
            "_id": "$killer_id",
            "player_name": {"$first": "$killer_name"},
            "death_count": {"$sum": 1},
            "most_used_weapon": {"$max": "$weapon"}
        }},
        {"$sort": {"death_count": -1}},
        {"$limit": limit}
    ]
    
    # Execute queries
    kills_collection = db.kills
    killed_results = await kills_collection.aggregate(killed_pipeline).to_list(limit)
    killed_by_results = await kills_collection.aggregate(killed_by_pipeline).to_list(limit)
    
    # Format results
    killed_players = [
        {
            "player_id": k["_id"],
            "player_name": k["player_name"],
            "kill_count": k["kill_count"],
            "most_used_weapon": k["most_used_weapon"]
        } for k in killed_results
    ]
    
    killed_by_players = [
        {
            "player_id": k["_id"],
            "player_name": k["player_name"],
            "death_count": k["death_count"],
            "most_used_weapon": k["most_used_weapon"]
        } for k in killed_by_results
    ]
    
    # Get nemesis and prey information
    nemesis_data = {
        "player_id": player.nemesis_id,
        "player_name": player.nemesis_name,
        "death_count": player.nemesis_deaths
    } if player.nemesis_id else None
    
    prey_data = {
        "player_id": player.prey_id,
        "player_name": player.prey_name,
        "kill_count": player.prey_kills
    } if player.prey_id else None
    
    result = {
        "player_id": player_id,
        "player_name": player.player_name,
        "total_kills": player.total_kills,
        "total_deaths": player.total_deaths,
        "nemesis": nemesis_data,
        "prey": prey_data,
        "killed_players": killed_players,
        "killed_by_players": killed_by_players
    }
    
    return result