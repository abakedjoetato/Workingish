"""
Command helper utility for displaying commands in a paginated, user-friendly format.
"""

import discord
from typing import List, Dict, Any, Optional, Union
import logging

logger = logging.getLogger('deadside_bot')

# Command categories with emojis for titles only
CATEGORIES = {
    "server": {
        "emoji": "🖥️",
        "name": "SERVER MANAGEMENT",
        "description": "Commands for managing game server connections and settings"
    },
    "stats": {
        "emoji": "📊",
        "name": "STATISTICS",
        "description": "Player and server statistics tracking commands"
    },
    "faction": {
        "emoji": "⚔️",
        "name": "FACTION",
        "description": "Commands for creating and managing player factions"
    },
    "killfeed": {
        "emoji": "💀",
        "name": "KILLFEED",
        "description": "Killfeed notification commands and settings"
    },
    "connections": {
        "emoji": "🔌",
        "name": "CONNECTIONS",
        "description": "Player connection tracking and notifications"
    },
    "mission": {
        "emoji": "🎯",
        "name": "MISSIONS",
        "description": "Mission alert commands and tracking"
    },
    "admin": {
        "emoji": "⚙️",
        "name": "ADMIN",
        "description": "Administrative commands for bot management"
    },
    "utility": {
        "emoji": "🛠️",
        "name": "UTILITY",
        "description": "General utility commands"
    }
}

# Define colors for different embed types - emerald-themed
COLORS = {
    "default": 0x50C878,  # Emerald green
    "error": 0xFF5555,     # Soft red for errors
    "success": 0x55FF55,   # Light green for success
    "neutral": 0x555555,   # Grey for neutral information
    "premium": 0xFFD700,   # Gold for premium features
}

class CommandsView(discord.ui.View):
    """Interactive view for browsing commands with pagination."""
    
    def __init__(
        self, 
        command_data: Dict[str, List[Dict[str, Any]]], 
        author_id: int,
        timeout: int = 180
    ):
        super().__init__(timeout=timeout)
        self.command_data = command_data
        self.author_id = author_id
        self.current_category = list(command_data.keys())[0]
        self.current_page = 1
        self.pages_per_category = {}
        
        # Calculate pages for each category (5 commands per page)
        for category, commands in command_data.items():
            self.pages_per_category[category] = max(1, (len(commands) + 4) // 5)
        
        # Set up buttons when view is initialized
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current page and category."""
        # Clear existing items
        self.clear_items()
        
        # Category selection dropdown
        self.add_item(self.get_category_select())
        
        # Add navigation buttons
        self.add_item(self.get_prev_button())
        self.add_item(self.get_page_counter())
        self.add_item(self.get_next_button())
    
    def get_category_select(self):
        """Create the category selection dropdown."""
        select = discord.ui.Select(
            placeholder="Select Command Category",
            custom_id="category_select"
        )
        
        for key, data in CATEGORIES.items():
            if key in self.command_data:
                select.add_option(
                    label=data["name"],
                    value=key,
                    description=data["description"],
                    emoji=data["emoji"],
                    default=(key == self.current_category)
                )
        
        async def category_callback(interaction: discord.Interaction):
            # Verify this is the original author
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "You cannot control someone else's command menu.", 
                    ephemeral=True
                )
                return
                
            self.current_category = select.values[0]
            self.current_page = 1
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.get_current_embed(),
                view=self
            )
        
        select.callback = category_callback
        return select
    
    def get_prev_button(self):
        """Create the previous page button."""
        button = discord.ui.Button(
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_page",
            disabled=(self.current_page == 1)
        )
        
        async def prev_callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "You cannot control someone else's command menu.", 
                    ephemeral=True
                )
                return
                
            self.current_page = max(1, self.current_page - 1)
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.get_current_embed(),
                view=self
            )
        
        button.callback = prev_callback
        return button
    
    def get_page_counter(self):
        """Create the page counter button (non-interactive)."""
        max_pages = self.pages_per_category.get(self.current_category, 1)
        return discord.ui.Button(
            label=f"Page {self.current_page}/{max_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id="page_counter",
            disabled=True
        )
    
    def get_next_button(self):
        """Create the next page button."""
        max_pages = self.pages_per_category.get(self.current_category, 1)
        button = discord.ui.Button(
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="next_page",
            disabled=(self.current_page >= max_pages)
        )
        
        async def next_callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "You cannot control someone else's command menu.", 
                    ephemeral=True
                )
                return
                
            max_pages = self.pages_per_category.get(self.current_category, 1)
            self.current_page = min(max_pages, self.current_page + 1)
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.get_current_embed(),
                view=self
            )
        
        button.callback = next_callback
        return button
    
    def get_current_embed(self) -> discord.Embed:
        """Generate the embed for the current page and category."""
        category_info = CATEGORIES.get(self.current_category, {
            "emoji": "📖",
            "name": "COMMANDS",
            "description": "Available commands"
        })
        
        # Create base embed with emerald theme
        embed = discord.Embed(
            title=f"{category_info['emoji']} {category_info['name']}",
            description=category_info['description'],
            color=COLORS["default"]
        )
        
        # Get commands for current category
        commands = self.command_data.get(self.current_category, [])
        
        # Calculate start and end indices for current page
        start_idx = (self.current_page - 1) * 5
        end_idx = min(start_idx + 5, len(commands))
        
        # No commands in this category
        if not commands:
            embed.add_field(
                name="No Commands Available",
                value="There are no commands in this category.",
                inline=False
            )
            return embed
        
        # Add command fields for current page
        for cmd in commands[start_idx:end_idx]:
            name = cmd.get("name", "Unknown Command")
            description = cmd.get("description", "No description available")
            usage = cmd.get("usage", "")
            examples = cmd.get("examples", [])
            required_permissions = cmd.get("required_permissions", [])
            premium_tier = cmd.get("premium_tier", None)
            
            # Format the value with usage, examples, and requirements
            value = f"{description}\n\n"
            
            if usage:
                value += f"**Usage:** `{usage}`\n"
            
            if examples:
                examples_text = "\n".join([f"• `{ex}`" for ex in examples[:2]])
                value += f"**Examples:**\n{examples_text}\n"
            
            if required_permissions:
                perms = ", ".join(required_permissions)
                value += f"**Required Permissions:** {perms}\n"
            
            if premium_tier:
                value += f"**Premium Tier:** {premium_tier.capitalize()}\n"
            
            embed.add_field(
                name=name,
                value=value,
                inline=False
            )
        
        # Add footer with navigation help
        embed.set_footer(
            text=f"Page {self.current_page}/{self.pages_per_category.get(self.current_category, 1)} • Use the dropdown to switch categories"
        )
        
        return embed

async def get_all_commands(bot) -> Dict[str, List[Dict[str, Any]]]:
    """
    Gather all commands from the bot and format them for display.
    
    Returns:
        Dict mapping category names to lists of command dictionaries.
    """
    result = {}
    
    # Make sure all categories are represented even if empty
    for category in CATEGORIES:
        result[category] = []
    
    # Add manually defined category commands for demonstration
    # while waiting for Discord to register the actual commands
    
    # SERVER COMMANDS
    result["server"].extend([
        {
            "name": "/server add",
            "description": "Add a new game server to track",
            "usage": "/server add <name> <host> <port> [username] [password]",
            "examples": ["/server add \"My Server\" 192.168.1.100 22 admin"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        },
        {
            "name": "/server list",
            "description": "List all configured game servers",
            "usage": "/server list",
            "examples": ["/server list"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/server status",
            "description": "Check the status of game servers",
            "usage": "/server status [name]",
            "examples": ["/server status", "/server status \"My Server\""],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/server remove",
            "description": "Remove a game server from tracking",
            "usage": "/server remove <name>",
            "examples": ["/server remove \"My Server\""],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        }
    ])
    
    # STATS COMMANDS
    result["stats"].extend([
        {
            "name": "/stats player",
            "description": "View detailed player statistics",
            "usage": "/stats player <name>",
            "examples": ["/stats player JohnDoe"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/stats leaderboard",
            "description": "View the server kill leaderboard",
            "usage": "/stats leaderboard [stat_type] [limit]",
            "examples": ["/stats leaderboard kills 10"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/stats me",
            "description": "View your own player statistics",
            "usage": "/stats me",
            "examples": ["/stats me"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/stats link",
            "description": "Link your Discord account to a game character",
            "usage": "/stats link <player_name>",
            "examples": ["/stats link JohnDoe"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/stats unlink",
            "description": "Unlink a character from your Discord account",
            "usage": "/stats unlink [player_name]",
            "examples": ["/stats unlink", "/stats unlink JohnDoe"],
            "required_permissions": [],
            "premium_tier": None
        },
        {
            "name": "/stats weapon",
            "description": "View statistics for a specific weapon",
            "usage": "/stats weapon <name>",
            "examples": ["/stats weapon M4A1"],
            "required_permissions": [],
            "premium_tier": "warlord"
        }
    ])
    
    # KILLFEED COMMANDS
    result["killfeed"].extend([
        {
            "name": "/killfeed channel",
            "description": "Set channel for killfeed notifications",
            "usage": "/killfeed channel [#channel]",
            "examples": ["/killfeed channel #killfeed"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        },
        {
            "name": "/killfeed disable",
            "description": "Disable killfeed notifications",
            "usage": "/killfeed disable",
            "examples": ["/killfeed disable"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        }
    ])
    
    # CONNECTION COMMANDS
    result["connections"].extend([
        {
            "name": "/connections channel",
            "description": "Set channel for connection notifications",
            "usage": "/connections channel [#channel]",
            "examples": ["/connections channel #connections"],
            "required_permissions": ["Administrator"],
            "premium_tier": "warlord"
        },
        {
            "name": "/connections disable",
            "description": "Disable connection notifications",
            "usage": "/connections disable",
            "examples": ["/connections disable"],
            "required_permissions": ["Administrator"], 
            "premium_tier": "warlord"
        },
        {
            "name": "/connections list",
            "description": "List recent player connections",
            "usage": "/connections list [server_name] [limit]",
            "examples": ["/connections list \"My Server\" 10"],
            "required_permissions": [],
            "premium_tier": "warlord"
        }
    ])
    
    # MISSION COMMANDS
    result["mission"].extend([
        {
            "name": "/mission channel",
            "description": "Set channel for mission notifications",
            "usage": "/mission channel [#channel]",
            "examples": ["/mission channel #missions"],
            "required_permissions": ["Administrator"],
            "premium_tier": "warlord"
        },
        {
            "name": "/mission disable",
            "description": "Disable mission notifications",
            "usage": "/mission disable",
            "examples": ["/mission disable"],
            "required_permissions": ["Administrator"],
            "premium_tier": "warlord"
        }
    ])
    
    # FACTION COMMANDS
    result["faction"].extend([
        {
            "name": "/faction create",
            "description": "Create a new faction",
            "usage": "/faction create <name> <abbreviation>",
            "examples": ["/faction create \"Black Watch\" BW"],
            "required_permissions": [],
            "premium_tier": "warlord"
        },
        {
            "name": "/faction info",
            "description": "View information about a faction",
            "usage": "/faction info [name]",
            "examples": ["/faction info", "/faction info \"Black Watch\""],
            "required_permissions": [],
            "premium_tier": "warlord"
        },
        {
            "name": "/faction list",
            "description": "List all factions in the guild",
            "usage": "/faction list",
            "examples": ["/faction list"],
            "required_permissions": [],
            "premium_tier": "warlord"
        },
        {
            "name": "/faction invite",
            "description": "Invite a member to your faction",
            "usage": "/faction invite @member",
            "examples": ["/faction invite @User"],
            "required_permissions": [],
            "premium_tier": "warlord"
        },
        {
            "name": "/faction leave",
            "description": "Leave your current faction",
            "usage": "/faction leave",
            "examples": ["/faction leave"],
            "required_permissions": [],
            "premium_tier": "warlord"
        },
        {
            "name": "/faction stats",
            "description": "View combined statistics for all members of a faction",
            "usage": "/faction stats [name]",
            "examples": ["/faction stats", "/faction stats \"Black Watch\""],
            "required_permissions": [],
            "premium_tier": "warlord"
        }
    ])
    
    # ADMIN COMMANDS
    result["admin"].extend([
        {
            "name": "/admin premium",
            "description": "View or set premium tier for a guild",
            "usage": "/admin premium [guild_id] [tier]",
            "examples": ["/admin premium", "/admin premium 123456789 warlord"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        },
        {
            "name": "/admin features",
            "description": "Display available features by premium tier",
            "usage": "/admin features",
            "examples": ["/admin features"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        },
        {
            "name": "/admin link",
            "description": "Link a Discord member to a game player",
            "usage": "/admin link @member <player_name>",
            "examples": ["/admin link @User PlayerName"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        },
        {
            "name": "/admin unlink",
            "description": "Unlink a Discord member from a game player",
            "usage": "/admin unlink @member [player_name]",
            "examples": ["/admin unlink @User", "/admin unlink @User PlayerName"],
            "required_permissions": ["Administrator"],
            "premium_tier": None
        }
    ])
    
    # UTILITY COMMANDS
    # Add any actual utility commands from the bot
    for cmd in bot.application_commands:
        try:
            # Get basic command info
            cmd_name = cmd.name
            cmd_description = cmd.description or "No description available"
            
            # Standalone commands like ping, commands go to utility
            category = "utility"
            
            # Skip command groups that we've manually added above
            if cmd_name in ["server", "connections", "killfeed", "mission", "faction", "admin"]:
                continue
                
            # Get usage and examples
            usage = get_command_usage(cmd_name, cmd)
            examples = get_command_examples(cmd_name, cmd)
            
            # Determine permissions and premium tier requirements
            required_permissions = get_required_permissions(cmd)
            premium_tier = get_premium_tier_requirement(cmd)
            
            # Add the command to the utility category
            result[category].append({
                "name": f"/{cmd_name}",
                "description": cmd_description,
                "usage": usage,
                "examples": examples,
                "required_permissions": required_permissions,
                "premium_tier": premium_tier
            })
        except Exception as e:
            logger.error(f"Error processing command {cmd.name}: {e}")
            continue
            
    # Remove empty categories
    result = {k: v for k, v in result.items() if v}
    
    # Sort commands within each category alphabetically
    for category in result:
        result[category] = sorted(result[category], key=lambda x: x["name"])
    
    return result

def get_command_category(cmd) -> str:
    """Determine the category for a command based on its name or properties."""
    cmd_name = cmd.name.lower()
    
    # Direct category matches
    if cmd_name in CATEGORIES:
        return cmd_name
    
    # Check for prefix matches
    for category in CATEGORIES:
        if cmd_name.startswith(f"{category}_"):
            return category
    
    # Default to utility for standalone utility commands
    if cmd_name in ["ping", "commands"]:
        return "utility"
    
    # If we can't determine the category, use the first part of the name
    # or default to "utility"
    parts = cmd_name.split('_')
    if parts[0] in CATEGORIES:
        return parts[0]
    
    return "utility"

def get_command_usage(group_name: str, cmd, is_subcommand: bool = False) -> str:
    """Generate usage information for a command."""
    if is_subcommand:
        usage = f"/{group_name} {cmd.name}"
    else:
        usage = f"/{cmd.name}"
    
    # Add parameters if available
    if hasattr(cmd, 'options') and cmd.options:
        for opt in cmd.options:
            if opt.required:
                usage += f" <{opt.name}>"
            else:
                usage += f" [{opt.name}]"
    
    return usage

def get_command_examples(group_name: str, cmd, is_subcommand: bool = False) -> List[str]:
    """Generate example usages for a command."""
    examples = []
    
    # Base command name
    if is_subcommand:
        base_cmd = f"/{group_name} {cmd.name}"
    else:
        base_cmd = f"/{cmd.name}"
    
    # Add a basic example
    examples.append(base_cmd)
    
    # If there are parameters, add an example with them
    if hasattr(cmd, 'options') and cmd.options:
        example_with_params = base_cmd
        for opt in cmd.options:
            if opt.required:
                # Use parameter name as placeholder
                example_with_params += f" {opt.name}"
        
        # Only add if different from the base command
        if example_with_params != base_cmd:
            examples.append(example_with_params)
    
    return examples

def get_required_permissions(cmd) -> List[str]:
    """Determine required permissions for a command."""
    permissions = []
    
    # Check if this command is admin-only
    if hasattr(cmd, 'parent') and cmd.parent and cmd.parent.name == "admin":
        permissions.append("Administrator")
    
    # Check for specific permission requirements based on command name
    cmd_name = cmd.name.lower()
    if any(keyword in cmd_name for keyword in ["delete", "remove", "purge"]):
        permissions.append("Manage Messages")
    elif any(keyword in cmd_name for keyword in ["ban", "kick"]):
        permissions.append("Moderate Members")
    
    return permissions

def get_premium_tier_requirement(cmd) -> Optional[str]:
    """Determine if a command requires a premium tier."""
    # Example logic - this should be replaced with actual premium tier checking
    if hasattr(cmd, 'parent') and cmd.parent:
        parent_name = cmd.parent.name.lower()
        
        # Faction commands require Warlord tier
        if parent_name == "faction" and cmd.name.lower() in ["create", "transfer"]:
            return "warlord"
        
        # Connection and killfeed notifications require paid tiers
        if parent_name in ["connections", "killfeed"] and cmd.name.lower() in ["channel"]:
            return "survivor"
    
    # Default to None (no premium requirement)
    return None