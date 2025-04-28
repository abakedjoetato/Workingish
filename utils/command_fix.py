"""
Command Registration Fix Utility

This module provides utilities to fix issues with Discord slash command registration.
Specifically, it addresses the 'NoneType' object is not iterable error that occurs
when integration_types is None during command.to_dict() calls.
"""

import logging
import discord

logger = logging.getLogger('deadside_bot.utils.command_fix')

def fix_command_group(command_group):
    """
    Fix a SlashCommandGroup by ensuring integration_types is not None.
    
    Args:
        command_group: The SlashCommandGroup to fix
        
    Returns:
        The fixed SlashCommandGroup
    """
    if not isinstance(command_group, discord.SlashCommandGroup):
        logger.warning(f"Not a SlashCommandGroup: {type(command_group)}")
        return command_group
        
    # Fix the integration_types attribute if it's None
    if not hasattr(command_group, 'integration_types') or command_group.integration_types is None:
        # Must have at least one item according to Discord API - use 1 for GUILD_INSTALL
        command_group.integration_types = [1]
        logger.info(f"Fixed integration_types for command group: {command_group.name}")
    elif len(command_group.integration_types) == 0:
        # Discord API requires at least one integration type - use 1 for GUILD_INSTALL
        command_group.integration_types = [1]
        logger.info(f"Added required item to integration_types for command group: {command_group.name}")
    
    # Fix the contexts attribute if it's None
    if not hasattr(command_group, 'contexts') or command_group.contexts is None:
        # Must have at least one item according to Discord API - use 2 for GUILD
        command_group.contexts = [2]
        logger.info(f"Fixed contexts for command group: {command_group.name}")
    elif len(command_group.contexts) == 0:
        # Discord API requires at least one context - use 2 for GUILD
        command_group.contexts = [2]
        logger.info(f"Added required item to contexts for command group: {command_group.name}")
    
    # Fix any other potential None attributes that should be lists
    for attr_name in ['mention_roles', 'mention_users', 'name_localizations', 'description_localizations']:
        if hasattr(command_group, attr_name) and getattr(command_group, attr_name) is None:
            setattr(command_group, attr_name, {})
            logger.info(f"Fixed {attr_name} for command group: {command_group.name}")
        
    # Also fix any subcommands
    subcommands = getattr(command_group, 'subcommands', None)
    if subcommands is not None:
        # Handle case where subcommands might be a dict or a list
        if isinstance(subcommands, dict):
            subcmds = subcommands.values()
        elif isinstance(subcommands, list):
            subcmds = subcommands
        else:
            logger.warning(f"Unexpected subcommands type: {type(subcommands)}")
            subcmds = []
            
        for cmd in subcmds:
            # Fix subcommand integration_types
            if hasattr(cmd, 'integration_types') and cmd.integration_types is None:
                cmd.integration_types = [1]  # 1 = GUILD_INSTALL
                logger.info(f"Fixed integration_types for subcommand: {cmd.name}")
            elif hasattr(cmd, 'integration_types') and len(cmd.integration_types) == 0:
                cmd.integration_types = [1]  # 1 = GUILD_INSTALL
                logger.info(f"Added required item to integration_types for subcommand: {cmd.name}")
                
            # Fix subcommand contexts
            if hasattr(cmd, 'contexts') and cmd.contexts is None:
                cmd.contexts = [2]  # 2 = GUILD
                logger.info(f"Fixed contexts for subcommand: {cmd.name}")
            elif hasattr(cmd, 'contexts') and len(cmd.contexts) == 0:
                cmd.contexts = [2]  # 2 = GUILD
                logger.info(f"Added required item to contexts for subcommand: {cmd.name}")
                
            # Fix other potential None attributes
            for attr_name in ['mention_roles', 'mention_users', 'name_localizations', 'description_localizations']:
                if hasattr(cmd, attr_name) and getattr(cmd, attr_name) is None:
                    setattr(cmd, attr_name, {})
                    logger.info(f"Fixed {attr_name} for subcommand: {cmd.name}")
    
    return command_group

def apply_command_fixes(bot):
    """
    Apply fixes to all command groups in all cogs.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        int: The number of command groups fixed
    """
    fixed_count = 0
    
    # Process each cog
    for cog_name, cog in bot.cogs.items():
        # Check if the cog has a get_commands method
        if hasattr(cog, "get_commands") and callable(cog.get_commands):
            try:
                # Get commands from the cog
                cog_commands = cog.get_commands()
                
                if cog_commands is None:
                    logger.error(f"Cog {cog_name} returned None instead of commands list")
                    continue
                    
                # Fix each command group
                for i, cmd in enumerate(cog_commands):
                    fixed_cmd = fix_command_group(cmd)
                    cog_commands[i] = fixed_cmd  # Replace with fixed version
                    fixed_count += 1
                    
            except Exception as e:
                logger.error(f"Error fixing commands for cog {cog_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    return fixed_count