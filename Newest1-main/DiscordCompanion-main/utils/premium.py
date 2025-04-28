import logging
from config import PREMIUM_TIERS

logger = logging.getLogger('deadside_bot.utils.premium')

async def get_premium_tiers():
    """
    Get the available premium tiers and their limits
    
    Returns:
        dict: Premium tier configuration
    """
    # This could be extended to fetch from a database or API
    return PREMIUM_TIERS

async def get_premium_limits(tier):
    """
    Get the limits for a specific premium tier
    
    Args:
        tier: Premium tier name
        
    Returns:
        dict: Limits for the specified tier
    """
    tiers = await get_premium_tiers()
    
    # Return the specified tier or fall back to free
    return tiers.get(tier, tiers["free"])

async def set_premium_tier(guild_config, tier):
    """
    Set the premium tier for a guild
    
    Args:
        guild_config: GuildConfig object
        tier: Premium tier name
    """
    # Validate tier
    tiers = await get_premium_tiers()
    if tier not in tiers:
        raise ValueError(f"Invalid premium tier: {tier}")
    
    # Update tier
    guild_config.premium_tier = tier
    
    # Get database instance for update
    from database.connection import Database
    db = await Database.get_instance()
    await guild_config.update(db)
    
    logger.info(f"Updated premium tier for guild {guild_config.guild_id} to {tier}")
    return guild_config

async def check_premium_feature(guild_config, feature):
    """
    Check if a guild has access to a premium feature
    
    Args:
        guild_config: GuildConfig object
        feature: Feature name to check
        
    Returns:
        bool: True if the guild has access to the feature
    """
    # Get premium limits
    limits = await get_premium_limits(guild_config.premium_tier)
    
    # Check if feature exists and is enabled
    return feature in limits and limits[feature]

async def check_and_notify_limits(ctx, guild_config, feature, current_count=None):
    """
    Check if a guild is approaching or has reached limits for a feature
    
    Args:
        ctx: Discord command context
        guild_config: GuildConfig object
        feature: Feature to check (e.g., 'max_servers')
        current_count: Current usage count
        
    Returns:
        bool: True if under the limit, False if at or over the limit
    """
    # Get premium limits
    limits = await get_premium_limits(guild_config.premium_tier)
    
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
