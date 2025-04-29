import os
import logging
import json
import asyncio
import time
import discord

# Enhanced command registration function that fixes multiple issues at once
async def optimized_command_sync(bot):
    """
    Enhanced command registration that properly handles rate limits and context issues
    with a single batch registration approach
    """
    logger = logging.getLogger('deadside_bot')
    logger.info("Starting optimized command registration process")
    
    # 1. First fix all SlashCommandGroup objects that might have context issues
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'analytics') and cog_name == 'AnalyticsCog':
            # Ensure analytics group uses guild_only instead of contexts
            analytics_group = cog.analytics
            if hasattr(analytics_group, 'guild_only'):
                analytics_group.guild_only = True
                logger.info("Fixed analytics group guild_only parameter")
            
            # Remove any string contexts that cause errors
            if hasattr(analytics_group, 'contexts') and isinstance(analytics_group.contexts, set):
                # Check if any strings in the contexts
                string_contexts = [c for c in analytics_group.contexts if isinstance(c, str)]
                if string_contexts:
                    # Remove string contexts and use guild_only instead
                    analytics_group.contexts = [c for c in analytics_group.contexts if not isinstance(c, str)]
                    analytics_group.guild_only = True
                    logger.info("Removed string contexts from analytics group")
    
    # 2. Deduplicate commands to ensure clean registration
    unique_names = set()
    kept_commands = []
    
    for cmd in bot.application_commands:
        if cmd.name not in unique_names:
            unique_names.add(cmd.name)
            kept_commands.append(cmd)
            logger.info(f"Keeping command: {cmd.name}")
        else:
            logger.warning(f"Removing duplicate command: {cmd.name}")
    
    # Replace application_commands with deduplicated list
    bot.application_commands.clear()
    for cmd in kept_commands:
        bot.application_commands.append(cmd)
    
    # 3. Create a unified batch payload of all commands with proper error checking
    commands_payload = []
    
    for cmd in bot.application_commands:
        try:
            # Convert command to dictionary payload
            cmd_dict = cmd.to_dict()
            
            # Ensure description exists and is valid
            if not cmd_dict.get('description'):
                cmd_dict['description'] = f"Command for {cmd_dict.get('name', 'unknown')} functionality"
            
            # Fix any contexts issues
            if 'contexts' in cmd_dict:
                contexts = cmd_dict['contexts']
                if any(isinstance(c, str) for c in contexts):
                    # Replace string contexts with guild_only=True
                    cmd_dict.pop('contexts', None)
                    cmd_dict['guild_only'] = True
            
            commands_payload.append(cmd_dict)
            logger.info(f"Added command to payload: {cmd.name}")
        except Exception as e:
            logger.error(f"Error converting command {cmd.name} to dict: {e}")
    
    # 4. Register all commands in a single batch request with retry logic
    max_retries = 5
    for retry in range(max_retries):
        try:
            # Use Discord's HTTP API directly
            from discord.http import Route
            
            # First verify we can access the API
            try:
                test_route = Route("GET", f"/applications/{bot.application_id}/commands")
                await bot.http.request(test_route)
                logger.info("Discord API access verified")
            except Exception as e:
                logger.error(f"Cannot access Discord API: {e}")
                # If we can't even access the API, no need to retry
                return False
            
            # Use PUT to replace all commands in one batch
            route = Route("PUT", f"/applications/{bot.application_id}/commands")
            result = await bot.http.request(route, json=commands_payload)
            
            logger.info(f"Successfully registered all {len(commands_payload)} commands!")
            
            # Update last command check time
            with open(".last_command_check.txt", "w") as f:
                f.write(str(time.time()))
            
            return True
            
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = getattr(e, 'retry_after', 60)
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    await asyncio.sleep(retry_after + 5)  # Add buffer time
            else:
                logger.error(f"HTTP Error: {e}")
                if retry < max_retries - 1:
                    await asyncio.sleep(5 * (retry + 1))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if retry < max_retries - 1:
                await asyncio.sleep(5 * (retry + 1))
    
    # If we get here, all retries failed
    logger.error(f"Failed to register commands after {max_retries} attempts")
    
    # Emergency fallback - register just the ping command
    try:
        logger.warning("Attempting emergency fallback: registering ping command directly")
        ping_command = {
            "name": "ping",
            "description": "Check bot response time",
            "type": 1
        }
        route = Route("POST", f"/applications/{bot.application_id}/commands")
        await bot.http.request(route, json=ping_command)
        logger.info("Emergency ping command registered")
    except Exception as e:
        logger.error(f"Emergency fallback failed: {e}")
    
    return False