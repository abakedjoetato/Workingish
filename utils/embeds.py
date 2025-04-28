"""
Embed Utilities

This module provides standardized Discord embeds for various command responses.
"""

import discord
from datetime import datetime

# Standard colors for embeds
COLORS = {
    "success": 0x57F287,  # Green
    "error": 0xED4245,    # Red
    "info": 0x3498DB,     # Blue
    "warning": 0xFEE75C,  # Yellow
    "server": 0x9B59B6,   # Purple
    "player": 0x1ABC9C,   # Teal
    "killfeed": 0xE74C3C, # Dark Red
    "mission": 0xF1C40F,  # Gold
    "faction": 0x7289DA,  # Blurple
    "connection": 0x00BFFF # Sky Blue
}

EMOJIS = {
    "success": "✅",
    "error": "❌",
    "info": "ℹ️",
    "warning": "⚠️",
    "add": "➕",
    "remove": "➖",
    "stats": "📊",
    "player": "👤",
    "server": "🖥️",
    "mission": "🎯",
    "clock": "⏱️",
    "location": "📍",
    "kill": "☠️",
    "death": "💀",
    "online": "🟢",
    "offline": "🔴",
    "faction": "👥",
    "crown": "👑",
    "tier": "🏆",
    "connection": "🔗",
    "money": "💰",
    "xp": "📈"
}

def create_basic_embed(title, description=None, color="info", timestamp=True):
    """
    Create a basic embed with standardized formatting
    
    Args:
        title: Embed title
        description: Optional embed description
        color: Color of the embed (success, error, info, warning, etc.)
        timestamp: Whether to include a timestamp
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS.get(color, COLORS["info"])
    )
    
    if timestamp:
        embed.timestamp = datetime.utcnow()
        
    return embed

def create_server_embed(server_data, status=None):
    """
    Create an embed for server information
    
    Args:
        server_data: Server data from database
        status: Optional server status from query
        
    Returns:
        discord.Embed: Formatted server embed
    """
    server_name = server_data.get("name", "Unknown Server")
    embed = create_basic_embed(
        f"{EMOJIS['server']} {server_name}",
        color="server"
    )
    
    # Add server details
    host = server_data.get("host", "Unknown")
    port = server_data.get("port", "Unknown")
    embed.add_field(
        name="Connection Details",
        value=f"Host: `{host}`\nPort: `{port}`",
        inline=True
    )
    
    # Add status information if available
    if status:
        online = status.get("online", False)
        status_emoji = EMOJIS["online"] if online else EMOJIS["offline"]
        status_text = "Online" if online else "Offline"
        
        if online:
            # Add player count if available
            players = status.get("players", 0)
            max_players = status.get("maxplayers", 0)
            embed.add_field(
                name=f"{status_emoji} Status",
                value=f"{status_text}\nPlayers: {players}/{max_players}",
                inline=True
            )
            
            # Add map if available
            if "map" in status and status["map"] != "Unknown":
                embed.add_field(
                    name=f"{EMOJIS['location']} Map",
                    value=status["map"],
                    inline=True
                )
        else:
            # Just show offline status with any error
            error_msg = status.get("error", "Server not responding")
            embed.add_field(
                name=f"{status_emoji} Status",
                value=f"{status_text}\n{error_msg}",
                inline=True
            )
    
    # Add footer with last query time if available
    if status and "query_time" in status:
        try:
            # Format the timestamp nicely
            query_time = datetime.fromisoformat(status["query_time"])
            time_str = discord.utils.format_dt(query_time, style="R")
            embed.set_footer(text=f"Last updated: {time_str}")
        except:
            # Fallback to raw timestamp if parsing fails
            embed.set_footer(text=f"Last updated: {status['query_time']}")
    
    return embed

def create_player_embed(player_data, server_name=None):
    """
    Create an embed for player statistics
    
    Args:
        player_data: Player statistics data
        server_name: Optional server name
        
    Returns:
        discord.Embed: Formatted player statistics embed
    """
    player_name = player_data.get("name", "Unknown Player")
    embed = create_basic_embed(
        f"{EMOJIS['player']} {player_name}",
        color="player"
    )
    
    if server_name:
        embed.description = f"Stats on server: **{server_name}**"
    
    # Main stats section
    kills = player_data.get("kills", 0)
    deaths = player_data.get("deaths", 0)
    kd_ratio = kills / deaths if deaths > 0 else kills
    
    embed.add_field(
        name=f"{EMOJIS['kill']} Kills",
        value=f"`{kills}`",
        inline=True
    )
    
    embed.add_field(
        name=f"{EMOJIS['death']} Deaths",
        value=f"`{deaths}`",
        inline=True
    )
    
    embed.add_field(
        name="K/D Ratio",
        value=f"`{kd_ratio:.2f}`",
        inline=True
    )
    
    # Additional stats if available
    if "playtime" in player_data:
        hours = player_data["playtime"] / 60.0
        embed.add_field(
            name=f"{EMOJIS['clock']} Playtime",
            value=f"`{hours:.1f}` hours",
            inline=True
        )
    
    if "last_seen" in player_data:
        try:
            last_seen = datetime.fromisoformat(player_data["last_seen"])
            time_str = discord.utils.format_dt(last_seen, style="R")
            embed.add_field(
                name="Last Seen",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Last Seen",
                value=str(player_data["last_seen"]),
                inline=True
            )
    
    # Faction info if available
    if "faction" in player_data and player_data["faction"]:
        faction_name = player_data["faction"].get("name", "Unknown Faction")
        faction_role = player_data.get("faction_role", "Member")
        
        embed.add_field(
            name=f"{EMOJIS['faction']} Faction",
            value=f"{faction_name} ({faction_role})",
            inline=True
        )
    
    # Nemesis/Prey information if available
    rivals = player_data.get("rivals", {})
    if rivals:
        nemesis_name = rivals.get("nemesis", {}).get("name", None)
        nemesis_kills = rivals.get("nemesis", {}).get("kills", 0)
        
        prey_name = rivals.get("prey", {}).get("name", None)
        prey_kills = rivals.get("prey", {}).get("kills", 0)
        
        if nemesis_name:
            embed.add_field(
                name="Nemesis",
                value=f"{nemesis_name} ({nemesis_kills} kills)",
                inline=True
            )
            
        if prey_name:
            embed.add_field(
                name="Prey",
                value=f"{prey_name} ({prey_kills} kills)",
                inline=True
            )
    
    # Add linked accounts if any
    linked = player_data.get("linked_accounts", [])
    if linked:
        linked_names = ", ".join([acc.get("name", "Unknown") for acc in linked])
        embed.add_field(
            name="Linked Accounts",
            value=linked_names,
            inline=False
        )
    
    return embed

def create_killfeed_embed(kill_data, server_name=None):
    """
    Create an embed for killfeed entries
    
    Args:
        kill_data: Kill event data
        server_name: Optional server name
        
    Returns:
        discord.Embed: Formatted killfeed embed
    """
    killer_name = kill_data.get("killer", {}).get("name", "Unknown")
    victim_name = kill_data.get("victim", {}).get("name", "Unknown")
    
    # Basic embed setup
    embed = create_basic_embed(
        f"{EMOJIS['kill']} Killfeed",
        description=f"**{killer_name}** killed **{victim_name}**",
        color="killfeed"
    )
    
    # Add server name if provided
    if server_name:
        embed.description += f"\nServer: **{server_name}**"
    
    # Add weapon if available
    weapon = kill_data.get("weapon", "Unknown")
    if weapon and weapon != "Unknown":
        embed.add_field(
            name="Weapon",
            value=weapon,
            inline=True
        )
    
    # Add distance if available
    distance = kill_data.get("distance", None)
    if distance:
        embed.add_field(
            name="Distance",
            value=f"{distance}m",
            inline=True
        )
    
    # Add time if available
    if "timestamp" in kill_data:
        try:
            kill_time = datetime.fromisoformat(kill_data["timestamp"])
            time_str = discord.utils.format_dt(kill_time, style="R")
            embed.add_field(
                name="Time",
                value=time_str,
                inline=True
            )
        except:
            # Fallback to raw timestamp
            embed.add_field(
                name="Time",
                value=str(kill_data["timestamp"]),
                inline=True
            )
    
    # Add special flags if available (headshot, etc.)
    flags = []
    if kill_data.get("headshot", False):
        flags.append("Headshot")
    if kill_data.get("backstab", False):
        flags.append("Backstab")
        
    if flags:
        embed.add_field(
            name="Special",
            value=", ".join(flags),
            inline=True
        )
    
    return embed

def create_mission_embed(mission_data, server_name=None):
    """
    Create an embed for mission information
    
    Args:
        mission_data: Mission data
        server_name: Optional server name
        
    Returns:
        discord.Embed: Formatted mission embed
    """
    mission_type = mission_data.get("type", "Unknown Mission")
    title = f"{EMOJIS['mission']} {mission_type}"
    
    # Add status to title if available
    status = mission_data.get("status", "Active")
    if status.lower() == "completed":
        title += " (Completed)"
    elif status.lower() == "failed":
        title += " (Failed)"
    
    embed = create_basic_embed(
        title,
        color="mission"
    )
    
    # Add server name if provided
    if server_name:
        embed.description = f"Server: **{server_name}**"
    
    # Add details if available
    if "location" in mission_data:
        embed.add_field(
            name=f"{EMOJIS['location']} Location",
            value=mission_data["location"],
            inline=True
        )
    
    if "difficulty" in mission_data:
        embed.add_field(
            name="Difficulty",
            value=mission_data["difficulty"],
            inline=True
        )
    
    if "reward" in mission_data:
        embed.add_field(
            name=f"{EMOJIS['money']} Reward",
            value=mission_data["reward"],
            inline=True
        )
    
    # Add timing information
    if "start_time" in mission_data:
        try:
            start_time = datetime.fromisoformat(mission_data["start_time"])
            time_str = discord.utils.format_dt(start_time, style="R")
            embed.add_field(
                name="Started",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Started",
                value=str(mission_data["start_time"]),
                inline=True
            )
    
    if status.lower() != "active" and "end_time" in mission_data:
        try:
            end_time = datetime.fromisoformat(mission_data["end_time"])
            time_str = discord.utils.format_dt(end_time, style="R")
            embed.add_field(
                name="Ended",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Ended",
                value=str(mission_data["end_time"]),
                inline=True
            )
    
    # Add participants if available
    if "participants" in mission_data and mission_data["participants"]:
        participants = mission_data["participants"]
        if isinstance(participants, list) and len(participants) > 0:
            names = []
            for p in participants[:5]:  # Limit to 5 names
                if isinstance(p, dict) and "name" in p:
                    names.append(p["name"])
                elif isinstance(p, str):
                    names.append(p)
            
            # Add ellipsis if there are more participants
            if len(participants) > 5:
                names.append(f"...and {len(participants) - 5} more")
                
            embed.add_field(
                name="Participants",
                value=", ".join(names),
                inline=False
            )
    
    return embed

def create_faction_embed(faction_data, member_count=None):
    """
    Create an embed for faction information
    
    Args:
        faction_data: Faction data
        member_count: Optional member count
        
    Returns:
        discord.Embed: Formatted faction embed
    """
    faction_name = faction_data.get("name", "Unknown Faction")
    embed = create_basic_embed(
        f"{EMOJIS['faction']} {faction_name}",
        color="faction"
    )
    
    # Add description if available
    if "description" in faction_data and faction_data["description"]:
        embed.description = faction_data["description"]
    
    # Add leader info if available
    if "leader" in faction_data and faction_data["leader"]:
        leader_name = faction_data["leader"].get("name", "Unknown")
        embed.add_field(
            name=f"{EMOJIS['crown']} Leader",
            value=leader_name,
            inline=True
        )
    
    # Add member count if provided
    if member_count is not None:
        embed.add_field(
            name="Members",
            value=str(member_count),
            inline=True
        )
    
    # Add creation date if available
    if "created_at" in faction_data:
        try:
            created_at = datetime.fromisoformat(faction_data["created_at"])
            time_str = discord.utils.format_dt(created_at, style="D")
            embed.add_field(
                name="Created",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Created",
                value=str(faction_data["created_at"]),
                inline=True
            )
    
    # Add stats if available
    if "stats" in faction_data:
        stats = faction_data["stats"]
        kills = stats.get("kills", 0)
        deaths = stats.get("deaths", 0)
        
        embed.add_field(
            name=f"{EMOJIS['kill']} Kills",
            value=str(kills),
            inline=True
        )
        
        embed.add_field(
            name=f"{EMOJIS['death']} Deaths",
            value=str(deaths),
            inline=True
        )
        
        # Calculate KD ratio
        kd_ratio = kills / deaths if deaths > 0 else kills
        embed.add_field(
            name="K/D Ratio",
            value=f"{kd_ratio:.2f}",
            inline=True
        )
    
    return embed

def create_connection_embed(connection_data, server_name=None):
    """
    Create an embed for connection information
    
    Args:
        connection_data: Connection data
        server_name: Optional server name
        
    Returns:
        discord.Embed: Formatted connection embed
    """
    player_name = connection_data.get("player", {}).get("name", "Unknown Player")
    action = connection_data.get("action", "Unknown").title()
    
    title = f"{EMOJIS['connection']} Player {action}"
    
    if action.lower() == "connect":
        color = "success"
        emoji = EMOJIS["online"]
    else:  # disconnect
        color = "error"
        emoji = EMOJIS["offline"]
    
    embed = create_basic_embed(
        title,
        description=f"{emoji} **{player_name}** has {action.lower()}ed",
        color=color
    )
    
    # Add server name if provided
    if server_name:
        embed.description += f" to **{server_name}**"
    
    # Add timestamp if available
    if "timestamp" in connection_data:
        try:
            conn_time = datetime.fromisoformat(connection_data["timestamp"])
            time_str = discord.utils.format_dt(conn_time, style="R")
            embed.add_field(
                name="Time",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Time",
                value=str(connection_data["timestamp"]),
                inline=True
            )
    
    # Add IP info if available (truncated for privacy)
    if "ip" in connection_data and connection_data["ip"]:
        ip = connection_data["ip"]
        # Only show the first two octets for privacy
        if "." in ip:
            parts = ip.split(".")
            masked_ip = f"{parts[0]}.{parts[1]}.*.*"
            embed.add_field(
                name="IP (partial)",
                value=masked_ip,
                inline=True
            )
    
    # Add session duration for disconnects
    if action.lower() == "disconnect" and "duration" in connection_data:
        minutes = connection_data["duration"]
        hours = minutes / 60.0
        
        if hours >= 1:
            duration = f"{hours:.1f} hours"
        else:
            duration = f"{minutes} minutes"
            
        embed.add_field(
            name="Session Duration",
            value=duration,
            inline=True
        )
    
    return embed

def create_error_embed(title, description=None):
    """
    Create an error embed with standardized formatting
    
    Args:
        title: Error title
        description: Optional error description
        
    Returns:
        discord.Embed: Formatted error embed
    """
    return create_basic_embed(
        f"{EMOJIS['error']} {title}",
        description=description,
        color="error"
    )

def create_success_embed(title, description=None):
    """
    Create a success embed with standardized formatting
    
    Args:
        title: Success title
        description: Optional success description
        
    Returns:
        discord.Embed: Formatted success embed
    """
    return create_basic_embed(
        f"{EMOJIS['success']} {title}",
        description=description,
        color="success"
    )

def create_info_embed(title, description=None):
    """
    Create an info embed with standardized formatting
    
    Args:
        title: Info title
        description: Optional info description
        
    Returns:
        discord.Embed: Formatted info embed
    """
    return create_basic_embed(
        f"{EMOJIS['info']} {title}",
        description=description,
        color="info"
    )

def create_warning_embed(title, description=None):
    """
    Create a warning embed with standardized formatting
    
    Args:
        title: Warning title
        description: Optional warning description
        
    Returns:
        discord.Embed: Formatted warning embed
    """
    return create_basic_embed(
        f"{EMOJIS['warning']} {title}",
        description=description,
        color="warning"
    )

def create_leaderboard_embed(server, players, stat_type="kills", timeframe="all"):
    """
    Create an embed showing player leaderboard statistics
    
    Args:
        server: Server data dictionary
        players: List of player data dictionaries  
        stat_type: Type of stat to sort by (kills, deaths, kd, time)
        timeframe: Time period for the leaderboard (all, week, day)
        
    Returns:
        discord.Embed: Formatted leaderboard embed
    """
    # Sort players based on the selected stat
    if stat_type == "kills":
        sorted_players = sorted(players, key=lambda p: p.get("kills", 0), reverse=True)
        title = "🏆 Kills Leaderboard"
        description = f"Top killers on {server.get('name', 'Unknown Server')}"
    elif stat_type == "deaths":
        sorted_players = sorted(players, key=lambda p: p.get("deaths", 0), reverse=True)
        title = "💀 Deaths Leaderboard"
        description = f"Most deaths on {server.get('name', 'Unknown Server')}"
    elif stat_type == "kd":
        # Calculate K/D ratio with safe division
        for player in players:
            player["kd_ratio"] = player.get("kills", 0) / max(player.get("deaths", 1), 1)
        sorted_players = sorted(players, key=lambda p: p.get("kd_ratio", 0), reverse=True)
        title = "⚖️ K/D Ratio Leaderboard"
        description = f"Best K/D ratios on {server.get('name', 'Unknown Server')}"
    elif stat_type == "time":
        sorted_players = sorted(players, key=lambda p: p.get("playtime", 0), reverse=True)
        title = "⏱️ Playtime Leaderboard"
        description = f"Most active players on {server.get('name', 'Unknown Server')}"
    else:
        sorted_players = sorted(players, key=lambda p: p.get("kills", 0), reverse=True)
        title = "🏆 Player Leaderboard"
        description = f"Top players on {server.get('name', 'Unknown Server')}"
    
    # Add timeframe to title if not "all"
    if timeframe == "week":
        title += " (Last 7 Days)"
    elif timeframe == "day":
        title += " (Last 24 Hours)"
    
    # Create embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS.get("player")
    )
    
    # Get top 10 players for the leaderboard
    top_players = sorted_players[:10]
    
    # Create leaderboard table
    if stat_type == "kills":
        leaderboard_text = ""
        for i, player in enumerate(top_players, 1):
            kills = player.get("kills", 0)
            deaths = player.get("deaths", 0)
            kd = kills / max(deaths, 1)
            
            # Add medal emoji for top 3
            if i == 1:
                prefix = "🥇"
            elif i == 2:
                prefix = "🥈"
            elif i == 3:
                prefix = "🥉"
            else:
                prefix = f"{i}."
                
            leaderboard_text += f"{prefix} **{player.get('name', 'Unknown')}** - {kills} kills, {kd:.2f} K/D\n"
            
        embed.add_field(name="Top Killers", value=leaderboard_text or "No players found", inline=False)
        
    elif stat_type == "deaths":
        leaderboard_text = ""
        for i, player in enumerate(top_players, 1):
            deaths = player.get("deaths", 0)
            
            # Add medal emoji for top 3
            if i == 1:
                prefix = "🥇"
            elif i == 2:
                prefix = "🥈"
            elif i == 3:
                prefix = "🥉"
            else:
                prefix = f"{i}."
                
            leaderboard_text += f"{prefix} **{player.get('name', 'Unknown')}** - {deaths} deaths\n"
            
        embed.add_field(name="Most Deaths", value=leaderboard_text or "No players found", inline=False)
        
    elif stat_type == "kd":
        leaderboard_text = ""
        for i, player in enumerate(top_players, 1):
            kills = player.get("kills", 0)
            deaths = player.get("deaths", 0)
            kd = player.get("kd_ratio", kills / max(deaths, 1))
            
            # Add medal emoji for top 3
            if i == 1:
                prefix = "🥇"
            elif i == 2:
                prefix = "🥈"
            elif i == 3:
                prefix = "🥉"
            else:
                prefix = f"{i}."
                
            leaderboard_text += f"{prefix} **{player.get('name', 'Unknown')}** - {kd:.2f} K/D ({kills} kills, {deaths} deaths)\n"
            
        embed.add_field(name="Best K/D Ratios", value=leaderboard_text or "No players found", inline=False)
        
    elif stat_type == "time":
        leaderboard_text = ""
        for i, player in enumerate(top_players, 1):
            # Format playtime in hours
            playtime_hours = player.get("playtime", 0) / 3600  # Convert seconds to hours
            
            # Add medal emoji for top 3
            if i == 1:
                prefix = "🥇"
            elif i == 2:
                prefix = "🥈"
            elif i == 3:
                prefix = "🥉"
            else:
                prefix = f"{i}."
                
            leaderboard_text += f"{prefix} **{player.get('name', 'Unknown')}** - {playtime_hours:.1f} hours\n"
            
        embed.add_field(name="Most Active Players", value=leaderboard_text or "No players found", inline=False)
    
    # Add footer with timestamp and server info
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    embed.set_footer(text=f"Server: {server.get('name', 'Unknown')} | Data as of {current_time}")
    
    return embed

def create_batch_progress_embed(progress_data, server_name=None):
    """
    Create an embed showing batch processing progress
    
    Args:
        progress_data: Progress data dictionary
        server_name: Optional server name
        
    Returns:
        discord.Embed: Formatted progress embed
    """
    # Default title
    title = f"{EMOJIS['stats']} Batch Processing Progress"
    
    # Add server name to title if provided
    if server_name:
        title = f"{EMOJIS['stats']} {server_name} Batch Processing"
        
    embed = create_basic_embed(
        title,
        color="info"
    )
    
    # Get progress details
    status = progress_data.get("status", "Unknown")
    current = progress_data.get("current", 0)
    total = progress_data.get("total", 0)
    
    # Calculate percentage
    if total > 0:
        percentage = int((current / total) * 100)
    else:
        percentage = 0
        
    # Create progress bar (20 characters wide)
    bar_length = 20
    filled_length = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Add progress information
    embed.description = f"Status: **{status}**\n"
    embed.description += f"Progress: **{current}/{total}** files processed\n"
    embed.description += f"```\n{bar} {percentage}%\n```"
    
    # Add time information if available
    if "started_at" in progress_data:
        try:
            start_time = datetime.fromisoformat(progress_data["started_at"])
            time_str = discord.utils.format_dt(start_time, style="R")
            embed.add_field(
                name="Started",
                value=time_str,
                inline=True
            )
        except:
            embed.add_field(
                name="Started",
                value=str(progress_data["started_at"]),
                inline=True
            )
    
    # Add estimated completion time if available
    if "eta" in progress_data:
        embed.add_field(
            name="ETA",
            value=progress_data["eta"],
            inline=True
        )
        
    # Add processing rate if available
    if "rate" in progress_data:
        embed.add_field(
            name="Processing Rate",
            value=f"{progress_data['rate']:.1f} files/sec",
            inline=True
        )
    
    # Add any error information
    if "errors" in progress_data and progress_data["errors"]:
        error_count = len(progress_data["errors"])
        recent_errors = progress_data["errors"][-3:]  # Show only the 3 most recent errors
        
        error_text = f"{error_count} errors encountered:\n"
        for err in recent_errors:
            error_text += f"• {err}\n"
            
        if error_count > 3:
            error_text += f"...and {error_count - 3} more"
            
        embed.add_field(
            name="Errors",
            value=error_text,
            inline=False
        )
    
    return embed