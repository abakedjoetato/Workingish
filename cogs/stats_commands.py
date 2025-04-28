import discord
from discord.ext import commands
import logging
from database.connection import Database
from database.models import Server, Player, Kill
from utils.embeds import create_player_stats_embed, create_server_stats_embed
from bson import ObjectId

logger = logging.getLogger('deadside_bot.cogs.stats')

# Define the slash command group outside the class first
stats_group = discord.SlashCommandGroup(
    name="stats",
    description="Commands for viewing player and server statistics"
)

class StatsCommands(commands.Cog):
    """Commands for viewing player and server statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("StatsCommands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            logger.debug("Set database for StatsCommands cog from bot")
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [stats_group]
    
    @stats_group.command(name="player", description="View statistics for a specific player")
    async def player_stats(self, ctx, 
                          player_name: discord.Option(str, "The player name to look up", required=True)):
        """
        View statistics for a specific player
        
        Usage: /stats player <player_name>
        """
        try:
            db = await Database.get_instance()
            
            # Find player by name (case-insensitive)
            collection = await db.get_collection("players")
            cursor = collection.find({
                "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
            })
            players = await cursor.to_list(None)
            
            if not players:
                await ctx.respond(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
                return
            
            # Process each matching player
            for player_data in players:
                player = Player(**{**player_data, "_id": player_data["_id"]})
                
                # Get additional stats
                player_stats = await self.get_player_extended_stats(db, player.player_id)
                
                # Check if this is a main or alt character and modify display accordingly
                embed = await create_player_stats_embed(player, player_stats)
                
                # Check if this player is a main character (has alts)
                if hasattr(player, 'alt_player_ids') and player.alt_player_ids:
                    # This is a main character, get its alts
                    alt_names = []
                    alt_kills = 0
                    alt_deaths = 0
                    
                    for alt_id in player.alt_player_ids:
                        alt_data = await collection.find_one({"_id": ObjectId(alt_id)})
                        if alt_data:
                            alt_player = Player(**{**alt_data, "_id": alt_data["_id"]})
                            alt_names.append(alt_player.player_name)
                            alt_kills += alt_player.total_kills
                            alt_deaths += alt_player.total_deaths
                    
                    # Update the embed title to show this is a main character
                    embed.title = f"🌟 {player.player_name} (Main Character)"
                    
                    # Add alt characters field
                    if alt_names:
                        embed.add_field(
                            name="Alt Characters", 
                            value=", ".join(alt_names),
                            inline=False
                        )
                        
                        # Calculate combined stats
                        total_kills = player.total_kills + alt_kills
                        total_deaths = player.total_deaths + alt_deaths
                        kd_ratio = total_kills / max(1, total_deaths)
                        
                        embed.add_field(
                            name="Combined Stats (All Characters)",
                            value=f"Kills: **{total_kills}**\n" +
                                  f"Deaths: **{total_deaths}**\n" +
                                  f"K/D Ratio: **{kd_ratio:.2f}**",
                            inline=False
                        )
                        
                # Check if this player is an alt character (has a main)
                elif hasattr(player, 'main_player_id') and player.main_player_id:
                    # This is an alt character, get its main
                    main_data = await collection.find_one({"_id": ObjectId(player.main_player_id)})
                    if main_data:
                        main_player = Player(**{**main_data, "_id": main_data["_id"]})
                        
                        # Update the embed to show this is an alt character
                        embed.title = f"{player.player_name} (Alt of {main_player.player_name})"
                        
                        embed.add_field(
                            name="Main Character",
                            value=f"{main_player.player_name}",
                            inline=False
                        )
                
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="me", description="View your own statistics if linked to a player")
    async def my_stats(self, ctx):
        """View your own statistics (if your Discord account is linked to a player)"""
        try:
            db = await Database.get_instance()
            
            # Find players linked to this Discord user
            players = await Player.get_by_discord_id(db, str(ctx.author.id))
            
            if not players:
                await ctx.respond("⚠️ Your Discord account is not linked to any players. Use `/stats link <player_name>` to link your account.")
                return
            
            # Find main characters first
            mains = []
            alts = []
            standalone = []
            
            for player in players:
                # Check if this player is a main (has alts)
                has_alts = hasattr(player, 'alt_player_ids') and player.alt_player_ids
                # Check if this player is an alt (has a main)
                has_main = hasattr(player, 'main_player_id') and player.main_player_id
                
                if has_alts:
                    mains.append(player)
                elif has_main:
                    alts.append(player)
                else:
                    standalone.append(player)
            
            # Display main characters first with combined stats
            for main in mains:
                # Get additional stats for main
                main_stats = await self.get_player_extended_stats(db, main.player_id)
                
                # Get all alts of this main
                character_alts = []
                total_kills = main.total_kills
                total_deaths = main.total_deaths
                
                if hasattr(main, 'alt_player_ids') and main.alt_player_ids:
                    for alt_id in main.alt_player_ids:
                        alt_player = next((p for p in players if str(p._id) == alt_id), None)
                        if alt_player:
                            character_alts.append(alt_player)
                            total_kills += alt_player.total_kills
                            total_deaths += alt_player.total_deaths
                
                # Create combined stats embed
                embed = await create_player_stats_embed(main, main_stats)
                
                # Modify embed to show this is a main character
                embed.title = f"🌟 {main.player_name} (Main Character)"
                
                # Add combined stats if there are alts
                if character_alts:
                    kd_ratio = total_kills / max(1, total_deaths)
                    
                    alt_names = [alt.player_name for alt in character_alts]
                    embed.add_field(
                        name="Alt Characters",
                        value=", ".join(alt_names),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Combined Stats (All Characters)",
                        value=f"Kills: **{total_kills}**\n" +
                              f"Deaths: **{total_deaths}**\n" +
                              f"K/D Ratio: **{kd_ratio:.2f}**",
                        inline=False
                    )
                
                embed.set_footer(text="Use /stats linkalt to connect more alt characters to your main")
                await ctx.respond(embed=embed)
            
            # Skip alts since they're shown with the main
            
            # Show standalone characters
            for player in standalone:
                # Get additional stats
                player_stats = await self.get_player_extended_stats(db, player.player_id)
                
                # Create and send embed
                embed = await create_player_stats_embed(player, player_stats)
                
                # Add note about setting as main
                embed.add_field(
                    name="Character Management",
                    value=f"Make this your main: `/stats setmain {player.player_name}`\n" +
                          f"Use main characters to track stats across multiple alts.",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting self stats: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
            
    @stats_group.command(name="link", description="Link your Discord account to a game character")
    async def link_player(self, ctx, 
                         player_name: discord.Option(str, "Name of your character in-game", required=True)):
        """
        Link your Discord account to a game character
        
        Usage: /stats link <player_name>
        
        This allows you to use /stats me to quickly view your own statistics.
        You can link multiple characters if you have alts.
        """
        try:
            db = await Database.get_instance()
            
            # Find player by name (case-insensitive)
            collection = await db.get_collection("players")
            cursor = collection.find({
                "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
            })
            players = await cursor.to_list(None)
            
            if not players:
                await ctx.respond(f"⚠️ Player '{player_name}' not found. The name must match exactly how it appears in-game.")
                return
            
            # Check if player is already linked to someone else
            player = Player(**{**players[0], "_id": players[0]["_id"]})
            if player.discord_id and player.discord_id != str(ctx.author.id):
                await ctx.respond(f"⚠️ Character '{player.player_name}' is already linked to another Discord user. Please contact an admin if you believe this is an error.")
                return
                
            # Update player with Discord ID
            player.discord_id = str(ctx.author.id)
            await player.update(db)
            
            # Create confirmation embed with emerald theme
            embed = discord.Embed(
                title="Character Linked Successfully",
                description=f"Your Discord account has been linked to **{player.player_name}**",
                color=0x50C878  # Emerald green
            )
            embed.add_field(
                name="Stats Overview",
                value=f"Kills: **{player.total_kills}**\nDeaths: **{player.total_deaths}**"
            )
            embed.add_field(
                name="Quick Access",
                value="Use `/stats me` to quickly view your statistics"
            )
            embed.set_footer(text="You can link multiple characters if you play with alts")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error linking player: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
            
    @stats_group.command(name="unlink", description="Unlink a character from your Discord account")
    async def unlink_player(self, ctx,
                           player_name: discord.Option(str, "Name of character to unlink (leave empty to show all linked characters)", required=False) = None):
        """
        Unlink a character from your Discord account
        
        Usage: /stats unlink [player_name]
        
        If no player name is provided, shows all your linked characters
        """
        try:
            db = await Database.get_instance()
            
            # Get all linked players first
            players = await Player.get_by_discord_id(db, str(ctx.author.id))
            
            if not players:
                await ctx.respond("❓ You don't have any linked characters.")
                return
                
            if player_name:
                # Find the specific player to unlink
                player_to_unlink = next((p for p in players if p.player_name.lower() == player_name.lower()), None)
                
                if not player_to_unlink:
                    await ctx.respond(f"⚠️ You don't have a character named '{player_name}' linked to your account.")
                    return
                
                # Update player to remove Discord ID
                player_to_unlink.discord_id = None
                
                # Also remove any main/alt relationships
                player_collection = await db.get_collection("players")
                await player_collection.update_one(
                    {"_id": player_to_unlink._id},
                    {"$unset": {"main_player_id": "", "alt_player_ids": ""}}
                )
                
                # Remove this player from other characters' alt lists
                await player_collection.update_many(
                    {"alt_player_ids": {"$in": [str(player_to_unlink._id)]}},
                    {"$pull": {"alt_player_ids": str(player_to_unlink._id)}}
                )
                
                await player_to_unlink.update(db)
                
                await ctx.respond(f"✅ Successfully unlinked character '{player_to_unlink.player_name}' from your Discord account.")
            else:
                # Show all linked characters with main/alt relationships
                embed = discord.Embed(
                    title="Your Linked Characters",
                    description=f"You have {len(players)} linked character(s)",
                    color=0x50C878  # Emerald green
                )
                
                # Group characters by main/alt relationship
                mains = []
                alts = []
                standalone = []
                
                for player in players:
                    # Check if this player is a main (has alts)
                    has_alts = hasattr(player, 'alt_player_ids') and player.alt_player_ids
                    # Check if this player is an alt (has a main)
                    has_main = hasattr(player, 'main_player_id') and player.main_player_id
                    
                    if has_alts:
                        mains.append(player)
                    elif has_main:
                        alts.append(player)
                    else:
                        standalone.append(player)
                
                # Add main characters first with their alts
                for main in mains:
                    # Get alt names if available
                    alt_names = []
                    if hasattr(main, 'alt_player_ids') and main.alt_player_ids:
                        for alt_id in main.alt_player_ids:
                            alt_player = next((p for p in players if str(p._id) == alt_id), None)
                            if alt_player:
                                alt_names.append(alt_player.player_name)
                    
                    alt_list = f"\nAlts: {', '.join(alt_names)}" if alt_names else ""
                    
                    embed.add_field(
                        name=f"🌟 {main.player_name} (Main)",
                        value=f"Kills: {main.total_kills}\nDeaths: {main.total_deaths}{alt_list}\n" +
                              f"Unlink: `/stats unlink {main.player_name}`",
                        inline=False
                    )
                
                # Add standalone characters
                for player in standalone:
                    embed.add_field(
                        name=player.player_name,
                        value=f"Kills: {player.total_kills}\nDeaths: {player.total_deaths}\n" +
                              f"Unlink: `/stats unlink {player.player_name}`\n" +
                              f"Make main: `/stats setmain {player.player_name}`",
                        inline=True
                    )
                
                embed.set_footer(text="Use /stats unlink <name> to unlink a specific character")
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error unlinking player: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="setmain", description="Set one of your characters as your main character")
    async def set_main_character(self, ctx,
                               player_name: discord.Option(str, "Name of character to set as your main", required=True)):
        """
        Designate one of your linked characters as your main character
        
        Usage: /stats setmain <player_name>
        
        Setting a main character allows you to link alt characters to it.
        This is useful for tracking combined statistics across all your characters.
        """
        try:
            db = await Database.get_instance()
            
            # Get all linked players first
            players = await Player.get_by_discord_id(db, str(ctx.author.id))
            
            if not players:
                await ctx.respond("❓ You don't have any linked characters. Use `/stats link <player_name>` first.")
                return
                
            # Find the specific player to set as main
            player_to_set = next((p for p in players if p.player_name.lower() == player_name.lower()), None)
            
            if not player_to_set:
                await ctx.respond(f"⚠️ You don't have a character named '{player_name}' linked to your account.")
                return
            
            # Check if this player is already an alt of another character
            if hasattr(player_to_set, 'main_player_id') and player_to_set.main_player_id:
                # Find the main player
                player_collection = await db.get_collection("players")
                main_data = await player_collection.find_one({"_id": ObjectId(player_to_set.main_player_id)})
                
                if main_data:
                    main_player = Player(**{**main_data, "_id": main_data["_id"]})
                    await ctx.respond(f"⚠️ '{player_name}' is already an alt of '{main_player.player_name}'. "
                                     f"You must first unlink it using `/stats unlink {player_name}`.")
                    return
            
            # Get current main characters
            mains = [p for p in players if hasattr(p, 'alt_player_ids') and p.alt_player_ids]
            
            # If we already have another main, ask for confirmation
            if mains and str(mains[0]._id) != str(player_to_set._id):
                # There's another main already, clear its alt list
                player_collection = await db.get_collection("players")
                for main in mains:
                    # Reset the old main's alt list
                    await player_collection.update_one(
                        {"_id": main._id},
                        {"$unset": {"alt_player_ids": ""}}
                    )
            
            # Set this player as a main (with empty alt list to start)
            player_collection = await db.get_collection("players")
            await player_collection.update_one(
                {"_id": player_to_set._id},
                {"$set": {"alt_player_ids": []}, "$unset": {"main_player_id": ""}}
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title="Main Character Set",
                description=f"**{player_to_set.player_name}** is now your main character",
                color=0x50C878  # Emerald green
            )
            
            embed.add_field(
                name="What This Means",
                value="You can now link your alt characters to this main character\n" +
                      "This helps with tracking your combined statistics",
                inline=False
            )
            
            embed.add_field(
                name="Next Steps",
                value="Use `/stats linkalt <alt_name>` to link your alt characters to this main",
                inline=False
            )
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error setting main character: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="linkalt", description="Link an alt character to your main character")
    async def link_alt_character(self, ctx,
                               alt_name: discord.Option(str, "Name of character to set as an alt", required=True)):
        """
        Link an alt character to your main character
        
        Usage: /stats linkalt <alt_name>
        
        The character must already be linked to your Discord account.
        You must have already set a main character using /stats setmain.
        """
        try:
            db = await Database.get_instance()
            
            # Get all linked players first
            players = await Player.get_by_discord_id(db, str(ctx.author.id))
            
            if not players:
                await ctx.respond("❓ You don't have any linked characters. Use `/stats link <player_name>` first.")
                return
            
            # Find the alt to link
            alt_player = next((p for p in players if p.player_name.lower() == alt_name.lower()), None)
            
            if not alt_player:
                await ctx.respond(f"⚠️ You don't have a character named '{alt_name}' linked to your account.")
                return
            
            # Check if this player is already an alt
            if hasattr(alt_player, 'main_player_id') and alt_player.main_player_id:
                # Find the main player
                player_collection = await db.get_collection("players")
                main_data = await player_collection.find_one({"_id": ObjectId(alt_player.main_player_id)})
                
                if main_data:
                    main_player = Player(**{**main_data, "_id": main_data["_id"]})
                    await ctx.respond(f"⚠️ '{alt_name}' is already an alt of '{main_player.player_name}'.")
                    return
            
            # Find main character
            mains = [p for p in players if hasattr(p, 'alt_player_ids') and p.alt_player_ids]
            
            if not mains:
                await ctx.respond("⚠️ You haven't set a main character yet. Use `/stats setmain <name>` first.")
                return
            
            main_player = mains[0]
            
            # Don't allow linking the main as its own alt
            if str(main_player._id) == str(alt_player._id):
                await ctx.respond("⚠️ You can't link your main character as an alt of itself.")
                return
            
            # Update main player to add this alt to its list
            player_collection = await db.get_collection("players")
            
            # Check if alt_player_ids exists, if not create it
            if not hasattr(main_player, 'alt_player_ids'):
                await player_collection.update_one(
                    {"_id": main_player._id},
                    {"$set": {"alt_player_ids": []}}
                )
                main_player.alt_player_ids = []
            
            # Add alt to main's alt list if not already present
            if str(alt_player._id) not in main_player.alt_player_ids:
                await player_collection.update_one(
                    {"_id": main_player._id},
                    {"$push": {"alt_player_ids": str(alt_player._id)}}
                )
            
            # Mark alt as belonging to main
            await player_collection.update_one(
                {"_id": alt_player._id},
                {"$set": {"main_player_id": str(main_player._id)}}
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title="Alt Character Linked",
                description=f"**{alt_player.player_name}** is now linked as an alt of **{main_player.player_name}**",
                color=0x50C878  # Emerald green
            )
            
            # Calculate combined stats
            total_kills = main_player.total_kills
            total_deaths = main_player.total_deaths
            
            # Include this alt's stats
            total_kills += alt_player.total_kills
            total_deaths += alt_player.total_deaths
            
            # Include other alts' stats if any
            for alt_id in main_player.alt_player_ids:
                if alt_id != str(alt_player._id):  # Skip the one we just added
                    other_alt = next((p for p in players if str(p._id) == alt_id), None)
                    if other_alt:
                        total_kills += other_alt.total_kills
                        total_deaths += other_alt.total_deaths
            
            # Calculate K/D ratio
            kd_ratio = total_kills / max(1, total_deaths)
            
            embed.add_field(
                name="Combined Statistics",
                value=f"Kills: **{total_kills}**\n" +
                      f"Deaths: **{total_deaths}**\n" +
                      f"K/D Ratio: **{kd_ratio:.2f}**",
                inline=False
            )
            
            embed.add_field(
                name="Character Management",
                value="Use `/stats me` to see all your linked characters\n" +
                      f"Use `/stats unlink {alt_name}` to remove this alt link",
                inline=False
            )
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error linking alt character: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="server", description="View statistics for a server")
    async def server_stats(self, ctx, 
                          server_name: discord.Option(str, "Server name to view stats for", required=False) = None):
        """
        View statistics for a server
        
        Usage: /stats server [server_name]
        
        If no server name is provided, stats for all servers will be shown.
        """
        try:
            db = await Database.get_instance()
            
            if server_name:
                # Get stats for specific server
                servers = await Server.get_by_guild(db, ctx.guild.id)
                server = next((s for s in servers if s.name.lower() == server_name.lower()), None)
                
                if not server:
                    await ctx.respond(f"⚠️ Server '{server_name}' not found. Use `/server list` to see all configured servers.")
                    return
                
                # Get server stats
                server_stats = await self.get_server_stats(db, server._id)
                
                # Create and send embed
                embed = await create_server_stats_embed(server, server_stats)
                await ctx.respond(embed=embed)
            else:
                # Get stats for all servers in this guild
                servers = await Server.get_by_guild(db, ctx.guild.id)
                
                if not servers:
                    await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                    return
                
                # Process each server
                for server in servers:
                    # Get server stats
                    server_stats = await self.get_server_stats(db, server._id)
                    
                    # Create and send embed
                    embed = await create_server_stats_embed(server, server_stats)
                    await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="leaderboard", description="View the leaderboard for a specific stat")
    async def leaderboard(self, ctx, 
                         stat_type: discord.Option(str, "Stat type to show (kills, deaths, kd)", required=False, choices=["kills", "deaths", "kd"]) = "kills",
                         limit: discord.Option(int, "Number of players to show (max: 25)", required=False, min_value=1, max_value=25) = 10):
        """
        View the leaderboard for a specific stat
        
        Usage: /stats leaderboard [stat_type] [limit]
        
        stat_type: kills, deaths, kd (default: kills)
        limit: Number of players to show (default: 10, max: 25)
        """
        try:
            # Validate arguments
            if stat_type.lower() not in ["kills", "deaths", "kd"]:
                await ctx.respond("⚠️ Invalid stat type. Choose from: kills, deaths, kd")
                return
            
            # Limit the leaderboard size
            if limit > 25:
                limit = 25
            
            db = await Database.get_instance()
            
            # Get servers for this guild to filter stats
            servers = await Server.get_by_guild(db, ctx.guild.id)
            server_ids = [server._id for server in servers]
            
            if not server_ids:
                await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                return
            
            # Build the leaderboard based on stat type
            if stat_type.lower() == "kills":
                # Sort by kills
                collection = await db.get_collection("players")
                cursor = collection.find({}).sort("total_kills", -1).limit(limit)
                
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
                collection = await db.get_collection("players")
                cursor = collection.find({}).sort("total_deaths", -1).limit(limit)
                
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
                collection = await db.get_collection("players")
                cursor = collection.find({"total_kills": {"$gte": 10}})
                
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
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
    @stats_group.command(name="weapons", description="View weapon usage statistics")
    async def weapon_stats(self, ctx, 
                          player_name: discord.Option(str, "Player name to show weapon stats for", required=False) = None):
        """
        View weapon usage statistics
        
        Usage: /stats weapons [player_name]
        
        If a player name is provided, shows weapon stats for that player.
        Otherwise, shows overall weapon stats across all players.
        """
        try:
            db = await Database.get_instance()
            
            # Get servers for this guild to filter stats
            servers = await Server.get_by_guild(db, ctx.guild.id)
            server_ids = [server._id for server in servers]
            
            if not server_ids:
                await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                return
            
            if player_name:
                # Get weapon stats for a specific player
                collection = await db.get_collection("players")
                cursor = collection.find({
                    "player_name": {"$regex": f"^{player_name}$", "$options": "i"}
                })
                players = await cursor.to_list(None)
                
                if not players:
                    await ctx.respond(f"⚠️ Player '{player_name}' not found. Names are case-sensitive.")
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
                
                collection = await db.get_collection("kills")
                cursor = collection.aggregate(pipeline)
                
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
                
                collection = await db.get_collection("kills")
                cursor = collection.aggregate(pipeline)
                
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
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error getting weapon stats: {e}")
            await ctx.respond(f"⚠️ An error occurred: {e}")
    
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
            # Get weapon stats - simplified tracking
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
            
            collection = await db.get_collection("kills")
            cursor = collection.aggregate(weapon_pipeline)
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
            
            collection = await db.get_collection("kills")
            cursor = collection.aggregate(victims_pipeline)
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
            
            collection = await db.get_collection("kills")
            cursor = collection.aggregate(killers_pipeline)
            async for stat in cursor:
                killer_id = stat["_id"]["id"]
                killer_name = stat["_id"]["name"]
                stats["killed_by"][killer_name] = {
                    "id": killer_id,
                    "deaths": stat["count"]
                }
            
            # Get longest kill
            collection = await db.get_collection("kills")
            cursor = collection.find({
                "killer_id": player_id,
                "is_suicide": False
            }).sort("distance", -1).limit(1)
            longest_kill = await cursor.to_list(1)
            
            if longest_kill:
                kill = longest_kill[0]
                stats["longest_kill"] = {
                    "distance": kill["distance"],
                    "weapon": kill["weapon"],
                    "victim": kill["victim_name"],
                    "timestamp": kill["timestamp"]
                }
            
            # Get recent kills
            cursor = collection.find({
                "killer_id": player_id,
                "is_suicide": False
            }).sort("timestamp", -1).limit(5)
            recent_kills = await cursor.to_list(5)
            
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
            collection = await db.get_collection("kills")
            cursor = collection.find({
                "server_id": server_id,
                "is_suicide": False
            }).sort("distance", -1).limit(1)
            longest_kill = await cursor.to_list(1)
            
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
            cursor = collection.find({
                "server_id": server_id
            }).sort("timestamp", -1).limit(5)
            recent_kills = await cursor.to_list(5)
            
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

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_application_command(stats_group)
    bot.add_cog(StatsCommands(bot))
