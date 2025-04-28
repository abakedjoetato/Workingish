"""
Error Handling Utilities

This module provides utilities for consistent error handling across the bot.
It includes functions for logging errors, formatting error messages, and handling
specific types of exceptions.
"""

import discord
import logging
import traceback
import sys
from datetime import datetime, timezone
from utils.embeds import COLORS, EMOJIS

logger = logging.getLogger('deadside_bot.utils.error_handler')

class ErrorHandler:
    """
    Class for handling errors consistently across the bot
    """
    
    @staticmethod
    async def handle_command_error(ctx, error, ephemeral=True):
        """
        Handle an error that occurred during command execution
        
        Args:
            ctx: Command context
            error: The error that occurred
            ephemeral: Whether to send the error message as an ephemeral message
        """
        try:
            # Log the error
            logger.error(f"Error handling command {ctx.command}:")
            logger.error(f"{error.__class__.__name__}: {str(error)}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            
            # Get the bot instance
            bot = ctx.bot
            
            # Format the error message based on the type of error
            if isinstance(error, discord.ApplicationCommandInvokeError):
                # If it's a wrapped error, unwrap it
                error = error.original
            
            # Handle specific error types
            if isinstance(error, discord.CheckFailure) or isinstance(error, discord.MissingPermissions):
                await ctx.respond("⚠️ You don't have permission to use this command.", ephemeral=True)
            elif isinstance(error, discord.NotFound):
                await ctx.respond("⚠️ The requested resource was not found.", ephemeral=True)
            elif isinstance(error, discord.Forbidden):
                await ctx.respond("⚠️ I don't have permission to perform that action.", ephemeral=True)
            elif isinstance(error, discord.HTTPException):
                await ctx.respond(f"⚠️ An HTTP error occurred: {error.status} {error.text}", ephemeral=True)
            elif isinstance(error, discord.InvalidArgument):
                await ctx.respond(f"⚠️ Invalid argument: {str(error)}", ephemeral=True)
            elif isinstance(error, discord.DiscordServerError):
                await ctx.respond("⚠️ Discord is having issues right now. Please try again later.", ephemeral=True)
            else:
                # Generic error message for unknown error types
                await ctx.respond(f"❌ An error occurred while processing your command: {str(error)}", ephemeral=True)
                
                # Log error to database if it's serious
                try:
                    if hasattr(bot, 'db') and bot.db:
                        await ErrorHandler.log_error_to_database(ctx, error, bot.db)
                except Exception as e:
                    logger.error(f"Failed to log error to database: {e}")
                    
        except Exception as e:
            # If error handling itself fails, make one last attempt to notify the user
            logger.error(f"Error while handling another error: {e}")
            try:
                await ctx.respond("❌ An error occurred, and then another error occurred while handling it.", ephemeral=True)
            except:
                pass
    
    @staticmethod
    async def log_error_to_database(ctx, error, db):
        """
        Log an error to the database for later analysis
        
        Args:
            ctx: Command context
            error: The error that occurred
            db: Database instance
        """
        try:
            # Get error collection
            errors_collection = await db.get_collection("errors")
            
            # Create error document
            error_doc = {
                "timestamp": datetime.now(timezone.utc),
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "command": ctx.command.qualified_name if ctx.command else "Unknown",
                "command_args": str(ctx.kwargs) if hasattr(ctx, 'kwargs') else "{}",
                "guild_id": str(ctx.guild.id) if ctx.guild else None,
                "channel_id": str(ctx.channel.id) if ctx.channel else None,
                "user_id": str(ctx.author.id) if ctx.author else None,
                "traceback": traceback.format_exception(type(error), error, error.__traceback__)
            }
            
            # Insert the error document
            await errors_collection.insert_one(error_doc)
            
            logger.info(f"Logged error to database: {error.__class__.__name__}")
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
    
    @staticmethod
    async def format_error_embed(error_message, include_support=True):
        """
        Format an error message as an embed
        
        Args:
            error_message: The error message to display
            include_support: Whether to include support information
            
        Returns:
            discord.Embed: Formatted error embed
        """
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            description=error_message,
            color=COLORS["error"]
        )
        
        if include_support:
            embed.add_field(
                name="Need help?",
                value="If this error persists, please contact server administrators.",
                inline=False
            )
            
        embed.set_footer(text=f"Error occurred at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return embed
    
    @staticmethod
    async def handle_database_error(ctx, error, operation=None):
        """
        Handle a database error
        
        Args:
            ctx: Command context
            error: The error that occurred
            operation: The database operation that failed
        """
        # Log the error
        if operation:
            logger.error(f"Database error during {operation}: {error}")
        else:
            logger.error(f"Database error: {error}")
            
        # Notify the user
        await ctx.respond(
            f"❌ A database error occurred. Please try again later.",
            ephemeral=True
        )
        
        # Log to database
        try:
            if hasattr(ctx.bot, 'db') and ctx.bot.db:
                error_doc = {
                    "timestamp": datetime.now(timezone.utc),
                    "error_type": "DatabaseError",
                    "error_message": str(error),
                    "operation": operation,
                    "command": ctx.command.qualified_name if ctx.command else "Unknown",
                    "guild_id": str(ctx.guild.id) if ctx.guild else None,
                    "channel_id": str(ctx.channel.id) if ctx.channel else None,
                    "user_id": str(ctx.author.id) if ctx.author else None
                }
                
                errors_collection = await ctx.bot.db.get_collection("errors")
                await errors_collection.insert_one(error_doc)
        except Exception as e:
            logger.error(f"Failed to log database error to database: {e}")
            
    @staticmethod
    async def handle_http_error(ctx, error, operation=None):
        """
        Handle an HTTP error
        
        Args:
            ctx: Command context
            error: The error that occurred
            operation: The HTTP operation that failed
        """
        # Log the error
        if operation:
            logger.error(f"HTTP error during {operation}: {error}")
        else:
            logger.error(f"HTTP error: {error}")
            
        # Notify the user with appropriate message based on error type
        if isinstance(error, discord.Forbidden):
            await ctx.respond(
                "⚠️ I don't have permission to perform that action. Please check my permissions.",
                ephemeral=True
            )
        elif isinstance(error, discord.NotFound):
            await ctx.respond(
                "⚠️ The requested resource was not found.",
                ephemeral=True
            )
        elif isinstance(error, discord.HTTPException):
            if error.status == 429:
                await ctx.respond(
                    "⚠️ I'm being rate limited by Discord. Please try again in a few moments.",
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    f"⚠️ An HTTP error occurred: {error.status} {error.text}",
                    ephemeral=True
                )
        else:
            await ctx.respond(
                f"⚠️ An error occurred while communicating with Discord: {str(error)}",
                ephemeral=True
            )