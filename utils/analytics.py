"""
Analytics Utility

This module provides advanced analytics functions for server and player statistics, 
allowing for detailed insights into game activity and performance metrics.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from database.connection import Database
from database.models import Player, Kill, ConnectionEvent, Server

logger = logging.getLogger('deadside_bot.utils.analytics')

class AnalyticsService:
    """Service for generating advanced analytics and statistics"""
    
    @staticmethod
    async def get_server_stats(server_id: str, time_period: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive server statistics for a given time period
        
        Args:
            server_id: MongoDB ObjectId of the server
            time_period: Number of days to include in stats (default: 7)
            
        Returns:
            Dict containing server statistics
        """
        db = await Database.get_instance()
        start_date = datetime.utcnow() - timedelta(days=time_period)
        
        # Get kill events within time period
        kills_collection = await db.get_collection("kills")
        total_kills = await kills_collection.count_documents({
            "server_id": server_id,
            "timestamp": {"$gte": start_date}
        })
        
        # Get suicide count
        suicide_count = await kills_collection.count_documents({
            "server_id": server_id,
            "timestamp": {"$gte": start_date},
            "is_suicide": True
        })
        
        # Get unique player count
        player_ids = set()
        cursor = kills_collection.find({
            "server_id": server_id,
            "timestamp": {"$gte": start_date}
        })
        
        async for doc in cursor:
            player_ids.add(doc["killer_id"])
            player_ids.add(doc["victim_id"])
        
        unique_players = len(player_ids)
        
        # Get connection events
        connections_collection = await db.get_collection("connection_events")
        joins = await connections_collection.count_documents({
            "server_id": server_id,
            "timestamp": {"$gte": start_date},
            "event_type": "connect"
        })
        
        leaves = await connections_collection.count_documents({
            "server_id": server_id,
            "timestamp": {"$gte": start_date},
            "event_type": "disconnect"
        })
        
        # Get most active hours (hour of day with most kills)
        pipeline = [
            {"$match": {
                "server_id": server_id,
                "timestamp": {"$gte": start_date}
            }},
            {"$project": {
                "hour": {"$hour": "$timestamp"}
            }},
            {"$group": {
                "_id": "$hour",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        most_active_hours = []
        async for doc in cursor:
            most_active_hours.append({
                "hour": doc["_id"],
                "count": doc["count"]
            })
        
        # Get most used weapons
        pipeline = [
            {"$match": {
                "server_id": server_id,
                "timestamp": {"$gte": start_date}
            }},
            {"$group": {
                "_id": "$weapon",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        weapons = []
        async for doc in cursor:
            if doc["_id"] and doc["_id"].strip():  # Skip empty weapon names
                weapons.append({
                    "name": doc["_id"],
                    "count": doc["count"]
                })
        
        # Get average kill distance
        pipeline = [
            {"$match": {
                "server_id": server_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": None,
                "avg_distance": {"$avg": "$distance"}
            }}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        avg_distance = 0
        async for doc in cursor:
            avg_distance = round(doc["avg_distance"], 2)
        
        return {
            "time_period": time_period,
            "total_kills": total_kills,
            "unique_players": unique_players,
            "suicide_count": suicide_count,
            "player_joins": joins,
            "player_leaves": leaves,
            "most_active_hours": most_active_hours,
            "top_weapons": weapons,
            "avg_kill_distance": avg_distance
        }
    
    @staticmethod
    async def get_player_analytics(player_id: str, time_period: int = 7) -> Dict[str, Any]:
        """
        Get detailed player analytics for a given time period
        
        Args:
            player_id: SteamID of the player
            time_period: Number of days to include in stats (default: 7)
            
        Returns:
            Dict containing player analytics
        """
        db = await Database.get_instance()
        start_date = datetime.utcnow() - timedelta(days=time_period)
        
        # Get the player from database
        player = await Player.get_by_player_id(db, player_id)
        if not player:
            return {"error": "Player not found"}
        
        # Get kill events where player was killer
        kills_collection = await db.get_collection("kills")
        kills_count = await kills_collection.count_documents({
            "killer_id": player_id,
            "timestamp": {"$gte": start_date},
            "is_suicide": False
        })
        
        # Get death events where player was victim
        deaths_count = await kills_collection.count_documents({
            "victim_id": player_id,
            "timestamp": {"$gte": start_date}
        })
        
        # Calculate K/D ratio
        kd_ratio = kills_count / max(deaths_count, 1)  # Avoid division by zero
        
        # Get player's favorite weapons
        pipeline = [
            {"$match": {
                "killer_id": player_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": "$weapon",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        favorite_weapons = []
        async for doc in cursor:
            if doc["_id"] and doc["_id"].strip():  # Skip empty weapon names
                favorite_weapons.append({
                    "name": doc["_id"],
                    "count": doc["count"]
                })
        
        # Get average kill distance
        pipeline = [
            {"$match": {
                "killer_id": player_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": None,
                "avg_distance": {"$avg": "$distance"}
            }}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        avg_kill_distance = 0
        async for doc in cursor:
            avg_kill_distance = round(doc["avg_distance"], 2)
        
        # Get most frequent victims (players killed most by this player)
        pipeline = [
            {"$match": {
                "killer_id": player_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": {"id": "$victim_id", "name": "$victim_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        frequent_victims = []
        async for doc in cursor:
            frequent_victims.append({
                "id": doc["_id"]["id"],
                "name": doc["_id"]["name"],
                "count": doc["count"]
            })
        
        # Get most frequent killers (players who killed this player most)
        pipeline = [
            {"$match": {
                "victim_id": player_id,
                "timestamp": {"$gte": start_date}
            }},
            {"$group": {
                "_id": {"id": "$killer_id", "name": "$killer_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        frequent_killers = []
        async for doc in cursor:
            frequent_killers.append({
                "id": doc["_id"]["id"],
                "name": doc["_id"]["name"],
                "count": doc["count"]
            })
        
        # Get activity hours (when player gets most kills)
        pipeline = [
            {"$match": {
                "killer_id": player_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$project": {
                "hour": {"$hour": "$timestamp"}
            }},
            {"$group": {
                "_id": "$hour",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        active_hours = []
        async for doc in cursor:
            active_hours.append({
                "hour": doc["_id"],
                "count": doc["count"]
            })
        
        # Calculate improvement trend (K/D ratio over time)
        # Split the time period into segments and calculate K/D for each
        segments = min(time_period, 7)  # Max 7 segments to avoid too many calculations
        segment_duration = timedelta(days=time_period / segments)
        
        trend_data = []
        for i in range(segments):
            segment_start = start_date + segment_duration * i
            segment_end = start_date + segment_duration * (i + 1)
            
            segment_kills = await kills_collection.count_documents({
                "killer_id": player_id,
                "timestamp": {"$gte": segment_start, "$lt": segment_end},
                "is_suicide": False
            })
            
            segment_deaths = await kills_collection.count_documents({
                "victim_id": player_id,
                "timestamp": {"$gte": segment_start, "$lt": segment_end}
            })
            
            segment_kd = segment_kills / max(segment_deaths, 1)
            
            trend_data.append({
                "segment": i + 1,
                "start_date": segment_start.isoformat(),
                "end_date": segment_end.isoformat(),
                "kills": segment_kills,
                "deaths": segment_deaths,
                "kd_ratio": round(segment_kd, 2)
            })
        
        # Determine improvement status
        if len(trend_data) >= 2:
            first_kd = trend_data[0]["kd_ratio"]
            last_kd = trend_data[-1]["kd_ratio"]
            improvement = ((last_kd - first_kd) / max(first_kd, 0.01)) * 100
        else:
            improvement = 0
            
        # Get suicide count
        suicide_count = await kills_collection.count_documents({
            "killer_id": player_id,
            "victim_id": player_id,
            "timestamp": {"$gte": start_date},
            "is_suicide": True
        })
        
        return {
            "player_id": player_id,
            "player_name": player.player_name,
            "time_period": time_period,
            "total_kills": kills_count,
            "total_deaths": deaths_count,
            "kd_ratio": round(kd_ratio, 2),
            "favorite_weapons": favorite_weapons,
            "avg_kill_distance": avg_kill_distance,
            "frequent_victims": frequent_victims,
            "frequent_killers": frequent_killers,
            "active_hours": active_hours,
            "improvement_trend": trend_data,
            "improvement_percentage": round(improvement, 2),
            "suicide_count": suicide_count,
            "is_improving": improvement > 5,  # Consider improving if > 5% better
            "all_time_kills": player.total_kills,
            "all_time_deaths": player.total_deaths,
            "faction_id": player.faction_id,
            "nemesis": {"id": player.nemesis_id, "name": player.nemesis_name, "deaths": player.nemesis_deaths},
            "prey": {"id": player.prey_id, "name": player.prey_name, "kills": player.prey_kills}
        }
    
    @staticmethod
    async def get_leaderboard(server_id: str, sort_by: str = "kills", limit: int = 10, 
                             time_period: Optional[int] = 7) -> List[Dict[str, Any]]:
        """
        Get leaderboard data for a server
        
        Args:
            server_id: MongoDB ObjectId of the server
            sort_by: Metric to sort by ('kills', 'kd', 'distance', 'headshots')
            limit: Maximum number of players to include
            time_period: Number of days to include (None = all-time stats)
            
        Returns:
            List of player leaderboard entries
        """
        db = await Database.get_instance()
        leaderboard = []
        
        if time_period is None:
            # Use all-time stats from player records
            players_collection = await db.get_collection("players")
            
            # Get top players based on sort criteria
            if sort_by == "kills":
                cursor = players_collection.find().sort("total_kills", -1).limit(limit)
            elif sort_by == "kd":
                # Need to calculate KD ratio during processing
                cursor = players_collection.find().sort("total_kills", -1).limit(limit * 3)  # Get more to filter
            else:
                # Default to kills for other criteria when using all-time stats
                cursor = players_collection.find().sort("total_kills", -1).limit(limit)
            
            async for doc in cursor:
                player = Player(**{**doc, "_id": doc.get("_id")})
                
                kd_ratio = player.total_kills / max(player.total_deaths, 1)
                
                leaderboard.append({
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "kills": player.total_kills,
                    "deaths": player.total_deaths,
                    "kd_ratio": round(kd_ratio, 2),
                    "faction_id": player.faction_id
                })
                
            # If sorting by KD, we need to sort the processed results
            if sort_by == "kd":
                leaderboard.sort(key=lambda x: x["kd_ratio"], reverse=True)
                leaderboard = leaderboard[:limit]  # Trim to desired limit
                
        else:
            # Get time-specific stats from kill events
            start_date = datetime.utcnow() - timedelta(days=time_period)
            kills_collection = await db.get_collection("kills")
            
            # Get list of player IDs from kill events
            player_stats = {}
            cursor = kills_collection.find({
                "server_id": server_id,
                "timestamp": {"$gte": start_date}
            })
            
            async for doc in cursor:
                killer_id = doc["killer_id"]
                victim_id = doc["victim_id"]
                is_suicide = doc.get("is_suicide", False)
                distance = doc.get("distance", 0)
                
                # Process killer stats (skip if suicide)
                if not is_suicide:
                    if killer_id not in player_stats:
                        player_stats[killer_id] = {
                            "player_id": killer_id,
                            "player_name": doc["killer_name"],
                            "kills": 0,
                            "deaths": 0,
                            "total_distance": 0,
                            "kill_count_for_distance": 0,
                            "longest_kill": 0
                        }
                    
                    player_stats[killer_id]["kills"] += 1
                    player_stats[killer_id]["player_name"] = doc["killer_name"]  # Update name in case it changed
                    
                    # Track distance stats
                    if distance > 0:
                        player_stats[killer_id]["total_distance"] += distance
                        player_stats[killer_id]["kill_count_for_distance"] += 1
                        player_stats[killer_id]["longest_kill"] = max(
                            player_stats[killer_id]["longest_kill"], distance
                        )
                
                # Process victim stats (always count deaths)
                if victim_id not in player_stats:
                    player_stats[victim_id] = {
                        "player_id": victim_id,
                        "player_name": doc["victim_name"],
                        "kills": 0,
                        "deaths": 0,
                        "total_distance": 0,
                        "kill_count_for_distance": 0,
                        "longest_kill": 0
                    }
                
                player_stats[victim_id]["deaths"] += 1
                player_stats[victim_id]["player_name"] = doc["victim_name"]  # Update name in case it changed
            
            # Finalize player stats and prepare for sorting
            for player_id, stats in player_stats.items():
                # Calculate KD ratio
                kd_ratio = stats["kills"] / max(stats["deaths"], 1)
                stats["kd_ratio"] = round(kd_ratio, 2)
                
                # Calculate average kill distance
                if stats["kill_count_for_distance"] > 0:
                    stats["avg_distance"] = round(stats["total_distance"] / stats["kill_count_for_distance"], 2)
                else:
                    stats["avg_distance"] = 0
                
                # Get faction info
                player = await Player.get_by_player_id(db, player_id)
                if player:
                    stats["faction_id"] = player.faction_id
                else:
                    stats["faction_id"] = None
            
            # Convert to list and sort based on criteria
            player_list = list(player_stats.values())
            
            if sort_by == "kills":
                player_list.sort(key=lambda x: x["kills"], reverse=True)
            elif sort_by == "kd":
                player_list.sort(key=lambda x: x["kd_ratio"], reverse=True)
            elif sort_by == "distance":
                player_list.sort(key=lambda x: x["avg_distance"], reverse=True)
            else:
                # Default to kills
                player_list.sort(key=lambda x: x["kills"], reverse=True)
            
            # Apply limit and select fields for response
            leaderboard = player_list[:limit]
            
            # Clean up response
            for entry in leaderboard:
                entry.pop("total_distance", None)
                entry.pop("kill_count_for_distance", None)
        
        return leaderboard
    
    @staticmethod
    async def get_faction_analytics(faction_id: str, time_period: int = 7) -> Dict[str, Any]:
        """
        Get detailed analytics for a faction
        
        Args:
            faction_id: MongoDB ObjectId of the faction
            time_period: Number of days to include in stats (default: 7)
            
        Returns:
            Dict containing faction analytics
        """
        db = await Database.get_instance()
        start_date = datetime.utcnow() - timedelta(days=time_period)
        
        # Get all players in the faction
        players_collection = await db.get_collection("players")
        faction_players = []
        
        cursor = players_collection.find({"faction_id": faction_id})
        async for doc in cursor:
            faction_players.append(Player(**{**doc, "_id": doc.get("_id")}))
        
        if not faction_players:
            return {"error": "No players found in faction"}
        
        # Get faction name from first player's faction info
        faction_collection = await db.get_collection("factions")
        faction_data = await faction_collection.find_one({"_id": faction_id})
        faction_name = faction_data.get("name", "Unknown Faction") if faction_data else "Unknown Faction"
        
        # Get player IDs for queries
        player_ids = [player.player_id for player in faction_players]
        
        # Get kill events by faction members
        kills_collection = await db.get_collection("kills")
        kills_count = await kills_collection.count_documents({
            "killer_id": {"$in": player_ids},
            "timestamp": {"$gte": start_date},
            "is_suicide": False
        })
        
        # Get death events for faction members
        deaths_count = await kills_collection.count_documents({
            "victim_id": {"$in": player_ids},
            "timestamp": {"$gte": start_date}
        })
        
        # Calculate faction K/D ratio
        faction_kd_ratio = kills_count / max(deaths_count, 1)
        
        # Get top performers in the faction
        player_performance = []
        for player in faction_players:
            player_kills = await kills_collection.count_documents({
                "killer_id": player.player_id,
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            })
            
            player_deaths = await kills_collection.count_documents({
                "victim_id": player.player_id,
                "timestamp": {"$gte": start_date}
            })
            
            player_kd = player_kills / max(player_deaths, 1)
            
            player_performance.append({
                "player_id": player.player_id,
                "player_name": player.player_name,
                "kills": player_kills,
                "deaths": player_deaths,
                "kd_ratio": round(player_kd, 2)
            })
        
        # Sort by kills
        player_performance.sort(key=lambda x: x["kills"], reverse=True)
        
        # Get faction's top weapons
        pipeline = [
            {"$match": {
                "killer_id": {"$in": player_ids},
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": "$weapon",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        top_weapons = []
        async for doc in cursor:
            if doc["_id"] and doc["_id"].strip():  # Skip empty weapon names
                top_weapons.append({
                    "name": doc["_id"],
                    "count": doc["count"]
                })
        
        # Get average kill distance for the faction
        pipeline = [
            {"$match": {
                "killer_id": {"$in": player_ids},
                "timestamp": {"$gte": start_date},
                "is_suicide": False
            }},
            {"$group": {
                "_id": None,
                "avg_distance": {"$avg": "$distance"}
            }}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        avg_distance = 0
        async for doc in cursor:
            avg_distance = round(doc["avg_distance"], 2)
        
        # Get faction vs faction stats
        rival_factions = {}
        
        # For each kill by a faction member, track the victim's faction
        cursor = kills_collection.find({
            "killer_id": {"$in": player_ids},
            "timestamp": {"$gte": start_date},
            "is_suicide": False
        })
        
        async for kill in cursor:
            victim_id = kill["victim_id"]
            
            # Skip if victim is also in the faction (internal kills)
            if victim_id in player_ids:
                continue
            
            # Get victim's faction
            victim = await Player.get_by_player_id(db, victim_id)
            if victim and victim.faction_id:
                victim_faction_id = victim.faction_id
                
                # Get faction name
                victim_faction_data = await faction_collection.find_one({"_id": victim_faction_id})
                victim_faction_name = victim_faction_data.get("name", "Unknown") if victim_faction_data else "Unknown"
                
                if victim_faction_id not in rival_factions:
                    rival_factions[victim_faction_id] = {
                        "faction_id": victim_faction_id,
                        "faction_name": victim_faction_name,
                        "kills_against": 0,
                        "deaths_to": 0
                    }
                
                rival_factions[victim_faction_id]["kills_against"] += 1
        
        # For each death of a faction member, track the killer's faction
        cursor = kills_collection.find({
            "victim_id": {"$in": player_ids},
            "timestamp": {"$gte": start_date}
        })
        
        async for kill in cursor:
            killer_id = kill["killer_id"]
            
            # Skip if killer is also in the faction (internal kills)
            if killer_id in player_ids:
                continue
            
            # Get killer's faction
            killer = await Player.get_by_player_id(db, killer_id)
            if killer and killer.faction_id:
                killer_faction_id = killer.faction_id
                
                # Get faction name
                killer_faction_data = await faction_collection.find_one({"_id": killer_faction_id})
                killer_faction_name = killer_faction_data.get("name", "Unknown") if killer_faction_data else "Unknown"
                
                if killer_faction_id not in rival_factions:
                    rival_factions[killer_faction_id] = {
                        "faction_id": killer_faction_id,
                        "faction_name": killer_faction_name,
                        "kills_against": 0,
                        "deaths_to": 0
                    }
                
                rival_factions[killer_faction_id]["deaths_to"] += 1
        
        # Calculate KD ratios for rivalries and sort
        rivalry_list = list(rival_factions.values())
        for rival in rivalry_list:
            rival["kd_ratio"] = round(rival["kills_against"] / max(rival["deaths_to"], 1), 2)
        
        # Sort by KD ratio
        rivalry_list.sort(key=lambda x: x["kd_ratio"], reverse=True)
        
        return {
            "faction_id": faction_id,
            "faction_name": faction_name,
            "time_period": time_period,
            "member_count": len(faction_players),
            "total_kills": kills_count,
            "total_deaths": deaths_count,
            "kd_ratio": round(faction_kd_ratio, 2),
            "top_performers": player_performance[:5],  # Top 5 players
            "top_weapons": top_weapons,
            "avg_kill_distance": avg_distance,
            "rivalries": rivalry_list[:5]  # Top 5 rivalries
        }