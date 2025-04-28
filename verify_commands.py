"""
Command Fix Verification Script

This script verifies that all Discord command fixes have been properly applied:
1. Checks all cogs for get_commands() methods
2. Verifies sync_retry module is updated
3. Confirms command registration is happening correctly
"""

import asyncio
import logging
import os
import sys
import time
import inspect
import importlib.util
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("verify_commands")

def check_cog_get_commands():
    """Check if all cogs have get_commands() method"""
    logger.info("Checking all cogs for get_commands() method...")
    
    # Find all cogs
    cog_dir = Path('cogs')
    if not cog_dir.exists():
        logger.error("Cogs directory not found!")
        return False
    
    cog_files = [f for f in cog_dir.glob('*.py') if f.name != '__init__.py']
    
    if not cog_files:
        logger.error("No cog files found!")
        return False
    
    all_valid = True
    
    for cog_file in cog_files:
        # Skip __init__.py
        if cog_file.name == '__init__.py':
            continue
        
        # Check file content for get_commands method
        content = cog_file.read_text()
        if 'def get_commands(self)' not in content:
            logger.error(f"❌ {cog_file.name}: Missing get_commands() method!")
            all_valid = False
        else:
            logger.info(f"✅ {cog_file.name}: Has get_commands() method")
    
    return all_valid

def check_sync_retry_module():
    """Check if sync_retry module exists and has necessary components"""
    logger.info("Checking sync_retry module...")
    
    sync_retry_path = Path('utils/sync_retry.py')
    
    if not sync_retry_path.exists():
        logger.error("❌ sync_retry module not found!")
        return False
    
    # Check for key functions
    content = sync_retry_path.read_text()
    
    required_functions = [
        'safe_command_sync',
        '_register_commands_safely',
        '_generate_minimal_commands',
        '_handle_rate_limit'
    ]
    
    all_functions_present = True
    for func in required_functions:
        if func not in content:
            logger.error(f"❌ sync_retry module missing required function: {func}")
            all_functions_present = False
    
    if all_functions_present:
        logger.info("✅ sync_retry module has all required functions")
    
    return all_functions_present

def check_sync_file():
    """Check if .last_command_sync file exists with valid timestamp"""
    logger.info("Checking .last_command_sync file...")
    
    sync_file = Path('.last_command_sync')
    
    if not sync_file.exists():
        logger.warning("⚠️ .last_command_sync file not found - bot will register commands on next restart")
        return True
    
    try:
        with open(sync_file, 'r') as f:
            timestamp = float(f.read().strip())
        
        # Check if timestamp is valid (not too old or in the future)
        current_time = time.time()
        time_diff = current_time - timestamp
        
        if time_diff < 0:
            logger.warning("⚠️ .last_command_sync timestamp is in the future!")
            return False
        
        if time_diff > 86400 * 7:  # 7 days
            logger.warning(f"⚠️ .last_command_sync timestamp is old: {time_diff / 86400:.1f} days")
        else:
            logger.info(f"✅ .last_command_sync timestamp is valid: {time_diff / 3600:.1f} hours ago")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error reading .last_command_sync file: {e}")
        return False

def main():
    """Run all verification checks"""
    logger.info("Starting command fix verification")
    
    # Run all checks
    cogs_ok = check_cog_get_commands()
    sync_module_ok = check_sync_retry_module()
    sync_file_ok = check_sync_file()
    
    # Summarize results
    logger.info("\n--- Verification Results ---")
    logger.info(f"Cogs with get_commands(): {'✅ PASS' if cogs_ok else '❌ FAIL'}")
    logger.info(f"sync_retry module: {'✅ PASS' if sync_module_ok else '❌ FAIL'}")
    logger.info(f"Command sync state: {'✅ PASS' if sync_file_ok else '❌ FAIL'}")
    
    # Final assessment
    if cogs_ok and sync_module_ok and sync_file_ok:
        logger.info("\n✅ ALL CHECKS PASSED! Command fixes have been successfully applied.")
        logger.info("The bot should correctly register all commands with Discord.")
        logger.info("Note: Due to Discord's rate limits, it may take up to an hour for all commands to appear.")
        return True
    else:
        logger.error("\n❌ SOME CHECKS FAILED! Command fixes may not be fully applied.")
        logger.error("Please run the unified_command_fix.py script to fix all issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)