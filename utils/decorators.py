"""
Decorators Module

This module provides useful decorators for command handlers and other functions.
Includes decorators for premium tier enforcement, rate limiting, guild-only commands,
server requirement checks, and more.
"""

import asyncio
import functools
import logging
import inspect
from datetime import datetime
from typing import Any, Callable, Optional, TypeVar, cast, List, Dict, Union, Tuple

# Import types from our helper module
from utils.lsp_error_suppressors import DiscordContext, DiscordGuild, DiscordMember

logger = logging.getLogger('deadside_bot.utils.decorators')

# Type variables for generic typing
F = TypeVar('F', bound=Callable[..., Any])

# Mapping for tier names to numeric values for consistent comparison
TIER_MAPPING = {
    # String tier names
    "survivor": 0,
    "warlord": 1, 
    "overseer": 2,
    "free": 0,
    "premium": 1,
    "enterprise": 2,
    # Legacy numeric tiers
    0: 0,
    1: 1,
    2: 2
}

# Display names for tiers
TIER_DISPLAY_NAMES = {
    0: "Survivor (Free)",
    1: "Warlord (Premium)",
    2: "Overseer (Enterprise)"
}

# Maximum servers allowed per tier
TIER_MAX_SERVERS = {
    0: 1,  # Survivor
    1: 3,  # Warlord
    2: 10  # Overseer
}

async def get_guild_numeric_tier(db, guild_id: str) -> int:
    """
    Get the numeric tier for a guild
    
    Args:
        db: Database instance
        guild_id: Discord guild ID
        
    Returns:
        Numeric tier (0 = survivor, 1 = warlord, 2 = overseer)
    """
    try:
        if not db:
            logger.error("No database instance provided to get_guild_numeric_tier")
            return 0
            
        guild_tier = await db.get_guild_premium_tier(guild_id)
        return TIER_MAPPING.get(guild_tier, 0)
    except Exception as e:
        logger.error(f"Error getting guild tier: {e}")
        return 0

async def check_premium_tier(ctx: DiscordContext, required_tier: int) -> Tuple[bool, str]:
    """
    Check if a guild has a sufficient premium tier
    
    Args:
        ctx: Discord context
        required_tier: Minimum tier required
        
    Returns:
        Tuple of (has_required_tier, error_message)
    """
    from database.connection import Database
    
    try:
        # Always allow in DMs for testing
        if ctx.guild is None:
            return True, ""
            
        # Get the guild's premium tier
        db = await Database.get_instance()
        if not db:
            logger.error("Failed to get database instance in check_premium_tier")
            return False, "⚠️ Could not verify premium status. Please try again later."
            
        numeric_guild_tier = await get_guild_numeric_tier(db, ctx.guild.id)
        
        if numeric_guild_tier < required_tier:
            required_tier_name = TIER_DISPLAY_NAMES.get(required_tier, f"Tier {required_tier}")
            current_tier_name = TIER_DISPLAY_NAMES.get(numeric_guild_tier, f"Tier {numeric_guild_tier}")
            
            error_message = (
                f"⚠️ This command requires **{required_tier_name}** tier, but this server is on **{current_tier_name}** tier.\n"
                f"Please upgrade to access this feature."
            )
            return False, error_message
            
        return True, ""
    except Exception as e:
        logger.error(f"Error in check_premium_tier: {e}")
        return False, "⚠️ Could not verify premium status. Please try again later."

def premium_tier_required(tier: int = 1) -> Callable[[F], F]:
    """
    Decorator to restrict command access based on guild premium tier
    
    Args:
        tier: Minimum premium tier required (0 = survivor, 1 = warlord, 2 = overseer)
        
    Returns:
        Decorated function that checks premium tier before execution
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            # Check premium tier
            has_required_tier, error_message = await check_premium_tier(ctx, tier)
            
            if not has_required_tier:
                await ctx.respond(error_message, ephemeral=True)
                return None
                
            # Execute the function if the tier is sufficient
            return await func(self, ctx, *args, **kwargs)
        
        # Add an attribute to the function for easy checking
        setattr(wrapper, '_premium_tier_required', tier)
        
        return cast(F, wrapper)
    
    return decorator

def premium_feature_required(feature: str) -> Callable[[F], F]:
    """
    Decorator to restrict command access based on guild premium features
    
    Args:
        feature: Feature name (e.g., 'faction_system', 'advanced_stats')
        
    Returns:
        Decorated function that checks premium features before execution
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.connection import Database
            
            # Always allow in DMs for testing
            if ctx.guild is None:
                return await func(self, ctx, *args, **kwargs)
            
            try:
                # Check if the guild has the required feature
                db = await Database.get_instance()
                if not db:
                    logger.error(f"Failed to get database instance in premium_feature_required for {func.__name__}")
                    await ctx.respond("⚠️ Could not verify feature access. Please try again later.", ephemeral=True)
                    return None
                
                # Get guild premium tier
                guild_tier = await db.get_guild_premium_tier(ctx.guild.id)
                numeric_guild_tier = TIER_MAPPING.get(guild_tier, 0)
                
                # Map features to required tiers
                feature_tiers = {
                    "basic_stats": 0,
                    "killfeed": 0,
                    "player_linking": 0,
                    "faction_system": 1,
                    "advanced_stats": 1,
                    "rivalry_tracking": 1,
                    "batch_processing": 1,
                    "mission_alerts": 1,
                    "extended_history": 2,
                    "priority_support": 2,
                    "custom_branding": 2
                }
                
                required_tier = feature_tiers.get(feature, 1)  # Default to premium tier if feature unknown
                
                if numeric_guild_tier < required_tier:
                    required_tier_name = TIER_DISPLAY_NAMES.get(required_tier, f"Tier {required_tier}")
                    current_tier_name = TIER_DISPLAY_NAMES.get(numeric_guild_tier, f"Tier {numeric_guild_tier}")
                    
                    await ctx.respond(
                        f"⚠️ The {feature.replace('_', ' ')} feature requires **{required_tier_name}** tier, "
                        f"but this server is on **{current_tier_name}** tier.\n"
                        f"Please upgrade to access this feature.", ephemeral=True
                    )
                    return None
                
                # Execute the function if the tier is sufficient
                return await func(self, ctx, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in premium_feature_required for {func.__name__}: {e}")
                await ctx.respond("⚠️ Could not verify feature access. Please try again later.", ephemeral=True)
                return None
        
        # Add attributes to the function for easy checking
        setattr(wrapper, '_premium_feature_required', feature)
        
        return cast(F, wrapper)
    
    return decorator

def guild_only() -> Callable[[F], F]:
    """
    Decorator to restrict command access to guild channels only
    
    Returns:
        Decorated function that checks if command is used in a guild
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            if ctx.guild is None:
                await ctx.respond("⚠️ This command can only be used in a server, not in DMs.", ephemeral=True)
                return None
            
            return await func(self, ctx, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator

def with_server_check(require_default: bool = True) -> Callable[[F], F]:
    """
    Decorator to check if the guild has at least one server configured
    
    Args:
        require_default: Whether to require a default server to be set
        
    Returns:
        Decorated function that checks for server configuration
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.models import Server
            
            if ctx.guild is None:
                await ctx.respond("⚠️ This command can only be used in a server, not in DMs.", ephemeral=True)
                return None
            
            # Check if the guild has any servers configured
            servers = await Server.get_servers_for_guild(ctx.guild.id)
            if not servers:
                await ctx.respond(
                    "⚠️ No game servers are configured for this Discord server.\n"
                    "Please use `/server add` to add a game server first.", ephemeral=True
                )
                return None
            
            # Check if default server is required and set
            if require_default:
                default_server = await Server.get_default_for_guild(ctx.guild.id)
                if default_server is None:
                    await ctx.respond(
                        "⚠️ No default game server is set for this Discord server.\n"
                        "Please use `/server default` to set a default server.", ephemeral=True
                    )
                    return None
            
            return await func(self, ctx, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator

def check_server_limit() -> Callable[[F], F]:
    """
    Decorator to check if a guild has reached its server limit based on premium tier
    
    This is used for the server add command to prevent adding more servers than allowed.
    
    Returns:
        Decorated function that checks server limits
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.models import Server
            from database.connection import Database
            
            if ctx.guild is None:
                await ctx.respond("⚠️ This command can only be used in a server, not in DMs.", ephemeral=True)
                return None
            
            try:
                # Get the guild's servers and premium tier
                servers = await Server.get_servers_for_guild(ctx.guild.id)
                server_count = len(servers)
                
                # Get premium tier
                db = await Database.get_instance()
                numeric_guild_tier = await get_guild_numeric_tier(db, ctx.guild.id)
                
                # Get server limit based on tier
                server_limit = TIER_MAX_SERVERS.get(numeric_guild_tier, 1)
                
                # Check if adding another server would exceed the limit
                if server_count >= server_limit:
                    tier_name = TIER_DISPLAY_NAMES.get(numeric_guild_tier, f"Tier {numeric_guild_tier}")
                    next_tier = numeric_guild_tier + 1
                    next_tier_name = TIER_DISPLAY_NAMES.get(next_tier, f"Tier {next_tier}")
                    next_tier_limit = TIER_MAX_SERVERS.get(next_tier, server_limit + 5)
                    
                    await ctx.respond(
                        f"⚠️ You have reached the maximum of **{server_limit}** servers allowed on the **{tier_name}** tier.\n"
                        f"Upgrade to **{next_tier_name}** tier to add up to **{next_tier_limit}** servers.", 
                        ephemeral=True
                    )
                    return None
                
                # Execute the function if within limits
                return await func(self, ctx, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in check_server_limit for {func.__name__}: {e}")
                await ctx.respond("⚠️ Could not verify server limits. Please try again later.", ephemeral=True)
                return None
        
        return cast(F, wrapper)
    
    return decorator

def server_exists() -> Callable[[F], F]:
    """
    Decorator to check if a server exists in the database for the current guild
    
    Returns:
        Decorated function that checks server existence
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.models import Server
            
            if ctx.guild is None:
                await ctx.respond("⚠️ This command can only be used in a server, not in DMs.", ephemeral=True)
                return None
            
            # Check if the server ID is passed in kwargs
            server_id = kwargs.get('server_id')
            
            # If server_id is provided, check if it exists
            if server_id:
                server = await Server.get_by_id(server_id)
                if not server or str(server.guild_id) != str(ctx.guild.id):
                    await ctx.respond(
                        "⚠️ The specified server does not exist or doesn't belong to this Discord server.",
                        ephemeral=True
                    )
                    return None
            
            # If no server_id is provided, check if there's at least one server
            else:
                servers = await Server.get_servers_for_guild(ctx.guild.id)
                if not servers:
                    await ctx.respond(
                        "⚠️ No game servers are configured for this Discord server.\n"
                        "Please use `/server add` to add a game server first.",
                        ephemeral=True
                    )
                    return None
            
            return await func(self, ctx, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator

def premium_server(tier: int = 1) -> Callable[[F], F]:
    """
    Decorator to check if a server meets premium tier requirements
    
    This is different from premium_tier_required as it checks the specific
    server being referenced in the command rather than the guild overall.
    
    Args:
        tier: Minimum premium tier required (0 = survivor, 1 = warlord, 2 = overseer)
        
    Returns:
        Decorated function that checks server premium tier
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.models import Server
            from database.connection import Database
            
            if ctx.guild is None:
                await ctx.respond("⚠️ This command can only be used in a server, not in DMs.", ephemeral=True)
                return None
            
            # Check if the server ID is passed in kwargs
            server_id = kwargs.get('server_id')
            
            # Get the guild's premium tier
            db = await Database.get_instance()
            if not db:
                logger.error("Failed to get database instance in premium_server")
                await ctx.respond("⚠️ Could not verify premium status. Please try again later.", ephemeral=True)
                return None
                
            numeric_guild_tier = await get_guild_numeric_tier(db, ctx.guild.id)
            
            # If premium tier is insufficient, error
            if numeric_guild_tier < tier:
                required_tier_name = TIER_DISPLAY_NAMES.get(tier, f"Tier {tier}")
                current_tier_name = TIER_DISPLAY_NAMES.get(numeric_guild_tier, f"Tier {numeric_guild_tier}")
                
                await ctx.respond(
                    f"⚠️ This command requires **{required_tier_name}** tier, but this server is on **{current_tier_name}** tier.\n"
                    f"Please upgrade to access this feature.",
                    ephemeral=True
                )
                return None
            
            # If server_id is provided, check if it exists
            if server_id:
                server = await Server.get_by_id(server_id)
                if not server or str(server.guild_id) != str(ctx.guild.id):
                    await ctx.respond(
                        "⚠️ The specified server does not exist or doesn't belong to this Discord server.",
                        ephemeral=True
                    )
                    return None
            
            return await func(self, ctx, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator

def rate_limit(limit: int = 1, per: float = 5.0) -> Callable[[F], F]:
    """
    Decorator to apply rate limiting to a command
    
    Args:
        limit: Number of calls allowed per time period
        per: Time period in seconds
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(func: F) -> F:
        # Use a dict to track rate limits per user
        rate_limits = {}
        
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            # Get the user ID as the rate limit key
            user_id = str(ctx.author.id)
            
            # Check if user has any rate limit data
            if user_id in rate_limits:
                calls = rate_limits[user_id]["calls"]
                reset_time = rate_limits[user_id]["reset_at"]
                
                # If reset time has passed, reset the counter
                now = asyncio.get_event_loop().time()
                if now > reset_time:
                    calls = 0
                    reset_time = now + per
                
                # If user has exceeded the limit, notify them
                if calls >= limit:
                    remaining = reset_time - now
                    await ctx.respond(
                        f"⚠️ Rate limit exceeded. Please try again in {remaining:.1f} seconds.", 
                        ephemeral=True
                    )
                    return None
                
                # Increment the call counter
                rate_limits[user_id] = {"calls": calls + 1, "reset_at": reset_time}
            else:
                # First call for this user
                now = asyncio.get_event_loop().time()
                rate_limits[user_id] = {"calls": 1, "reset_at": now + per}
            
            # Execute the function
            return await func(self, ctx, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator