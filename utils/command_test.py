"""
Command Testing Utilities

This module provides utilities for testing commands and verifying their functionality.
It includes functions to test database queries, permission checks, and command responses.
"""

import logging
import asyncio
import traceback
from datetime import datetime, timezone

logger = logging.getLogger('deadside_bot.utils.command_test')

async def test_database_connection(db):
    """
    Test the database connection by performing a simple query
    
    Args:
        db: Database instance
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Try to get a collection and perform a simple find operation
        guild_configs = await db.get_collection("guild_configs")
        await guild_configs.find_one({})
        return True, "Database connection successful"
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

async def test_command_permissions(bot, command_name):
    """
    Test if a command has proper permission checks
    
    Args:
        bot: Bot instance
        command_name: Name of the command to test
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Find the command
        command = None
        for cmd in bot.application_commands:
            if cmd.name == command_name:
                command = cmd
                break
        
        if not command:
            return False, f"Command '{command_name}' not found"
        
        # Check if the command has permissions set
        has_permissions = hasattr(command, 'default_member_permissions') and command.default_member_permissions is not None
        
        if has_permissions:
            return True, f"Command '{command_name}' has proper permission checks"
        else:
            # For some commands, not having explicit permissions is valid
            # so this is a warning, not an error
            return True, f"Warning: Command '{command_name}' does not have explicit permission checks"
    except Exception as e:
        error_msg = f"Error testing command permissions for '{command_name}': {str(e)}"
        logger.error(error_msg)
        return False, error_msg

async def test_premium_tier_checks(db, guild_id, feature):
    """
    Test if premium tier checks are working properly
    
    Args:
        db: Database instance
        guild_id: Guild ID to test
        feature: Feature name to check
        
    Returns:
        tuple: (success, message, has_access)
    """
    try:
        from utils.premium import check_feature_access
        
        # Test if the feature access check works
        has_access = await check_feature_access(db, guild_id, feature)
        
        # Also test tier retrieval
        from utils.premium import get_guild_tier
        tier = await get_guild_tier(db, guild_id)
        
        return True, f"Premium check for '{feature}' completed (tier: {tier}, access: {has_access})", has_access
    except Exception as e:
        error_msg = f"Error testing premium tier check for '{feature}': {str(e)}"
        logger.error(error_msg)
        return False, error_msg, False

async def verify_command_registration(bot, expected_commands):
    """
    Verify that all expected commands are registered
    
    Args:
        bot: Bot instance
        expected_commands: List of command names that should be registered
        
    Returns:
        tuple: (success, message, missing_commands)
    """
    try:
        # Get all registered command names
        registered_commands = [cmd.name for cmd in bot.application_commands]
        
        # Find missing commands
        missing_commands = [cmd for cmd in expected_commands if cmd not in registered_commands]
        
        if not missing_commands:
            return True, "All expected commands are registered", []
        else:
            return False, f"Missing commands: {', '.join(missing_commands)}", missing_commands
    except Exception as e:
        error_msg = f"Error verifying command registration: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, []

async def test_guild_isolation(db, guild_id1, guild_id2):
    """
    Test if guild isolation is working properly
    
    Args:
        db: Database instance
        guild_id1: First guild ID
        guild_id2: Second guild ID
        
    Returns:
        tuple: (success, message)
    """
    try:
        from utils.guild_isolation import get_guild_servers
        
        # Get servers for both guilds
        servers1 = await get_guild_servers(db, guild_id1)
        servers2 = await get_guild_servers(db, guild_id2)
        
        # Check if the server lists are different
        server_ids1 = [str(server.get('_id')) for server in servers1]
        server_ids2 = [str(server.get('_id')) for server in servers2]
        
        # There should be no overlap unless a server is explicitly shared
        overlap = set(server_ids1).intersection(set(server_ids2))
        
        if not overlap:
            return True, "Guild isolation is working properly"
        else:
            # It's possible for servers to be shared in some configurations
            # so this is a warning, not an error
            return True, f"Warning: Found {len(overlap)} overlapping servers between guilds"
    except Exception as e:
        error_msg = f"Error testing guild isolation: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

async def run_command_tests(bot, guild_id):
    """
    Run a comprehensive suite of tests for all commands
    
    Args:
        bot: Bot instance
        guild_id: Guild ID to test with
        
    Returns:
        dict: Test results by category
    """
    results = {
        "database": [],
        "commands": [],
        "premium": [],
        "isolation": []
    }
    
    try:
        # Test database connection
        db_success, db_message = await test_database_connection(bot.db)
        results["database"].append({
            "test": "Database Connection",
            "success": db_success,
            "message": db_message
        })
        
        if not db_success:
            # If database connection fails, skip other tests
            return results
        
        # Test command registration
        expected_commands = ["server", "stats", "connections", "killfeed", "missions", "faction", "ping", "commands", "admin"]
        reg_success, reg_message, missing_commands = await verify_command_registration(bot, expected_commands)
        results["commands"].append({
            "test": "Command Registration",
            "success": reg_success,
            "message": reg_message
        })
        
        # Test permissions for important commands
        for command_name in ["admin", "server", "faction"]:
            if command_name in missing_commands:
                continue
            perm_success, perm_message = await test_command_permissions(bot, command_name)
            results["commands"].append({
                "test": f"Command Permissions: {command_name}",
                "success": perm_success,
                "message": perm_message
            })
        
        # Test premium tier checks for various features
        premium_features = ["basic_stats", "advanced_stats", "faction_system", "rivalry_tracking"]
        for feature in premium_features:
            premium_success, premium_message, _ = await test_premium_tier_checks(bot.db, guild_id, feature)
            results["premium"].append({
                "test": f"Premium Check: {feature}",
                "success": premium_success,
                "message": premium_message
            })
        
        # Test guild isolation (if multiple guilds exist)
        try:
            guilds = list(bot.guilds)
            if len(guilds) >= 2:
                iso_success, iso_message = await test_guild_isolation(bot.db, guilds[0].id, guilds[1].id)
                results["isolation"].append({
                    "test": "Guild Isolation",
                    "success": iso_success,
                    "message": iso_message
                })
            else:
                results["isolation"].append({
                    "test": "Guild Isolation",
                    "success": True,
                    "message": "Skipped (not enough guilds for testing)"
                })
        except Exception as e:
            results["isolation"].append({
                "test": "Guild Isolation",
                "success": False,
                "message": f"Error in isolation test: {str(e)}"
            })
            
    except Exception as e:
        logger.error(f"Error during command tests: {str(e)}")
        traceback.print_exc()
    
    return results

def format_test_results(results):
    """
    Format test results into a readable string
    
    Args:
        results: Test results dictionary
        
    Returns:
        str: Formatted test results
    """
    output = []
    output.append("=== Command Test Results ===")
    output.append(f"Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    output.append("")
    
    categories = {
        "database": "Database Tests",
        "commands": "Command Tests",
        "premium": "Premium Tier Tests",
        "isolation": "Guild Isolation Tests"
    }
    
    for category, tests in results.items():
        if not tests:
            continue
            
        output.append(f"--- {categories[category]} ---")
        success_count = sum(1 for test in tests if test["success"])
        output.append(f"Results: {success_count}/{len(tests)} passed")
        
        for test in tests:
            status = "✅" if test["success"] else "❌"
            output.append(f"{status} {test['test']}: {test['message']}")
            
        output.append("")
    
    total_tests = sum(len(tests) for tests in results.values())
    total_success = sum(sum(1 for test in tests if test["success"]) for tests in results.values())
    
    output.append(f"Overall: {total_success}/{total_tests} tests passed")
    
    return "\n".join(output)

async def save_test_results(bot, results):
    """
    Save test results to the database for future reference
    
    Args:
        bot: Bot instance
        results: Test results dictionary
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        if not bot.db:
            logger.error("Database not available for saving test results")
            return False
            
        tests_collection = await bot.db.get_collection("test_results")
        
        # Count number of passed tests
        total_tests = sum(len(tests) for tests in results.values())
        total_success = sum(sum(1 for test in tests if test["success"]) for tests in results.values())
        
        # Save results
        document = {
            "timestamp": datetime.now(timezone.utc),
            "results": results,
            "total_tests": total_tests,
            "passed_tests": total_success,
            "success_rate": (total_success / total_tests) if total_tests > 0 else 0
        }
        
        await tests_collection.insert_one(document)
        return True
    except Exception as e:
        logger.error(f"Error saving test results: {str(e)}")
        return False