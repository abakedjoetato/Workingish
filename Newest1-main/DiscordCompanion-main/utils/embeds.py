import discord
from datetime import datetime
from config import COLORS

async def create_server_embed(server, parser_status=None):
    """
    Create an embed for server information
    
    Args:
        server: Server object
        parser_status: Optional list of parser states
        
    Returns:
        discord.Embed: Server information embed
    """
    embed = discord.Embed(
        title=f"Server: {server.name}",
        description=f"IP: {server.ip}:{server.port}",
        color=discord.Color(COLORS["primary"])
    )
    
    # Server configuration details
    embed.add_field(
        name="Configuration",
        value=f"Access Method: {server.access_method}\n"
              f"Log Path: {server.log_path}\n"
              f"CSV Parsing: {'Enabled' if server.csv_enabled else 'Disabled'}\n"
              f"Log Parsing: {'Enabled' if server.log_enabled else 'Disabled'}"
    )
    
    # Add parser status if available
    if parser_status:
        csv_parsers = [p for p in parser_status if p["parser_type"] == "csv"]
        log_parsers = [p for p in parser_status if p["parser_type"] == "log"]
        
        if csv_parsers:
            csv_status = "✅ Running" if any(p["last_position"] > 0 for p in csv_parsers) else "⚠️ Not started"
            csv_updated = max([p["updated_at"] for p in csv_parsers], default=None)
            if csv_updated:
                time_diff = datetime.utcnow() - csv_updated
                minutes = int(time_diff.total_seconds() / 60)
                csv_last_updated = f"{minutes} minutes ago" if minutes < 60 else f"{int(minutes/60)} hours ago"
            else:
                csv_last_updated = "Never"
                
            embed.add_field(
                name="CSV Parser Status",
                value=f"Status: {csv_status}\nLast Run: {csv_last_updated}"
            )
        
        if log_parsers:
            log_status = "✅ Running" if any(p["last_position"] > 0 for p in log_parsers) else "⚠️ Not started"
            log_updated = max([p["updated_at"] for p in log_parsers], default=None)
            if log_updated:
                time_diff = datetime.utcnow() - log_updated
                minutes = int(time_diff.total_seconds() / 60)
                log_last_updated = f"{minutes} minutes ago" if minutes < 60 else f"{int(minutes/60)} hours ago"
            else:
                log_last_updated = "Never"
                
            embed.add_field(
                name="Log Parser Status",
                value=f"Status: {log_status}\nLast Run: {log_last_updated}"
            )
    
    # Add server timestamps
    embed.add_field(
        name="Server Info",
        value=f"Added: {server.added_at.strftime('%Y-%m-%d %H:%M')}\n"
              f"Updated: {server.updated_at.strftime('%Y-%m-%d %H:%M')}"
    )
    
    # Set footer
    embed.set_footer(text=f"Server ID: {server._id}")
    
    return embed

async def create_player_stats_embed(player, extended_stats=None):
    """
    Create an embed for player statistics
    
    Args:
        player: Player object
        extended_stats: Optional extended player statistics
        
    Returns:
        discord.Embed: Player statistics embed
    """
    # Calculate K/D ratio
    kd_ratio = player.total_kills / max(1, player.total_deaths)
    
    embed = discord.Embed(
        title=f"Player: {player.player_name}",
        description=f"ID: {player.player_id}",
        color=discord.Color(COLORS["primary"])
    )
    
    # Basic stats
    embed.add_field(
        name="Basic Stats",
        value=f"Kills: {player.total_kills}\n"
              f"Deaths: {player.total_deaths}\n"
              f"K/D Ratio: {kd_ratio:.2f}"
    )
    
    # Add Discord link if available
    if player.discord_id:
        embed.add_field(
            name="Discord",
            value=f"Linked to <@{player.discord_id}>"
        )
    
    # Add extended stats if available
    if extended_stats:
        # Top weapons
        if extended_stats["weapons"]:
            weapons_text = ""
            for weapon, stats in list(extended_stats["weapons"].items())[:3]:  # Top 3
                weapons_text += f"{weapon}: {stats['kills']} kills ({stats['avg_distance']:.1f}m avg)\n"
            
            embed.add_field(
                name="Top Weapons",
                value=weapons_text if weapons_text else "No weapon data"
            )
        
        # Most killed players
        if extended_stats["victims"]:
            victims_text = ""
            for victim_name, stats in extended_stats["victims"].items():
                victims_text += f"{victim_name}: {stats['kills']} times\n"
            
            embed.add_field(
                name="Most Killed",
                value=victims_text if victims_text else "No data"
            )
        
        # Killed by
        if extended_stats["killed_by"]:
            killers_text = ""
            for killer_name, stats in extended_stats["killed_by"].items():
                killers_text += f"{killer_name}: {stats['deaths']} times\n"
            
            embed.add_field(
                name="Killed By",
                value=killers_text if killers_text else "No data"
            )
        
        # Longest kill
        if extended_stats["longest_kill"]:
            longest = extended_stats["longest_kill"]
            embed.add_field(
                name="Longest Kill",
                value=f"Distance: {longest['distance']:.1f}m\n"
                      f"Weapon: {longest['weapon']}\n"
                      f"Victim: {longest['victim']}\n"
                      f"Date: {longest['timestamp'].strftime('%Y-%m-%d')}"
            )
        
        # Recent kills
        if extended_stats["recent_kills"]:
            recent_text = ""
            for kill in extended_stats["recent_kills"]:
                recent_text += f"{kill['victim']} with {kill['weapon']} ({kill['distance']:.1f}m)\n"
            
            embed.add_field(
                name="Recent Kills",
                value=recent_text if recent_text else "No recent kills"
            )
    
    # Add player timestamps
    embed.add_field(
        name="Player Info",
        value=f"First Seen: {player.first_seen.strftime('%Y-%m-%d')}\n"
              f"Last Seen: {player.last_seen.strftime('%Y-%m-%d')}"
    )
    
    # Set footer
    embed.set_footer(text=f"Player ID: {player.player_id}")
    
    return embed

async def create_server_stats_embed(server, stats):
    """
    Create an embed for server statistics
    
    Args:
        server: Server object
        stats: Server statistics dictionary
        
    Returns:
        discord.Embed: Server statistics embed
    """
    embed = discord.Embed(
        title=f"Statistics for {server.name}",
        description=f"IP: {server.ip}:{server.port}",
        color=discord.Color(COLORS["info"])
    )
    
    # Basic stats
    embed.add_field(
        name="Overview",
        value=f"Total Players: {stats['total_players']}\n"
              f"Total Kills: {stats['total_kills']}\n"
              f"Total Suicides: {stats['total_suicides']}"
    )
    
    # Top killers
    if stats["top_killers"]:
        killers_text = ""
        for killer in stats["top_killers"]:
            killers_text += f"{killer['name']}: {killer['kills']} kills\n"
        
        embed.add_field(
            name="Top Killers",
            value=killers_text
        )
    
    # Top weapons
    if stats["top_weapons"]:
        weapons_text = ""
        for weapon in stats["top_weapons"]:
            weapons_text += f"{weapon['weapon']}: {weapon['kills']} kills\n"
        
        embed.add_field(
            name="Top Weapons",
            value=weapons_text
        )
    
    # Longest kill
    if stats["longest_kill"]:
        longest = stats["longest_kill"]
        embed.add_field(
            name="Longest Kill",
            value=f"Distance: {longest['distance']:.1f}m\n"
                  f"Killer: {longest['killer']}\n"
                  f"Victim: {longest['victim']}\n"
                  f"Weapon: {longest['weapon']}"
        )
    
    # Recent kills
    if stats["recent_kills"]:
        recent_text = ""
        for kill in stats["recent_kills"]:
            if kill["is_suicide"]:
                recent_text += f"{kill['killer_name']} died to {kill['weapon']}\n"
            else:
                recent_text += f"{kill['killer']} killed {kill['victim']} with {kill['weapon']} ({kill['distance']:.1f}m)\n"
        
        embed.add_field(
            name="Recent Kills",
            value=recent_text,
            inline=False
        )
    
    # Mission stats
    if stats["mission_stats"]["total"] > 0:
        mission_text = f"Total Missions: {stats['mission_stats']['total']}\n"
        for mission_type, count in stats["mission_stats"]["by_type"].items():
            mission_text += f"{mission_type}: {count}\n"
        
        embed.add_field(
            name="Missions",
            value=mission_text,
            inline=False
        )
    
    # Set footer
    embed.set_footer(text=f"Server ID: {server._id}")
    
    return embed

async def create_killfeed_embed(kill, server_name):
    """
    Create an embed for killfeed notifications
    
    Args:
        kill: Kill object
        server_name: Name of the server
        
    Returns:
        discord.Embed: Killfeed embed
    """
    # Choose color based on kill type
    if kill.is_suicide:
        color = discord.Color(COLORS["warning"])
    elif kill.is_menu_suicide:
        color = discord.Color(COLORS["neutral"])
    elif kill.is_fall_death:
        color = discord.Color(COLORS["warning"])
    else:
        color = discord.Color(COLORS["danger"])
    
    # Create embed title based on kill type
    if kill.is_suicide:
        title = f"☠️ {kill.killer_name} died"
    elif kill.is_menu_suicide:
        title = f"💨 {kill.killer_name} relocated (menu suicide)"
    elif kill.is_fall_death:
        title = f"⚡ {kill.killer_name} died to fall damage"
    else:
        title = f"💀 {kill.killer_name} killed {kill.victim_name}"
    
    embed = discord.Embed(
        title=title,
        description=f"Server: {server_name}",
        color=color,
        timestamp=kill.timestamp
    )
    
    # Add kill details
    if not kill.is_suicide and not kill.is_menu_suicide:
        embed.add_field(
            name="Weapon",
            value=kill.weapon
        )
        
        embed.add_field(
            name="Distance",
            value=f"{kill.distance:.1f}m" if kill.distance > 0 else "Close range"
        )
    else:
        embed.add_field(
            name="Cause",
            value=kill.weapon
        )
    
    # Set footer
    embed.set_footer(text=f"Deadside Killfeed | {kill.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed

async def create_connection_embed(connection, server_name):
    """
    Create an embed for connection notifications
    
    Args:
        connection: ConnectionEvent object
        server_name: Name of the server
        
    Returns:
        discord.Embed: Connection embed
    """
    # Choose color and title based on connection type
    if connection.event_type == "connect":
        color = discord.Color(COLORS["success"])
        title = f"🟢 {connection.player_name} connected"
        
    elif connection.event_type == "disconnect":
        color = discord.Color(COLORS["neutral"])
        title = f"🔴 {connection.player_name} disconnected"
        
    elif connection.event_type == "kick":
        color = discord.Color(COLORS["warning"])
        title = f"⛔ {connection.player_name} was kicked"
    
    else:
        color = discord.Color(COLORS["info"])
        title = f"ℹ️ {connection.player_name} {connection.event_type}"
    
    embed = discord.Embed(
        title=title,
        description=f"Server: {server_name}",
        color=color,
        timestamp=connection.timestamp
    )
    
    # Add kick reason if applicable
    if connection.event_type == "kick" and connection.reason:
        embed.add_field(
            name="Reason",
            value=connection.reason
        )
    
    # Add player ID if available
    if connection.player_id:
        embed.add_field(
            name="Player ID",
            value=connection.player_id
        )
    
    # Set footer
    embed.set_footer(text=f"Deadside Connections | {connection.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed

async def create_mission_embed(event, server_name):
    """
    Create an embed for mission and server event notifications
    
    Args:
        event: ServerEvent object
        server_name: Name of the server
        
    Returns:
        discord.Embed: Mission embed
    """
    event_type = event.event_type.lower()
    
    # Choose color and emoji based on event type
    if event_type == "mission":
        color = discord.Color(COLORS["primary"])
        emoji = "🎯"
    elif event_type == "helicrash":
        color = discord.Color(COLORS["danger"])
        emoji = "🚁"
    elif event_type == "airdrop":
        color = discord.Color(COLORS["info"])
        emoji = "🪂"
    elif event_type == "trader":
        color = discord.Color(COLORS["success"])
        emoji = "💰"
    elif event_type == "server_start":
        color = discord.Color(COLORS["success"])
        emoji = "🟢"
    elif event_type == "server_stop":
        color = discord.Color(COLORS["danger"])
        emoji = "🔴"
    else:
        color = discord.Color(COLORS["neutral"])
        emoji = "ℹ️"
    
    # Format title based on event type
    event_title = event_type.replace("_", " ").title()
    title = f"{emoji} {event_title}"
    
    embed = discord.Embed(
        title=title,
        description=f"Server: {server_name}",
        color=color,
        timestamp=event.timestamp
    )
    
    # Add event details based on type
    if event_type == "mission":
        mission_name = event.details.get("name", "Unknown")
        mission_level = event.details.get("level", "Unknown")
        
        embed.add_field(
            name="Mission",
            value=mission_name
        )
        
        embed.add_field(
            name="Level",
            value=mission_level
        )
        
    elif event_type in ["helicrash", "airdrop", "trader"]:
        location = event.details.get("location", "Unknown")
        
        embed.add_field(
            name="Location",
            value=location
        )
    
    # Set footer
    embed.set_footer(text=f"Deadside Events | {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed
