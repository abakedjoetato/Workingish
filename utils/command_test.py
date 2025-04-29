"""
Command Testing Utility

This module provides tools for testing and validating commands 
and methods within the bot in both development and production environments.
"""

import logging
import asyncio
import traceback
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Tuple, Union

from database.connection import Database
from database.models import Server, Player, Kill

logger = logging.getLogger('deadside_bot.utils.command_test')

class TestResult:
    """Result of a command or method test"""
    
    def __init__(self, name: str, success: bool, duration_ms: float, error: Optional[Exception] = None, 
                 output: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize test result
        
        Args:
            name: Name of the test
            success: Whether the test passed
            duration_ms: Duration of the test in milliseconds
            error: Exception raised during test (if any)
            output: String output from the test
            details: Additional test details
        """
        self.name = name
        self.success = success
        self.duration_ms = duration_ms
        self.error = error
        self.error_traceback = traceback.format_exception(
            type(error), error, error.__traceback__
        ) if error else None
        self.output = output
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error": str(self.error) if self.error else None,
            "error_traceback": self.error_traceback,
            "output": self.output,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
    
    def __str__(self) -> str:
        """String representation of test result"""
        status = "✅ PASSED" if self.success else "❌ FAILED"
        result = f"{self.name}: {status} ({self.duration_ms:.2f}ms)"
        
        if self.error:
            result += f"\nError: {self.error}"
            
        if self.output:
            result += f"\nOutput: {self.output}"
            
        return result


class CommandTester:
    """Utility for testing commands and methods"""
    
    def __init__(self, save_results: bool = True, results_file: str = "logs/test_results.json"):
        """
        Initialize command tester
        
        Args:
            save_results: Whether to save test results to file
            results_file: Path to file for saving results
        """
        self.save_results = save_results
        self.results_file = results_file
        self.results: List[TestResult] = []
        
    async def test_method(self, name: str, method: Callable, *args, **kwargs) -> TestResult:
        """
        Test a specific method
        
        Args:
            name: Name of the test
            method: Method to test
            *args: Arguments to pass to method
            **kwargs: Keyword arguments to pass to method
            
        Returns:
            TestResult with test outcome
        """
        start_time = datetime.utcnow()
        success = False
        error = None
        output = None
        details = {}
        
        try:
            logger.info(f"Running test: {name}")
            
            # Check if method is a coroutine function
            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)
                
            output = str(result) if result is not None else "No output"
            success = True
            details["result"] = result if isinstance(result, (str, int, float, bool)) else "Complex result type"
            
        except Exception as e:
            error = e
            logger.error(f"Test {name} failed: {e}")
            logger.error(traceback.format_exc())
        
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        result = TestResult(name, success, duration_ms, error, output, details)
        self.results.append(result)
        
        if self.save_results:
            await self._save_results()
            
        return result
    
    async def test_database_connection(self) -> TestResult:
        """Test database connection"""
        return await self.test_method(
            "Database Connection", 
            self._test_db_connection
        )
    
    async def _test_db_connection(self) -> Dict[str, Any]:
        """Internal method to test database connection"""
        db = await Database.get_instance()
        
        # Test getting a collection
        players_collection = await db.get_collection("players")
        count = await players_collection.count_documents({})
        
        # Test listing collections
        collections = await db.list_collection_names()
        
        return {
            "connected": True,
            "player_count": count,
            "collections": collections
        }
    
    async def test_server_commands(self, guild_id: str) -> List[TestResult]:
        """
        Test server-related commands
        
        Args:
            guild_id: Discord guild ID to test with
            
        Returns:
            List of test results
        """
        results = []
        
        # Test getting servers for guild
        results.append(await self.test_method(
            "Get Servers for Guild",
            self._test_get_servers,
            guild_id
        ))
        
        # More server tests can be added here
        
        return results
    
    async def _test_get_servers(self, guild_id: str) -> Dict[str, Any]:
        """Internal method to test getting servers for guild"""
        db = await Database.get_instance()
        servers = await Server.get_by_guild(db, guild_id)
        
        return {
            "server_count": len(servers),
            "servers": [{"name": s.name, "ip": s.ip, "port": s.port} for s in servers]
        }
    
    async def test_player_stats(self, player_id: Optional[str] = None) -> List[TestResult]:
        """
        Test player statistics commands
        
        Args:
            player_id: Optional player ID to test with (finds one if None)
            
        Returns:
            List of test results
        """
        results = []
        
        # First, find a player if none specified
        if not player_id:
            result = await self.test_method(
                "Find Player for Testing",
                self._test_find_player
            )
            results.append(result)
            
            if result.success and result.details and "player_id" in result.details:
                player_id = result.details["player_id"]
            else:
                # Early return if we can't find a player
                return results
                
        # Test getting player by ID
        results.append(await self.test_method(
            "Get Player by ID",
            self._test_get_player,
            player_id
        ))
        
        # Test getting player stats
        results.append(await self.test_method(
            "Get Player Stats",
            self._test_get_player_stats,
            player_id
        ))
        
        # Test getting player's nemesis
        results.append(await self.test_method(
            "Get Player Nemesis",
            self._test_get_player_nemesis,
            player_id
        ))
        
        # Test getting player's prey
        results.append(await self.test_method(
            "Get Player Prey",
            self._test_get_player_prey,
            player_id
        ))
        
        return results
    
    async def _test_find_player(self) -> Dict[str, Any]:
        """Internal method to find a player for testing"""
        db = await Database.get_instance()
        players_collection = await db.get_collection("players")
        
        # Find a player with reasonable stats (some kills/deaths)
        player_doc = await players_collection.find_one({
            "total_kills": {"$gte": 1},
            "total_deaths": {"$gte": 1}
        })
        
        if not player_doc:
            # Try to find any player
            player_doc = await players_collection.find_one({})
            
        if not player_doc:
            raise ValueError("No players found in database")
            
        return {
            "player_id": player_doc["player_id"],
            "player_name": player_doc["player_name"]
        }
    
    async def _test_get_player(self, player_id: str) -> Dict[str, Any]:
        """Internal method to test getting player by ID"""
        db = await Database.get_instance()
        player = await Player.get_by_player_id(db, player_id)
        
        if not player:
            raise ValueError(f"Player not found with ID: {player_id}")
            
        return {
            "player_id": player.player_id,
            "player_name": player.player_name,
            "kills": player.total_kills,
            "deaths": player.total_deaths
        }
    
    async def _test_get_player_stats(self, player_id: str) -> Dict[str, Any]:
        """Internal method to test getting player stats"""
        db = await Database.get_instance()
        player = await Player.get_by_player_id(db, player_id)
        
        if not player:
            raise ValueError(f"Player not found with ID: {player_id}")
        
        # Get recent kills
        kills_collection = await db.get_collection("kills")
        recent_kills = await kills_collection.count_documents({
            "killer_id": player_id,
            "is_suicide": False
        })
        
        recent_deaths = await kills_collection.count_documents({
            "victim_id": player_id
        })
        
        kd_ratio = player.total_kills / max(player.total_deaths, 1)
        
        return {
            "player_name": player.player_name,
            "total_kills": player.total_kills,
            "total_deaths": player.total_deaths,
            "kd_ratio": round(kd_ratio, 2),
            "recent_kills": recent_kills,
            "recent_deaths": recent_deaths
        }
    
    async def _test_get_player_nemesis(self, player_id: str) -> Dict[str, Any]:
        """Internal method to test getting player's nemesis"""
        db = await Database.get_instance()
        player = await Player.get_by_player_id(db, player_id)
        
        if not player:
            raise ValueError(f"Player not found with ID: {player_id}")
            
        return {
            "has_nemesis": bool(player.nemesis_id),
            "nemesis_id": player.nemesis_id,
            "nemesis_name": player.nemesis_name,
            "nemesis_deaths": player.nemesis_deaths
        }
    
    async def _test_get_player_prey(self, player_id: str) -> Dict[str, Any]:
        """Internal method to test getting player's prey"""
        db = await Database.get_instance()
        player = await Player.get_by_player_id(db, player_id)
        
        if not player:
            raise ValueError(f"Player not found with ID: {player_id}")
            
        return {
            "has_prey": bool(player.prey_id),
            "prey_id": player.prey_id,
            "prey_name": player.prey_name,
            "prey_kills": player.prey_kills
        }
    
    async def test_leaderboard(self, server_id: Optional[str] = None) -> List[TestResult]:
        """
        Test leaderboard functionality
        
        Args:
            server_id: Optional server ID to test with (uses first available if None)
            
        Returns:
            List of test results
        """
        results = []
        
        # First, find a server if none specified
        if not server_id:
            result = await self.test_method(
                "Find Server for Testing",
                self._test_find_server
            )
            results.append(result)
            
            if result.success and result.details and "server_id" in result.details:
                server_id = result.details["server_id"]
            else:
                # Early return if we can't find a server
                return results
        
        # Test different leaderboard sort options
        for sort_by in ["kills", "kd"]:
            results.append(await self.test_method(
                f"Get Leaderboard (sort: {sort_by})",
                self._test_get_leaderboard,
                server_id,
                sort_by
            ))
        
        return results
    
    async def _test_find_server(self) -> Dict[str, Any]:
        """Internal method to find a server for testing"""
        db = await Database.get_instance()
        servers_collection = await db.get_collection("servers")
        
        server_doc = await servers_collection.find_one({})
        if not server_doc:
            raise ValueError("No servers found in database")
            
        return {
            "server_id": str(server_doc["_id"]),
            "server_name": server_doc["name"]
        }
    
    async def _test_get_leaderboard(self, server_id: str, sort_by: str = "kills") -> Dict[str, Any]:
        """Internal method to test getting leaderboard"""
        db = await Database.get_instance()
        kills_collection = await db.get_collection("kills")
        
        # Get player IDs with kills on this server
        pipeline = [
            {"$match": {"server_id": server_id, "is_suicide": False}},
            {"$group": {
                "_id": "$killer_id",
                "name": {"$first": "$killer_name"},
                "kills": {"$sum": 1}
            }},
            {"$sort": {"kills": -1}},
            {"$limit": 10}
        ]
        
        cursor = kills_collection.aggregate(pipeline)
        top_killers = await cursor.to_list(None)
        
        # Get death counts for these players
        leaderboard = []
        for entry in top_killers:
            player_id = entry["_id"]
            
            deaths = await kills_collection.count_documents({
                "server_id": server_id,
                "victim_id": player_id
            })
            
            kd_ratio = entry["kills"] / max(deaths, 1)
            
            leaderboard.append({
                "player_id": player_id,
                "player_name": entry["name"],
                "kills": entry["kills"],
                "deaths": deaths,
                "kd_ratio": round(kd_ratio, 2)
            })
        
        # Sort by requested metric
        if sort_by == "kd":
            leaderboard.sort(key=lambda x: x["kd_ratio"], reverse=True)
        
        return {
            "leaderboard_count": len(leaderboard),
            "leaderboard": leaderboard[:5]  # Return top 5 for brevity
        }
    
    async def test_kill_tracking(self) -> List[TestResult]:
        """
        Test kill tracking functionality
        
        Returns:
            List of test results
        """
        results = []
        
        # Test finding a recent kill
        results.append(await self.test_method(
            "Find Recent Kill",
            self._test_find_recent_kill
        ))
        
        # Test getting kill details
        kill_result = results[0]
        if kill_result.success and kill_result.details and "kill_id" in kill_result.details:
            kill_id = kill_result.details["kill_id"]
            
            results.append(await self.test_method(
                "Get Kill Details",
                self._test_get_kill_details,
                kill_id
            ))
        
        return results
    
    async def _test_find_recent_kill(self) -> Dict[str, Any]:
        """Internal method to find a recent kill"""
        db = await Database.get_instance()
        kills_collection = await db.get_collection("kills")
        
        # Find a non-suicide kill
        kill_doc = await kills_collection.find_one({
            "is_suicide": False
        }, sort=[("timestamp", -1)])  # Most recent first
        
        if not kill_doc:
            raise ValueError("No kills found in database")
            
        return {
            "kill_id": str(kill_doc["_id"]),
            "killer": kill_doc["killer_name"],
            "victim": kill_doc["victim_name"],
            "weapon": kill_doc.get("weapon", "Unknown"),
            "distance": kill_doc.get("distance", 0)
        }
    
    async def _test_get_kill_details(self, kill_id: str) -> Dict[str, Any]:
        """Internal method to test getting kill details"""
        db = await Database.get_instance()
        kills_collection = await db.get_collection("kills")
        
        from bson import ObjectId
        kill_doc = await kills_collection.find_one({"_id": ObjectId(kill_id)})
        
        if not kill_doc:
            raise ValueError(f"Kill not found with ID: {kill_id}")
            
        # Get killer details
        killer = await Player.get_by_player_id(db, kill_doc["killer_id"])
        
        # Get victim details
        victim = await Player.get_by_player_id(db, kill_doc["victim_id"])
        
        return {
            "timestamp": kill_doc["timestamp"].isoformat(),
            "killer_name": kill_doc["killer_name"],
            "killer_total_kills": killer.total_kills if killer else "Unknown",
            "victim_name": kill_doc["victim_name"],
            "victim_total_deaths": victim.total_deaths if victim else "Unknown",
            "weapon": kill_doc.get("weapon", "Unknown"),
            "distance": kill_doc.get("distance", 0)
        }
    
    async def test_parser(self) -> List[TestResult]:
        """
        Test CSV parser functionality
        
        Returns:
            List of test results
        """
        results = []
        
        # Test finding a server with CSV enabled
        results.append(await self.test_method(
            "Find CSV-Enabled Server",
            self._test_find_csv_server
        ))
        
        # More parser tests could be added here
        
        return results
    
    async def _test_find_csv_server(self) -> Dict[str, Any]:
        """Internal method to find a server with CSV parsing enabled"""
        db = await Database.get_instance()
        servers_collection = await db.get_collection("servers")
        
        server_doc = await servers_collection.find_one({
            "csv_enabled": True
        })
        
        if not server_doc:
            raise ValueError("No servers with CSV parsing enabled found")
            
        return {
            "server_id": str(server_doc["_id"]),
            "server_name": server_doc["name"],
            "log_path": server_doc["log_path"]
        }
    
    async def test_discord_commands(self) -> List[TestResult]:
        """
        Test that Discord commands are registered properly
        
        Returns:
            List of test results
        """
        return [await self.test_method(
            "Check Discord Commands",
            self._test_discord_commands
        )]
    
    async def _test_discord_commands(self) -> Dict[str, Any]:
        """Internal method to test Discord command registration"""
        # This must be run after the bot is initialized
        from main import bot
        
        command_count = len(bot.application_commands)
        command_groups = {}
        
        for cmd in bot.application_commands:
            if hasattr(cmd, 'options') and cmd.options:
                group_name = cmd.name
                command_groups[group_name] = []
                
                for subcmd in cmd.options:
                    if hasattr(subcmd, 'name'):
                        command_groups[group_name].append(subcmd.name)
        
        standalone_commands = []
        for cmd in bot.application_commands:
            if not hasattr(cmd, 'options') or not cmd.options:
                standalone_commands.append(cmd.name)
        
        return {
            "command_count": command_count,
            "command_groups": command_groups,
            "standalone_commands": standalone_commands
        }
    
    async def _save_results(self):
        """Save test results to JSON file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.results_file), exist_ok=True)
            
            # Convert results to dictionaries
            results_dict = [result.to_dict() for result in self.results]
            
            # Write to file
            async with open(self.results_file, 'w') as f:
                await f.write(json.dumps(results_dict, indent=2))
                
            logger.info(f"Saved test results to {self.results_file}")
        except Exception as e:
            logger.error(f"Error saving test results: {e}")
    
    def print_summary(self):
        """Print summary of test results"""
        if not self.results:
            print("No tests have been run")
            return
        
        passed = sum(1 for result in self.results if result.success)
        failed = len(self.results) - passed
        
        print(f"=== TEST SUMMARY ===")
        print(f"Total tests: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {passed/len(self.results)*100:.2f}%")
        print(f"==================")
        
        if failed > 0:
            print("\nFailed tests:")
            for result in self.results:
                if not result.success:
                    print(f"- {result.name}: {result.error}")


async def run_all_tests():
    """Run all available tests"""
    tester = CommandTester()
    
    print("Running database connection test...")
    await tester.test_database_connection()
    
    print("Running server command tests...")
    await tester.test_server_commands("example_guild_id")
    
    print("Running player stats tests...")
    await tester.test_player_stats()
    
    print("Running leaderboard tests...")
    await tester.test_leaderboard()
    
    print("Running kill tracking tests...")
    await tester.test_kill_tracking()
    
    print("Running parser tests...")
    await tester.test_parser()
    
    print("Running Discord command tests...")
    await tester.test_discord_commands()
    
    tester.print_summary()
    
    return tester.results


if __name__ == "__main__":
    # Run tests directly if script is executed
    asyncio.run(run_all_tests())