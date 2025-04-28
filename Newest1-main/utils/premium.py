import logging
import discord
from config import PREMIUM_TIERS

logger = logging.getLogger('deadside_bot.utils.premium')

async def get_premium_tiers():
    """
    Get the available premium tiers and their limits
    
    Returns:
        dict: Premium tier configuration
    """
    # This could be extended to fetch from a database or API
    if not PREMIUM_TIERS:
        logger.error("PREMIUM_TIERS is not defined in config")
        # Provide fallback defaults to prevent NoneType errors
        return {
            "free": {
                "max_servers": 1,
                "historical_parsing": False,
                "max_history_days": 0,
                "custom_embeds": False,
                "advanced_stats": False,
            }
        }
    return PREMIUM_TIERS

async def get_premium_limits(tier):
    """
    Get the limits for a specific premium tier
    
    Args:
        tier: Premium tier name
        
    Returns:
        dict: Limits for the specified tier
    """
    try:
        tiers = await get_premium_tiers()
        
        # Ensure tier is a string and not None
        tier_key = str(tier) if tier else "free"
        
        # Return the specified tier or fall back to free
        return tiers.get(tier_key, tiers.get("free", {}))
    except Exception as e:
        logger.error(f"Error getting premium limits: {e}")
        # Return fallback defaults to prevent NoneType errors
        return {
            "max_servers": 1,
            "historical_parsing": False,
            "max_history_days": 0,
            "custom_embeds": False,
            "advanced_stats": False,
        }

async def get_guild_premium_tier(guild_id):
    """
    Get the premium tier for a guild
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        str: Premium tier name
    """
    try:
        # Get database instance
        from database.connection import Database
        db = await Database.get_instance()
        
        if db is None:
            import logging
            logging.getLogger('deadside_bot.utils.premium').error("Database instance is None in get_guild_premium_tier")
            return "free"
            
        # Home guild always has enterprise tier
        try:
            is_home = await db.is_home_guild(guild_id)
            if is_home:
                return "enterprise"
        except Exception as e:
            import logging
            logging.getLogger('deadside_bot.utils.premium').error(f"Error checking home guild status: {e}")
            # Continue to get tier directly
        
        # Get guild configuration
        try:
            return await db.get_guild_premium_tier(guild_id)
        except Exception as e:
            import logging
            logging.getLogger('deadside_bot.utils.premium').error(f"Error getting premium tier from db: {e}")
            return "free"
    except Exception as e:
        import logging
        logging.getLogger('deadside_bot.utils.premium').error(f"Unexpected error in get_guild_premium_tier: {e}")
        return "free"

async def set_premium_tier(guild_id, tier, ctx=None):
    """
    Set the premium tier for a guild
    
    Args:
        guild_id: Discord guild ID
        tier: Premium tier name
        ctx: Optional Discord context for permission check
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Get database instance
    from database.connection import Database
    db = await Database.get_instance()
    
    # Don't allow changing home guild tier
    if await db.is_home_guild(guild_id):
        if ctx:
            await ctx.send("⚠️ Home guild tier cannot be changed.")
        return False
    
    # Validate tier
    tiers = await get_premium_tiers()
    if tier not in tiers:
        if ctx:
            await ctx.send(f"⚠️ Invalid premium tier: {tier}")
        return False
    
    try:
        # Update tier in database
        await db.set_guild_premium_tier(guild_id, tier)
        
        if ctx:
            await ctx.send(f"✅ Updated premium tier for guild {guild_id} to {tier}")
        
        logger.info(f"Updated premium tier for guild {guild_id} to {tier}")
        return True
    except Exception as e:
        logger.error(f"Failed to update premium tier: {e}")
        if ctx:
            await ctx.send("⚠️ Failed to update premium tier.")
        return False

async def check_premium_feature(guild_id, feature):
    """
    Check if a guild has access to a premium feature
    
    Args:
        guild_id: Discord guild ID
        feature: Feature name to check
        
    Returns:
        bool: True if the guild has access to the feature
    """
    # Get premium tier for guild
    tier = await get_guild_premium_tier(guild_id)
    
    # Get premium limits
    limits = await get_premium_limits(tier)
    
    # Check if feature exists and is enabled
    return feature in limits and limits[feature]

async def check_and_notify_limits(ctx, guild_id, feature, current_count=None):
    """
    Check if a guild is approaching or has reached limits for a feature
    
    Args:
        ctx: Discord command context
        guild_id: Discord guild ID
        feature: Feature to check (e.g., 'max_servers')
        current_count: Current usage count
        
    Returns:
        bool: True if under the limit, False if at or over the limit
    """
    # Get premium tier for guild
    tier = await get_guild_premium_tier(guild_id)
    
    # Get premium limits
    limits = await get_premium_limits(tier)
    
    # Check if feature has a limit
    if feature not in limits:
        return True
    
    max_value = limits[feature]
    
    # Skip if no limit or current count not provided
    if max_value is None or current_count is None:
        return True
    
    # Check if over limit
    if current_count >= max_value:
        await ctx.send(f"⚠️ You've reached your {feature} limit ({max_value}). "
                      f"Upgrade your premium tier for higher limits.")
        return False
    
    # Check if approaching limit (80% or higher)
    if current_count >= (max_value * 0.8):
        await ctx.send(f"⚠️ You're approaching your {feature} limit ({current_count}/{max_value}). "
                      f"Consider upgrading your premium tier for higher limits.")
    
    return True

async def is_home_guild(guild_id):
    """
    Check if a guild is the home guild
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        bool: True if the guild is the home guild
    """
    try:
        if guild_id is None:
            return False
            
        from database.connection import Database
        db = await Database.get_instance()
        
        if db is None:
            import logging
            logging.getLogger('deadside_bot.utils.premium').error("Database instance is None in is_home_guild")
            return False
            
        return await db.is_home_guild(guild_id)
    except Exception as e:
        import logging
        logging.getLogger('deadside_bot.utils.premium').error(f"Error in is_home_guild: {e}")
        return False

async def set_home_guild(guild_id, ctx=None):
    """
    Set the home guild
    
    Args:
        guild_id: Discord guild ID to set as home
        ctx: Optional Discord context for response
        
    Returns:
        bool: True if successful
    """
    try:
        from database.connection import Database
        db = await Database.get_instance()
        
        if db is None:
            logger.error("Database instance is None in set_home_guild")
            if ctx:
                await ctx.send("⚠️ Failed to connect to database.")
            return False
        
        try:
            await db.set_home_guild_id(guild_id)
            
            if ctx:
                await ctx.send(f"✅ Set guild {guild_id} as the home guild with enterprise premium tier.")
            
            logger.info(f"Set guild {guild_id} as the home guild")
            return True
        except Exception as e:
            logger.error(f"Failed to set home guild: {e}")
            if ctx:
                await ctx.send("⚠️ Failed to set home guild.")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in set_home_guild: {e}")
        if ctx:
            await ctx.send("⚠️ Failed to set home guild due to an unexpected error.")
        return False

def is_guild_admin(ctx):
    """
    Check if a user is an admin in the guild
    
    Args:
        ctx: Discord command context
        
    Returns:
        bool: True if the user is an admin
    """
    if not ctx.guild:
        return False
    
    # Check if user has administrator permission
    if ctx.author.guild_permissions.administrator:
        return True
    
    # Check if user has manage guild permission
    if ctx.author.guild_permissions.manage_guild:
        return True
    
    return False

async def is_home_guild_admin(ctx):
    """
    Check if a user is an admin in the home guild
    
    Args:
        ctx: Discord command context
        
    Returns:
        bool: True if the user is an admin in the home guild
    """
    if not ctx.guild:
        return False
    
    # Check if this is the home guild
    if not await is_home_guild(ctx.guild.id):
        return False
    
    # Check if user is an admin
    return is_guild_admin(ctx)

async def is_bot_owner(ctx):
    """
    Check if a user is the bot owner
    
    Args:
        ctx: Discord command context
        
    Returns:
        bool: True if the user is the bot owner
    """
    # Use built-in check
    return await ctx.bot.is_owner(ctx.author)
