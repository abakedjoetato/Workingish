"""
Cog Command Fix Implementation

This script standardizes the get_commands() method across all cogs to ensure
consistent command registration with Discord.
"""

import logging
import os
import inspect
import importlib.util
from pathlib import Path

logger = logging.getLogger("cog_fix")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def check_cog_file(file_path):
    """
    Check if a cog file has the get_commands() method implemented correctly.
    
    Args:
        file_path: Path to the cog file
        
    Returns:
        tuple: (is_valid, class_name, has_get_commands)
    """
    try:
        # Load the module
        module_name = os.path.basename(file_path).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find the cog class
        cog_class = None
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, '__mro__'):
                if 'Cog' in str(obj.__mro__):
                    cog_class = obj
                    break
        
        if not cog_class:
            return False, None, False
            
        # Check if the class has get_commands method
        has_get_commands = hasattr(cog_class, 'get_commands')
        
        return True, cog_class.__name__, has_get_commands
    except Exception as e:
        logger.error(f"Error checking cog file {file_path}: {e}")
        return False, None, False

def main():
    """Check all cog files for get_commands() implementation"""
    logger.info("Checking all cogs for get_commands() implementation")
    
    # Find all cog files
    cog_dir = Path('cogs')
    cog_files = list(cog_dir.glob('*.py'))
    
    if not cog_files:
        logger.error(f"No cog files found in directory: {cog_dir}")
        return
        
    logger.info(f"Found {len(cog_files)} cog files")
    
    # Check each file
    missing_get_commands = []
    
    for file_path in cog_files:
        # Skip __init__.py
        if file_path.name == '__init__.py':
            continue
            
        is_valid, class_name, has_get_commands = check_cog_file(file_path)
        
        if is_valid:
            status = "✅ Has get_commands()" if has_get_commands else "❌ Missing get_commands()"
            logger.info(f"{file_path.name}: {class_name} - {status}")
            
            if not has_get_commands:
                missing_get_commands.append((file_path, class_name))
        else:
            logger.warning(f"{file_path.name}: Not a valid cog file or could not be analyzed")
    
    # Report results
    if missing_get_commands:
        logger.warning(f"Found {len(missing_get_commands)} cogs missing get_commands() method:")
        for file_path, class_name in missing_get_commands:
            logger.warning(f"  - {file_path.name}: {class_name}")
    else:
        logger.info("All cogs have get_commands() method implemented correctly!")
    
if __name__ == "__main__":
    main()