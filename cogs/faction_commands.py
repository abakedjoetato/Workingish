import discord
from discord.ext import commands
import logging
from datetime import datetime
from bson import ObjectId

from database.models import Faction, Player
from utils.embeds import create_faction_embed
from utils.decorators import premium_tier_required, guild_only
from utils.premium import check_feature_access, get_tier_display_info

logger = logging.getLogger('deadside_bot.factions')

# Create a SlashCommandGroup for faction commands
faction_group = discord.SlashCommandGroup(
    name="faction",
    description="Commands for managing player factions",
    default_member_permissions=discord.Permissions(manage_roles=True)
)

class FactionCommands(commands.Cog):
    """Commands for managing player factions"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
    
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("Faction commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
        
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [faction_group]
        
    @faction_group.command(name="create", description="Create a new faction")
    @premium_tier_required(tier=1)
    @guild_only()
    async def create_faction(self, ctx, name: str, abbreviation: str):
        """
        Create a new faction with the given name and abbreviation
        
        This will create a Discord role for the faction and set up the creator as the faction leader.
        """
        # Check if the abbreviation is valid (3 chars or less)
        if len(abbreviation) > 3:
            await ctx.respond("⚠️ Abbreviation must be 3 characters or less.", ephemeral=True)
            return
            
        # Check if guild has permission to manage roles
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.respond("⚠️ I don't have permission to manage roles in this server. Please grant the 'Manage Roles' permission.", ephemeral=True)
            return
            
        # Check if guild has permission to manage nicknames
        if not ctx.guild.me.guild_permissions.manage_nicknames:
            await ctx.respond("⚠️ I don't have permission to manage nicknames in this server. Please grant the 'Manage Nicknames' permission.", ephemeral=True)
            return
            
        # Check if a faction with this name or abbreviation already exists
        db = self.bot.db
        existing_faction = await Faction.get_by_name(db, name, ctx.guild.id)
        if existing_faction:
            await ctx.respond(f"⚠️ A faction with the name '{name}' already exists.", ephemeral=True)
            return
            
        existing_faction = await Faction.get_by_abbreviation(db, abbreviation, ctx.guild.id)
        if existing_faction:
            await ctx.respond(f"⚠️ A faction with the abbreviation '{abbreviation.upper()}' already exists.", ephemeral=True)
            return
            
        # Check if user is already in a faction
        existing_member_faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if existing_member_faction:
            await ctx.respond(f"⚠️ You are already a member of the faction '{existing_member_faction.name}'. Leave that faction first before creating a new one.", ephemeral=True)
            return
        
        # Create the faction role
        try:
            faction_role = await ctx.guild.create_role(
                name=name,
                reason=f"Faction created by {ctx.author.display_name}"
            )
        except discord.Forbidden:
            await ctx.respond("⚠️ I don't have permission to create roles.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await ctx.respond(f"⚠️ Failed to create faction role: {e}", ephemeral=True)
            return
        
        # Add the role to the creator
        try:
            await ctx.author.add_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to assign faction role: {e}", ephemeral=True)
            # Delete the role since we couldn't assign it
            try:
                await faction_role.delete()
            except:
                pass
            return
        
        # Update the user's nickname with the faction abbreviation
        try:
            current_name = ctx.author.display_name
            if not current_name.startswith(f"{abbreviation.upper()}"):
                new_nickname = f"{abbreviation.upper()} {current_name}"
                if len(new_nickname) > 32:  # Discord nickname limit
                    new_nickname = new_nickname[:32]
                await ctx.author.edit(nick=new_nickname)
        except discord.Forbidden:
            await ctx.respond("⚠️ I don't have permission to change your nickname, but the faction has been created.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to update nickname, but the faction has been created: {e}", ephemeral=True)
        
        # Create the faction in the database
        faction = await Faction.create(
            db,
            name=name,
            abbreviation=abbreviation,
            guild_id=ctx.guild.id,
            leader_id=str(ctx.author.id),
            members=[str(ctx.author.id)],
            role_id=str(faction_role.id)
        )
        
        # Create and send the faction embed
        embed = await create_faction_embed(faction, ctx.guild)
        await ctx.respond(f"✅ Faction '{name}' created successfully with abbreviation '{abbreviation.upper()}'!", embed=embed)
        
    @faction_group.command(name="info", description="View faction information")
    @premium_tier_required(tier=1)
    async def faction_info(self, ctx, name: str = None):
        """
        View information about a faction
        
        If no faction name is provided, displays info about your current faction.
        """
        db = self.bot.db
        faction = None
        
        # If no name provided, check if user is in a faction
        if not name:
            faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
            if not faction:
                await ctx.respond("⚠️ You are not in a faction. Please provide a faction name to view details.", ephemeral=True)
                return
        else:
            # Try to find the faction by name
            faction = await Faction.get_by_name(db, name, ctx.guild.id)
            if not faction:
                # Try by abbreviation
                faction = await Faction.get_by_abbreviation(db, name, ctx.guild.id)
                
            if not faction:
                await ctx.respond(f"⚠️ Faction '{name}' not found.", ephemeral=True)
                return
        
        await ctx.respond("⏳ Gathering faction statistics...", ephemeral=True)
        
        # Calculate member stats
        member_stats = {
            "total_kills": 0,
            "total_deaths": 0,
            "weapon_counts": {}
        }
        
        # Get player stats for each member
        for member_id in faction.members:
            players = await Player.get_by_discord_id(db, member_id)
            
            if not players:
                continue
                
            for player in players:
                # Add to faction totals
                member_stats["total_kills"] += player.total_kills
                member_stats["total_deaths"] += player.total_deaths
                
                # Get detailed stats for this player
                try:
                    # Get kill data to find weapons
                    kills_collection = await db.get_collection("kills")
                    cursor = kills_collection.find({
                        "killer_id": player.player_id,
                        "is_suicide": False
                    })
                    
                    async for kill in cursor:
                        # Track weapon usage
                        weapon = kill.get("weapon", "Unknown")
                        if weapon in member_stats["weapon_counts"]:
                            member_stats["weapon_counts"][weapon] += 1
                        else:
                            member_stats["weapon_counts"][weapon] = 1
                except Exception as e:
                    logger.error(f"Error retrieving weapon stats: {e}")
        
        # Find top weapon
        top_weapon = sorted(member_stats["weapon_counts"].items(), key=lambda x: x[1], reverse=True)
        member_stats["top_weapon"] = top_weapon[0][0] if top_weapon else "None"
        
        # Create and send the faction embed with member stats
        embed = await create_faction_embed(faction, ctx.guild, member_stats)
        await ctx.respond(embed=embed)
        
    @faction_group.command(name="list", description="List all factions in this server")
    @premium_tier_required(tier=1)
    async def list_factions(self, ctx):
        """List all factions in the current guild"""
        db = self.bot.db
        factions = await Faction.get_all_for_guild(db, ctx.guild.id)
        
        if not factions:
            await ctx.respond("No factions have been created in this server yet.", ephemeral=True)
            return
            
        # Create an embed to display the factions
        embed = discord.Embed(
            title="Factions",
            description=f"There are {len(factions)} factions in this server",
            color=discord.Color.blue()
        )
        
        for faction in factions:
            # Get the faction role if it exists
            role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
            role_mention = role.mention if role else "No role"
            
            # Add field for each faction
            embed.add_field(
                name=f"{faction.name} [{faction.abbreviation}]",
                value=f"Members: {len(faction.members)}\nLeader: <@{faction.leader_id}>\nRole: {role_mention}",
                inline=True
            )
            
        await ctx.respond(embed=embed)
        
    @faction_group.command(name="invite", description="Invite a member to your faction")
    @premium_tier_required(tier=1)
    async def invite_member(self, ctx, member: discord.Member):
        """
        Invite a member to your faction
        
        Only faction leaders can invite new members.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can invite new members.", ephemeral=True)
            return
            
        # Check if the target member is already in a faction
        member_faction = await Faction.get_by_member(db, str(member.id), ctx.guild.id)
        if member_faction:
            await ctx.respond(f"⚠️ {member.display_name} is already a member of the faction '{member_faction.name}'.", ephemeral=True)
            return
            
        # Check if bot has permission to manage roles and nicknames
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.respond("⚠️ I don't have permission to manage roles in this server. Please grant the 'Manage Roles' permission.", ephemeral=True)
            return
            
        if not ctx.guild.me.guild_permissions.manage_nicknames:
            await ctx.respond("⚠️ I don't have permission to manage nicknames in this server. Please grant the 'Manage Nicknames' permission.", ephemeral=True)
            return
            
        # Get the faction role
        faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
        if not faction_role:
            await ctx.respond(f"⚠️ Faction role for '{faction.name}' not found. The role may have been deleted.", ephemeral=True)
            return
            
        # Add the member to the faction
        faction.members.append(str(member.id))
        await faction.update(db)
        
        # Add the role to the member
        try:
            await member.add_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to assign faction role: {e}", ephemeral=True)
            # Remove the member from the faction in the database
            faction.members.remove(str(member.id))
            await faction.update(db)
            return
        
        # Update the member's nickname with the faction abbreviation
        try:
            current_name = member.display_name
            if not current_name.startswith(f"{faction.abbreviation}"):
                new_nickname = f"{faction.abbreviation} {current_name}"
                if len(new_nickname) > 32:  # Discord nickname limit
                    new_nickname = new_nickname[:32]
                await member.edit(nick=new_nickname)
        except discord.Forbidden:
            await ctx.respond(f"✅ {member.mention} has been added to the faction, but I couldn't update their nickname due to missing permissions.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"✅ {member.mention} has been added to the faction, but I couldn't update their nickname: {e}", ephemeral=True)
            
        # Send success message
        await ctx.respond(f"✅ {member.mention} has been added to the faction '{faction.name}'!")
        
        # Send a DM to the invited member
        try:
            await member.send(f"You have been added to the faction '{faction.name}' in {ctx.guild.name}!")
        except:
            # Silently ignore if we can't DM the member
            pass
        
    @faction_group.command(name="leave", description="Leave your current faction")
    @premium_tier_required(tier=1)
    async def leave_faction(self, ctx):
        """Leave your current faction"""
        db = self.bot.db
        
        # Check if the user is in a faction
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        # If the user is the faction leader, they can't leave unless they're the only member
        if faction.leader_id == str(ctx.author.id) and len(faction.members) > 1:
            await ctx.respond("⚠️ As the faction leader, you can't leave the faction while there are other members. Either transfer leadership first using `/faction_transfer` or remove all members.", ephemeral=True)
            return
            
        # If they're the last member (and therefore the leader), delete the faction
        if len(faction.members) == 1 and faction.leader_id == str(ctx.author.id):
            # Delete the faction role
            try:
                faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
                if faction_role:
                    await faction_role.delete(reason=f"Faction '{faction.name}' deleted by last member")
            except Exception as e:
                await ctx.respond(f"⚠️ Failed to delete faction role: {e}", ephemeral=True)
                
            # Delete the faction from the database
            await faction.delete(db)
            
            # Reset the user's nickname
            try:
                current_name = ctx.author.display_name
                if current_name.startswith(f"{faction.abbreviation} "):
                    new_nickname = current_name[len(faction.abbreviation)+1:]
                    await ctx.author.edit(nick=new_nickname)
            except:
                pass
                
            await ctx.respond(f"✅ You have left the faction '{faction.name}' and it has been deleted as you were the last member.")
            return
            
        # Remove the member from the faction
        faction.members.remove(str(ctx.author.id))
        await faction.update(db)
        
        # Remove the faction role
        try:
            faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
            if faction_role:
                await ctx.author.remove_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to remove faction role: {e}", ephemeral=True)
        
        # Reset the user's nickname
        try:
            current_name = ctx.author.display_name
            if current_name.startswith(f"{faction.abbreviation} "):
                new_nickname = current_name[len(faction.abbreviation)+1:]
                await ctx.author.edit(nick=new_nickname)
        except:
            pass
            
        await ctx.respond(f"✅ You have left the faction '{faction.name}'.")
        
    @faction_group.command(name="remove", description="Remove a member from your faction")
    @premium_tier_required(tier=1)
    async def remove_member(self, ctx, member: discord.Member):
        """
        Remove a member from your faction
        
        Only faction leaders can remove members.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can remove members.", ephemeral=True)
            return
            
        # Check if the target member is in the faction
        if str(member.id) not in faction.members:
            await ctx.respond(f"⚠️ {member.display_name} is not a member of your faction.", ephemeral=True)
            return
            
        # Check if the target is the leader (can't remove yourself this way)
        if str(member.id) == faction.leader_id:
            await ctx.respond("⚠️ You can't remove yourself as the faction leader. Use `/faction_leave` instead.", ephemeral=True)
            return
            
        # Remove the member from the faction
        faction.members.remove(str(member.id))
        await faction.update(db)
        
        # Remove the faction role
        try:
            faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
            if faction_role:
                await member.remove_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to remove faction role: {e}", ephemeral=True)
        
        # Reset the member's nickname
        try:
            current_name = member.display_name
            if current_name.startswith(f"{faction.abbreviation} "):
                new_nickname = current_name[len(faction.abbreviation)+1:]
                await member.edit(nick=new_nickname)
        except:
            pass
            
        await ctx.respond(f"✅ {member.mention} has been removed from the faction '{faction.name}'.")
        
        # Send a DM to the removed member
        try:
            await member.send(f"You have been removed from the faction '{faction.name}' in {ctx.guild.name}.")
        except:
            # Silently ignore if we can't DM the member
            pass
            
    @faction_group.command(name="transfer", description="Transfer faction leadership to another member")
    @premium_tier_required(tier=1)
    async def transfer_leadership(self, ctx, member: discord.Member):
        """
        Transfer faction leadership to another member
        
        Only faction leaders can transfer leadership.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can transfer leadership.", ephemeral=True)
            return
            
        # Check if the target member is in the faction
        if str(member.id) not in faction.members:
            await ctx.respond(f"⚠️ {member.display_name} is not a member of your faction.", ephemeral=True)
            return
            
        # Check if the target is already the leader
        if str(member.id) == faction.leader_id:
            await ctx.respond(f"⚠️ {member.display_name} is already the faction leader.", ephemeral=True)
            return
            
        # Transfer leadership
        faction.leader_id = str(member.id)
        await faction.update(db)
            
        await ctx.respond(f"✅ Leadership of faction '{faction.name}' has been transferred to {member.mention}.")
        
        # Send a DM to the new leader
        try:
            await member.send(f"You are now the leader of the faction '{faction.name}' in {ctx.guild.name}!")
        except:
            # Silently ignore if we can't DM the member
            pass
            
    @faction_group.command(name="stats", description="View faction statistics")
    @premium_tier_required(tier=1)
    async def faction_stats(self, ctx, name: str = None):
        """
        View combined statistics for all members of a faction
        
        If no faction name is provided, displays stats for your current faction.
        """
        db = self.bot.db
        faction = None
        
        # If no name provided, check if user is in a faction
        if not name:
            faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
            if not faction:
                await ctx.respond("⚠️ You are not in a faction. Please provide a faction name to view stats.", ephemeral=True)
                return
        else:
            # Try to find the faction by name
            faction = await Faction.get_by_name(db, name, ctx.guild.id)
            if not faction:
                # Try by abbreviation
                faction = await Faction.get_by_abbreviation(db, name, ctx.guild.id)
                
            if not faction:
                await ctx.respond(f"⚠️ Faction '{name}' not found.", ephemeral=True)
                return
        
        # Notify that we're calculating stats
        await ctx.respond(f"⏳ Calculating combined statistics for faction '{faction.name}'...", ephemeral=True)
        
        # Get all members of the faction that have linked Discord accounts
        if not faction.members:
            await ctx.respond(f"⚠️ Faction '{faction.name}' has no members with linked game accounts.", ephemeral=True)
            return
            
        # Initialize faction stats
        total_kills = 0
        total_deaths = 0
        weapon_counts = {}
        member_stats = []
        
        # Get player stats for each linked Discord account in the faction
        for member_id in faction.members:
            players = await Player.get_by_discord_id(db, member_id)
            
            if not players:
                continue
                
            member_total_kills = 0
            member_total_deaths = 0
            
            for player in players:
                # Add to faction totals
                total_kills += player.total_kills
                total_deaths += player.total_deaths
                member_total_kills += player.total_kills
                member_total_deaths += player.total_deaths
                
                # Get detailed stats for this player
                try:
                    # Get kill data to find weapons
                    kills_collection = await db.get_collection("kills")
                    cursor = kills_collection.find({
                        "killer_id": player.player_id,
                        "is_suicide": False
                    })
                    
                    async for kill in cursor:
                        # Track weapon usage
                        weapon = kill.get("weapon", "Unknown")
                        if weapon in weapon_counts:
                            weapon_counts[weapon] += 1
                        else:
                            weapon_counts[weapon] = 1
                except Exception as e:
                    logger.error(f"Error retrieving weapon stats: {e}")
            
            # Only add member to stats if they have activity
            if member_total_kills > 0 or member_total_deaths > 0:
                member_stats.append({
                    "id": member_id,
                    "kills": member_total_kills,
                    "deaths": member_total_deaths,
                    "kd": member_total_kills / max(1, member_total_deaths)
                })
        
        # Sort weapons by usage count
        top_weapons = sorted(weapon_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Sort members by kills
        member_stats.sort(key=lambda x: x["kills"], reverse=True)
        
        # Calculate K/D ratio for the faction
        kd_ratio = total_kills / max(1, total_deaths)
        
        # Get top weapon name (or "None" if no weapons)
        top_weapon = top_weapons[0][0] if top_weapons else "None"
        
        # Create a simplified embed for the faction stats in the requested format
        embed = discord.Embed(
            title=f"FACTION STATISTICS",
            color=discord.Color.blue()
        )
        
        # Format with aligned columns for clean display
        embed.add_field(
            name=f"{faction.name} [{faction.abbreviation}]",
            value=f"```\nKILLS         DEATHS        TOP WEAPON\n{total_kills:<14}{total_deaths:<14}{top_weapon}\n```",
            inline=False
        )
        
        # Send the embed
        await ctx.respond(embed=embed)
        
    @faction_group.command(name="leaderboard", description="View faction leaderboard for the server") 
    @premium_tier_required(tier=1)
    async def faction_leaderboard(self, ctx):
        """
        View a leaderboard of all factions in the server
        """
        db = self.bot.db
        
        # Get all factions in this guild
        factions = await Faction.get_all_for_guild(db, ctx.guild.id)
        
        if not factions:
            await ctx.respond("No factions have been created in this server yet.", ephemeral=True)
            return
            
        await ctx.respond("⏳ Calculating faction leaderboard...", ephemeral=True)
        
        # Calculate stats for each faction
        faction_stats = []
        
        for faction in factions:
            # Initialize faction stats
            total_kills = 0
            total_deaths = 0
            weapon_counts = {}
            
            # Get player stats for each member
            for member_id in faction.members:
                players = await Player.get_by_discord_id(db, member_id)
                
                if not players:
                    continue
                    
                for player in players:
                    # Add to faction totals
                    total_kills += player.total_kills
                    total_deaths += player.total_deaths
                    
                    # Get detailed stats for this player
                    try:
                        # Get kill data to find weapons
                        kills_collection = await db.get_collection("kills")
                        cursor = kills_collection.find({
                            "killer_id": player.player_id,
                            "is_suicide": False
                        })
                        
                        async for kill in cursor:
                            # Track weapon usage
                            weapon = kill.get("weapon", "Unknown")
                            if weapon in weapon_counts:
                                weapon_counts[weapon] += 1
                            else:
                                weapon_counts[weapon] = 1
                    except Exception as e:
                        logger.error(f"Error retrieving weapon stats: {e}")
            
            # Calculate K/D ratio
            kd_ratio = total_kills / max(1, total_deaths)
            
            # Get top weapon
            top_weapon = sorted(weapon_counts.items(), key=lambda x: x[1], reverse=True)
            top_weapon_name = top_weapon[0][0] if top_weapon else "None"
            
            # Add to faction stats list
            faction_stats.append({
                "name": faction.name,
                "abbreviation": faction.abbreviation,
                "kills": total_kills,
                "deaths": total_deaths,
                "kd": kd_ratio,
                "top_weapon": top_weapon_name,
                "member_count": len(faction.members)
            })
        
        # Sort factions by kills
        faction_stats.sort(key=lambda x: x["kills"], reverse=True)
        
        # Create embed for leaderboard
        embed = discord.Embed(
            title="FACTION LEADERBOARD",
            description=f"Top {min(5, len(faction_stats))} factions by kills",
            color=discord.Color.gold()
        )
        
        # Format header for leaderboard stats table
        stats_header = f"```\nRANK  {'FACTION':<16} {'KILLS':<8} {'DEATHS':<8} {'K/D':<6} {'TOP WEAPON':<15}\n{'═' * 60}\n```"
        embed.add_field(name="📊 Statistics", value=stats_header, inline=False)
        
        # Add formatted stats for top 5 factions
        stats_value = "```\n"
        for i, faction in enumerate(faction_stats[:5], 1):
            # Format each row with aligned columns
            faction_name = f"{faction['abbreviation']} {faction['name']}"
            if len(faction_name) > 14:
                faction_name = faction_name[:14] + '..'
                
            weapon_name = faction['top_weapon']
            if len(weapon_name) > 15:
                weapon_name = weapon_name[:13] + '..'
                
            # Format: Rank, Name, Kills, Deaths, K/D ratio, Top weapon
            stats_value += f"{i:<5}{faction_name:<16}{faction['kills']:<8}{faction['deaths']:<8}{faction['kd']:.2f:<6}{weapon_name:<15}\n"
        
        stats_value += "```"
        embed.add_field(name="", value=stats_value, inline=False)
        
        # Set footer
        embed.set_footer(text=f"Guild: {ctx.guild.name} | Total Factions: {len(factions)}")
        
        # Send the embed
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(FactionCommands(bot))