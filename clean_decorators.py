#!/usr/bin/env python3
"""
Script to clean duplicate decorators in Python files.
This script identifies and removes duplicate command decorators.
"""

import os
import re
import sys
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('decorator_cleaner')

def find_python_files(directory):
    """Find all Python files in the given directory."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def clean_duplicate_decorators(file_path):
    """Remove duplicate decorators in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        cleaned_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # Look for lines with server_group.command or any other command group
            if re.search(r'@\w+_group\.command\(', line):
                # Check if next line also has a command decorator
                if i + 1 < len(lines) and re.search(r'@\w+_group\.command\(', lines[i + 1]):
                    logger.info(f"Found duplicate decorator at line {i+1} in {file_path}")
                    cleaned_lines.append(line)
                    i += 2  # Skip the next line (duplicate decorator)
                    modified = True
                    continue
            
            cleaned_lines.append(line)
            i += 1
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned_lines)
            logger.info(f"Cleaned {file_path}")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main entry point."""
    # Process a specific file first (if it exists)
    target_file = 'cogs/server_commands_refactored.py'
    if os.path.exists(target_file):
        logger.info(f"Processing target file: {target_file}")
        if clean_duplicate_decorators(target_file):
            logger.info(f"Successfully cleaned target file: {target_file}")
    
    # Process all other files
    directory = 'cogs'
    files = find_python_files(directory)
    cleaned_count = 0
    
    for file_path in files:
        # Skip the file we already processed
        if file_path == target_file:
            continue
            
        if clean_duplicate_decorators(file_path):
            cleaned_count += 1
    
    logger.info(f"Cleaned {cleaned_count} additional files")
    return 0

if __name__ == '__main__':
    sys.exit(main())