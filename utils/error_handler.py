"""
Error Handler Module

This module provides standardized error handling for Discord commands and other functions.
It ensures consistent error messages and logging across the application.
"""

import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, Callable, Union, cast

import discord
from utils.lsp_error_suppressors import DiscordContext

logger = logging.getLogger('deadside_bot.utils.error_handler')

class ErrorHandlerConfig:
    """Configuration for the error handler"""
    
    # Enable or disable user-visible error details
    SHOW_ERROR_DETAILS = False
    
    # Formatting for error messages
    ERROR_PREFIX = "⚠️ "
    ERROR_FORMAT = "{prefix}{message}"
    DETAILED_ERROR_FORMAT = "{prefix}{message}\n\n**Technical details**: {details}"
    
    # Common error messages
    GENERIC_ERROR = "An error occurred while processing your request. Please try again later."
    PERMISSION_ERROR = "You don't have permission to use this command."
    NOT_FOUND_ERROR = "The requested resource was not found."
    VALIDATION_ERROR = "There was an issue with your input."
    DATABASE_ERROR = "There was an issue with the database operation."
    DISCORD_API_ERROR = "There was an issue with the Discord API."
    NETWORK_ERROR = "There was a network issue. Please try again later."
    
    # Timeouts
    DEFAULT_TIMEOUT_SECONDS = 15.0
    EXTENDED_TIMEOUT_SECONDS = 30.0

async def handle_command_error(ctx: DiscordContext, error: Exception, **kwargs: Any) -> None:
    """
    Handle errors from Discord commands
    
    Args:
        ctx: Discord context
        error: The error that occurred
        **kwargs: Additional context for error handling
    """
    # Get the command name for logging
    command_name = getattr(ctx, "command", None)
    command_name = getattr(command_name, "name", "unknown_command") if command_name else "unknown_command"
    
    # Log the error
    logger.error(f"Error in command '{command_name}': {str(error)}")
    logger.error(traceback.format_exc())
    
    # Determine the error message to show
    user_message = ErrorHandlerConfig.GENERIC_ERROR
    is_handled = False
    is_ephemeral = True
    
    # Handle different error types
    if isinstance(error, discord.errors.Forbidden):
        user_message = "I don't have permission to perform this action."
        is_handled = True
    
    elif isinstance(error, discord.errors.NotFound):
        user_message = ErrorHandlerConfig.NOT_FOUND_ERROR
        is_handled = True
    
    elif isinstance(error, discord.errors.DiscordServerError):
        user_message = "Discord is having issues right now. Please try again later."
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.CommandInvokeError):
        # Unwrap the original error
        original = getattr(error, "original", error)
        return await handle_command_error(ctx, original, **kwargs)
    
    elif isinstance(error, discord.ext.commands.MissingPermissions):
        user_message = ErrorHandlerConfig.PERMISSION_ERROR
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.BotMissingPermissions):
        missing = getattr(error, "missing_permissions", [])
        missing_str = ", ".join(p.replace("_", " ").title() for p in missing)
        user_message = f"I need the following permissions to run this command: {missing_str}"
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.MissingRequiredArgument):
        param = getattr(error, "param", None)
        param_name = getattr(param, "name", "unknown") if param else "unknown"
        user_message = f"Missing required argument: `{param_name}`"
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.CommandOnCooldown):
        retry_after = getattr(error, "retry_after", 1)
        user_message = f"This command is on cooldown. Please try again in {retry_after:.1f} seconds."
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.NoPrivateMessage):
        user_message = "This command cannot be used in private messages."
        is_handled = True
    
    elif isinstance(error, discord.ext.commands.CheckFailure):
        user_message = "You don't have permission to use this command."
        is_handled = True
    
    elif isinstance(error, TimeoutError):
        user_message = "The operation timed out. Please try again later."
        is_handled = True
    
    elif isinstance(error, ValueError):
        user_message = f"{ErrorHandlerConfig.VALIDATION_ERROR} {str(error)}"
        is_handled = True
    
    elif isinstance(error, Exception):
        if ErrorHandlerConfig.SHOW_ERROR_DETAILS:
            user_message = ErrorHandlerConfig.DETAILED_ERROR_FORMAT.format(
                prefix=ErrorHandlerConfig.ERROR_PREFIX,
                message=ErrorHandlerConfig.GENERIC_ERROR,
                details=str(error)
            )
        else:
            user_message = ErrorHandlerConfig.ERROR_FORMAT.format(
                prefix=ErrorHandlerConfig.ERROR_PREFIX,
                message=ErrorHandlerConfig.GENERIC_ERROR
            )
    
    # Send the error message to the user
    try:
        if hasattr(ctx, "respond") and callable(ctx.respond):
            await ctx.respond(user_message, ephemeral=is_ephemeral)
        elif hasattr(ctx, "send") and callable(ctx.send):
            await ctx.send(user_message)
    except Exception as e:
        logger.error(f"Failed to send error message: {str(e)}")
        
    # Return whether the error was handled
    return is_handled

def format_error(error_message: str, is_detailed: bool = False, **kwargs: Any) -> str:
    """
    Format an error message for display
    
    Args:
        error_message: The error message
        is_detailed: Whether to include technical details
        **kwargs: Additional context for formatting
        
    Returns:
        Formatted error message
    """
    if is_detailed and ErrorHandlerConfig.SHOW_ERROR_DETAILS:
        details = kwargs.get("details", "No details available")
        return ErrorHandlerConfig.DETAILED_ERROR_FORMAT.format(
            prefix=ErrorHandlerConfig.ERROR_PREFIX,
            message=error_message,
            details=details
        )
    else:
        return ErrorHandlerConfig.ERROR_FORMAT.format(
            prefix=ErrorHandlerConfig.ERROR_PREFIX,
            message=error_message
        )

def setup_command_error_handling(bot: Any) -> None:
    """
    Set up global error handling for a Discord bot
    
    Args:
        bot: Discord bot instance
    """
    @bot.event
    async def on_command_error(ctx: DiscordContext, error: Exception) -> None:
        await handle_command_error(ctx, error)
        
    @bot.event
    async def on_application_command_error(ctx: DiscordContext, error: Exception) -> None:
        await handle_command_error(ctx, error)
        
    logger.info("Global error handling set up for bot")

class ErrorLogger:
    """Utility class for logging errors"""
    
    @staticmethod
    def log_error(error: Exception, context: Optional[Dict[str, Any]] = None, 
                  source: Optional[str] = None) -> None:
        """
        Log an error with context
        
        Args:
            error: The error to log
            context: Additional context for the error
            source: Source of the error (e.g., function name)
        """
        source_info = f" in {source}" if source else ""
        logger.error(f"Error{source_info}: {str(error)}")
        
        if context:
            logger.error(f"Context: {context}")
            
        logger.error(traceback.format_exc())
        
    @staticmethod
    def log_warning(message: str, context: Optional[Dict[str, Any]] = None, 
                    source: Optional[str] = None) -> None:
        """
        Log a warning with context
        
        Args:
            message: The warning message
            context: Additional context for the warning
            source: Source of the warning (e.g., function name)
        """
        source_info = f" in {source}" if source else ""
        logger.warning(f"Warning{source_info}: {message}")
        
        if context:
            logger.warning(f"Context: {context}")
            
    @staticmethod
    async def log_async_errors(coro: Callable, *args: Any, source: Optional[str] = None, 
                              **kwargs: Any) -> Optional[Any]:
        """
        Execute an async function and log any errors
        
        Args:
            coro: Async function to execute
            *args: Arguments for the function
            source: Source of the function (e.g., function name)
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function or None if an error occurred
        """
        try:
            return await coro(*args, **kwargs)
        except Exception as e:
            ErrorLogger.log_error(e, {
                "args": args,
                "kwargs": kwargs
            }, source or coro.__name__)
            return None