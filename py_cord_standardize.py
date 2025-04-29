"""
Comprehensive standardization script to convert all discord.py usage to py-cord

This script makes a single pass through the entire codebase to:
1. Find all direct discord.py imports and references
2. Update deprecated methods and attributes
3. Ensure consistent usage of py-cord

Run as: python py_cord_standardize.py
"""

import os
import re
import sys
import glob
from pathlib import Path

# Files/directories to exclude from processing
EXCLUDE_PATTERNS = [
    '.git',
    '__pycache__',
    '.venv',
    'venv',
    'env',
    '.env',
    '.cache',
    '.pythonlibs'
]

# Patterns for direct imports to fix
IMPORT_PATTERNS = [
    # Import patterns
    (r'from discord\.commands import (\w+)', r'from discord.commands import \1'),  # Keep as is
    (r'from discord\.ext\.commands import (\w+)', r'from discord.ext.commands import \1'),  # Keep as is
    (r'from discord\.ext import commands, tasks', r'from discord.ext import commands, tasks'),  # Keep as is
    (r'from discord\.ext import commands', r'from discord.ext import commands'),  # Keep as is
    (r'from discord\.ext import tasks', r'from discord.ext import tasks'),  # Keep as is
    (r'from discord\.http import Route', r'from discord.http import Route'),  # Keep as is
    (r'from discord\._http', r'from discord._http'),  # Keep as is but flag for checking
    
    # Fix guild_only deprecation warning by using contexts
    (r'guild_only\s*=\s*True', r'contexts=[discord.InteractionContextType.guild]'),
    (r'contexts=[discord.InteractionContextType.guild]', r'contexts=[discord.InteractionContextType.guild]'),
]

# Python files to check for http route handling
HTTP_ROUTE_FILES = [
    'utils/sync_retry.py',
    'utils/fixed_sync_retry.py',
    'utils/command_test.py',
    'command_registration_fix.py',
    'new_sync_commands.py',
    'new_sync_function.py',
]

def should_exclude(file_path):
    """Check if a file should be excluded from processing"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern in str(file_path):
            return True
    return False

def process_file(file_path):
    """Process a single Python file to update imports and references"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    modified = False
    
    # Apply import pattern replacements
    for pattern, replacement in IMPORT_PATTERNS:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified = True
    
    # Special handling for specific files
    if str(file_path) in HTTP_ROUTE_FILES:
        # Add specific fixes for HTTP route handling
        if "discord.http import Route" in content and "from urllib.parse import quote" not in content:
            content = re.sub(
                r'from discord\.http import Route',
                'from discord.http import Route\nfrom urllib.parse import quote as _uriquote',
                content
            )
            modified = True
            
    # Update guild_only usage in SlashCommandGroup
    if "SlashCommandGroup" in content:
        # Update guild_only parameter in SlashCommandGroup
        content = re.sub(
            r'SlashCommandGroup\(\s*([\'"][\w_]+[\'"])\s*,\s*([\'"][\w\s]+[\'"])\s*,\s*guild_only\s*=\s*True',
            r'SlashCommandGroup(\1, \2, contexts=[discord.InteractionContextType.guild]',
            content
        )
        modified = True
    
    # Only write the file if changes were made
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def process_directory(directory):
    """Process all Python files in a directory recursively"""
    processed_files = 0
    modified_files = 0
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d))]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                processed_files += 1
                
                if process_file(file_path):
                    modified_files += 1
                    print(f"Updated: {file_path}")
    
    return processed_files, modified_files

def main():
    """Main entry point"""
    project_root = os.getcwd()
    print(f"Standardizing project to use py-cord consistently...")
    
    processed_files, modified_files = process_directory(project_root)
    
    print(f"\nStandardization complete.")
    print(f"Processed {processed_files} Python files.")
    print(f"Modified {modified_files} files to standardize py-cord usage.")

if __name__ == "__main__":
    main()