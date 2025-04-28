import logging
from datetime import datetime, timedelta
from utils.guild_isolation import get_server_ids_for_guild, check_server_ownership
from utils.premium import get_guild_premium_tier, get_premium_limits

logger = logging.getLogger('deadside_bot.utils.parser_isolation')

async def get_historical_days_limit(guild_id):
    """
    Get the number of days of historical data a guild can access
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        int: Maximum days of historical data
    """
    # Get premium tier and limits
    tier = await get_guild_premium_tier(guild_id)
    limits = await get_premium_limits(tier)
    
    # Check if historical parsing is enabled
    if not limits.get("historical_parsing", False):
        return 0
    
    # Return max history days
    return limits.get("max_history_days", 0)

async def can_parse_historical(guild_id):
    """
    Check if a guild has access to historical parsing
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        bool: True if the guild can parse historical data
    """
    return await get_historical_days_limit(guild_id) > 0

async def filter_parsers_by_guild(parsers, guild_id):
    """
    Filter parsers to only include those for a specific guild's servers
    
    Args:
        parsers: List of parser objects
        guild_id: Discord guild ID
        
    Returns:
        list: Filtered list of parsers
    """
    # Get server IDs for this guild
    server_ids = await get_server_ids_for_guild(guild_id)
    
    # Filter parsers
    filtered_parsers = []
    for parser in parsers:
        if parser.server_id in server_ids:
            filtered_parsers.append(parser)
    
    return filtered_parsers

async def can_run_historical_parser(guild_id, server_id):
    """
    Check if a guild can run a historical parser for a server
    
    Args:
        guild_id: Discord guild ID
        server_id: Server ObjectId
        
    Returns:
        tuple: (bool, str) - (Can run, reason if not)
    """
    # Verify server ownership
    if not await check_server_ownership(guild_id, server_id):
        return (False, "Server does not belong to this guild")
    
    # Check historical parsing access
    days_limit = await get_historical_days_limit(guild_id)
    if days_limit <= 0:
        return (False, "Historical parsing not available in current premium tier")
    
    return (True, "")

async def get_historical_cutoff_date(guild_id):
    """
    Get the earliest date a guild can parse historical data for
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        datetime: Earliest allowed date
    """
    days = await get_historical_days_limit(guild_id)
    if days <= 0:
        return datetime.utcnow()
    
    return datetime.utcnow() - timedelta(days=days)

async def is_date_in_historical_range(guild_id, date):
    """
    Check if a date is within the historical range for a guild
    
    Args:
        guild_id: Discord guild ID
        date: Date to check
        
    Returns:
        bool: True if date is within range
    """
    cutoff = await get_historical_cutoff_date(guild_id)
    return date >= cutoff