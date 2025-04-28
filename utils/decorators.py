"""
Decorators Module

This module provides useful decorators for command handlers and other functions.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar, cast

# Import types from our helper module
from utils.lsp_error_suppressors import DiscordContext

logger = logging.getLogger('deadside_bot.utils.decorators')

# Type variables for generic typing
F = TypeVar('F', bound=Callable[..., Any])

def premium_tier_required(tier: int = 1) -> Callable[[F], F]:
    """
    Decorator to restrict command access based on guild premium tier
    
    Args:
        tier: Minimum premium tier required (0 = free, 1 = premium, 2 = enterprise)
        
    Returns:
        Decorated function that checks premium tier before execution
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, ctx: DiscordContext, *args: Any, **kwargs: Any) -> Any:
            from database.connection import Database
            
            # Always allow in DMs for testing
            if ctx.guild is None:
                return await func(self, ctx, *args, **kwargs)
            
            # Get the guild's premium tier
            db = await Database.get_instance()
            guild_tier = await db.get_guild_premium_tier(ctx.guild.id)
            
            # Check if the guild meets the premium tier requirement
            # Convert string tiers to numeric
            numeric_guild_tier = 0  # default to free
            if isinstance(guild_tier, str):
                if guild_tier == "premium":
                    numeric_guild_tier = 1
                elif guild_tier == "enterprise":
                    numeric_guild_tier = 2
            elif isinstance(guild_tier, int):
                numeric_guild_tier = guild_tier
                
            if numeric_guild_tier < tier:
                tier_names = {0: "Survivor (Free)", 1: "Warlord (Premium)", 2: "Overseer (Enterprise)"}
                required_tier = tier_names.get(tier, f"Tier {tier}")
                current_tier = tier_names.get(numeric_guild_tier, f"Tier {numeric_guild_tier}")
                
                await ctx.respond(
                    f"⚠️ This command requires **{required_tier}** tier, but this server is on **{current_tier}** tier.\n"
                    f"Please upgrade to access this feature.", ephemeral=True
                )
                return None
            
            # Execute the function if the tier is sufficient
            return await func(self, ctx, *args, **kwargs)
        
        # Add an attribute to the function for easy checking
        setattr(wrapper, '_premium_tier_required', tier)
        
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