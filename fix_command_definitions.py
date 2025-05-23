#!/usr/bin/env python3
"""
Command Definition Fixer

This script permanently fixes all command definitions in cog files by adding
missing integration_types and contexts attributes. It edits the source files directly
rather than applying runtime fixes.

This is a one-time fix to eliminate the need for the runtime command_fix utility.
"""

import os
import re
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('command_definition_fixer')

# Regular expressions to find SlashCommandGroup definitions
SLASH_CMD_GROUP_REGEX = r'(\w+)\s*=\s*(?:discord\.)?SlashCommandGroup\s*\(\s*[\'"](\w+)[\'"].*?\)'
ATTRS_REGEX = r'SlashCommandGroup\s*\(([^)]*)\)'

def fix_file(file_path):
    """Fix command definitions in a single file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    groups_fixed = 0
    
    # Find all SlashCommandGroup definitions
    group_matches = re.finditer(SLASH_CMD_GROUP_REGEX, content, re.DOTALL)
    
    for match in group_matches:
        var_name = match.group(1)
        cmd_name = match.group(2)
        
        # Get the full argument string
        attrs_match = re.search(ATTRS_REGEX, content[match.start():match.start() + 500], re.DOTALL)
        if not attrs_match:
            continue
            
        attr_str = attrs_match.group(1)
        
        # Check if integration_types is missing
        if 'integration_types' not in attr_str:
            # Fix the integration_types attribute
            end_pos = match.start() + attrs_match.end() - 1
            fixed_attrs = attr_str.rstrip()
            if fixed_attrs.endswith(','):
                fixed_attrs += '\n        integration_types=[discord.IntegrationType.guild_install],'
            else:
                fixed_attrs += ',\n        integration_types=[discord.IntegrationType.guild_install],'
                
            # Replace the attribute string
            content = content[:match.start() + attrs_match.start(1)] + fixed_attrs + content[match.start() + attrs_match.end(1):]
            groups_fixed += 1
            logger.info(f"Fixed integration_types for {cmd_name} in {file_path}")
        
        # Check if contexts is missing (after potentially updating integration_types)
        if 'contexts' not in attr_str and 'contexts' not in content:
            # Re-get the match since content may have changed
            attrs_match = re.search(ATTRS_REGEX, content[match.start():match.start() + 600], re.DOTALL)
            if not attrs_match:
                continue
                
            attr_str = attrs_match.group(1)
            end_pos = match.start() + attrs_match.end() - 1
            fixed_attrs = attr_str.rstrip()
            if fixed_attrs.endswith(','):
                fixed_attrs += '\n        contexts=[discord.InteractionContextType.guild],'
            else:
                fixed_attrs += ',\n        contexts=[discord.InteractionContextType.guild],'
                
            # Replace the attribute string
            content = content[:match.start() + attrs_match.start(1)] + fixed_attrs + content[match.start() + attrs_match.end(1):]
            groups_fixed += 1
            logger.info(f"Fixed contexts for {cmd_name} in {file_path}")
    
    # Only write back if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Updated {file_path} with {groups_fixed} fixes")
    
    return groups_fixed

def fix_subcommand_definitions(file_path):
    """Fix subcommand definitions that might be missing proper attributes"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    cmds_fixed = 0
    
    # Look for subcommand or slash command decorators without contexts
    sub_cmd_pattern = r'@(\w+)\.(?:sub)?command\s*\(([^)]*)\)'
    matches = re.finditer(sub_cmd_pattern, content, re.DOTALL)
    
    for match in matches:
        group_name = match.group(1)
        attrs = match.group(2)
        
        # Fix missing contexts
        if 'contexts=' not in attrs:
            fixed_attrs = attrs.rstrip()
            if fixed_attrs.endswith(','):
                fixed_attrs += ' contexts=[discord.InteractionContextType.guild],'
            else:
                fixed_attrs += ', contexts=[discord.InteractionContextType.guild],'
            
            # Replace the attribute string
            new_decorator = f'@{group_name}.command({fixed_attrs})'
            content = content[:match.start()] + new_decorator + content[match.end():]
            cmds_fixed += 1
            logger.info(f"Fixed contexts for subcommand in {file_path}")
        
        # Now check if integration_types is missing (after potentially updating contexts)
        if 'integration_types=' not in attrs and 'integration_types=' not in content[match.start():match.start()+500]:
            # Re-get the match since content may have changed
            new_match = re.search(r'@' + re.escape(group_name) + r'\.(?:sub)?command\s*\(([^)]*)\)', 
                                content[match.start():match.start()+500], re.DOTALL)
            if not new_match:
                continue
                
            new_attrs = new_match.group(1)
            fixed_attrs = new_attrs.rstrip()
            if fixed_attrs.endswith(','):
                fixed_attrs += ' integration_types=[discord.IntegrationType.guild_install],'
            else:
                fixed_attrs += ', integration_types=[discord.IntegrationType.guild_install],'
            
            # Replace the attribute string
            new_decorator = f'@{group_name}.command({fixed_attrs})'
            content = content[:match.start()] + new_decorator + content[match.start()+new_match.start():]
            cmds_fixed += 1
            logger.info(f"Fixed integration_types for subcommand in {file_path}")
    
    # Only write back if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Updated {file_path} with {cmds_fixed} subcommand fixes")
    
    return cmds_fixed

def fix_standalone_commands(file_path):
    """Fix standalone slash commands (not part of a group)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    cmds_fixed = 0
    
    # Look for @commands.slash_command or @bot.slash_command decorators
    cmd_pattern = r'@(?:commands|bot)\.slash_command\s*\(([^)]*)\)'
    matches = re.finditer(cmd_pattern, content, re.DOTALL)
    
    for match in matches:
        attrs = match.group(1)
        
        # Fix missing integration_types
        if 'integration_types=' not in attrs:
            fixed_attrs = attrs.rstrip()
            if fixed_attrs.endswith(','):
                fixed_attrs += ' integration_types=[discord.IntegrationType.guild_install],'
            else:
                fixed_attrs += ', integration_types=[discord.IntegrationType.guild_install],'
            
            # Replace the attribute string
            content = content[:match.start()] + '@commands.slash_command(' + fixed_attrs + ')' + content[match.end():]
            cmds_fixed += 1
            logger.info(f"Fixed integration_types for slash_command in {file_path}")
        
        # Re-get all matches since content may have changed
        matches = re.finditer(cmd_pattern, content, re.DOTALL)
        for m in matches:
            if 'contexts=' not in m.group(1):
                attrs = m.group(1)
                fixed_attrs = attrs.rstrip()
                if fixed_attrs.endswith(','):
                    fixed_attrs += ' contexts=[discord.InteractionContextType.guild],'
                else:
                    fixed_attrs += ', contexts=[discord.InteractionContextType.guild],'
                
                # Replace the attribute string
                content = content[:m.start()] + '@commands.slash_command(' + fixed_attrs + ')' + content[m.end():]
                cmds_fixed += 1
                logger.info(f"Fixed contexts for slash_command in {file_path}")
                break
    
    # Only write back if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Updated {file_path} with {cmds_fixed} standalone command fixes")
    
    return cmds_fixed

def main():
    """Main entry point"""
    cogs_dir = './cogs'
    main_files = ['main.py', 'fixed_main.py']
    total_fixes = 0
    
    # Process all Python files in the cogs directory
    for root, _, files in os.walk(cogs_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                file_path = os.path.join(root, file)
                group_fixes = fix_file(file_path)
                subcommand_fixes = fix_subcommand_definitions(file_path)
                standalone_fixes = fix_standalone_commands(file_path)
                total_fixes += group_fixes + subcommand_fixes + standalone_fixes
    
    # Also check main files
    for main_file in main_files:
        if os.path.exists(main_file):
            group_fixes = fix_file(main_file)
            subcommand_fixes = fix_subcommand_definitions(main_file)
            standalone_fixes = fix_standalone_commands(main_file)
            total_fixes += group_fixes + subcommand_fixes + standalone_fixes
    
    logger.info(f"Completed with {total_fixes} total fixes")

if __name__ == '__main__':
    main()