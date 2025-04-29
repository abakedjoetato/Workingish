import discord
from discord.ext import commands, tasks
import logging
from database.connection import Database
from database.models import Server, Player, Kill
from utils.embeds import create_player_stats_embed, create_server_stats_embed
from bson import ObjectId

logger = logging.getLogger('deadside_bot.cogs.stats')

class StatsCommands(commands.Cog):
    """Commands for viewing player and server statistics"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="stats", invoke_without_command=True)
    async def stats(self, ctx):
        """View statistics commands. Use !stats player or !stats server"""
        await ctx.send("Available commands: `player`, `server`, `leaderboard`, `weapons`, `me`")
    
    @stats.command(name="player")
    async def player_stats(self, ctx, *, player_name: str):
        """
        View statistics for a specific player
        
        Usage: !stats player <player_name>
        """
        try:
            db = await Database.get_instance()
            
            # Find player by name (case-insensitive)
            players = await db.get_collection("players").find({
                "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
            }).to_list(None)
            
            if not players:
                await ctx.send(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
                return
            
            # Process each matching player
            for player_data in players:
                player = Player(**{**player_data, "_id": player_data["_id"]})
                
                # Get additional stats
                player_stats = await self.get_player_extended_stats(db, player.player_id)
                
                # Create and send embed
                embed = await create_player_stats_embed(player, player_stats)
                await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @stats.command(name="me")
    async def my_stats(self, ctx):
        """View your own statistics (if your Discord account is linked to a player)"""
        try:
            db = await Database.get_instance()
            
            # Find players linked to this Discord user
            players = await Player.get_by_discord_id(db, str(ctx.author.id))
            
            if not players:
                await ctx.send("⚠️ Your Discord account is not linked to any players. Use `!link player <player_name>` to link your account.")
                return
            
            # Process each linked player
            for player in players:
                # Get additional stats
                player_stats = await self.get_player_extended_stats(db, player.player_id)
                
                # Create and send embed
                embed = await create_player_stats_embed(player, player_stats)
                await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting self stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @stats.command(name="server")
    async def server_stats(self, ctx, *, server_name: str = None):
        """
        View statistics for a server
        
        Usage: !stats server [server_name]
        
        If no server name is provided, stats for all servers will be shown.
        """
        try:
            db = await Database.get_instance()
            
            if server_name:
                # Get stats for specific server
                servers = await Server.get_by_guild(db, ctx.guild.id)
                server = next((s for s in servers if s.name.lower() == server_name.lower()), None)
                
                if not server:
                    await ctx.send(f"⚠️ Server '{server_name}' not found. Use `!server list` to see all configured servers.")
                    return
                
                # Get server stats
                server_stats = await self.get_server_stats(db, server._id)
                
                # Create and send embed
                embed = await create_server_stats_embed(server, server_stats)
                await ctx.send(embed=embed)
            else:
                # Get stats for all servers in this guild
                servers = await Server.get_by_guild(db, ctx.guild.id)
                
                if not servers:
                    await ctx.send("No servers have been configured yet. Use `!server add` to add a server.")
                    return
                
                # Process each server
                for server in servers:
                    # Get server stats
                    server_stats = await self.get_server_stats(db, server._id)
                    
                    # Create and send embed
                    embed = await create_server_stats_embed(server, server_stats)
                    await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @stats.command(name="leaderboard")
    async def leaderboard(self, ctx, stat_type: str = "kills", limit: int = 10):
        """
        View the leaderboard for a specific stat
        
        Usage: !stats leaderboard [stat_type] [limit]
        
        stat_type: kills, deaths, kd (default: kills)
        limit: Number of players to show (default: 10, max: 25)
        """
        try:
            # Validate arguments
            if stat_type.lower() not in ["kills", "deaths", "kd"]:
                await ctx.send("⚠️ Invalid stat type. Choose from: kills, deaths, kd")
                return
            
            # Limit the leaderboard size
            if limit > 25:
                limit = 25
            
            db = await Database.get_instance()
            
            # Get servers for this guild to filter stats
            servers = await Server.get_by_guild(db, ctx.guild.id)
            server_ids = [server._id for server in servers]
            
            if not server_ids:
                await ctx.send("No servers have been configured yet. Use `!server add` to add a server.")
                return
            
            # Build the leaderboard based on stat type
            if stat_type.lower() == "kills":
                # Sort by kills
                cursor = db.get_collection("players").find({}).sort("total_kills", -1).limit(limit)
                
                players = []
                async for data in cursor:
                    players.append(Player(**{**data, "_id": data["_id"]}))
                
                # Create embed
                embed = discord.Embed(
                    title=f"Top {limit} Players by Kills",
                    description=f"Across all servers in {ctx.guild.name}",
                    color=discord.Color.blue()
                )
                
                for i, player in enumerate(players, 1):
                    kd_ratio = player.total_kills / max(1, player.total_deaths)
                    embed.add_field(
                        name=f"{i}. {player.player_name}",
                        value=f"Kills: **{player.total_kills}**\n"
                              f"Deaths: {player.total_deaths}\n"
                              f"K/D: {kd_ratio:.2f}",
                        inline=True
                    )
                
            elif stat_type.lower() == "deaths":
                # Sort by deaths
                cursor = db.get_collection("players").find({}).sort("total_deaths", -1).limit(limit)
                
                players = []
                async for data in cursor:
                    players.append(Player(**{**data, "_id": data["_id"]}))
                
                # Create embed
                embed = discord.Embed(
                    title=f"Top {limit} Players by Deaths",
                    description=f"Across all servers in {ctx.guild.name}",
                    color=discord.Color.red()
                )
                
                for i, player in enumerate(players, 1):
                    kd_ratio = player.total_kills / max(1, player.total_deaths)
                    embed.add_field(
                        name=f"{i}. {player.player_name}",
                        value=f"Deaths: **{player.total_deaths}**\n"
                              f"Kills: {player.total_kills}\n"
                              f"K/D: {kd_ratio:.2f}",
                        inline=True
                    )
                
            elif stat_type.lower() == "kd":
                # Get players with at least 10 kills
                cursor = db.get_collection("players").find({"total_kills": {"$gte": 10}})
                
                players = []
                async for data in cursor:
                    player = Player(**{**data, "_id": data["_id"]})
                    kd_ratio = player.total_kills / max(1, player.total_deaths)
                    players.append((player, kd_ratio))
                
                # Sort by K/D ratio and take top N
                players.sort(key=lambda x: x[1], reverse=True)
                players = players[:limit]
                
                # Create embed
                embed = discord.Embed(
                    title=f"Top {limit} Players by K/D Ratio",
                    description=f"Across all servers in {ctx.guild.name} (min. 10 kills)",
                    color=discord.Color.green()
                )
                
                for i, (player, kd_ratio) in enumerate(players, 1):
                    embed.add_field(
                        name=f"{i}. {player.player_name}",
                        value=f"K/D: **{kd_ratio:.2f}**\n"
                              f"Kills: {player.total_kills}\n"
                              f"Deaths: {player.total_deaths}",
                        inline=True
                    )
            
            # Set footer
            embed.set_footer(text=f"Use !stats player <name> for detailed player stats")
            
            await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    @stats.command(name="weapons")
    async def weapon_stats(self, ctx, *, player_name: str = None):
        """
        View weapon usage statistics
        
        Usage: !stats weapons [player_name]
        
        If a player name is provided, shows weapon stats for that player.
        Otherwise, shows overall weapon stats across all players.
        """
        try:
            db = await Database.get_instance()
            
            # Get servers for this guild to filter stats
            servers = await Server.get_by_guild(db, ctx.guild.id)
            server_ids = [server._id for server in servers]
            
            if not server_ids:
                await ctx.send("No servers have been configured yet. Use `!server add` to add a server.")
                return
            
            if player_name:
                # Get weapon stats for a specific player
                players = await db.get_collection("players").find({
                    "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
                }).to_list(None)
                
                if not players:
                    await ctx.send(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
                    return
                
                player = Player(**{**players[0], "_id": players[0]["_id"]})
                
                # Find kills by this player
                pipeline = [
                    {"$match": {"killer_id": player.player_id, "server_id": {"$in": server_ids}}},
                    {"$group": {
                        "_id": "$weapon",
                        "count": {"$sum": 1},
                        "total_distance": {"$sum": "$distance"},
                        "max_distance": {"$max": "$distance"}
                    }},
                    {"$sort": {"count": -1}}
                ]
                
                cursor = db.get_collection("kills").aggregate(pipeline)
                
                weapon_stats = []
                async for stat in cursor:
                    weapon_stats.append(stat)
                
                # Create embed
                embed = discord.Embed(
                    title=f"Weapon Stats for {player.player_name}",
                    description=f"Total Kills: {player.total_kills}",
                    color=discord.Color.blue()
                )
                
                for stat in weapon_stats:
                    weapon = stat["_id"]
                    count = stat["count"]
                    percent = (count / max(1, player.total_kills)) * 100
                    avg_distance = stat["total_distance"] / max(1, count)
                    
                    embed.add_field(
                        name=f"{weapon}",
                        value=f"Kills: **{count}** ({percent:.1f}%)\n"
                              f"Avg. Distance: {avg_distance:.1f}m\n"
                              f"Max Distance: {stat['max_distance']:.1f}m",
                        inline=True
                    )
                
            else:
                # Get overall weapon stats
                pipeline = [
                    {"$match": {"server_id": {"$in": server_ids}}},
                    {"$group": {
                        "_id": "$weapon",
                        "count": {"$sum": 1},
                        "total_distance": {"$sum": "$distance"},
                        "max_distance": {"$max": "$distance"}
                    }},
                    {"$sort": {"count": -1}}
                ]
                
                cursor = db.get_collection("kills").aggregate(pipeline)
                
                weapon_stats = []
                async for stat in cursor:
                    weapon_stats.append(stat)
                
                # Get total kill count
                total_kills = sum(stat["count"] for stat in weapon_stats)
                
                # Create embed
                embed = discord.Embed(
                    title=f"Overall Weapon Stats",
                    description=f"Total Kills: {total_kills}",
                    color=discord.Color.blue()
                )
                
                for stat in weapon_stats:
                    weapon = stat["_id"]
                    count = stat["count"]
                    percent = (count / max(1, total_kills)) * 100
                    avg_distance = stat["total_distance"] / max(1, count)
                    
                    embed.add_field(
                        name=f"{weapon}",
                        value=f"Kills: **{count}** ({percent:.1f}%)\n"
                              f"Avg. Distance: {avg_distance:.1f}m\n"
                              f"Max Distance: {stat['max_distance']:.1f}m",
                        inline=True
                    )
            
            # Set footer
            embed.set_footer(text=f"Use !stats player <name> for detailed player stats")
            
            await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting weapon stats: {e}")
            await ctx.send(f"⚠️ An error occurred: {e}")
    
    async def get_player_extended_stats(self, db, player_id):
        """Get extended statistics for a player"""
        stats = {
            "weapons": {},
            "victims": {},
            "killed_by": {},
            "longest_kill": None,
            "recent_kills": []
        }
        
        if not player_id:
            return stats
        
        try:
            # Get weapon stats
            weapon_pipeline = [
                {"$match": {"killer_id": player_id}},
                {"$group": {
                    "_id": "$weapon",
                    "count": {"$sum": 1},
                    "total_distance": {"$sum": "$distance"},
                    "max_distance": {"$max": "$distance"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            cursor = db.get_collection("kills").aggregate(weapon_pipeline)
            async for stat in cursor:
                stats["weapons"][stat["_id"]] = {
                    "kills": stat["count"],
                    "avg_distance": stat["total_distance"] / max(1, stat["count"]),
                    "max_distance": stat["max_distance"]
                }
            
            # Get most killed players
            victims_pipeline = [
                {"$match": {"killer_id": player_id, "is_suicide": False}},
                {"$group": {
                    "_id": {"id": "$victim_id", "name": "$victim_name"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            cursor = db.get_collection("kills").aggregate(victims_pipeline)
            async for stat in cursor:
                victim_id = stat["_id"]["id"]
                victim_name = stat["_id"]["name"]
                stats["victims"][victim_name] = {
                    "id": victim_id,
                    "kills": stat["count"]
                }
            
            # Get players who killed this player
            killers_pipeline = [
                {"$match": {"victim_id": player_id, "is_suicide": False}},
                {"$group": {
                    "_id": {"id": "$killer_id", "name": "$killer_name"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            cursor = db.get_collection("kills").aggregate(killers_pipeline)
            async for stat in cursor:
                killer_id = stat["_id"]["id"]
                killer_name = stat["_id"]["name"]
                stats["killed_by"][killer_name] = {
                    "id": killer_id,
                    "deaths": stat["count"]
                }
            
            # Get longest kill
            longest_kill = await db.get_collection("kills").find({
                "killer_id": player_id,
                "is_suicide": False
            }).sort("distance", -1).limit(1).to_list(1)
            
            if longest_kill:
                kill = longest_kill[0]
                stats["longest_kill"] = {
                    "distance": kill["distance"],
                    "weapon": kill["weapon"],
                    "victim": kill["victim_name"],
                    "timestamp": kill["timestamp"]
                }
            
            # Get recent kills
            recent_kills = await db.get_collection("kills").find({
                "killer_id": player_id,
                "is_suicide": False
            }).sort("timestamp", -1).limit(5).to_list(5)
            
            for kill in recent_kills:
                stats["recent_kills"].append({
                    "victim": kill["victim_name"],
                    "weapon": kill["weapon"],
                    "distance": kill["distance"],
                    "timestamp": kill["timestamp"]
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting extended player stats: {e}")
            return stats
    
    async def get_server_stats(self, db, server_id):
        """Get statistics for a server"""
        stats = {
            "total_kills": 0,
            "total_suicides": 0,
            "total_players": 0,
            "top_weapons": [],
            "top_killers": [],
            "longest_kill": None,
            "recent_kills": [],
            "mission_stats": {
                "total": 0,
                "by_type": {}
            }
        }
        
        try:
            # Get basic kill stats
            kill_stats = await db.get_collection("kills").aggregate([
                {"$match": {"server_id": server_id}},
                {"$group": {
                    "_id": None,
                    "total_kills": {"$sum": 1},
                    "total_suicides": {"$sum": {"$cond": [{"$eq": ["$is_suicide", True]}, 1, 0]}}
                }}
            ]).to_list(1)
            
            if kill_stats:
                stats["total_kills"] = kill_stats[0]["total_kills"]
                stats["total_suicides"] = kill_stats[0]["total_suicides"]
            
            # Count unique players
            player_count = await db.get_collection("kills").aggregate([
                {"$match": {"server_id": server_id}},
                {"$group": {
                    "_id": {"$cond": [
                        {"$not": ["$killer_id"]},
                        "$victim_id",
                        "$killer_id"
                    ]}
                }},
                {"$count": "total"}
            ]).to_list(1)
            
            if player_count:
                stats["total_players"] = player_count[0]["total"]
            
            # Get top weapons
            top_weapons = await db.get_collection("kills").aggregate([
                {"$match": {"server_id": server_id}},
                {"$group": {
                    "_id": "$weapon",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]).to_list(5)
            
            stats["top_weapons"] = [{"weapon": w["_id"], "kills": w["count"]} for w in top_weapons]
            
            # Get top killers
            top_killers = await db.get_collection("kills").aggregate([
                {"$match": {"server_id": server_id, "is_suicide": False}},
                {"$group": {
                    "_id": {"id": "$killer_id", "name": "$killer_name"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]).to_list(5)
            
            stats["top_killers"] = [
                {"name": k["_id"]["name"], "id": k["_id"]["id"], "kills": k["count"]}
                for k in top_killers
            ]
            
            # Get longest kill
            longest_kill = await db.get_collection("kills").find({
                "server_id": server_id,
                "is_suicide": False
            }).sort("distance", -1).limit(1).to_list(1)
            
            if longest_kill:
                kill = longest_kill[0]
                stats["longest_kill"] = {
                    "distance": kill["distance"],
                    "weapon": kill["weapon"],
                    "killer": kill["killer_name"],
                    "victim": kill["victim_name"],
                    "timestamp": kill["timestamp"]
                }
            
            # Get recent kills
            recent_kills = await db.get_collection("kills").find({
                "server_id": server_id
            }).sort("timestamp", -1).limit(5).to_list(5)
            
            for kill in recent_kills:
                stats["recent_kills"].append({
                    "killer": kill["killer_name"],
                    "victim": kill["victim_name"],
                    "weapon": kill["weapon"],
                    "distance": kill["distance"],
                    "timestamp": kill["timestamp"],
                    "is_suicide": kill["is_suicide"]
                })
            
            # Get mission stats
            mission_stats = await db.get_collection("server_events").aggregate([
                {"$match": {"server_id": server_id, "event_type": "mission"}},
                {"$group": {
                    "_id": "$details.name",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]).to_list(None)
            
            stats["mission_stats"]["by_type"] = {m["_id"]: m["count"] for m in mission_stats}
            stats["mission_stats"]["total"] = sum(m["count"] for m in mission_stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            return stats
