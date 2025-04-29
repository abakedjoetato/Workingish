async def sync_slash_commands():
    """Register all slash commands to Discord with unified approach and proper rate limit handling"""
    try:
        logger.info("📝 STARTING UNIFIED COMMAND REGISTRATION")
        
        # Use our optimized command registration function from utils/command_fix
        try:
            from utils.command_fix import optimized_command_sync, apply_command_fixes, patch_discord_internals
            
            # First ensure all command objects are properly fixed
            logger.info("Applying command fixes before registration")
            
            # Apply the monkey patch to Discord internals
            if patch_discord_internals():
                logger.info("✅ Successfully patched Discord.py internals for improved command handling")
            else:
                logger.warning("⚠️ Could not patch Discord.py internals, will rely on command-by-command fixes")
            
            # Apply fixes to all command groups in all cogs
            fixed_count = apply_command_fixes(bot)
            logger.info(f"🔧 Applied fixes to {fixed_count} command objects")
            
            # Use our optimized registration approach
            logger.info("Using optimized command registration approach")
            result = await optimized_command_sync(bot)
            
            if result:
                logger.info("✅ Successfully registered all commands with optimized approach")
                return True
            else:
                logger.warning("⚠️ Optimized command registration failed, falling back to alternatives")
        except Exception as e:
            logger.error(f"❌ Error in optimized command registration: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # First fallback: Try using sync_retry module if available
        try:
            from utils.sync_retry import safe_command_sync
            logger.info("Trying sync_retry fallback method")
            
            # We specifically avoid using bot.sync_commands() directly to prevent duplicate registration
            result = await safe_command_sync(bot)
            if result:
                logger.info("✅ Successfully synced commands with sync_retry fallback")
                
                # Save last successful sync time to prevent unnecessary retries
                with open(".last_command_check.txt", "w") as f:
                    f.write(str(time.time()))
                
                return True
            else:
                logger.warning("⚠️ sync_retry fallback failed, trying direct method")
        except Exception as e:
            logger.error(f"❌ Error with sync_retry fallback: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Second fallback: Use bot's built-in sync_commands
        try:
            logger.info("Using direct bot.sync_commands as second fallback")
            
            await bot.sync_commands(
                guild_ids=None,  # Register to global scope
                delete_existing=False  # Don't delete existing commands
            )
            logger.info("✅ Successfully synced commands with built-in method")
            
            # Save last successful sync time to prevent unnecessary retries
            with open(".last_command_check.txt", "w") as f:
                f.write(str(time.time()))
            
            return True
        except Exception as e:
            logger.error(f"❌ Error with built-in sync method: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Last resort: Register individual commands directly via API
        try:
            if len(bot.application_commands) > 0:
                # Just to ensure we have at least the ping command registered
                logger.warning("⚠️ Attempting to register individual commands as final resort")
                return await register_commands_individually(bot, [cmd.to_dict() for cmd in bot.application_commands])
        except Exception as e:
            logger.error(f"❌ Even individual command registration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return False
        
    except Exception as e:
        logger.error(f"❌ Critical error in slash command registration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False