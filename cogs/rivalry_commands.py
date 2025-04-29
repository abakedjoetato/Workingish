import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timedelta
import traceback
from typing import Optional, List, Dict, Any, Union
import json

# Import database models and utilities
from database.connection import Database
from database.models import Server, Player, Kill
from utils.rivalry_tracking import update_rivalry_data, get_nemesis_data, get_prey_data, get_player_relationships
from utils.player_link import get_linked_player_for_user
from utils.decorators import server_exists, premium_server, guild_only
from utils.embeds import create_embed, format_timestamp

logger = logging.getLogger(__name__)

class RivalryCommands(commands.Cog):
    """Commands for player rivalry tracking (Prey/Nemesis system)"""
    
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("RivalryCommands cog loaded")
        
    def get_commands(self):
        """Return all commands this cog provides for help listings"""
        return [
            self.rivalry_group,
            self.update_rivalry,
            self.nemesis,
            self.prey,
            self.relationships
        ]
        
    # Command group for rivalry-related commands
    rivalry_group = discord.SlashCommandGroup(
        name="rivalry",
        description="Player rivalry tracking system (Nemesis/Prey)"
    )
    
    @rivalry_group.command(
        name="update",
        description="Update rivalry tracking data for a server [Premium Only]", contexts=[discord.InteractionContextType.guild],)
    @premium_server()
    @server_exists()
    async def update_rivalry(
        self, 
        ctx,
        days: discord.Option(int, "Number of days of data to analyze", required=False, default=7, min_value=1, max_value=30)
    ):
        """
        Update rivalry tracking data for a server
        
        This command analyzes recent kill data to determine each player's nemesis (player who kills them the most)
        and prey (player they kill the most). Premium servers can analyze up to 30 days of data.
        
        Usage: /rivalry update [days]
        """
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            server = await Server.get_by_guild_id(db, str(ctx.guild.id))
            
            if not server:
                await ctx.respond("No server configured for this Discord server. Use `/server add` first.", ephemeral=True)
                return
                
            # Start update process
            embed = create_embed(
                title="🔄 Updating Rivalry Data",
                description=f"Analyzing {days} days of kill data to identify nemesis and prey relationships.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Status", value="Processing...", inline=False)
            
            message = await ctx.respond(embed=embed)
            
            # Call the update function
            start_time = datetime.utcnow()
            result = await update_rivalry_data(str(server._id), days)
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            # Update the embed with results
            embed.title = "✅ Rivalry Data Updated"
            embed.description = f"Analysis of {days} days of kill data is complete."
            embed.set_field_at(
                0, 
                name="Results", 
                value=f"• **Total Players:** {result['total_players']}\n"
                      f"• **Updated Players:** {result['updated_players']}\n"
                      f"• **Time Period:** {format_timestamp(result['start_date'])} to {format_timestamp(result['end_date'])}\n"
                      f"• **Processing Time:** {processing_time:.2f} seconds",
                inline=False
            )
            
            await message.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in update_rivalry: {e}")
            traceback.print_exc()
            await ctx.respond(f"An error occurred: {str(e)}")
            
    @rivalry_group.command(
        name="nemesis",
        description="View nemesis information for a player [Premium Only]", 
        contexts=[discord.InteractionContextType.guild]
    )
    @premium_server()
    @server_exists()
    async def nemesis(
        self,
        ctx,
        player_name: discord.Option(str, "Player name to lookup (default: your linked player)", required=False) = None
    ):
        """
        View nemesis information for a player
        
        Your nemesis is the player who has killed you the most times.
        This command shows detailed information about your relationship with your nemesis.
        
        Usage: /rivalry nemesis [player_name]
        """
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            server = await Server.get_by_guild_id(db, str(ctx.guild.id))
            
            if not server:
                await ctx.respond("No server configured for this Discord server. Use `/server add` first.", ephemeral=True)
                return
            
            # Determine which player to look up
            player = None
            player_id = None
            
            if player_name:
                # Search for the player by name
                players_collection = db.get_collection("players")
                player_doc = await players_collection.find_one({"player_name": {"$regex": f"^{player_name}$", "$options": "i"}})
                if player_doc:
                    player_id = player_doc["player_id"]
            else:
                # Look up the player linked to this Discord user
                linked_player = await get_linked_player_for_user(ctx.author.id)
                if linked_player:
                    player_id = linked_player.player_id
                else:
                    await ctx.respond("You don't have a linked player. Either specify a player name or link your account first with `/player link`.", ephemeral=True)
                    return
            
            if not player_id:
                await ctx.respond(f"Player '{player_name}' not found in the database.", ephemeral=True)
                return
                
            # Get nemesis data
            nemesis_data = await get_nemesis_data(player_id, str(server._id))
            
            if not nemesis_data or not nemesis_data["nemesis_id"]:
                await ctx.respond(f"No nemesis found for {player_name or 'your linked player'}.", ephemeral=True)
                return
                
            # Create embed
            embed = create_embed(
                title=f"😈 Nemesis of {nemesis_data['player_name']}",
                description=f"**{nemesis_data['nemesis_name']}** has killed {nemesis_data['player_name']} {nemesis_data['nemesis_deaths']} times.",
                color=discord.Color.red()
            )
            
            # Add kill/death ratio
            embed.add_field(
                name="Kill/Death Ratio", 
                value=f"K/D: **{nemesis_data['kd_ratio']}**\n"
                      f"You've killed them: **{nemesis_data['player_kills']}** times\n"
                      f"They've killed you: **{nemesis_data['nemesis_deaths']}** times",
                inline=False
            )
            
            # Add favorite weapons
            if nemesis_data["favorite_weapons"]:
                weapon_text = "\n".join([f"• **{w['weapon']}**: {w['count']} kills" for w in nemesis_data["favorite_weapons"]])
                embed.add_field(name="Favorite Weapons", value=weapon_text, inline=True)
                
            # Add recent kills
            if nemesis_data["recent_kills"]:
                recent_text = "\n".join([
                    f"• {format_timestamp(k['timestamp'])}: {k['weapon']} ({int(k['distance'])}m)" 
                    for k in nemesis_data["recent_kills"][:5]
                ])
                embed.add_field(name="Recent Kills", value=recent_text, inline=True)
                
            # Add player stats
            embed.add_field(
                name="Player Stats", 
                value=f"**{nemesis_data['player_name']}**\n"
                      f"Kills: {nemesis_data['player_kills']}\n"
                      f"Deaths: {nemesis_data['nemesis_deaths']}",
                inline=True
            )
            
            # Add nemesis stats
            embed.add_field(
                name="Nemesis Stats", 
                value=f"**{nemesis_data['nemesis_name']}**\n"
                      f"Total Kills: {nemesis_data['nemesis_total_kills']}\n"
                      f"Total Deaths: {nemesis_data['nemesis_total_deaths']}",
                inline=True
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in nemesis: {e}")
            traceback.print_exc()
            await ctx.respond(f"An error occurred: {str(e)}")
            
    @rivalry_group.command(
        name="prey",
        description="View prey information for a player [Premium Only]", 
        contexts=[discord.InteractionContextType.guild]
    )
    @premium_server()
    @server_exists()
    async def prey(
        self,
        ctx,
        player_name: discord.Option(str, "Player name to lookup (default: your linked player)", required=False) = None
    ):
        """
        View prey information for a player
        
        Your prey is the player you have killed the most times.
        This command shows detailed information about your relationship with your prey.
        
        Usage: /rivalry prey [player_name]
        """
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            server = await Server.get_by_guild_id(db, str(ctx.guild.id))
            
            if not server:
                await ctx.respond("No server configured for this Discord server. Use `/server add` first.", ephemeral=True)
                return
            
            # Determine which player to look up
            player = None
            player_id = None
            
            if player_name:
                # Search for the player by name
                players_collection = db.get_collection("players")
                player_doc = await players_collection.find_one({"player_name": {"$regex": f"^{player_name}$", "$options": "i"}})
                if player_doc:
                    player_id = player_doc["player_id"]
            else:
                # Look up the player linked to this Discord user
                linked_player = await get_linked_player_for_user(ctx.author.id)
                if linked_player:
                    player_id = linked_player.player_id
                else:
                    await ctx.respond("You don't have a linked player. Either specify a player name or link your account first with `/player link`.", ephemeral=True)
                    return
            
            if not player_id:
                await ctx.respond(f"Player '{player_name}' not found in the database.", ephemeral=True)
                return
                
            # Get prey data
            prey_data = await get_prey_data(player_id, str(server._id))
            
            if not prey_data or not prey_data["prey_id"]:
                await ctx.respond(f"No prey found for {player_name or 'your linked player'}.", ephemeral=True)
                return
                
            # Create embed
            embed = create_embed(
                title=f"🎯 Prey of {prey_data['player_name']}",
                description=f"**{prey_data['player_name']}** has killed {prey_data['prey_name']} {prey_data['prey_kills']} times.",
                color=discord.Color.green()
            )
            
            # Add kill/death ratio
            embed.add_field(
                name="Kill/Death Ratio", 
                value=f"K/D: **{prey_data['kd_ratio']}**\n"
                      f"You've killed them: **{prey_data['prey_kills']}** times\n"
                      f"They've killed you: **{prey_data['prey_revenge_kills']}** times",
                inline=False
            )
            
            # Add favorite weapons
            if prey_data["favorite_weapons"]:
                weapon_text = "\n".join([f"• **{w['weapon']}**: {w['count']} kills" for w in prey_data["favorite_weapons"]])
                embed.add_field(name="Favorite Weapons", value=weapon_text, inline=True)
                
            # Add recent kills
            if prey_data["recent_kills"]:
                recent_text = "\n".join([
                    f"• {format_timestamp(k['timestamp'])}: {k['weapon']} ({int(k['distance'])}m)" 
                    for k in prey_data["recent_kills"][:5]
                ])
                embed.add_field(name="Recent Kills", value=recent_text, inline=True)
                
            # Add player stats
            embed.add_field(
                name="Hunter Stats", 
                value=f"**{prey_data['player_name']}**\n"
                      f"Kills: {prey_data['prey_kills']}\n"
                      f"Deaths: {prey_data['prey_revenge_kills']}",
                inline=True
            )
            
            # Add prey stats
            embed.add_field(
                name="Prey Stats", 
                value=f"**{prey_data['prey_name']}**\n"
                      f"Total Kills: {prey_data['prey_total_kills']}\n"
                      f"Total Deaths: {prey_data['prey_total_deaths']}",
                inline=True
            )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in prey: {e}")
            traceback.print_exc()
            await ctx.respond(f"An error occurred: {str(e)}")
            
    @rivalry_group.command(
        name="relationships",
        description="View kill relationships between a player and others [Premium Only]", 
        contexts=[discord.InteractionContextType.guild]
    )
    @premium_server()
    @server_exists()
    async def relationships(
        self,
        ctx,
        player_name: discord.Option(str, "Player name to lookup (default: your linked player)", required=False) = None,
        limit: discord.Option(int, "Maximum number of relationships to show", required=False, min_value=1, max_value=20) = 10
    ):
        """
        View kill relationships between a player and others
        
        This command shows a summary of players you've killed and players who have killed you.
        It also shows your prey and nemesis if available.
        
        Usage: /rivalry relationships [player_name] [limit]
        """
        await ctx.defer()
        
        try:
            db = await Database.get_instance()
            server = await Server.get_by_guild_id(db, str(ctx.guild.id))
            
            if not server:
                await ctx.respond("No server configured for this Discord server. Use `/server add` first.", ephemeral=True)
                return
                
            # Determine which player to look up
            player = None
            player_id = None
            
            if player_name:
                # Search for the player by name
                players_collection = db.get_collection("players")
                player_doc = await players_collection.find_one({"player_name": {"$regex": f"^{player_name}$", "$options": "i"}})
                if player_doc:
                    player_id = player_doc["player_id"]
            else:
                # Look up the player linked to this Discord user
                linked_player = await get_linked_player_for_user(ctx.author.id)
                if linked_player:
                    player_id = linked_player.player_id
                else:
                    await ctx.respond("You don't have a linked player. Either specify a player name or link your account first with `/player link`.", ephemeral=True)
                    return
                    
            if not player_id:
                await ctx.respond(f"Player '{player_name}' not found in the database.", ephemeral=True)
                return
                
            # Get relationship data
            rel_data = await get_player_relationships(player_id, str(server._id), limit)
            
            if not rel_data:
                await ctx.respond(f"No relationship data found for {player_name or 'your linked player'}.", ephemeral=True)
                return
                
            # Create embed
            embed = create_embed(
                title=f"🔄 Player Relationships for {rel_data['player_name']}",
                description=f"Summary of kills and deaths for {rel_data['player_name']} (Total Kills: {rel_data['total_kills']}, Total Deaths: {rel_data['total_deaths']})",
                color=discord.Color.gold()
            )
            
            # Add nemesis and prey info if available
            if rel_data["nemesis"]:
                nemesis = rel_data["nemesis"]
                embed.add_field(
                    name="😈 Nemesis",
                    value=f"**{nemesis['player_name']}** has killed you {nemesis['death_count']} times",
                    inline=True
                )
                
            if rel_data["prey"]:
                prey = rel_data["prey"]
                embed.add_field(
                    name="🎯 Prey",
                    value=f"You've killed **{prey['player_name']}** {prey['kill_count']} times",
                    inline=True
                )
                
            # Players you've killed
            if rel_data["killed_players"]:
                killed_text = "\n".join([
                    f"• **{p['player_name']}**: {p['kill_count']} kills ({p['most_used_weapon']})" 
                    for p in rel_data["killed_players"][:5]
                ])
                embed.add_field(name="Players You've Killed", value=killed_text, inline=False)
                
            # Players who've killed you
            if rel_data["killed_by_players"]:
                killed_by_text = "\n".join([
                    f"• **{p['player_name']}**: {p['death_count']} deaths ({p['most_used_weapon']})" 
                    for p in rel_data["killed_by_players"][:5]
                ])
                embed.add_field(name="Players Who've Killed You", value=killed_by_text, inline=False)
                
            # Add pagination if there are more results
            killed_count = len(rel_data["killed_players"])
            killed_by_count = len(rel_data["killed_by_players"])
                
            if killed_count > 5 or killed_by_count > 5:
                more_text = []
                if killed_count > 5:
                    more_text.append(f"{killed_count - 5} more players killed")
                if killed_by_count > 5:
                    more_text.append(f"{killed_by_count - 5} more killers")
                    
                embed.set_footer(text=f"Showing top 5 results. {' and '.join(more_text)} not shown. Use a higher limit to see more.")
                
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in relationships: {e}")
            traceback.print_exc()
            await ctx.respond(f"An error occurred: {str(e)}", ephemeral=True)
            
def setup(bot):
    """Add the cog to the bot directly"""
    bot.add_cog(RivalryCommands(bot))