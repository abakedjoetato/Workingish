"""
Embeds Utility

This module provides utility functions for creating and formatting Discord embeds
consistently across the application.
"""

import discord
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

def create_embed(
    title: str,
    description: str,
    color: discord.Color = discord.Color.blurple(),
    timestamp: bool = True,
    footer_text: str = None,
    footer_icon: str = None,
    thumbnail: str = None,
    image: str = None,
    author_name: str = None,
    author_icon: str = None,
    author_url: str = None,
    fields: list = None,
    url: str = None,
) -> discord.Embed:
    """
    Create a Discord embed with consistent styling
    
    Args:
        title: Title of the embed
        description: Description text
        color: Color of the embed
        timestamp: Whether to include current timestamp
        footer_text: Text to display in the footer
        footer_icon: URL for footer icon
        thumbnail: URL for thumbnail image
        image: URL for main image
        author_name: Name to display in author field
        author_icon: URL for author icon
        author_url: URL for author name
        fields: List of field dictionaries with name, value, and inline keys
        url: URL for the embed title
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow() if timestamp else None,
        url=url
    )
    
    # Add footer if provided
    if footer_text:
        embed.set_footer(text=footer_text, icon_url=footer_icon)
        
    # Add thumbnail if provided
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
        
    # Add image if provided
    if image:
        embed.set_image(url=image)
        
    # Add author if provided
    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon, url=author_url)
        
    # Add fields if provided
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", "Field"),
                value=field.get("value", "Value"),
                inline=field.get("inline", False)
            )
            
    return embed

def format_timestamp(dt: datetime, format_type: str = "R") -> str:
    """
    Format a datetime object as a Discord timestamp
    
    Args:
        dt: Datetime object to format
        format_type: Discord timestamp format type:
            't': Short Time (e.g., 9:41 PM)
            'T': Long Time (e.g., 9:41:30 PM)
            'd': Short Date (e.g., 30/06/2021)
            'D': Long Date (e.g., 30 June 2021)
            'f': Short Date/Time (e.g., 30 June 2021 9:41 PM)
            'F': Long Date/Time (e.g., Wednesday, 30 June 2021 9:41 PM)
            'R': Relative Time (e.g., 2 hours ago)
            
    Returns:
        str: Formatted Discord timestamp string
    """
    if not dt:
        return "Unknown"
        
    try:
        unix_timestamp = int(dt.timestamp())
        return f"<t:{unix_timestamp}:{format_type}>"
    except (AttributeError, ValueError, TypeError) as e:
        logger.error(f"Error formatting timestamp: {e}")
        return "Invalid date"
        
def server_info_embed(server_data: Dict[str, Any]) -> discord.Embed:
    """
    Create an embed displaying server information
    
    Args:
        server_data: Dictionary with server information
        
    Returns:
        discord.Embed: Formatted server info embed
    """
    status = server_data.get("status", "Unknown")
    status_emoji = "🟢" if status == "online" else "🔴"
    
    embed = create_embed(
        title=f"{status_emoji} {server_data.get('name', 'Unknown Server')}",
        description=f"Server information for {server_data.get('name', 'Unknown')}",
        color=discord.Color.green() if status == "online" else discord.Color.red()
    )
    
    # Add server details
    embed.add_field(
        name="Status",
        value=f"{status_emoji} {status.capitalize()}",
        inline=True
    )
    
    embed.add_field(
        name="Players",
        value=f"{server_data.get('players', 0)}/{server_data.get('max_players', 0)}",
        inline=True
    )
    
    embed.add_field(
        name="Address",
        value=f"{server_data.get('ip', 'Unknown')}:{server_data.get('port', 'Unknown')}",
        inline=True
    )
    
    # Add additional fields if available
    if server_data.get("map"):
        embed.add_field(
            name="Map",
            value=server_data.get("map"),
            inline=True
        )
        
    if server_data.get("version"):
        embed.add_field(
            name="Version",
            value=server_data.get("version"),
            inline=True
        )
        
    if server_data.get("added_at"):
        embed.add_field(
            name="Added",
            value=format_timestamp(server_data.get("added_at")),
            inline=True
        )
        
    # Add footer with last update time
    embed.set_footer(text=f"Last updated: {format_timestamp(server_data.get('last_updated', datetime.utcnow()))}")
    
    return embed
    
def error_embed(title: str, description: str) -> discord.Embed:
    """Alias for create_error_embed"""
    return create_error_embed(title, description)

def create_error_embed(title: str, description: str) -> discord.Embed:
    """
    Create an error embed with standardized formatting
    
    Args:
        title: Error title
        description: Error description
        
    Returns:
        discord.Embed: Formatted error embed
    """
    return create_embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red()
    )
    
def success_embed(title: str, description: str) -> discord.Embed:
    """Alias for create_success_embed"""
    return create_success_embed(title, description)
    
def create_success_embed(title: str, description: str) -> discord.Embed:
    """
    Create a success embed with standardized formatting
    
    Args:
        title: Success title
        description: Success description
        
    Returns:
        discord.Embed: Formatted success embed
    """
    return create_embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green()
    )
    
def warning_embed(title: str, description: str) -> discord.Embed:
    """
    Create a warning embed with standardized formatting
    
    Args:
        title: Warning title
        description: Warning description
        
    Returns:
        discord.Embed: Formatted warning embed
    """
    return create_embed(
        title=f"⚠️ {title}",
        description=description,
        color=discord.Color.gold()
    )
    
def create_server_embed(server_data: Dict[str, Any]) -> discord.Embed:
    """
    Create an embed for server information (alias for server_info_embed)
    
    Args:
        server_data: Dictionary with server information
        
    Returns:
        discord.Embed: Formatted server info embed
    """
    return server_info_embed(server_data)
    
def create_info_embed(title: str, description: str) -> discord.Embed:
    """
    Create an information embed with standardized formatting
    
    Args:
        title: Info title
        description: Info description
        
    Returns:
        discord.Embed: Formatted info embed
    """
    return create_embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blue()
    )
    
def create_basic_embed(title: str, description: str, color: discord.Color = None) -> discord.Embed:
    """
    Create a basic embed with minimal styling
    
    Args:
        title: Title of the embed
        description: Description text
        color: Color of the embed (optional)
        
    Returns:
        discord.Embed: Simple formatted embed
    """
    if color is None:
        color = discord.Color.blurple()
        
    return create_embed(
        title=title,
        description=description,
        color=color
    )
    
def create_player_embed(player_data: Dict[str, Any], server_name: str = None) -> discord.Embed:
    """
    Create an embed displaying player statistics
    
    Args:
        player_data: Dictionary with player information
        server_name: Optional server name for context
        
    Returns:
        discord.Embed: Formatted player statistics embed
    """
    if not player_data:
        return create_error_embed("Player Not Found", "No player data found")
        
    name = player_data.get("player_name", "Unknown Player")
    player_id = player_data.get("player_id", "Unknown ID")
    
    embed = create_embed(
        title=f"📊 {name}",
        description=f"Statistics for player {name}" + (f" on {server_name}" if server_name else ""),
        color=discord.Color.blue()
    )
    
    # Core player stats
    embed.add_field(
        name="Kill Statistics", 
        value=f"**Kills:** {player_data.get('total_kills', 0)}\n"
              f"**Deaths:** {player_data.get('total_deaths', 0)}\n"
              f"**K/D Ratio:** {round(player_data.get('total_kills', 0) / max(1, player_data.get('total_deaths', 0)), 2)}", 
        inline=True
    )
    
    # Add timestamp data
    first_seen = player_data.get("first_seen")
    last_seen = player_data.get("last_seen")
    
    if first_seen or last_seen:
        times_str = ""
        if first_seen:
            times_str += f"First seen: {format_timestamp(first_seen)}\n"
        if last_seen:
            times_str += f"Last seen: {format_timestamp(last_seen)}"
            
        embed.add_field(name="Activity", value=times_str, inline=True)
    
    # Add faction info if available
    faction_name = player_data.get("faction_name")
    if faction_name:
        embed.add_field(
            name="Faction",
            value=f"**{faction_name}**",
            inline=True
        )
    
    # Add prey/nemesis if available
    nemesis_name = player_data.get("nemesis_name") 
    prey_name = player_data.get("prey_name")
    
    if nemesis_name:
        nemesis_deaths = player_data.get("nemesis_deaths", 0)
        embed.add_field(
            name="😈 Nemesis",
            value=f"**{nemesis_name}** has killed you {nemesis_deaths} times",
            inline=True
        )
        
    if prey_name:
        prey_kills = player_data.get("prey_kills", 0)
        embed.add_field(
            name="🎯 Prey",
            value=f"You've killed **{prey_name}** {prey_kills} times",
            inline=True
        )
    
    # Add ID footer for reference
    embed.set_footer(text=f"Player ID: {player_id}")
    
    return embed
    
def create_leaderboard_embed(
    leaderboard_data: List[Dict[str, Any]], 
    title: str = "Leaderboard",
    description: str = "Top players by kills",
    server_name: str = None
) -> discord.Embed:
    """
    Create an embed displaying a player leaderboard
    
    Args:
        leaderboard_data: List of player entries for the leaderboard
        title: Title for the leaderboard
        description: Description for the leaderboard
        server_name: Optional server name for context
        
    Returns:
        discord.Embed: Formatted leaderboard embed
    """
    if not leaderboard_data:
        return create_error_embed("Leaderboard Error", "No leaderboard data available")
        
    if server_name:
        description += f" on {server_name}"
        
    embed = create_embed(
        title=f"🏆 {title}",
        description=description,
        color=discord.Color.gold()
    )
    
    # Format the leaderboard entries
    leaderboard_text = ""
    for i, player in enumerate(leaderboard_data):
        # Create medal emojis for top 3
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"`{i+1}.`"
            
        name = player.get("player_name", "Unknown")
        kills = player.get("total_kills", 0)
        deaths = player.get("total_deaths", 0)
        kd = round(kills / max(1, deaths), 2)
        
        leaderboard_text += f"{medal} **{name}** - {kills} kills, {deaths} deaths (K/D: {kd})\n"
        
        # Add a separator line after every 5 entries for readability
        if (i + 1) % 5 == 0 and i < len(leaderboard_data) - 1:
            leaderboard_text += "───────────────\n"
            
    embed.add_field(name="Rankings", value=leaderboard_text, inline=False)
    
    # Add timestamp
    embed.set_footer(text=f"Updated {format_timestamp(datetime.utcnow())}")
    
    return embed

def create_faction_embed(faction_data: Dict[str, Any], server_name: str = None) -> discord.Embed:
    """
    Create an embed displaying faction information
    
    Args:
        faction_data: Dictionary with faction information
        server_name: Optional server name for context
        
    Returns:
        discord.Embed: Formatted faction embed
    """
    if not faction_data:
        return create_error_embed("Faction Not Found", "No faction data found")
        
    faction_name = faction_data.get("name", "Unknown Faction")
    faction_id = faction_data.get("_id", "Unknown ID")
    faction_tag = faction_data.get("tag", "")
    description = faction_data.get("description", "No description available.")
    
    # Determine color if available, otherwise use default blue
    color_hex = faction_data.get("color", "#3498db")
    try:
        # Try to parse color as hex
        color_value = int(color_hex.lstrip('#'), 16)
        color = discord.Color(color_value)
    except (ValueError, AttributeError):
        # Default to blue if color is invalid
        color = discord.Color.blue()
    
    embed = create_embed(
        title=f"🏴 {faction_name}" + (f" [{faction_tag}]" if faction_tag else ""),
        description=description + (f"\n\nServer: **{server_name}**" if server_name else ""),
        color=color
    )
    
    # Add statistics
    members_count = len(faction_data.get("members", []))
    embed.add_field(
        name="Members",
        value=str(members_count),
        inline=True
    )
    
    # Add kills/deaths if available
    kills = faction_data.get("total_kills", 0)
    deaths = faction_data.get("total_deaths", 0)
    
    # Calculate K/D ratio if we have data
    if kills > 0 or deaths > 0:
        kd_ratio = round(kills / max(1, deaths), 2)
        embed.add_field(
            name="Statistics",
            value=f"**Kills:** {kills}\n**Deaths:** {deaths}\n**K/D Ratio:** {kd_ratio}",
            inline=True
        )
    
    # Add leader information if available
    leader_id = faction_data.get("leader_id")
    leader_name = faction_data.get("leader_name", "Unknown")
    
    if leader_id or leader_name != "Unknown":
        embed.add_field(
            name="Leader",
            value=leader_name,
            inline=True
        )
        
    # Add member list if available and not too long
    members = faction_data.get("members", [])
    if members and len(members) <= 15:
        members_text = ""
        for i, member in enumerate(members):
            name = member.get("name", "Unknown")
            if i < 14:
                members_text += f"• {name}\n"
            elif i == 14 and len(members) > 15:
                members_text += f"• ... and {len(members) - 14} more"
                break
            else:
                members_text += f"• {name}"
                
        if members_text:
            embed.add_field(
                name="Members List",
                value=members_text,
                inline=False
            )
    
    # Add timestamps if available
    created_at = faction_data.get("created_at")
    if created_at:
        embed.add_field(
            name="Created",
            value=format_timestamp(created_at),
            inline=True
        )
    
    # Add territory information if available
    territories = faction_data.get("territories", [])
    if territories:
        territories_text = ""
        for territory in territories[:5]:  # Limit to 5 territories to keep embed clean
            territories_text += f"• {territory.get('name', 'Unknown')}\n"
            
        if len(territories) > 5:
            territories_text += f"• ... and {len(territories) - 5} more"
            
        if territories_text:
            embed.add_field(
                name="Territories",
                value=territories_text,
                inline=True
            )
    
    # Add faction ID as footer
    embed.set_footer(text=f"Faction ID: {faction_id}")
    
    return embed

def create_connection_embed(connection_data: Dict[str, Any]) -> discord.Embed:
    """
    Create an embed displaying connection information
    
    Args:
        connection_data: Dictionary with connection information
        
    Returns:
        discord.Embed: Formatted connection embed
    """
    if not connection_data:
        return create_error_embed("Connection Not Found", "No connection data found")
        
    connection_name = connection_data.get("name", "Unknown Connection")
    connection_id = connection_data.get("_id", "Unknown ID")
    status = connection_data.get("status", "Unknown").lower()
    
    # Determine color based on connection status
    if status == "active" or status == "connected":
        color = discord.Color.green()
    elif status == "disabled" or status == "disconnected":
        color = discord.Color.red()
    else:
        color = discord.Color.gold()
        
    # Format status with emoji
    status_emoji = "🟢" if status == "active" or status == "connected" else "🔴"
    status_display = f"{status_emoji} {status.capitalize()}"
    
    embed = create_embed(
        title=f"🔌 {connection_name}",
        description=f"Connection details for {connection_name}",
        color=color
    )
    
    # Add status field
    embed.add_field(
        name="Status",
        value=status_display,
        inline=True
    )
    
    # Add connection type if available
    connection_type = connection_data.get("type")
    if connection_type:
        embed.add_field(
            name="Type",
            value=connection_type,
            inline=True
        )
    
    # Add server information if available
    server_name = connection_data.get("server_name")
    if server_name:
        embed.add_field(
            name="Server",
            value=server_name,
            inline=True
        )
    
    # Add timestamps if available
    created_at = connection_data.get("created_at")
    last_connected = connection_data.get("last_connected")
    
    if created_at or last_connected:
        time_text = ""
        if created_at:
            time_text += f"Created: {format_timestamp(created_at)}\n"
        if last_connected:
            time_text += f"Last Connected: {format_timestamp(last_connected)}"
            
        embed.add_field(
            name="Timeline",
            value=time_text,
            inline=False
        )
    
    # Add additional info if available
    settings = connection_data.get("settings", {})
    if settings:
        settings_text = ""
        for key, value in settings.items():
            if key != "password" and key != "token" and key != "api_key":  # Skip sensitive info
                settings_text += f"**{key.replace('_', ' ').title()}**: {value}\n"
                
        if settings_text:
            embed.add_field(
                name="Settings",
                value=settings_text,
                inline=False
            )
    
    # Add connection ID as footer
    embed.set_footer(text=f"Connection ID: {connection_id}")
    
    return embed

def create_mission_embed(mission_data: Dict[str, Any], server_name: str = None) -> discord.Embed:
    """
    Create an embed displaying mission information
    
    Args:
        mission_data: Dictionary with mission information
        server_name: Optional server name for context
        
    Returns:
        discord.Embed: Formatted mission embed
    """
    if not mission_data:
        return create_error_embed("Mission Not Found", "No mission data found")
        
    mission_name = mission_data.get("name", "Unknown Mission")
    mission_id = mission_data.get("_id", "Unknown ID")
    description = mission_data.get("description", "No description available.")
    status = mission_data.get("status", "Unknown")
    
    # Determine color based on mission status
    if status.lower() == "active":
        color = discord.Color.green()
    elif status.lower() == "completed":
        color = discord.Color.blue()
    elif status.lower() == "failed":
        color = discord.Color.red()
    else:
        color = discord.Color.gold()
        
    # Format status with emoji
    status_emoji = "✅" if status.lower() == "completed" else "❌" if status.lower() == "failed" else "🔄"
    status_display = f"{status_emoji} {status.capitalize()}"
    
    embed = create_embed(
        title=f"📋 {mission_name}",
        description=description + (f"\n\nServer: **{server_name}**" if server_name else ""),
        color=color
    )
    
    # Add status field
    embed.add_field(
        name="Status",
        value=status_display,
        inline=True
    )
    
    # Add objectives if available
    objectives = mission_data.get("objectives", [])
    if objectives:
        objectives_text = ""
        for i, objective in enumerate(objectives):
            obj_status = "✅" if objective.get("completed", False) else "⬜"
            objectives_text += f"{obj_status} {i+1}. {objective.get('description', 'Unknown objective')}\n"
            
        embed.add_field(
            name="Objectives",
            value=objectives_text or "None",
            inline=False
        )
    
    # Add rewards if available
    rewards = mission_data.get("rewards", [])
    if rewards:
        rewards_text = ""
        for reward in rewards:
            rewards_text += f"• {reward.get('name', 'Unknown reward')}: {reward.get('value', 'Unknown value')}\n"
            
        embed.add_field(
            name="Rewards",
            value=rewards_text or "None",
            inline=True
        )
    
    # Add time information
    start_time = mission_data.get("start_time")
    end_time = mission_data.get("end_time")
    
    if start_time or end_time:
        time_text = ""
        if start_time:
            time_text += f"Started: {format_timestamp(start_time)}\n"
        if end_time:
            time_text += f"Ended: {format_timestamp(end_time)}"
            
        embed.add_field(
            name="Timeline",
            value=time_text or "No timeline available",
            inline=True
        )
        
    # Add mission ID as footer
    embed.set_footer(text=f"Mission ID: {mission_id}")
    
    return embed

def create_batch_progress_embed(memory, description=None, color=None):
    """
    Create an embed for batch CSV parser progress
    
    Args:
        memory: Parser memory object with progress information
        description: Optional custom description
        color: Optional custom color (defaults based on status)
        
    Returns:
        discord.Embed: Progress embed
    """
    if not memory:
        return create_error_embed("Parser Status", "No progress data available")
        
    if not color:
        if memory.status == "Complete":
            color = discord.Color.green()
        elif memory.status == "Running":
            color = discord.Color.blue()
        elif "Error" in memory.status:
            color = discord.Color.red()
        else:
            color = discord.Color.gold()
            
    if not description:
        description = f"Current status: **{memory.status}**"
        
    embed = create_embed(
        title="CSV Batch Parser Progress",
        description=description,
        color=color
    )
    
    # Add fields for progress information
    if hasattr(memory, "percent_complete"):
        progress_bar = ""
        
        # Create a simple visual progress bar
        percent = int(memory.percent_complete)
        complete_chars = int(percent / 10)
        progress_bar = "█" * complete_chars + "░" * (10 - complete_chars)
            
        embed.add_field(
            name="Progress",
            value=f"{progress_bar} {percent}%",
            inline=False
        )
        
    if hasattr(memory, "processed_files") and hasattr(memory, "total_files"):
        embed.add_field(
            name="Files",
            value=f"{memory.processed_files}/{memory.total_files}",
            inline=True
        )
        
    if hasattr(memory, "processed_lines") and hasattr(memory, "total_lines"):
        embed.add_field(
            name="Log Lines",
            value=f"{memory.processed_lines:,}/{memory.total_lines:,}",
            inline=True
        )
        
    if hasattr(memory, "current_file") and memory.current_file:
        embed.add_field(
            name="Current File",
            value=f"`{memory.current_file}`",
            inline=True
        )
        
    if hasattr(memory, "start_time") and memory.start_time:
        elapsed = datetime.utcnow() - memory.start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
        
        embed.add_field(
            name="Elapsed Time",
            value=elapsed_str,
            inline=True
        )
        
    if hasattr(memory, "updated_at"):
        embed.set_footer(text=f"Last updated: {format_timestamp(memory.updated_at)}")
        
    return embed