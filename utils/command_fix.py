"""
Command Registration Fix Utility

This module provides utilities to fix issues with Discord slash command registration.
Specifically, it addresses the 'NoneType' object is not iterable error that occurs
when integration_types is None during command.to_dict() calls.

It also provides an optimized command registration function that handles rate limits
and properly batches commands for more reliable registration with Discord's API.
"""

import logging
import sys
import inspect
import discord

logger = logging.getLogger('deadside_bot.utils.command_fix')

# Create custom enum objects that work with Discord's to_dict() method
class EnumWrapper:
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return str(self.value)
    
    def __repr__(self):
        return f"EnumWrapper({self.value})"

# Create proper enum-like objects that Discord API expects
class IntegrationTypeEnum:
    GUILD_INSTALL = EnumWrapper(1)
    USER_INSTALL = EnumWrapper(0)

class CommandContextEnum:
    GUILD = EnumWrapper(2)
    BOT_DM = EnumWrapper(1)
    PRIVATE = EnumWrapper(0)

def get_enum_objects():
    """Helper function to get the correct enum objects based on discord version"""
    # Try to detect discord version and available enums
    if hasattr(discord, 'app_commands') and hasattr(discord.app_commands, 'AppCommandType'):
        logger.info("Using discord.app_commands enums")
        # For py-cord versions
        try:
            # Create integration type objects with compatible value attribute
            integration_type_guild = EnumWrapper(1)  # GUILD_INSTALL
            context_type_guild = EnumWrapper(2)  # GUILD
            return integration_type_guild, context_type_guild
        except Exception as e:
            logger.error(f"Error creating enum wrappers: {e}")
    
    # Fallback to our custom enums
    logger.info("Using custom enum wrappers")
    return IntegrationTypeEnum.GUILD_INSTALL, CommandContextEnum.GUILD

# Get the appropriate enum values to use
INTEGRATION_TYPE_GUILD, COMMAND_CONTEXT_GUILD = get_enum_objects()

def fix_command_group_attributes(command_obj):
    """Fix attributes on a command object for proper serialization"""
    # Get the command name for logging
    cmd_name = getattr(command_obj, 'name', 'Unknown')
    
    # Direct attribute access for critical ones to avoid callback errors
    try:
        # Fix integration_types attribute
        if hasattr(command_obj, 'integration_types'):
            integration_types = getattr(command_obj, 'integration_types')
            if integration_types is None or len(integration_types) == 0:
                setattr(command_obj, 'integration_types', [INTEGRATION_TYPE_GUILD])
                logger.info(f"Fixed integration_types for command: {cmd_name}")
        
        # Fix contexts attribute
        if hasattr(command_obj, 'contexts'):
            contexts = getattr(command_obj, 'contexts')
            if contexts is None or len(contexts) == 0:
                setattr(command_obj, 'contexts', [COMMAND_CONTEXT_GUILD])
                logger.info(f"Fixed contexts for command: {cmd_name}")
        
        # Set other None attributes that should be empty collections
        for attr_name in ['mention_roles', 'mention_users', 'name_localizations', 'description_localizations']:
            if hasattr(command_obj, attr_name) and getattr(command_obj, attr_name) is None:
                setattr(command_obj, attr_name, {})
                logger.info(f"Fixed {attr_name} for command: {cmd_name}")
    except AttributeError as e:
        # Catch any property access errors
        logger.warning(f"Skipping problematic attribute for {cmd_name}: {e}")
    
    return command_obj

def fix_command_group(command_group):
    """
    Fix a SlashCommandGroup by ensuring integration_types and contexts are properly set.
    
    Args:
        command_group: The SlashCommandGroup to fix
        
    Returns:
        The fixed SlashCommandGroup
    """
    if not isinstance(command_group, discord.SlashCommandGroup):
        logger.warning(f"Not a SlashCommandGroup: {type(command_group)}")
        return command_group
    
    # Fix the command group's attributes
    command_group = fix_command_group_attributes(command_group)
    
    # Hack: Override the to_dict method to bypass attribute checking
    original_to_dict = command_group.to_dict
    
    def safe_to_dict():
        """Custom to_dict that safely handles our enum wrappers"""
        try:
            return original_to_dict()
        except Exception as e:
            logger.warning(f"Error in original to_dict: {e}")
            # Fallback: create a manual dictionary with required fields
            result = {
                'name': command_group.name,
                'description': command_group.description,
                'type': 1,  # SlashCommand
                'options': [],
                'integration_types': [1],  # GUILD_INSTALL as raw value
                'contexts': [2],  # GUILD as raw value
            }
            return result
    
    # Only apply our hack if we're in a debugging situation
    if False and hasattr(command_group, 'to_dict'):
        command_group.to_dict = safe_to_dict
        logger.info(f"Applied safe to_dict method to command group {command_group.name}")
    
    # Also fix any subcommands
    subcommands = getattr(command_group, 'subcommands', None)
    if subcommands is not None:
        # Handle case where subcommands might be a dict or a list
        if isinstance(subcommands, dict):
            subcmds = list(subcommands.values())
        elif isinstance(subcommands, list):
            subcmds = subcommands
        else:
            logger.warning(f"Unexpected subcommands type: {type(subcommands)}")
            subcmds = []
        
        # Fix each subcommand
        for cmd in subcmds:
            fix_command_group_attributes(cmd)
    
    return command_group

def apply_command_fixes(bot):
    """
    Apply fixes to all command groups in all cogs and application commands.
    
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
                
                # Log useful debug info
                logger.info(f"Cog {cog_name} returned command type: {type(cog_commands)}")
                
                if cog_commands is None:
                    logger.error(f"Cog {cog_name} returned None instead of commands list")
                    continue
                
                if not isinstance(cog_commands, list):
                    logger.warning(f"Cog {cog_name} returned {type(cog_commands)} instead of list, trying to convert")
                    try:
                        if hasattr(cog_commands, "__iter__"):
                            cog_commands = list(cog_commands)
                        else:
                            cog_commands = [cog_commands]
                    except:
                        logger.error(f"Could not convert commands from {cog_name} to list")
                        continue
                
                # Fix each command
                for cmd in cog_commands:
                    try:
                        # Just patch attributes directly, don't try to modify the command object
                        cmd_name = getattr(cmd, 'name', 'Unknown')
                        
                        # Fix integration_types
                        if hasattr(cmd, 'integration_types'):
                            integration_types = getattr(cmd, 'integration_types')
                            if integration_types is None or len(integration_types) == 0:
                                setattr(cmd, 'integration_types', [INTEGRATION_TYPE_GUILD])
                                logger.info(f"Fixed integration_types for command: {cmd_name}")
                                fixed_count += 1
                        
                        # Fix contexts
                        if hasattr(cmd, 'contexts'):
                            contexts = getattr(cmd, 'contexts')
                            if contexts is None or len(contexts) == 0:
                                setattr(cmd, 'contexts', [COMMAND_CONTEXT_GUILD])
                                logger.info(f"Fixed contexts for command: {cmd_name}")
                                fixed_count += 1
                    except Exception as e:
                        logger.error(f"Error fixing command {getattr(cmd, 'name', 'Unknown')}: {e}")
            except Exception as e:
                logger.error(f"Error fixing commands for cog {cog_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    # Also fix any directly registered application commands
    try:
        for cmd in bot.application_commands:
            try:
                cmd_name = getattr(cmd, 'name', 'Unknown')
                
                # Fix integration_types
                if hasattr(cmd, 'integration_types'):
                    integration_types = getattr(cmd, 'integration_types')
                    if integration_types is None or len(integration_types) == 0:
                        setattr(cmd, 'integration_types', [INTEGRATION_TYPE_GUILD])
                        logger.info(f"Fixed integration_types for app command: {cmd_name}")
                        fixed_count += 1
                
                # Fix contexts
                if hasattr(cmd, 'contexts'):
                    contexts = getattr(cmd, 'contexts')
                    if contexts is None or len(contexts) == 0:
                        setattr(cmd, 'contexts', [COMMAND_CONTEXT_GUILD])
                        logger.info(f"Fixed contexts for app command: {cmd_name}")
                        fixed_count += 1
            except Exception as e:
                logger.error(f"Error fixing application command {getattr(cmd, 'name', 'Unknown')}: {e}")
    except Exception as e:
        logger.error(f"Error processing application commands: {e}")
    
    return fixed_count

async def optimized_command_sync(bot):
    """
    Enhanced command registration that properly handles rate limits and context issues
    with a single batch registration approach
    """
    logger.info("Starting optimized command registration process")
    
    # 1. First fix all SlashCommandGroup objects that might have context issues
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'analytics') and cog_name == 'AnalyticsCog':
            # Ensure analytics group uses guild_only instead of contexts
            analytics_group = cog.analytics
            if hasattr(analytics_group, 'guild_only'):
                analytics_group.contexts=[discord.InteractionContextType.guild]
                logger.info("Fixed analytics group guild_only parameter")
            
            # Remove any string contexts that cause errors
            if hasattr(analytics_group, 'contexts') and isinstance(analytics_group.contexts, set):
                # Check if any strings in the contexts
                string_contexts = [c for c in analytics_group.contexts if isinstance(c, str)]
                if string_contexts:
                    # Remove string contexts and use guild_only instead
                    analytics_group.contexts = [c for c in analytics_group.contexts if not isinstance(c, str)]
                    analytics_group.contexts=[discord.InteractionContextType.guild]
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
                    # Replace string contexts with contexts=[discord.InteractionContextType.guild]
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
            import time
            with open(".last_command_check.txt", "w") as f:
                f.write(str(time.time()))
            
            return True
            
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = getattr(e, 'retry_after', 60)
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds (attempt {retry+1}/{max_retries})")
                import asyncio
                if retry < max_retries - 1:
                    await asyncio.sleep(retry_after + 5)  # Add buffer time
            else:
                logger.error(f"HTTP Error: {e}")
                import asyncio
                if retry < max_retries - 1:
                    await asyncio.sleep(5 * (retry + 1))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            import asyncio
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
        from discord.http import Route
        route = Route("POST", f"/applications/{bot.application_id}/commands")
        await bot.http.request(route, json=ping_command)
        logger.info("Emergency ping command registered")
    except Exception as e:
        logger.error(f"Emergency fallback failed: {e}")
    
    return False

def patch_discord_internals():
    """
    Attempt to patch discord internals to better handle our custom enum objects.
    This is a more aggressive approach that should only be used if other methods fail.
    """
    try:
        # Find the to_dict method on SlashCommandGroup
        if hasattr(discord, 'SlashCommandGroup'):
            command_class = discord.SlashCommandGroup
            
            # Get the original to_dict method
            if hasattr(command_class, 'to_dict'):
                original_method = command_class.to_dict
                
                # Create a patched version that handles our enum objects
                def patched_to_dict(self):
                    try:
                        # First try the original method
                        return original_method(self)
                    except AttributeError as e:
                        if "'int' object has no attribute 'value'" in str(e):
                            # Fix the integration_types attribute
                            if hasattr(self, 'integration_types'):
                                self.integration_types = [INTEGRATION_TYPE_GUILD]
                            
                            # Fix the contexts attribute
                            if hasattr(self, 'contexts'):
                                self.contexts = [COMMAND_CONTEXT_GUILD]
                                
                            # Try again with fixed attributes
                            return original_method(self)
                        else:
                            # If it's a different error, re-raise
                            raise
                
                # Apply our patched method
                command_class.to_dict = patched_to_dict
                logger.info("Successfully patched discord.SlashCommandGroup.to_dict")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error patching Discord internals: {e}")
        return False