"""
Analytics Commands Module

This module provides Discord slash commands for accessing server and player analytics.
"""

import discord
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from database.connection import Database
from database.models import Server, Player
from utils.embeds import create_embed, error_embed
from utils.analytics import AnalyticsService
# Use Discord's ApplicationContext for slash commands
from discord.commands import ApplicationContext
from utils.decorators import premium_server, server_exists

logger = logging.getLogger('deadside_bot.cogs.analytics')

class AnalyticsCog(commands.Cog):
    """Analytics commands for Deadside statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        
    analytics = SlashCommandGroup(
        "analytics", 
        "Advanced statistics and analytics commands",
        default_member_permissions=None,
        guild_only=True
    )
    
    @analytics.command(name="server", description="Get detailed server analytics and statistics")
    @server_exists()
    @premium_server(tier=1)  # Warlord tier
    async def server_analytics(
        self, 
        ctx: ApplicationContext, 
        time_period: Option(int, "Time period in days", choices=[1, 7, 14, 30], default=7),
        server_index: Option(int, "Index of server to use (if guild has multiple servers)", default=1)
    ):
        """Get detailed server analytics and statistics"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Get server for this guild
            servers = await Server.get_by_guild(db, str(ctx.guild.id))
            if not servers:
                return await ctx.respond(embed=error_embed(
                    "No Server Found", 
                    "This Discord server doesn't have any game servers configured."
                ))
            
            # Validate server index
            if server_index < 1 or server_index > len(servers):
                return await ctx.respond(embed=error_embed(
                    "Invalid Server Index",
                    f"Please provide a server index between 1 and {len(servers)}."
                ))
            
            # Adjust index for zero-based list
            server = servers[server_index - 1]
            
            # Get server analytics
            analytics = await AnalyticsService.get_server_stats(str(server._id), time_period)
            
            # Create embed with analytics data
            embed = create_embed(
                title=f"Server Analytics: {server.name}",
                description=f"Statistics for the past {time_period} days",
                color=discord.Color.blue()
            )
            
            # Add general stats
            embed.add_field(
                name="General Stats",
                value=f"Total Kills: **{analytics['total_kills']}**\n"
                      f"Player Deaths: **{analytics['total_kills'] - analytics['suicide_count']}**\n"
                      f"Suicides: **{analytics['suicide_count']}**\n"
                      f"Unique Players: **{analytics['unique_players']}**\n"
                      f"Player Joins: **{analytics['player_joins']}**\n"
                      f"Player Leaves: **{analytics['player_leaves']}**",
                inline=True
            )
            
            # Add weapon stats
            weapon_text = ""
            for weapon in analytics['top_weapons']:
                weapon_text += f"{weapon['name']}: **{weapon['count']}**\n"
                
            if not weapon_text:
                weapon_text = "No weapon data available"
                
            embed.add_field(
                name="Top Weapons",
                value=weapon_text,
                inline=True
            )
            
            # Add activity stats
            activity_text = ""
            for hour in analytics['most_active_hours']:
                # Convert 24h format to 12h format for readability
                hour_12h = hour['hour'] % 12
                if hour_12h == 0:
                    hour_12h = 12
                    
                am_pm = "AM" if hour['hour'] < 12 else "PM"
                activity_text += f"{hour_12h} {am_pm}: **{hour['count']} kills**\n"
                
            if not activity_text:
                activity_text = "No activity data available"
                
            embed.add_field(
                name="Most Active Hours",
                value=activity_text,
                inline=True
            )
            
            # Add combat stats
            embed.add_field(
                name="Combat Stats",
                value=f"Average Kill Distance: **{analytics['avg_kill_distance']}m**",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in server_analytics: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching server analytics: {str(e)}"
            ))
    
    @analytics.command(name="player", description="Get detailed player analytics and statistics")
    @server_exists()
    @premium_server(tier=1)  # Warlord tier
    async def player_analytics(
        self, 
        ctx: ApplicationContext, 
        player_name: Option(str, "Player name to search for (partial name search supported)"),
        time_period: Option(int, "Time period in days", choices=[1, 7, 14, 30], default=7),
        server_index: Option(int, "Index of server to use (if guild has multiple servers)", default=1)
    ):
        """Get detailed player analytics and statistics"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Get server for this guild
            servers = await Server.get_by_guild(db, str(ctx.guild.id))
            if not servers:
                return await ctx.respond(embed=error_embed(
                    "No Server Found", 
                    "This Discord server doesn't have any game servers configured."
                ))
            
            # Validate server index
            if server_index < 1 or server_index > len(servers):
                return await ctx.respond(embed=error_embed(
                    "Invalid Server Index",
                    f"Please provide a server index between 1 and {len(servers)}."
                ))
            
            # Adjust index for zero-based list
            server = servers[server_index - 1]
            
            # Find player by name (partial match)
            players_collection = await db.get_collection("players")
            regex_pattern = {"$regex": f".*{player_name}.*", "$options": "i"}
            cursor = players_collection.find({"player_name": regex_pattern})
            player_docs = await cursor.to_list(None)
            
            if not player_docs:
                return await ctx.respond(embed=error_embed(
                    "Player Not Found",
                    f"No players found with name containing '{player_name}'."
                ))
            
            # If multiple matches, show selection
            if len(player_docs) > 1:
                selection_text = "Multiple players found. Please use one of these IDs with the `/analytics player_by_id` command:\n\n"
                
                for i, doc in enumerate(player_docs[:10]):  # Limit to top 10
                    player = Player(**{**doc, "_id": doc.get("_id")})
                    selection_text += f"**{i+1}.** {player.player_name} (ID: `{player.player_id}`)\n"
                    
                if len(player_docs) > 10:
                    selection_text += f"\n_...and {len(player_docs) - 10} more matches_"
                
                embed = create_embed(
                    title="Multiple Players Found",
                    description=selection_text,
                    color=discord.Color.gold()
                )
                
                return await ctx.respond(embed=embed)
            
            # Get player ID
            player_doc = player_docs[0]
            player_id = player_doc["player_id"]
            
            # Get player analytics
            analytics = await AnalyticsService.get_player_analytics(player_id, time_period)
            
            # Create embed
            embed = create_embed(
                title=f"Player Analytics: {analytics['player_name']}",
                description=f"Statistics for the past {time_period} days",
                color=discord.Color.blue()
            )
            
            # Add general stats
            embed.add_field(
                name="Performance Stats",
                value=f"Kills: **{analytics['total_kills']}**\n"
                      f"Deaths: **{analytics['total_deaths']}**\n"
                      f"K/D Ratio: **{analytics['kd_ratio']}**\n"
                      f"Suicides: **{analytics['suicide_count']}**\n"
                      f"Average Kill Distance: **{analytics['avg_kill_distance']}m**",
                inline=True
            )
            
            # Add weapon stats
            weapon_text = ""
            for weapon in analytics['favorite_weapons']:
                weapon_text += f"{weapon['name']}: **{weapon['count']}**\n"
                
            if not weapon_text:
                weapon_text = "No weapon data available"
                
            embed.add_field(
                name="Favorite Weapons",
                value=weapon_text,
                inline=True
            )
            
            # Add activity hours
            activity_text = ""
            for hour in analytics['active_hours']:
                # Convert 24h format to 12h format for readability
                hour_12h = hour['hour'] % 12
                if hour_12h == 0:
                    hour_12h = 12
                    
                am_pm = "AM" if hour['hour'] < 12 else "PM"
                activity_text += f"{hour_12h} {am_pm}: **{hour['count']} kills**\n"
                
            if not activity_text:
                activity_text = "No activity data available"
                
            embed.add_field(
                name="Active Hours",
                value=activity_text,
                inline=True
            )
            
            # Add nemesis/prey
            nemesis_text = "None"
            if analytics['nemesis']['id']:
                nemesis_text = f"{analytics['nemesis']['name']} (Deaths: **{analytics['nemesis']['deaths']}**)"
                
            prey_text = "None"
            if analytics['prey']['id']:
                prey_text = f"{analytics['prey']['name']} (Kills: **{analytics['prey']['kills']}**)"
            
            embed.add_field(
                name="Rivalry Info",
                value=f"Nemesis: {nemesis_text}\nPrey: {prey_text}",
                inline=False
            )
            
            # Add frequent victims
            victims_text = ""
            for victim in analytics['frequent_victims']:
                victims_text += f"{victim['name']}: **{victim['count']} kills**\n"
                
            if not victims_text:
                victims_text = "No frequent victims"
                
            embed.add_field(
                name="Frequent Victims",
                value=victims_text,
                inline=True
            )
            
            # Add frequent killers
            killers_text = ""
            for killer in analytics['frequent_killers']:
                killers_text += f"{killer['name']}: **{killer['count']} kills**\n"
                
            if not killers_text:
                killers_text = "No frequent killers"
                
            embed.add_field(
                name="Frequent Killers",
                value=killers_text,
                inline=True
            )
            
            # Add improvement information
            improvement_text = f"Performance Change: **{analytics['improvement_percentage']}%**"
            
            if analytics['is_improving']:
                improvement_text += " 📈"
            else:
                improvement_text += " 📉"
                
            embed.add_field(
                name="Improvement Trend",
                value=improvement_text,
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in player_analytics: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching player analytics: {str(e)}"
            ))
    
    @analytics.command(name="player_by_id", description="Get player analytics using exact Steam ID")
    @server_exists()
    @premium_server(tier=1)  # Warlord tier
    async def player_analytics_by_id(
        self, 
        ctx: ApplicationContext, 
        player_id: Option(str, "Steam ID of the player"),
        time_period: Option(int, "Time period in days", choices=[1, 7, 14, 30], default=7)
    ):
        """Get detailed player analytics and statistics using exact Steam ID"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Check if player exists
            player = await Player.get_by_player_id(db, player_id)
            if not player:
                return await ctx.respond(embed=error_embed(
                    "Player Not Found",
                    f"No player found with ID '{player_id}'."
                ))
            
            # Get player analytics
            analytics = await AnalyticsService.get_player_analytics(player_id, time_period)
            
            # Create embed
            embed = create_embed(
                title=f"Player Analytics: {analytics['player_name']}",
                description=f"Statistics for the past {time_period} days",
                color=discord.Color.blue()
            )
            
            # Add general stats
            embed.add_field(
                name="Performance Stats",
                value=f"Kills: **{analytics['total_kills']}**\n"
                      f"Deaths: **{analytics['total_deaths']}**\n"
                      f"K/D Ratio: **{analytics['kd_ratio']}**\n"
                      f"Suicides: **{analytics['suicide_count']}**\n"
                      f"Average Kill Distance: **{analytics['avg_kill_distance']}m**",
                inline=True
            )
            
            # Add weapon stats
            weapon_text = ""
            for weapon in analytics['favorite_weapons']:
                weapon_text += f"{weapon['name']}: **{weapon['count']}**\n"
                
            if not weapon_text:
                weapon_text = "No weapon data available"
                
            embed.add_field(
                name="Favorite Weapons",
                value=weapon_text,
                inline=True
            )
            
            # Add activity hours
            activity_text = ""
            for hour in analytics['active_hours']:
                # Convert 24h format to 12h format for readability
                hour_12h = hour['hour'] % 12
                if hour_12h == 0:
                    hour_12h = 12
                    
                am_pm = "AM" if hour['hour'] < 12 else "PM"
                activity_text += f"{hour_12h} {am_pm}: **{hour['count']} kills**\n"
                
            if not activity_text:
                activity_text = "No activity data available"
                
            embed.add_field(
                name="Active Hours",
                value=activity_text,
                inline=True
            )
            
            # Add nemesis/prey
            nemesis_text = "None"
            if analytics['nemesis']['id']:
                nemesis_text = f"{analytics['nemesis']['name']} (Deaths: **{analytics['nemesis']['deaths']}**)"
                
            prey_text = "None"
            if analytics['prey']['id']:
                prey_text = f"{analytics['prey']['name']} (Kills: **{analytics['prey']['kills']}**)"
            
            embed.add_field(
                name="Rivalry Info",
                value=f"Nemesis: {nemesis_text}\nPrey: {prey_text}",
                inline=False
            )
            
            # Add frequent victims
            victims_text = ""
            for victim in analytics['frequent_victims']:
                victims_text += f"{victim['name']}: **{victim['count']} kills**\n"
                
            if not victims_text:
                victims_text = "No frequent victims"
                
            embed.add_field(
                name="Frequent Victims",
                value=victims_text,
                inline=True
            )
            
            # Add frequent killers
            killers_text = ""
            for killer in analytics['frequent_killers']:
                killers_text += f"{killer['name']}: **{killer['count']} kills**\n"
                
            if not killers_text:
                killers_text = "No frequent killers"
                
            embed.add_field(
                name="Frequent Killers",
                value=killers_text,
                inline=True
            )
            
            # Add improvement information
            improvement_text = f"Performance Change: **{analytics['improvement_percentage']}%**"
            
            if analytics['is_improving']:
                improvement_text += " 📈"
            else:
                improvement_text += " 📉"
                
            embed.add_field(
                name="Improvement Trend",
                value=improvement_text,
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in player_analytics_by_id: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching player analytics: {str(e)}"
            ))
    
    @analytics.command(name="leaderboard", description="Get server leaderboard with various sorting options")
    @server_exists()
    async def leaderboard(
        self, 
        ctx: ApplicationContext, 
        sort_by: Option(str, "Stat to sort by", choices=["kills", "kd", "distance"], default="kills"),
        time_period: Option(int, "Time period in days (0 for all-time)", choices=[0, 1, 7, 14, 30], default=7),
        server_index: Option(int, "Index of server to use (if guild has multiple servers)", default=1)
    ):
        """Get server leaderboard with various sorting options"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Get server for this guild
            servers = await Server.get_by_guild(db, str(ctx.guild.id))
            if not servers:
                return await ctx.respond(embed=error_embed(
                    "No Server Found", 
                    "This Discord server doesn't have any game servers configured."
                ))
            
            # Validate server index
            if server_index < 1 or server_index > len(servers):
                return await ctx.respond(embed=error_embed(
                    "Invalid Server Index",
                    f"Please provide a server index between 1 and {len(servers)}."
                ))
            
            # Adjust index for zero-based list
            server = servers[server_index - 1]
            
            # Get leaderboard data
            time_param = None if time_period == 0 else time_period
            leaderboard = await AnalyticsService.get_leaderboard(str(server._id), sort_by, 10, time_param)
            
            # Create title based on sort and time period
            title = f"Leaderboard: {server.name}"
            if sort_by == "kills":
                title += " (by Kills)"
            elif sort_by == "kd":
                title += " (by K/D Ratio)"
            elif sort_by == "distance":
                title += " (by Avg Distance)"
                
            if time_period == 0:
                description = "All-time stats"
            else:
                description = f"Stats for the past {time_period} days"
            
            # Create embed
            embed = create_embed(
                title=title,
                description=description,
                color=discord.Color.gold()
            )
            
            # Add leaderboard entries
            leaderboard_text = ""
            for i, entry in enumerate(leaderboard):
                # Add emoji for top 3
                prefix = ""
                if i == 0:
                    prefix = "🥇 "
                elif i == 1:
                    prefix = "🥈 "
                elif i == 2:
                    prefix = "🥉 "
                else:
                    prefix = f"**{i+1}.** "
                
                # Format entry based on sort type
                entry_text = f"{prefix}{entry['player_name']}: "
                
                if sort_by == "kills":
                    entry_text += f"**{entry['kills']} kills**, {entry['deaths']} deaths, K/D {entry['kd_ratio']}"
                elif sort_by == "kd":
                    entry_text += f"**K/D {entry['kd_ratio']}**, {entry['kills']} kills, {entry['deaths']} deaths"
                elif sort_by == "distance":
                    entry_text += f"**{entry.get('avg_distance', 0)}m avg**, {entry['kills']} kills"
                
                leaderboard_text += f"{entry_text}\n"
            
            if not leaderboard_text:
                leaderboard_text = "No player data available for this time period"
                
            embed.add_field(
                name="Top Players",
                value=leaderboard_text,
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in leaderboard: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching leaderboard data: {str(e)}"
            ))
    
    @analytics.command(name="faction", description="Get detailed faction analytics")
    @server_exists()
    @premium_server(tier=1)  # Warlord tier
    async def faction_analytics(
        self, 
        ctx: ApplicationContext, 
        faction_id: Option(str, "ID of the faction"),
        time_period: Option(int, "Time period in days", choices=[1, 7, 14, 30], default=7)
    ):
        """Get detailed analytics for a specific faction"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Get faction analytics
            analytics = await AnalyticsService.get_faction_analytics(faction_id, time_period)
            
            if "error" in analytics:
                return await ctx.respond(embed=error_embed(
                    "Faction Not Found",
                    analytics["error"]
                ))
            
            # Create embed
            embed = create_embed(
                title=f"Faction Analytics: {analytics['faction_name']}",
                description=f"Statistics for the past {time_period} days",
                color=discord.Color.dark_green()
            )
            
            # Add general stats
            embed.add_field(
                name="Faction Stats",
                value=f"Members: **{analytics['member_count']}**\n"
                      f"Total Kills: **{analytics['total_kills']}**\n"
                      f"Total Deaths: **{analytics['total_deaths']}**\n"
                      f"K/D Ratio: **{analytics['kd_ratio']}**\n"
                      f"Avg Kill Distance: **{analytics['avg_kill_distance']}m**",
                inline=True
            )
            
            # Add top performers
            performers_text = ""
            for player in analytics['top_performers']:
                performers_text += f"{player['player_name']}: **{player['kills']} kills**, K/D {player['kd_ratio']}\n"
                
            if not performers_text:
                performers_text = "No performer data available"
                
            embed.add_field(
                name="Top Members",
                value=performers_text,
                inline=True
            )
            
            # Add top weapons
            weapons_text = ""
            for weapon in analytics['top_weapons']:
                weapons_text += f"{weapon['name']}: **{weapon['count']}**\n"
                
            if not weapons_text:
                weapons_text = "No weapon data available"
                
            embed.add_field(
                name="Faction Weapons",
                value=weapons_text,
                inline=True
            )
            
            # Add faction rivalries
            rivals_text = ""
            for rival in analytics['rivalries']:
                rivals_text += f"**{rival['faction_name']}**: "
                rivals_text += f"{rival['kills_against']} kills, {rival['deaths_to']} deaths, K/D {rival['kd_ratio']}\n"
                
            if not rivals_text:
                rivals_text = "No rivalry data available"
                
            embed.add_field(
                name="Faction Rivalries",
                value=rivals_text,
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in faction_analytics: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching faction analytics: {str(e)}"
            ))
    
    @analytics.command(name="factions", description="List all factions for easy reference")
    @server_exists()
    @premium_server(tier=1)  # Warlord tier
    async def list_factions(self, ctx: ApplicationContext):
        """List all factions for easy reference"""
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            
            # Get factions from database
            factions_collection = await db.get_collection("factions")
            cursor = factions_collection.find()
            factions = await cursor.to_list(None)
            
            if not factions:
                return await ctx.respond(embed=error_embed(
                    "No Factions",
                    "No factions have been created yet."
                ))
            
            # Create embed
            embed = create_embed(
                title="All Factions",
                description="Use these faction IDs with the `/analytics faction` command",
                color=discord.Color.dark_green()
            )
            
            # Add factions to embed
            factions_text = ""
            for faction in factions:
                factions_text += f"**{faction['name']}** (ID: `{faction['_id']}`)\n"
                
            embed.add_field(
                name="Available Factions",
                value=factions_text,
                inline=False
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in list_factions: {e}")
            await ctx.respond(embed=error_embed(
                "Error", 
                f"An error occurred while fetching factions: {str(e)}"
            ))

def setup(bot):
    bot.add_cog(AnalyticsCog(bot))