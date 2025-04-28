"""
Premium Tier System

This module handles premium tier checks and feature access control.
"""

import logging
from datetime import datetime

logger = logging.getLogger('deadside_bot.utils.premium')

# Define premium tiers
PREMIUM_TIERS = {
    "survivor": {
        "name": "Survivor",
        "emoji": "🔪",
        "max_servers": 1,
        "features": [
            "basic_stats",
            "killfeed",
            "player_linking"
        ]
    },
    "warlord": {
        "name": "Warlord",
        "emoji": "🗡️",
        "max_servers": 3,
        "features": [
            "basic_stats",
            "killfeed",
            "player_linking",
            "advanced_stats",
            "batch_processing",
            "faction_system",
            "advanced_killfeed",
            "mission_alerts",
            "rivalry_tracking",
            "event_tracking"
        ]
    },
    "overseer": {
        "name": "Overseer",
        "emoji": "👑",
        "max_servers": 10,
        "features": [
            "basic_stats",
            "killfeed",
            "player_linking",
            "advanced_stats",
            "batch_processing",
            "faction_system",
            "advanced_killfeed",
            "mission_alerts",
            "rivalry_tracking",
            "event_tracking",
            "priority_support",
            "custom_branding",
            "extended_history"
        ]
    }
}

async def get_guild_tier(db, guild_id):
    """
    Get the premium tier for a guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        str: Tier name (survivor, warlord, overseer)
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in get_guild_tier")
        return "survivor"  # Default tier
        
    try:
        guild_configs = await db.get_collection("guild_configs")
        config = await guild_configs.find_one({"guild_id": guild_id})
        
        if not config or "premium_tier" not in config:
            return "survivor"  # Default tier
            
        return config["premium_tier"]
    except Exception as e:
        logger.error(f"Error in get_guild_tier: {e}")
        return "survivor"  # Default tier on error

async def get_max_servers(db, guild_id):
    """
    Get the maximum number of servers a guild can have
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        int: Maximum number of servers
    """
    tier = await get_guild_tier(db, guild_id)
    return PREMIUM_TIERS.get(tier, PREMIUM_TIERS["survivor"])["max_servers"]

async def check_feature_access(db, guild_id, feature):
    """
    Check if a guild has access to a specific feature
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        feature: Feature to check
        
    Returns:
        bool: True if the guild has access, False otherwise
    """
    tier = await get_guild_tier(db, guild_id)
    tier_features = PREMIUM_TIERS.get(tier, PREMIUM_TIERS["survivor"])["features"]
    return feature in tier_features

async def check_premium_feature(db, ctx, feature, silent=False):
    """
    Check if a guild has access to a premium feature and respond accordingly
    
    Args:
        db: Database connection
        ctx: Command context
        feature: Feature to check
        silent: Whether to silently return or respond with a message
        
    Returns:
        bool: True if the guild has access, False otherwise
    """
    if not db or not ctx or not feature:
        return False
        
    try:
        # Get the guild ID from the context
        guild_id = ctx.guild.id
        
        # Check if the guild has access to the feature
        has_access = await check_feature_access(db, guild_id, feature)
        
        if not has_access and not silent:
            # Get tier info for messaging
            tier_info = await get_tier_display_info(db, guild_id)
            
            # Find which tier has this feature
            min_tier = None
            for tier_id, tier_data in PREMIUM_TIERS.items():
                if feature in tier_data["features"]:
                    if min_tier is None or PREMIUM_TIERS[tier_id]["max_servers"] < PREMIUM_TIERS[min_tier]["max_servers"]:
                        min_tier = tier_id
            
            if min_tier:
                required_tier = PREMIUM_TIERS[min_tier]["name"]
                await ctx.respond(
                    f"⚠️ This feature requires the **{required_tier}** tier. "
                    f"Your server is currently on the **{tier_info['name']}** tier. "
                    f"Please contact an administrator to upgrade.",
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    f"⚠️ You don't have access to this feature. "
                    f"Your server is currently on the **{tier_info['name']}** tier.",
                    ephemeral=True
                )
        
        return has_access
    except Exception as e:
        logger.error(f"Error in check_premium_feature: {e}")
        if not silent:
            await ctx.respond("❌ An error occurred while checking feature access.", ephemeral=True)
        return False

async def get_tier_display_info(db, guild_id):
    """
    Get display information for a guild's tier
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        dict: Display information including name, emoji, etc.
    """
    tier = await get_guild_tier(db, guild_id)
    tier_info = PREMIUM_TIERS.get(tier, PREMIUM_TIERS["survivor"])
    
    return {
        "name": tier_info["name"],
        "emoji": tier_info["emoji"],
        "max_servers": tier_info["max_servers"],
        "tier_id": tier
    }

async def count_guild_servers(db, guild_id):
    """
    Count the number of servers a guild has
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        int: Number of servers
    """
    if not db or not guild_id:
        logger.error("Missing database or guild_id in count_guild_servers")
        return 0
        
    try:
        servers_collection = await db.get_collection("servers")
        count = await servers_collection.count_documents({"guild_id": guild_id})
        return count
    except Exception as e:
        logger.error(f"Error in count_guild_servers: {e}")
        return 0

async def update_guild_tier(db, guild_id, tier):
    """
    Update a guild's premium tier
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        tier: Tier to set
        
    Returns:
        bool: True if successful, False otherwise
    """
    if tier not in PREMIUM_TIERS:
        logger.error(f"Invalid tier '{tier}' in update_guild_tier")
        return False
        
    if not db or not guild_id:
        logger.error("Missing database or guild_id in update_guild_tier")
        return False
        
    try:
        guild_configs = await db.get_collection("guild_configs")
        result = await guild_configs.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "premium_tier": tier,
                "tier_updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error in update_guild_tier: {e}")
        return False

async def get_premium_features_list(tier_id=None):
    """
    Get a list of features for a specific tier or all tiers
    
    Args:
        tier_id: Optional tier ID to get features for
        
    Returns:
        dict: Features by tier or for specific tier
    """
    if tier_id and tier_id in PREMIUM_TIERS:
        return PREMIUM_TIERS[tier_id]["features"]
        
    return {
        tier: info["features"] 
        for tier, info in PREMIUM_TIERS.items()
    }

async def get_premium_limits(db, guild_id):
    """
    Get the premium limits for a guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        dict: Premium limits
    """
    tier = await get_guild_tier(db, guild_id)
    tier_info = PREMIUM_TIERS.get(tier, PREMIUM_TIERS["survivor"])
    
    # Calculate history limits based on tier
    history_days = 1  # Default for survivor tier
    if tier == "warlord":
        history_days = 7
    elif tier == "overseer":
        history_days = 30
        
    # Build limits object
    limits = {
        "max_servers": tier_info["max_servers"],
        "history_days": history_days,
        "max_factions": 0,  # Default for survivor tier
        "max_rivals": 0,    # Default for survivor tier
        "can_use_batches": "batch_processing" in tier_info["features"],
        "can_use_factions": "faction_system" in tier_info["features"],
        "can_use_rivalry": "rivalry_tracking" in tier_info["features"],
        "can_use_advanced_stats": "advanced_stats" in tier_info["features"]
    }
    
    # Set faction and rival limits based on tier
    if tier == "warlord":
        limits["max_factions"] = 5
        limits["max_rivals"] = 3
    elif tier == "overseer":
        limits["max_factions"] = 15
        limits["max_rivals"] = 10
        
    return limits

async def format_tier_comparison():
    """
    Format a tier comparison for display
    
    Returns:
        dict: Formatted tier comparison
    """
    all_features = set()
    for tier_info in PREMIUM_TIERS.values():
        all_features.update(tier_info["features"])
    
    feature_display_names = {
        "basic_stats": "Basic Player Statistics",
        "killfeed": "Killfeed Notifications",
        "player_linking": "Main/Alt Character Linking",
        "advanced_stats": "Advanced Statistics",
        "batch_processing": "Historical Data Processing",
        "faction_system": "Faction System",
        "advanced_killfeed": "Advanced Killfeed",
        "mission_alerts": "Mission Alerts",
        "rivalry_tracking": "Rivalry Tracking",
        "event_tracking": "Event Tracking",
        "priority_support": "Priority Support",
        "custom_branding": "Custom Branding",
        "extended_history": "Extended History (30 days)"
    }
    
    comparison = {
        "features": [],
        "tiers": {tier: {"name": info["name"], "emoji": info["emoji"], "has_feature": []} for tier, info in PREMIUM_TIERS.items()}
    }
    
    # Sort features by availability
    sorted_features = sorted(all_features, key=lambda f: len([1 for tier_id, tier_info in PREMIUM_TIERS.items() if f in tier_info["features"]]))
    
    for feature in sorted_features:
        display_name = feature_display_names.get(feature, feature.replace("_", " ").title())
        comparison["features"].append(display_name)
        
        for tier_id, tier_info in PREMIUM_TIERS.items():
            comparison["tiers"][tier_id]["has_feature"].append(feature in tier_info["features"])
    
    return comparison