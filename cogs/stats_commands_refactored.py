import discord
from discord.ext import commands, tasks
import logging
import asyncio
import datetime
from database.connection import Database
from database.models import Player, Server, GuildConfig
from utils.embeds import create_player_embed, create_leaderboard_embed
from utils.guild_isolation import get_guild_servers, get_server_by_name
from utils.premium import check_feature_access, get_tier_display_info
import bson

logger = logging.getLogger('deadside_bot.cogs.stats')

# Create slash command group for stats commands
stats_group = discord.SlashCommandGroup(
    name="stats",
    description="Commands for viewing player and server statistics",
)

class StatsCommands(commands.Cog):
    """Commands for viewing player and server statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Stats commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        """Return all commands this cog provides"""
        return [stats_group]
    
    @stats_group.command(
        name="player",
        description="View detailed statistics for a player", 
        contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="player",
        description="View detailed statistics for a player", 
        contexts=[discord.InteractionContextType.guild],)
    async def stats_player(
        self, 
        ctx, 
        player_name: discord.Option(str, "Player name to search for", required=True),
        server_name: discord.Option(str, "Server to check (default: all accessible servers)", required=False) = None
    ):
        """View detailed statistics for a player"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Get servers for this guild
            servers_query = {}
            if server_name:
                servers_query = {
                    "name": {"$regex": f"^{server_name}$", "$options": "i"},
                    "guild_id": guild_id
                }
            else:
                servers_query = {"guild_id": guild_id}
                
            servers_collection = await self.db.get_collection("servers")
            server_cursor = servers_collection.find(servers_query)
            servers = await server_cursor.to_list(None)
            
            if not servers:
                if server_name:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                else:
                    await ctx.respond("❌ No servers found for this guild")
                return
                
            # Find the player in the specified servers
            players_collection = await self.db.get_collection("players")
            
            # Build player query
            player_query = {
                "name": {"$regex": f"^{player_name}$", "$options": "i"},
                "server_id": {"$in": [str(server["_id"]) for server in servers]}
            }
            
            # Find all matching players
            player_cursor = players_collection.find(player_query)
            players = await player_cursor.to_list(None)
            
            if not players:
                await ctx.respond(f"❌ No player found with name '{player_name}'")
                return
                
            # Get main player and check for linked alts
            main_player = players[0]
            linked_alts = []
            
            # Check if this player is a main account with alts
            if "alt_player_ids" in main_player and main_player["alt_player_ids"]:
                alt_ids = main_player["alt_player_ids"]
                if alt_ids:
                    alt_cursor = players_collection.find({"_id": {"$in": alt_ids}})
                    linked_alts = await alt_cursor.to_list(None)
            
            # Check if this player is an alt linked to a main account
            elif "main_player_id" in main_player and main_player["main_player_id"]:
                main_id = main_player["main_player_id"]
                main_account = await players_collection.find_one({"_id": main_id})
                
                if main_account:
                    # Switch to using the main account
                    if "alt_player_ids" in main_account and main_account["alt_player_ids"]:
                        alt_cursor = players_collection.find({
                            "_id": {"$in": main_account["alt_player_ids"]},
                            "_id": {"$ne": main_player["_id"]}  # Exclude this alt
                        })
                        other_alts = await alt_cursor.to_list(None)
                        
                        # Make the main player the main account and add this player to linked_alts
                        linked_alts = [main_player] + other_alts
                        main_player = main_account
            
            # Create the player embed
            embed = await create_player_embed(main_player, players, linked_alts, servers)
            
            # Add rivalry information if premium
            try:
                is_premium = await check_feature_access(self.db, guild_id, "rivalry_tracking")
                
                if is_premium and "nemesis_id" in main_player and main_player["nemesis_id"]:
                    # Add nemesis information
                    nemesis_name = main_player.get("nemesis_name", "Unknown")
                    nemesis_kills = main_player.get("nemesis_deaths", 0)
                    
                    embed.add_field(
                        name="☠️ Nemesis",
                        value=f"**{nemesis_name}** has killed you {nemesis_kills} times",
                        inline=True
                    )
                
                if is_premium and "prey_id" in main_player and main_player["prey_id"]:
                    # Add prey information
                    prey_name = main_player.get("prey_name", "Unknown")
                    prey_kills = main_player.get("prey_kills", 0)
                    
                    embed.add_field(
                        name="🎯 Prey",
                        value=f"You've killed **{prey_name}** {prey_kills} times",
                        inline=True
                    )
            except Exception as e:
                logger.error(f"Error adding rivalry information: {e}")
            
            await ctx.respond(@stats_group.command(
        name="leaderboard",
        description="View server leaderboard", 
        contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="leaderboard",
        description="View server leaderboard", 
        contexts=[discord.InteractionContextType.guild],
    )
    async def stats_leaderboard(
        self, 
        ctx, 
        server_name: discord.Option(str, "Server to show leaderboard for", required=False) = None,
        stat_type: discord.Option(str, "Stat to sort by", choices=["kills", "deaths", "kd", "time"], required=False) = "kills",
        timeframe: discord.Option(str, "Time period to show", choices=["all", "week", "day"], required=False) = "all"
    ):
        """View server leaderboard"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Find all servers if no server name provided
            if server_name:
                server = await get_server_by_name(self.db, server_name, guild_id)
                if not server:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                    return
                servers = [server]
            else:
                # Get all servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                if not servers:
                    await ctx.respond("❌ No servers found for this guild")
                    return
                
                # If multiple servers, ask the user to specify
                if len(servers) > 1:
                    server_list = "\n".join([f"- {server['name']}" for server in servers])
                    await ctx.respond(f"Multiple servers found. Please specify a server name:\n\n{server_list}")
                    return
                
                server = servers[0]
            
            # Build the timeframe filter if needed
            date_filter = {}
            if timeframe != "all":
                now = datetime.datetime.utcnow()
                if timeframe == "week":
                    start_date = now - datetime.timedelta(days=7)
                elif timeframe == "day":
                    start_date = now - datetime.timedelta(days=1)
                
                date_filter = {"last_seen": {"$gte": start_date}}
            
            # Build query for player stats
            player_query = {"server_id": str(server["_id"])}
            if date_filter:
                player_query.update(date_filter)
                
            # Get players for this server
            players_collection = await self.db.get_collection("players")
            player_cursor = players_collection.find(player_query)
            players = await player_cursor.to_list(None)
            
            if not players:
                await ctx.respond(f"❌ No players found for server '{server['name']}' in the selected timeframe")
                return
            
            # Create the leaderboard embed
            embed = await create_leaderboard_embed(server, players, stat_type, timeframe)
            await ctx.respond(embed=embed)
@stats_group.command(
        name="weapons",
        description="View weapon usage statistics for a server",
        contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="weapons",
        description="View weapon usage statistics for a server",
        contexts=[discord.InteractionContextType.guild],
    )
    async def stats_weapons(
        self, 
        ctx, 
        server_name: discord.Option(str, "Server to show stats for", required=False) = None
    ):
        """View weapon usage statistics for a server"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Find server
            if server_name:
                server = await get_server_by_name(self.db, server_name, guild_id)
                if not server:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                    return
                servers = [server]
            else:
                # Get all servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                if not servers:
                    await ctx.respond("❌ No servers found for this guild")
                    return
                
                # If multiple servers, ask the user to specify
                if len(servers) > 1:
                    server_list = "\n".join([f"- {server['name']}" for server in servers])
                    await ctx.respond(f"Multiple servers found. Please specify a server name:\n\n{server_list}")
                    return
                
                server = servers[0]
            
            # Get kills collection to analyze weapon stats
            kills_collection = await self.db.get_collection("kills")
            
            # Aggregate weapon statistics
            pipeline = [
                {"$match": {"server_id": str(server["_id"])}},
                {"$group": {
                    "_id": "$weapon",
                    "kills": {"$sum": 1}
                }},
                {"$sort": {"kills": -1}},
                {"$limit": 20}  # Top 20 weapons
            ]
            
            weapon_stats = await kills_collection.aggregate(pipeline).to_list(None)
            
            if not weapon_stats:
                await ctx.respond(f"❌ No weapon data found for server '{server['name']}'")
                return
            
            # Create the weapons embed
            embed = discord.Embed(
                title=f"🔫 Weapon Statistics - {server['name']}",
                description="Most used weapons on the server",
                color=discord.Color.blue()
            )
            
            # Add weapon stats in groups of 5 to avoid too many fields
            weapon_groups = [weapon_stats[i:i+5] for i in range(0, len(weapon_stats), 5)]
            
            for i, group in enumerate(weapon_groups):
                weapon_text = "\n".join([f"**{stat['_id']}**: {stat['kills']} kills" for stat in group])
                embed.add_field(
                    name=f"Top Weapons {i*5+1}-{i*5+len(group)}",
                    value=weapon_text,
                    inline=True
                )
            
            # Add total kills count
            total_kills = sum(stat['kills'] for stat in weapon_stats)
            embed.set_footer(text=f"Server: {server['name']} | Total kills analyzed: {total_kills}")
            
            await c@stats_group.command(
        name="deaths",
        description="View death statistics for a player or server", contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="deaths",
        description="View death statistics for a player or server", contexts=[discord.InteractionContextType.guild],): {e}")
            await ctx.respond(f"⚠️ Error retrieving weapon stats: {str(e)}", ephemeral=True)
    
    @stats_group.command(
        name="deaths",
        description="View death statistics for a player or server"
    )
    async def stats_deaths(
        self, 
        ctx, 
        player_name: discord.Option(str, "Player name (leave empty for server stats)", required=False) = None,
        server_name: discord.Option(str, "Server to show stats for", required=False) = None
    ):
        """View death statistics for a player or server"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Find server
            if server_name:
                server = await get_server_by_name(self.db, server_name, guild_id)
                if not server:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                    return
                servers = [server]
            else:
                # Get all servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                if not servers:
                    await ctx.respond("❌ No servers found for this guild")
                    return
                
                # If multiple servers, ask the user to specify
                if len(servers) > 1:
                    server_list = "\n".join([f"- {server['name']}" for server in servers])
                    await ctx.respond(f"Multiple servers found. Please specify a server name:\n\n{server_list}")
                    return
                
                server = servers[0]
            
            # Create death statistics embed
            if player_name:
                # Get player-specific death stats
                players_collection = await self.db.get_collection("players")
                player_query = {
                    "name": {"$regex": f"^{player_name}$", "$options": "i"},
                    "server_id": str(server["_id"])
                }
                
                player = await players_collection.find_one(player_query)
                if not player:
                    await ctx.respond(f"❌ No player found with name '{player_name}' on server '{server['name']}'")
                    return
                
                # Create player deaths embed
                embed = discord.Embed(
                    title=f"💀 Death Statistics - {player['name']}",
                    description=f"Death analysis for player on {server['name']}",
                    color=discord.Color.red()
                )
                
                # Add basic player stats
                embed.add_field(
                    name="Player Stats",
                    value=f"Kills: {player.get('kills', 0)}\nDeaths: {player.get('deaths', 0)}\nK/D Ratio: {player.get('kills', 0) / max(player.get('deaths', 1), 1):.2f}",
                    inline=False
                )
                
                # Get top killers of this player
                kills_collection = await self.db.get_collection("kills")
                
                # Get killers where this player is the victim
                killer_pipeline = [
                    {"$match": {
                        "victim_id": player.get('player_id', player.get('_id', '')),
                        "server_id": str(server["_id"]),
                        "is_suicide": False
                    }},
                    {"$group": {
                        "_id": "$killer_id",
                        "count": {"$sum": 1},
                        "killer_name": {"$first": "$killer_name"},
                        "weapons": {"$push": "$weapon"}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}  # Top 5 killers
                ]
                
                killers = await kills_collection.aggregate(killer_pipeline).to_list(None)
                
                if killers:
                    killers_text = "\n".join([f"**{killer['killer_name']}**: {killer['count']} kills" for killer in killers])
                    embed.add_field(
                        name="Top Killers",
                        value=killers_text,
                        inline=True
                    )
                    
                    # Add weapon analysis
                    # Collect all weapons used to kill this player
                    all_weapons = []
                    for killer in killers:
                        all_weapons.extend(killer.get('weapons', []))
                    
                    # Count weapon frequencies
                    weapon_counts = {}
                    for weapon in all_weapons:
                        if weapon in weapon_counts:
                            weapon_counts[weapon] += 1
                        else:
                            weapon_counts[weapon] = 1
                    
                    # Sort by frequency
                    sorted_weapons = sorted(weapon_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    if sorted_weapons:
                        weapons_text = "\n".join([f"**{weapon}**: {count} deaths" for weapon, count in sorted_weapons])
                        embed.add_field(
                            name="Death by Weapon",
                            value=weapons_text,
                            inline=True
                        )
                else:
                    embed.add_field(
                        name="Top Killers",
                        value="No kill data found",
                        inline=True
                    )
                
                # Add player's most common suicide methods if they have suicides
                suicide_pipeline = [
                    {"$match": {
                        "killer_id": player.get('player_id', player.get('_id', '')),
                        "victim_id": player.get('player_id', player.get('_id', '')),
                        "server_id": str(server["_id"]),
                        "is_suicide": True
                    }},
                    {"$group": {
                        "_id": "$weapon", 
                        "count": {"$sum": 1}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 3}
                ]
                
                suicides = await kills_collection.aggregate(suicide_pipeline).to_list(None)
                
                if suicides:
                    suicide_text = "\n".join([f"**{suicide['_id']}**: {suicide['count']} times" for suicide in suicides])
                    embed.add_field(
                        name="Suicide Methods",
                        value=suicide_text,
                        inline=False
                    )
            else:
                # Server-wide death statistics
                embed = discord.Embed(
                    title=f"💀 Death Statistics - {server['name']}",
                    description="Overview of deaths on the server",
                    color=discord.Color.red()
                )
                
                # Get kills collection for analysis
                kills_collection = await self.db.get_collection("kills")
                
                # Count total deaths
                total_deaths = await kills_collection.count_documents({"server_id": str(server["_id"])})
                
                # Count suicides
                suicides = await kills_collection.count_documents({
                    "server_id": str(server["_id"]),
                    "is_suicide": True
                })
                
                # Add general stats
                embed.add_field(
                    name="Overview",
                    value=f"Total Deaths: {total_deaths}\nSuicides: {suicides}\nPlayer Kills: {total_deaths - suicides}",
                    inline=False
                )
                
                # Get top killers on the server
                killer_pipeline = [
                    {"$match": {
                        "server_id": str(server["_id"]),
                        "is_suicide": False
                    }},
                    {"$group": {
                        "_id": "$killer_id",
                        "count": {"$sum": 1},
                        "killer_name": {"$first": "$killer_name"}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                
                killers = await kills_collection.aggregate(killer_pipeline).to_list(None)
                
                if killers:
                    killers_text = "\n".join([f"**{killer['killer_name']}**: {killer['count']} kills" for killer in killers])
                    embed.add_field(
                        name="Top Killers",
                        value=killers_text,
                        inline=True
                    )
                
                # Get most deaths by player
                victim_pipeline = [
                    {"$match": {
                        "server_id": str(server["_id"])
                    }},
                    {"$group": {
                        "_id": "$victim_id",
                        "count": {"$sum": 1},
                        "victim_name": {"$first": "$victim_name"}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                
                victims = await kills_collection.aggregate(victim_pipeline).to_list(None)
                
                if victims:
                    victims_text = "\n".join([f"**{victim['victim_name']}**: {victim['count']} deaths" for victim in victims])
                    embed.add_field(
                        name="Most Deaths",
                        value=victims_text,
                        inline=True
                    )
                
                # Get most deadly weapons
                weapon_pipeline = [
                    {"$match": {
                        "server_id": str(server["_id"])
                    }},
                    {"$group": {
                        "_id": "$weapon",
                        "count": {"$sum": 1}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                
                weapons = await kills_collection.aggregate(weapon_pipeline).to_list(None)
                
                if weapons:
                    weapons_text = "\n".join([f"**{weapon['_id']}**: {weapon['count']} kills" for weapon in weapons])
                    embed.add_field(
                        name="Deadliest Weapons",
                        value=weapons_text,
                 @stats_group.command(
        name="link",
        description="Link main and alt character accounts for combined statistics", contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="link",
        description="Link main and alt character accounts for combined statistics", contexts=[discord.InteractionContextType.guild],)Server: {server['name']} | Data as of {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in stats_deaths: {e}")
            await ctx.respond(f"⚠️ Error retrieving death statistics: {str(e)}", ephemeral=True)
    
    @stats_group.command(
        name="link",
        description="Link main and alt character accounts for combined statistics"
    )
    async def stats_link(
        self,
        ctx,
        main_name: discord.Option(str, "Main character name", required=True),
        alt_name: discord.Option(str, "Alt character name to link", required=True),
        server_name: discord.Option(str, "Server where both characters exist", required=False) = None
    ):
        """Link main and alt characters together for unified stats tracking"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Find server
            if server_name:
                server = await get_server_by_name(self.db, server_name, guild_id)
                if not server:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                    return
                servers = [server]
            else:
                # Get all servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                if not servers:
                    await ctx.respond("❌ No servers found for this guild")
                    return
                
                # If multiple servers, ask the user to specify
                if len(servers) > 1:
                    server_list = "\n".join([f"- {server['name']}" for server in servers])
                    await ctx.respond(f"Multiple servers found. Please specify a server name:\n\n{server_list}")
                    return
                
                server = servers[0]
            
            # Find main character
            players_collection = await self.db.get_collection("players")
            main_query = {
                "name": {"$regex": f"^{main_name}$", "$options": "i"},
                "server_id": str(server["_id"])
            }
            
            main_character = await players_collection.find_one(main_query)
            
            if not main_character:
                await ctx.respond(f"❌ Main character '{main_name}' not found on server '{server['name']}'")
                return
            
            # Find alt character
            alt_query = {
                "name": {"$regex": f"^{alt_name}$", "$options": "i"},
                "server_id": str(server["_id"])
            }
            
            alt_character = await players_collection.find_one(alt_query)
            
            if not alt_character:
                await ctx.respond(f"❌ Alt character '{alt_name}' not found on server '{server['name']}'")
                return
                
            # Make sure they're not the same character
            if main_character["_id"] == alt_character["_id"]:
                await ctx.respond("❌ Cannot link a character to itself")
                return
                
            # Check if alt is already linked to another main
            if "main_player_id" in alt_character and alt_character["main_player_id"]:
                # If linked to this same main, report success
                if alt_character["main_player_id"] == main_character["_id"]:
                    await ctx.respond(f"✅ '{alt_name}' is already linked to '{main_name}'")
                    return
                    
                # If linked to another main, fail
                await ctx.respond(f"❌ '{alt_name}' is already linked to another main character")
                return
            
            # Check if main is actually an alt of another character
            if "main_player_id" in main_character and main_character["main_player_id"]:
                await ctx.respond(f"❌ '{main_name}' is an alt character. Please use the main character instead.")
                return
            
            # Set up the link
            # 1. Update the alt to point to the main
            await players_collection.update_one(
                {"_id": alt_character["_id"]},
                {"$set": {"main_player_id": main_character["_id"]}}
            )
            
            # 2. Update the main to include the alt
            alt_list = main_character.get("alt_player_ids", [])
            if not alt_list:
                alt_list = []
            
            if alt_character["_id"] not in alt_list:
                alt_list.append(alt_character["_id"])
                
            await players_collection.update_one(
                {"_id": main_character["_id"]},
                {"$set": {"alt_player_ids": alt_list}}
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Characters Linked Successfully",
                description=f"'{alt_name}' is now linked as an alt of '{main_name}'",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Character Details",
                value=f"**Main:** {main_nam@stats_group.command(
        name="rivals",
        description="View your top rivals (nemesis and prey, contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="rivals",
        description="View your top rivals (nemesis and prey, contexts=[discord.InteractionContextType.guild],)      
            embed.add_field(
                name="What This Means",
                value="Statistics for both characters will be shown together in player lookups. The bot will use the main character's name for killfeed and other displays.",
                inline=False
            )
            
            # Add note about alt count
            embed.set_footer(text=f"Main character now has {len(alt_list)} linked alts")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error linking characters: {e}")
            await ctx.respond(f"❌ Error linking characters: {e}")
    
    @stats_group.command(
        name="rivals",
        description="View your top rivals (nemesis and prey) in PvP"
    )
    async def stats_rivals(
        self,
        ctx,
        player_name: discord.Option(str, "Player name to check rivals for", required=True),
        server_name: discord.Option(str, "Server to check on", required=False) = None
    ):
        """View your top rivals (nemesis who kill you, prey you hunt)"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
            
            # Check if this is a premium feature
            is_premium = await check_feature_access(self.db, guild_id, "rivalry_tracking")
            
            if not is_premium:
                tier_info = await get_tier_display_info(self.db, guild_id)
                embed = discord.Embed(
                    title="💎 Premium Feature",
                    description="Rivalry tracking is a premium feature",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="Current Tier",
                    value=f"{tier_info['emoji']} {tier_info['name']}",
                    inline=True
                )
                
                embed.add_field(
                    name="Required Tier",
                    value="🗡️ Warlord or higher",
                    inline=True
                )
                
                embed.add_field(
                    name="What You Get",
                    value="Track your nemesis (players who kill you most often) and prey (players you hunt successfully)",
                    inline=False
                )
                
                embed.set_footer(text="Upgrade your tier to access this feature")
                
                await ctx.respond(embed=embed)
                return
                
            # Find server
            if server_name:
                server = await get_server_by_name(self.db, server_name, guild_id)
                if not server:
                    await ctx.respond(f"❌ No server found with name '{server_name}'")
                    return
                servers = [server]
            else:
                # Get all servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                if not servers:
                    await ctx.respond("❌ No servers found for this guild")
                    return
                
                # If multiple servers, ask the user to specify
                if len(servers) > 1:
                    server_list = "\n".join([f"- {server['name']}" for server in servers])
                    await ctx.respond(f"Multiple servers found. Please specify a server name:\n\n{server_list}")
                    return
                
                server = servers[0]
            
            # Find the player
            players_collection = await self.db.get_collection("players")
            player_query = {
                "name": {"$regex": f"^{player_name}$", "$options": "i"},
                "server_id": str(server["_id"])
            }
            
            player = await players_collection.find_one(player_query)
            
            if not player:
                await ctx.respond(f"❌ No player found with name '{player_name}' on server '{server['name']}'")
                return
            
            # Get kills collection for analysis
            kills_collection = await self.db.get_collection("kills")
            
            # Build the rivalry embed
            embed = discord.Embed(
                title=f"🔄 Rivalry Data - {player_name}",
                description=f"PvP rivalry statistics on {server['name']}",
                color=discord.Color.purple()
            )
            
            # Add player's basic stats
            embed.add_field(
                name="Player Overview",
                value=f"Kills: {player.get('kills', 0)}\nDeaths: {player.get('deaths', 0)}\nK/D Ratio: {player.get('kills', 0) / max(player.get('deaths', 1), 1):.2f}",
                inline=False
            )
            
            # Find nemesis (players who kill this player the most)
            nemesis_pipeline = [
                {"$match": {
                    "victim_id": player.get('player_id', player.get('_id', '')),
                    "server_id": str(server["_id"]),
                    "is_suicide": False
                }},
                {"$group": {
                    "_id": "$killer_id",
                    "count": {"$sum": 1},
                    "killer_name": {"$first": "$killer_name"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            nemesis_list = await kills_collection.aggregate(nemesis_pipeline).to_list(None)
            
            if nemesis_list:
                nemesis_text = "\n".join([f"**{nemesis['killer_name']}**: {nemesis['count']} kills" for nemesis in nemesis_list])
                embed.add_field(
                    name="☠️ Your Nemesis",
                    value=nemesis_text,
                    inline=True
                )
            else:
                embed.add_field(
                    name="☠️ Your Nemesis",
                    value="No nemesis data available",
                    inline=True
                )
            
            # Find prey (players this player kills the most)
            prey_pipeline = [
                {"$match": {
                    "killer_id": player.get('player_id', player.get('_id', '')),
                    "server_id": str(server["_id"]),
                    "is_suicide": False
                }},
                {"$group": {
                    "_id": "$victim_id",
                    "count": {"$sum": 1},
                    "victim_name": {"$first": "$victim_name"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            prey_list = await kills_collection.aggregate(prey_pipeline).to_list(None)
            
            if prey_list:
                prey_text = "\n".join([f"**{prey['victim_name']}**: {prey['count']} kills" for prey in prey_list])
                embed.add_field(
                    name="🎯 Your Prey",
                    value=prey_text,
                    inline=True
                )
            else:
                embed.add_field(
                    name="🎯 Your Prey",
                    value="No prey data available",
                    inline=True
                )
            
            # Add favorite weapon information
            weapon_pipeline = [
                {"$match": {
                    "killer_id": player.get('player_id', player.get('_id', '')),
                    "server_id": str(server["_id"]),
                    "is_suicide": False
                }},
                {"$group": {
  @stats_group.command(
        name="factions",
        description="View faction statistics", contexts=[discord.InteractionContextType.guild], integration_types=[discord.IntegrationType.guild_install],)@stats_group.command(
        name="factions",
        description="View faction statistics", contexts=[discord.InteractionContextType.guild],)               {"$sort": {"count": -1}},
                {"$limit": 3}
            ]
            
            weapons = await kills_collection.aggregate(weapon_pipeline).to_list(None)
            
            if weapons:
                weapons_text = "\n".join([f"**{weapon['_id']}**: {weapon['count']} kills" for weapon in weapons])
                embed.add_field(
                    name="🔫 Favorite Weapons",
                    value=weapons_text,
                    inline=False
                )
            
            # Set footer with timestamp
            embed.set_footer(text=f"Server: {server['name']} | Data as of {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error retrieving rivalry data: {e}")
            await ctx.respond(f"❌ Error retrieving rivalry data: {e}")
    
    @stats_group.command(
        name="factions",
        description="View faction statistics"
    )
    async def stats_factions(
        self,
        ctx,
        server_name: discord.Option(str, "Server to show factions for", required=False) = None
    ):
        """View faction statistics and leaderboard"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
            
            # Check if factions is a premium feature
            is_premium = await check_feature_access(self.db, guild_id, "faction_system")
            
            if not is_premium:
                tier_info = await get_tier_display_info(self.db, guild_id)
                embed = discord.Embed(
                    title="💎 Premium Feature",
                    description="Faction system is a premium feature",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="Current Tier",
                    value=f"{tier_info['emoji']} {tier_info['name']}",
                    inline=True
                )
                
                embed.add_field(
                    name="Required Tier",
                    value="🗡️ Warlord or higher",
                    inline=True
                )
                
                embed.add_field(
                    name="What You Get",
                    value="Create factions, track faction statistics, and compete on faction leaderboards",
                    inline=False
                )
                
                embed.set_footer(text="Upgrade your tier to access this feature")
                
                await ctx.respond(embed=embed)
                return
            
            # Get factions collection
            factions_collection = await self.db.get_collection("factions")
            
            # Find all factions for this guild
            factions_query = {"guild_id": guild_id}
            factions_cursor = factions_collection.find(factions_query)
            factions = await factions_cursor.to_list(None)
            
            if not factions:
                await ctx.respond("❌ No factions found in this guild")
                return
            
            # Create the faction leaderboard embed
            embed = discord.Embed(
                title="👥 Faction Leaderboard",
                description=f"Faction statistics for {ctx.guild.name}",
                color=discord.Color.gold()
            )
            
            # Get players collection to get faction member stats
            players_collection = await self.db.get_collection("players")
            
            # Process each faction to get combined stats
            faction_stats = []
            
            for faction in factions:
                faction_id = faction["_id"]
                faction_name = faction.get("name", "Unknown Faction")
                faction_tag = faction.get("tag", "")
                faction_members = faction.get("member_ids", [])
                
                # Get all players in this faction
                if faction_members:
                    members_query = {"_id": {"$in": faction_members}}
                    members_cursor = players_collection.find(members_query)
                    members = await members_cursor.to_list(None)
                    
                    # Calculate combined stats
                    total_kills = sum(member.get("kills", 0) for member in members)
                    total_deaths = sum(member.get("deaths", 0) for member in members)
                    kd_ratio = total_kills / max(total_deaths, 1)
                    member_count = len(members)
                    
                    # Add to faction stats list
                    faction_stats.append({
                        "name": faction_name,
                        "tag": faction_tag,
                        "kills": total_kills,
                        "deaths": total_deaths,
                        "kd_ratio": kd_ratio,
                        "members": member_count
                    })
            
            # Sort factions by kills (or could use kd_ratio)
            faction_stats.sort(key=lambda x: x["kills"], reverse=True)
            
            # Add top factions to the embed
            if faction_stats:
                for i, faction in enumerate(faction_stats[:5]):  # Top 5 factions
                    embed.add_field(
                        name=f"{i+1}. {faction['name']} [{faction['tag']}]",
                        value=f"Members: {faction['members']}\nKills: {faction['kills']}\nDeaths: {faction['deaths']}\nK/D: {faction['kd_ratio']:.2f}",
                        inline=True
                    )
            
            # Add total faction count
            embed.set_footer(text=f"Total factions: {len(factions)} | Premium Feature")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error retrieving faction statistics: {e}")
            await ctx.respond(f"❌ Error retrieving faction statistics: {e}")