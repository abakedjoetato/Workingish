"""
Unified Command Fix Implementation

This script provides a one-stop solution for fixing all command-related issues
in the Discord bot. It ensures all cogs have proper get_commands() methods,
updates command registration handlers, and forces a sync with Discord API.

Usage:
    python unified_command_fix.py
"""

import sys
import os
import asyncio
import logging
import traceback
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("unified_fix")

# First check if the required implementations are present
if not Path("fix_all_commands.py").exists() or not Path("command_fix_implementation.py").exists():
    logger.error("Required implementation files not found.")
    logger.error("Please ensure both fix_all_commands.py and command_fix_implementation.py exist.")
    sys.exit(1)

# Import the implementations
try:
    from fix_all_commands import check_cog_files, update_utils_sync_retry
    from command_fix_implementation import safe_command_sync
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    sys.exit(1)

def check_and_fix_cogs():
    """Check all cog files for get_commands() implementation and fix if missing"""
    logger.info("Checking and fixing cog files...")
    fixed_count = check_cog_files()
    
    if fixed_count > 0:
        logger.info(f"✅ Successfully fixed {fixed_count} cog files")
    else:
        logger.info("✅ All cog files are already properly configured")
    
    return fixed_count

def update_sync_retry_module():
    """Update the sync_retry module with the latest implementation"""
    logger.info("Updating sync_retry module...")
    updated = update_utils_sync_retry()
    
    if updated:
        logger.info("✅ Successfully updated sync_retry module")
    else:
        logger.warning("⚠️ Failed to update sync_retry module")
    
    return updated

async def force_command_registration():
    """Force command registration for all commands"""
    logger.info("Forcing command registration...")
    
    try:
        # Clear the last sync timestamp to force a fresh sync
        last_sync_file = Path(".last_command_sync")
        if last_sync_file.exists():
            last_sync_file.unlink()
            logger.info("✅ Cleared previous sync timestamp")
        
        # Force a full sync with all commands
        result = await safe_command_sync(force=True)
        
        if result:
            logger.info("✅ Command registration completed successfully")
            return True
        else:
            logger.warning("⚠️ Command registration was not fully successful")
            logger.info("This is typically due to Discord's rate limits.")
            logger.info("The bot will automatically retry on next startup.")
            return False
    except Exception as e:
        logger.error(f"Error during command registration: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Execute all command fixes in a unified approach"""
    logger.info("Starting unified command fix process")
    
    # Step 1: Check and fix cogs
    check_and_fix_cogs()
    
    # Step 2: Update sync_retry module
    update_sync_retry_module()
    
    # Step 3: Force command registration
    asyncio.run(force_command_registration())
    
    # Step 4: Provide summary
    logger.info("Unified command fix process completed!")
    logger.info("Note: Due to Discord's rate limits, it may take up to an hour for all commands to be fully registered.")
    logger.info("      If commands don't appear immediately, please be patient.")

if __name__ == "__main__":
    main()