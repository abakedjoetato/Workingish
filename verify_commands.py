"""
Command Fix Verification Script

This script verifies that all Discord command fixes have been properly applied:
1. Checks all cogs for get_commands() methods
2. Verifies sync_retry module is updated
3. Confirms command registration is happening correctly
"""

import sys
import os
import logging
from pathlib import Path
import importlib.util

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("command_verify")

def check_cog_get_commands():
    """Check if all cogs have get_commands() method"""
    logger.info("Checking cogs for get_commands() method...")
    
    cog_dir = Path("cogs")
    required_cogs = [
        'server_commands_slash.py',
        'stats_commands.py',
        'killfeed_commands.py',
        'connection_commands.py',
        'mission_commands.py',
        'faction_commands.py',
        'admin_commands.py'
    ]
    
    # Track results
    valid_cogs = 0
    invalid_cogs = 0
    missing_cogs = 0
    
    # Check each required cog
    for cog_file in required_cogs:
        file_path = cog_dir / cog_file
        
        if not file_path.exists():
            logger.warning(f"❌ Cog file missing: {cog_file}")
            missing_cogs += 1
            continue
            
        # Check if the file has get_commands method
        with open(file_path, 'r') as f:
            content = f.read()
            
        if "def get_commands(self)" in content:
            logger.info(f"✅ {cog_file}: Has get_commands() method")
            valid_cogs += 1
        else:
            logger.error(f"❌ {cog_file}: Missing get_commands() method")
            invalid_cogs += 1
    
    # Summary
    logger.info(f"Cog verification summary: {valid_cogs} valid, {invalid_cogs} invalid, {missing_cogs} missing")
    
    return valid_cogs == len(required_cogs)

def check_sync_retry_module():
    """Check if sync_retry module exists and has necessary components"""
    logger.info("Checking sync_retry module...")
    
    module_path = Path("utils") / "sync_retry.py"
    
    if not module_path.exists():
        logger.error("❌ sync_retry module is missing")
        return False
        
    # Check content
    with open(module_path, 'r') as f:
        content = f.read()
    
    # Check for key elements
    required_elements = [
        "safe_command_sync",
        "CRITICAL_COMMANDS",
        "_handle_rate_limit",
        "_register_commands_safely",
        "_is_recent_sync",
        "VERSION ="
    ]
    
    missing_elements = []
    for element in required_elements:
        if element not in content:
            missing_elements.append(element)
            
    if missing_elements:
        logger.error(f"❌ sync_retry module is missing required elements: {', '.join(missing_elements)}")
        return False
        
    # Try to get version
    version_line = [line for line in content.splitlines() if "VERSION =" in line]
    if version_line:
        try:
            version = float(version_line[0].split("=")[1].strip())
            logger.info(f"✅ sync_retry module version: {version}")
            
            if version < 1.0:
                logger.warning(f"⚠️ sync_retry module version ({version}) may be outdated")
        except (ValueError, IndexError):
            logger.warning("⚠️ Could not parse sync_retry module version")
    
    logger.info("✅ sync_retry module exists and contains required elements")
    return True

def check_sync_file():
    """Check if .last_command_sync file exists with valid timestamp"""
    logger.info("Checking command sync state...")
    
    sync_file = Path(".last_command_sync")
    
    if not sync_file.exists():
        logger.warning("⚠️ No command sync timestamp found (.last_command_sync)")
        logger.info("This is normal if commands haven't been registered yet")
        return False
    
    # Try to read the timestamp
    try:
        with open(sync_file, 'r') as f:
            timestamp = float(f.read().strip())
            
        import time
        time_since = time.time() - timestamp
        hours_since = time_since / 3600
        
        logger.info(f"✅ Last command sync was {hours_since:.2f} hours ago")
        
        if hours_since > 24:
            logger.warning(f"⚠️ Command sync is more than 24 hours old")
    except Exception as e:
        logger.error(f"❌ Error reading sync timestamp: {e}")
        return False
    
    return True

def main():
    """Run all verification checks"""
    logger.info("Starting command fix verification...")
    
    # Track overall status
    status = True
    
    # Check 1: Cogs have get_commands() methods
    if not check_cog_get_commands():
        logger.error("❌ Some cogs are missing get_commands() methods")
        logger.info("Run fix_all_commands.py to fix this issue")
        status = False
    
    # Check 2: sync_retry module is properly set up
    if not check_sync_retry_module():
        logger.error("❌ sync_retry module is not properly set up")
        logger.info("Run update_utils_sync_retry() to fix this issue")
        status = False
    
    # Check 3: Command sync has been performed
    if not check_sync_file():
        logger.warning("⚠️ No record of command sync found")
        logger.info("This may be normal if the bot hasn't been run yet")
        # Don't fail for this, just warn
    
    # Check if all implementation files exist
    implementation_files = [
        "command_fix_implementation.py",
        "fix_all_commands.py",
        "unified_command_fix.py"
    ]
    
    missing_files = [f for f in implementation_files if not Path(f).exists()]
    
    if missing_files:
        logger.error(f"❌ Missing implementation files: {', '.join(missing_files)}")
        status = False
    else:
        logger.info("✅ All implementation files are present")
    
    # Final status
    if status:
        logger.info("✅ All command fixes have been properly applied!")
        logger.info("The bot should now register commands correctly with Discord")
    else:
        logger.error("❌ Some command fixes have not been properly applied")
        logger.info("Run unified_command_fix.py to fix all issues")
    
    return status

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)