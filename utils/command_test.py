"""
Command Testing Utilities

This module provides utilities for testing Discord commands, including premium tier enforcement,
permission handling, and general functionality testing.
"""

import asyncio
import datetime
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, Callable, Union, cast

# Import the necessary types from our suppressor module
from utils.lsp_error_suppressors import DiscordContext, DiscordCommand, DiscordMember, DiscordGuild, DiscordRole

logger = logging.getLogger('deadside_bot.utils.command_test')

class MockContext:
    """Mock context for testing commands"""
    def __init__(self, guild_id: str, user_id: str, channel_id: Optional[str] = None):
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel_id = channel_id or "test_channel"
        self.responses = []
        self.deferred = False
        self.acknowledged = False
        
        # Create mock guild, author, and channel
        self.guild = MockGuild(guild_id)
        self.author = MockMember(user_id, self.guild)
        self.channel = MockChannel(self.channel_id, self.guild)
        
    async def respond(self, content: str, **kwargs: Any) -> None:
        """Record a response for testing"""
        self.responses.append({
            "content": content,
            "ephemeral": kwargs.get("ephemeral", False),
            "embeds": kwargs.get("embeds", []),
            "view": kwargs.get("view", None),
            "file": kwargs.get("file", None),
            "timestamp": datetime.datetime.now()
        })
        
    async def send(self, content: str, **kwargs: Any) -> None:
        """Alias for respond to support both methods"""
        await self.respond(content, **kwargs)
        
    async def defer(self, **kwargs: Any) -> None:
        """Record a defer for testing"""
        self.deferred = True
        self.responses.append({
            "action": "defer",
            "ephemeral": kwargs.get("ephemeral", False),
            "timestamp": datetime.datetime.now()
        })
        
    async def followup(self, content: str, **kwargs: Any) -> None:
        """Record a followup for testing"""
        self.responses.append({
            "action": "followup",
            "content": content,
            "ephemeral": kwargs.get("ephemeral", False),
            "embeds": kwargs.get("embeds", []),
            "view": kwargs.get("view", None),
            "file": kwargs.get("file", None),
            "timestamp": datetime.datetime.now()
        })
        
    def get_guild(self) -> Optional['MockGuild']:
        """Get the guild for this context"""
        return self.guild
        
    def get_response_text(self) -> str:
        """Get all response text for testing"""
        return "\n".join([str(r.get('content', '')) for r in self.responses if 'content' in r])
        
    def clear_responses(self) -> None:
        """Clear all recorded responses"""
        self.responses = []

class MockGuild:
    """Mock guild for testing commands"""
    def __init__(self, guild_id: str):
        self.id = guild_id
        self.name = f"Test Guild {guild_id}"
        self.roles = {}
        self.members = {}
        self.channels = {}
        
    def add_role(self, role_id: str, name: str, permissions: int = 0) -> 'MockRole':
        """Add a role to the guild"""
        role = MockRole(role_id, name, permissions)
        self.roles[role_id] = role
        return role
        
    def add_member(self, user_id: str, roles: List[str] = None) -> 'MockMember':
        """Add a member to the guild"""
        member = MockMember(user_id, self, roles or [])
        self.members[user_id] = member
        return member
        
    def add_channel(self, channel_id: str, name: str) -> 'MockChannel':
        """Add a channel to the guild"""
        channel = MockChannel(channel_id, self, name)
        self.channels[channel_id] = channel
        return channel
        
    def get_member(self, user_id: str) -> Optional['MockMember']:
        """Get a member by ID"""
        return self.members.get(user_id)
        
    def get_role(self, role_id: str) -> Optional['MockRole']:
        """Get a role by ID"""
        return self.roles.get(role_id)
        
    def get_channel(self, channel_id: str) -> Optional['MockChannel']:
        """Get a channel by ID"""
        return self.channels.get(channel_id)

class MockMember:
    """Mock member for testing commands"""
    def __init__(self, user_id: str, guild: MockGuild, roles: List[str] = None):
        self.id = user_id
        self.name = f"Test User {user_id}"
        self.display_name = self.name
        self.guild = guild
        self.role_ids = roles or []
        self._roles = []
        
        # Add member to guild if not already there
        if guild and user_id not in guild.members:
            guild.members[user_id] = self
            
    @property
    def roles(self) -> List['MockRole']:
        """Get all roles for this member"""
        result = []
        for role_id in self.role_ids:
            role = self.guild.get_role(role_id)
            if role:
                result.append(role)
        return result
        
    def add_role(self, role_id: str) -> None:
        """Add a role to this member"""
        if role_id not in self.role_ids:
            self.role_ids.append(role_id)
            
    def remove_role(self, role_id: str) -> None:
        """Remove a role from this member"""
        if role_id in self.role_ids:
            self.role_ids.remove(role_id)
            
    async def send(self, content: str, **kwargs: Any) -> None:
        """Record a direct message for testing"""
        logger.info(f"DM to {self.name}: {content}")
        
    def has_role(self, role_id: str) -> bool:
        """Check if member has a role"""
        return role_id in self.role_ids

class MockRole:
    """Mock role for testing commands"""
    def __init__(self, role_id: str, name: str, permissions: int = 0):
        self.id = role_id
        self.name = name
        self.permissions = permissions
        
    def __str__(self) -> str:
        return self.name

class MockChannel:
    """Mock channel for testing commands"""
    def __init__(self, channel_id: str, guild: MockGuild, name: str = None):
        self.id = channel_id
        self.name = name or f"test-channel-{channel_id}"
        self.guild = guild
        self.messages = []
        
        # Add channel to guild if not already there
        if guild and channel_id not in guild.channels:
            guild.channels[channel_id] = self
            
    async def send(self, content: str, **kwargs: Any) -> None:
        """Record a message for testing"""
        self.messages.append({
            "content": content,
            "embeds": kwargs.get("embeds", []),
            "view": kwargs.get("view", None),
            "file": kwargs.get("file", None),
            "timestamp": datetime.datetime.now()
        })
        
    def get_message_text(self) -> str:
        """Get all message text for testing"""
        return "\n".join([str(m.get('content', '')) for m in self.messages if 'content' in m])
        
    def clear_messages(self) -> None:
        """Clear all recorded messages"""
        self.messages = []

async def test_command(command_func: Callable, guild_id: str, user_id: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test a Discord command function
    
    Args:
        command_func: The command function to test
        guild_id: The guild ID to use for testing
        user_id: The user ID to use for testing
        args: Additional positional arguments for the command
        kwargs: Additional keyword arguments for the command
        
    Returns:
        Tuple of (success, message, additional_data)
    """
    try:
        # Create a mock context
        ctx = MockContext(guild_id, user_id)
        
        # Call the command function with the mock context
        if args and kwargs:
            await command_func(ctx, *args, **kwargs)
        elif args:
            await command_func(ctx, *args)
        elif kwargs:
            await command_func(ctx, **kwargs)
        else:
            await command_func(ctx)
            
        # Check if there were any responses
        if not ctx.responses:
            return False, "Command did not generate any responses", {"context": ctx}
            
        return True, "Command executed successfully", {
            "context": ctx,
            "responses": ctx.responses,
            "response_text": ctx.get_response_text()
        }
    except Exception as e:
        error_msg = f"Error testing command: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg, {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

async def test_premium_tier_enforcement(command_func: Callable, guild_id: str, user_id: str, required_tier: int) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test premium tier enforcement for a command
    
    Args:
        command_func: The command function to test
        guild_id: The guild ID to use for testing
        user_id: The user ID to use for testing
        required_tier: The tier required for the command
        
    Returns:
        Tuple of (success, message, additional_data)
    """
    from database.connection import Database
    
    try:
        # Create a mock context
        ctx = MockContext(guild_id, user_id)
        
        # Set up the database for testing
        db = await Database.get_instance()
        if not db:
            return False, "Failed to get database instance", {}
            
        # Test with tier below requirement
        actual_tier = required_tier
        if actual_tier > 0:
            await db.update_guild_premium_tier(guild_id, actual_tier - 1)
        else:
            # If the required tier is 0, we'll test with tier 0 (should pass)
            await db.update_guild_premium_tier(guild_id, actual_tier)
            
        # Store test results
        test_results = []
        
        # If the required tier is greater than 0, test with lower tier first
        if required_tier > 0:
            # Test command execution
            ctx_below = MockContext(guild_id, user_id)
            await command_func(ctx_below)
            
            # Should have a denied response
            has_denial = any("requires" in str(r.get('content', '')) for r in ctx_below.responses)
            test_results.append({
                "tier": actual_tier - 1,
                "responses": ctx_below.responses,
                "denied": has_denial,
                "expected_denial": True
            })
            
            # Then with tier equal to requirement
            await db.update_guild_premium_tier(guild_id, actual_tier)
            
            # Test command execution
            ctx_equal = MockContext(guild_id, user_id)
            await command_func(ctx_equal)
            
            # Should not have a denied response
            has_denial = any("requires" in str(r.get('content', '')) for r in ctx_equal.responses)
            test_results.append({
                "tier": actual_tier,
                "responses": ctx_equal.responses,
                "denied": has_denial,
                "expected_denial": False
            })
            
            # Check if enforcement is working correctly
            enforcement_success = (
                test_results[0]["denied"] == test_results[0]["expected_denial"] and
                test_results[1]["denied"] == test_results[1]["expected_denial"]
            )
            
            if enforcement_success:
                return True, f"Premium tier enforcement is working correctly for tier {required_tier}", {
                    "required_tier": required_tier,
                    "test_results": test_results
                }
            else:
                return False, "Premium tier enforcement is not working correctly", {
                    "required_tier": required_tier,
                    "test_results": test_results
                }
        else:
            # For tier 0 (free), test directly
            ctx_free = MockContext(guild_id, user_id)
            await command_func(ctx_free)
            
            # Should not have a denied response
            has_denial = any("requires" in str(r.get('content', '')) for r in ctx_free.responses)
            test_results.append({
                "tier": 0,
                "responses": ctx_free.responses,
                "denied": has_denial,
                "expected_denial": False
            })
            
            # Check if free tier is accessible
            if not has_denial:
                return True, "Free tier command is accessible as expected", {
                    "required_tier": required_tier,
                    "test_results": test_results
                }
            else:
                return False, "Free tier command is being incorrectly denied", {
                    "required_tier": required_tier,
                    "test_results": test_results
                }
    except Exception as e:
        error_msg = f"Error testing premium tier enforcement: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg, {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

async def test_command_permission(command_func: Callable, guild_id: str, user_id: str, permission: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test permission enforcement for a command
    
    Args:
        command_func: The command function to test
        guild_id: The guild ID to use for testing
        user_id: The user ID to use for testing
        permission: The permission to test (e.g., 'manage_guild')
        
    Returns:
        Tuple of (success, message, additional_data)
    """
    try:
        # Create a mock guild and context
        guild = MockGuild(guild_id)
        
        # Create admin and regular roles
        admin_role = guild.add_role("admin_role", "Admin", 8)  # Administrator permission
        regular_role = guild.add_role("regular_role", "Regular", 0)
        
        # Create admin and regular members
        admin_member = guild.add_member("admin_user", ["admin_role"])
        regular_member = guild.add_member("regular_user", ["regular_role"])
        
        # Test results
        test_results = []
        
        # Test with regular user (should be denied)
        ctx_regular = MockContext(guild_id, "regular_user")
        ctx_regular.guild = guild
        ctx_regular.author = regular_member
        
        await command_func(ctx_regular)
        
        # Should have a denied response
        has_denial_regular = any(("permission" in str(r.get('content', '')) or "require" in str(r.get('content', ''))) for r in ctx_regular.responses)
        test_results.append({
            "user": "regular_user",
            "responses": ctx_regular.responses,
            "denied": has_denial_regular,
            "expected_denial": True
        })
        
        # Test with admin user (should be allowed)
        ctx_admin = MockContext(guild_id, "admin_user")
        ctx_admin.guild = guild
        ctx_admin.author = admin_member
        
        await command_func(ctx_admin)
        
        # Should not have a denied response
        has_denial_admin = any(("permission" in str(r.get('content', '')) or "require" in str(r.get('content', ''))) for r in ctx_admin.responses)
        test_results.append({
            "user": "admin_user",
            "responses": ctx_admin.responses,
            "denied": has_denial_admin,
            "expected_denial": False
        })
        
        # Check if permission enforcement is working correctly
        enforcement_success = (
            test_results[0]["denied"] == test_results[0]["expected_denial"] and
            test_results[1]["denied"] == test_results[1]["expected_denial"]
        )
        
        if enforcement_success:
            return True, f"Permission enforcement is working correctly for {permission}", {
                "permission": permission,
                "test_results": test_results
            }
        else:
            return False, "Permission enforcement is not working correctly", {
                "permission": permission,
                "test_results": test_results
            }
    except Exception as e:
        error_msg = f"Error testing permission enforcement: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg, {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

async def test_guild_only_enforcement(command_func: Callable) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test guild-only enforcement for a command
    
    Args:
        command_func: The command function to test
        
    Returns:
        Tuple of (success, message, additional_data)
    """
    try:
        # Create a context with no guild (DM)
        ctx_dm = MockContext("", "test_user")
        ctx_dm.guild = None
        
        await command_func(ctx_dm)
        
        # Should have a denied response
        has_denial_dm = any("server" in str(r.get('content', '')) for r in ctx_dm.responses)
        
        # Create a context with a guild
        ctx_guild = MockContext("test_guild", "test_user")
        
        await command_func(ctx_guild)
        
        # Should not have a denied response
        has_denial_guild = any("server" in str(r.get('content', '')) for r in ctx_guild.responses)
        
        # Check if guild-only enforcement is working correctly
        enforcement_success = has_denial_dm and not has_denial_guild
        
        if enforcement_success:
            return True, "Guild-only enforcement is working correctly", {
                "dm_responses": ctx_dm.responses,
                "guild_responses": ctx_guild.responses
            }
        else:
            return False, "Guild-only enforcement is not working correctly", {
                "dm_responses": ctx_dm.responses,
                "guild_responses": ctx_guild.responses
            }
    except Exception as e:
        error_msg = f"Error testing guild-only enforcement: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, error_msg, {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

async def test_all_commands(bot: Any, guild_id: str, user_id: str) -> Dict[str, Any]:
    """
    Test all commands in a bot
    
    Args:
        bot: Discord bot instance
        guild_id: The guild ID to use for testing
        user_id: The user ID to use for testing
        
    Returns:
        Dict containing test results
    """
    results = {}
    
    for command in bot.application_commands:
        command_name = command.name
        
        try:
            # Test the command
            success, message, data = await test_command(command, guild_id, user_id)
            
            # Store the result
            results[command_name] = {
                "success": success,
                "message": message,
                "data": data
            }
        except Exception as e:
            results[command_name] = {
                "success": False,
                "message": f"Error testing command: {str(e)}",
                "data": {
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            }
    
    return results