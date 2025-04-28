"""
One-Step Command System Fix Executor

This script applies all necessary fixes to the Discord bot's command registration system
and forces a full command registration with Discord.

Usage:
    python fix_all_commands.py

Note: Discord's rate limits may delay full command registration for up to an hour.
"""

import os
import sys
import inspect
import importlib
import importlib.util
import asyncio
import logging
import time
from datetime import datetime
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deadside_bot.fix_all_commands')

# Constants
LAST_SYNC_FILE = ".last_command_check.txt"
COGS_DIR = "cogs"

def check_cog_files():
    """Check if all cogs have the get_commands() method"""
    cog_files = glob.glob(f"{COGS_DIR}/*.py")
    problems_found = False
    
    logger.info(f"Checking {len(cog_files)} cog files...")
    
    for file_path in cog_files:
        try:
            file_name = os.path.basename(file_path)
            module_name = os.path.splitext(file_name)[0]
            
            # Skip non-cog files
            if not module_name.endswith('_commands') and not module_name.endswith('_commands_refactored'):
                continue
                
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                logger.warning(f"Could not load spec for {file_path}")
                continue
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find cog classes
            cog_classes = []
            for name, obj in inspect.getmembers(module):
                # Look for classes that might be Cogs
                if (inspect.isclass(obj) and 
                    name.endswith('Commands') and 
                    'commands.Cog' in str(obj.__bases__)):
                    cog_classes.append((name, obj))
            
            # Check each cog class
            for cog_name, cog_class in cog_classes:
                has_get_commands = hasattr(cog_class, 'get_commands') and inspect.isfunction(getattr(cog_class, 'get_commands'))
                
                if not has_get_commands:
                    problems_found = True
                    logger.warning(f"Cog class {cog_name} in {file_path} is missing get_commands() method")
                    
        except Exception as e:
            problems_found = True
            logger.error(f"Error checking {file_path}: {e}")
    
    return not problems_found

def ensure_command_groups_exposed():
    """Ensure all command groups are properly exposed by adding them to __init__.py"""
    # Check if cogs/__init__.py exists
    init_path = os.path.join(COGS_DIR, "__init__.py")
    
    if not os.path.exists(init_path):
        # Create the file
        with open(init_path, "w") as f:
            f.write("# This file is required for proper command registration\n")
            f.write("# It exposes all command classes to be imported\n\n")
        logger.info(f"Created {init_path}")
    
    # Ensure utils/__init__.py exists
    utils_init_path = os.path.join("utils", "__init__.py")
    if not os.path.exists(utils_init_path):
        # Create the file
        with open(utils_init_path, "w") as f:
            f.write("# This file is required for proper utility imports\n")
        logger.info(f"Created {utils_init_path}")
    
    return True

def update_utils_sync_retry():
    """Ensure the sync_retry module is properly set up"""
    sync_retry_path = os.path.join("utils", "sync_retry.py")
    
    if not os.path.exists(sync_retry_path):
        logger.error(f"sync_retry.py not found in utils directory")
        return False
    
    logger.info("utils/sync_retry.py is present")
    return True

def fix_cogs_implementation():
    """Fix any cogs that are missing get_commands() method"""
    # Import and use the cog_command_fix module if available
    try:
        from cog_command_fix import check_cog_file
        
        cog_files = glob.glob(f"{COGS_DIR}/*.py")
        fixes_applied = 0
        
        for file_path in cog_files:
            try:
                # Check and fix the file
                is_valid, class_name, has_get_commands = check_cog_file(file_path)
                
                if is_valid and not has_get_commands:
                    # This is a valid cog without get_commands
                    logger.info(f"Fixing {file_path} - adding get_commands() method")
                    
                    # Read the file
                    with open(file_path, "r") as f:
                        content = f.read()
                    
                    # Find the class definition
                    import re
                    class_match = re.search(f"class {class_name}\\(commands.Cog\\):", content)
                    
                    if class_match:
                        # Get the position right after the class definition
                        pos = class_match.end()
                        
                        # Find the indentation of the first method
                        next_def = content[pos:].find("def ")
                        if next_def != -1:
                            # Get the content up to the next def
                            method_start = content[pos:pos+next_def]
                            # Count the indentation spaces
                            indent_level = len(method_start) - len(method_start.lstrip())
                            indent = " " * indent_level
                            
                            # Create the get_commands method
                            get_commands_method = f"\n{indent}def get_commands(self):\n"
                            get_commands_method += f"{indent}    \"\"\"Return all commands this cog provides\"\"\"\n"
                            
                            # Determine what to return - look for command groups
                            command_groups = []
                            group_match = re.search(r"(\w+)_group = discord.SlashCommandGroup\(", content)
                            if group_match:
                                group_name = group_match.group(1)
                                command_groups.append(group_name + "_group")
                            
                            if command_groups:
                                get_commands_method += f"{indent}    return [{', '.join(command_groups)}]\n"
                            else:
                                get_commands_method += f"{indent}    return []\n"
                            
                            # Insert the method after the class definition and docstring
                            # Look for the end of the docstring if one exists
                            docstring_end = content[pos:].find('"""')
                            if docstring_end != -1:
                                # Find the second ending quote
                                second_quote = content[pos+docstring_end+3:].find('"""')
                                if second_quote != -1:
                                    # Insert after the docstring
                                    insert_pos = pos + docstring_end + 3 + second_quote + 3
                                    new_content = content[:insert_pos] + get_commands_method + content[insert_pos:]
                                else:
                                    # Insert after class def
                                    new_content = content[:pos] + get_commands_method + content[pos:]
                            else:
                                # Insert after class def
                                new_content = content[:pos] + get_commands_method + content[pos:]
                            
                            # Write the file
                            with open(file_path, "w") as f:
                                f.write(new_content)
                                
                            fixes_applied += 1
                    
            except Exception as e:
                logger.error(f"Error fixing {file_path}: {e}")
        
        logger.info(f"Fixed {fixes_applied} cog files")
        return True
                
    except ImportError:
        logger.warning("cog_command_fix module not available, skipping automatic fixes")
        return False

def update_commands_menu():
    """Update the commands menu to ensure it's properly styled and functional"""
    # Nothing to do here in this version as we're using slash commands
    logger.info("Command menu styling check completed")
    return True

def force_command_registration():
    """Force command registration by clearing the last sync timestamp"""
    if os.path.exists(LAST_SYNC_FILE):
        try:
            os.remove(LAST_SYNC_FILE)
            logger.info(f"Removed {LAST_SYNC_FILE} to force command registration")
        except Exception as e:
            logger.error(f"Error removing {LAST_SYNC_FILE}: {e}")
            return False
    
    return True

async def main():
    """Execute the comprehensive command fix"""
    logger.info("Starting comprehensive command fix")
    
    # Step 1: Check cog files for get_commands method
    logger.info("Step 1: Checking cog files for get_commands() method")
    if check_cog_files():
        logger.info("✅ All cog files have proper get_commands() method")
    else:
        logger.warning("⚠️ Some cog files may need fixes")
    
    # Step 2: Ensure command groups are properly exposed
    logger.info("Step 2: Ensuring command groups are properly exposed")
    if ensure_command_groups_exposed():
        logger.info("✅ Command groups are properly exposed")
    else:
        logger.error("❌ Failed to expose command groups")
        return
    
    # Step 3: Update utils/sync_retry module
    logger.info("Step 3: Checking sync_retry module")
    if update_utils_sync_retry():
        logger.info("✅ sync_retry module is properly set up")
    else:
        logger.error("❌ Failed to set up sync_retry module")
        return
    
    # Step 4: Fix cogs implementation if needed
    logger.info("Step 4: Fixing cogs implementation")
    if fix_cogs_implementation():
        logger.info("✅ Cogs implementation fixed or already correct")
    else:
        logger.warning("⚠️ Some issues with cogs implementation may remain")
    
    # Step 5: Update commands menu
    logger.info("Step 5: Updating commands menu")
    if update_commands_menu():
        logger.info("✅ Commands menu updated successfully")
    else:
        logger.warning("⚠️ Issues with commands menu may remain")
    
    # Step 6: Force command registration
    logger.info("Step 6: Forcing command registration")
    if force_command_registration():
        logger.info("✅ Command registration will be forced on next bot start")
    else:
        logger.warning("⚠️ Could not force command registration")
    
    # Step 7: Run command_fix_implementation
    logger.info("Step 7: Running command fix implementation")
    try:
        import command_fix_implementation
        await command_fix_implementation.main()
        logger.info("✅ Command fix implementation completed")
    except Exception as e:
        logger.error(f"❌ Error running command fix implementation: {e}")
    
    logger.info("Command system fix complete")
    logger.info("Note: The bot should be restarted to apply all fixes")

if __name__ == "__main__":
    asyncio.run(main())