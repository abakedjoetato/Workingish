async def sync_slash_commands():
    """Register all slash commands to Discord with unified approach and proper rate limit handling"""
    try:
        logger.info("📝 STARTING OPTIMIZED COMMAND REGISTRATION")
        
        # Check for command reset request (useful for debugging)
        if os.environ.get("CLEAR_COMMANDS", "false").lower() == "true":
            try:
                from discord.http import Route
                await bot.http.request(
                    Route("PUT", f"/applications/{bot.application_id}/commands"), 
                    json=[]
                )
                logger.info("🧹 Cleared all global commands")
                # Give Discord's API time to process the clearing
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error clearing commands: {e}")
        
        # 1. Fix command objects with the command_fix utilities
        try:
            from utils.command_fix import patch_discord_internals, apply_command_fixes
            
            # Apply global patch to Discord internals
            patch_result = patch_discord_internals()
            if patch_result:
                logger.info("✅ Successfully patched Discord.py internals for improved command handling")
            else:
                logger.warning("⚠️ Could not patch Discord.py internals, using per-command fixes instead")
            
            # Apply fixes to all command objects
            fixed_count = apply_command_fixes(bot)
            logger.info(f"🔧 Applied fixes to {fixed_count} command objects")
        except Exception as e:
            logger.error(f"❌ Error applying command fixes: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # 2. Deduplicate commands to avoid registration conflicts
        logger.info("Deduplicating commands for registration")
        unique_names = set()
        kept_commands = []
        
        for cmd in bot.application_commands:
            if cmd.name not in unique_names:
                unique_names.add(cmd.name)
                kept_commands.append(cmd)
                logger.info(f"Keeping command: {cmd.name}")
            else:
                logger.warning(f"Removing duplicate command: {cmd.name}")
        
        # Replace application_commands with deduplicated list
        bot.application_commands.clear()
        for cmd in kept_commands:
            bot.application_commands.append(cmd)
        
        # 3. Import any missing command groups from cogs
        logger.info("Ensuring all command groups are available")
        try:
            from cogs.analytics_cog import AnalyticsCog
            from cogs.faction_commands import FactionCommands
            from cogs.rivalry_commands import RivalryCommands
            
            # Add references to analytics command group
            for cog_name, cog_instance in bot.cogs.items():
                if hasattr(cog_instance, 'analytics') and cog_name == 'AnalyticsCog':
                    analytics_group = cog_instance.analytics
                    # Check if already registered
                    existing = next((cmd for cmd in bot.application_commands if cmd.name == 'analytics'), None)
                    if not existing:
                        logger.info("Adding analytics command group to bot")
                        bot.add_application_command(analytics_group)
                
                # Add any rivalry commands
                if hasattr(cog_instance, 'rivalry') and cog_name == 'RivalryCommands':
                    rivalry_group = cog_instance.rivalry
                    # Check if already registered
                    existing = next((cmd for cmd in bot.application_commands if cmd.name == 'rivalry'), None)
                    if not existing:
                        logger.info("Adding rivalry command group to bot")
                        bot.add_application_command(rivalry_group)
        except Exception as e:
            logger.error(f"Error adding specific command groups: {e}")
            
        # 4. Create a unified batch payload of all commands
        logger.info("Creating unified command payload for bulk registration")
        commands_payload = []
        
        for cmd in bot.application_commands:
            try:
                # Convert command to dictionary payload
                cmd_dict = cmd.to_dict()
                commands_payload.append(cmd_dict)
                logger.info(f"Added command to payload: {cmd.name}")
            except Exception as e:
                logger.error(f"Error converting command {cmd.name} to dict: {e}")
                
        # 5. Register all commands in a single batch with robust retry logic
        logger.info(f"Registering {len(commands_payload)} commands with Discord")
        
        max_retries = 5
        for retry in range(max_retries):
            try:
                # Use Discord's HTTP API directly for better control and error handling
                from discord.http import Route
                
                # First verify the application ID and auth are working
                try:
                    test_route = Route("GET", f"/applications/{bot.application_id}/commands")
                    await bot.http.request(test_route)
                    logger.info("✅ Discord API access verified")
                except Exception as e:
                    logger.error(f"❌ Cannot access Discord API. Verify your bot token: {e}")
                    # If we can't access the API at all, no point in retry
                    return False
                
                # Use PUT to replace all commands in one batch request
                route = Route("PUT", f"/applications/{bot.application_id}/commands")
                result = await bot.http.request(route, json=commands_payload)
                
                logger.info(f"✅ Successfully registered all {len(commands_payload)} commands in bulk!")
                
                # Save last successful sync time to prevent unnecessary retries
                with open(".last_command_check.txt", "w") as f:
                    f.write(str(time.time()))
                
                return True
                
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    # Extract retry time directly from Discord
                    retry_after = getattr(e, 'retry_after', 60)
                    logger.warning(f"⏱️ Rate limited. Retrying after {retry_after} seconds (attempt {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        await asyncio.sleep(retry_after + 2)  # Add a little buffer
                elif e.status == 400:  # Bad request
                    # Try to identify and fix the problematic command(s)
                    logger.error(f"Bad request error: {e}")
                    if retry < max_retries - 1:
                        logger.info("Attempting to fix command payload...")
                        # Ensure all commands have descriptions
                        for cmd in commands_payload:
                            if not cmd.get('description'):
                                cmd['description'] = f"Command for {cmd.get('name', 'unknown')} functionality"
                        await asyncio.sleep(5)
                else:
                    logger.error(f"HTTP Error: {e}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(10 * (retry + 1))  # Exponential backoff
            except Exception as e:
                logger.error(f"Error registering commands: {e}")
                if retry < max_retries - 1:
                    await asyncio.sleep(10 * (retry + 1))

        # If we reach here, all retries failed
        logger.error(f"Failed to register commands after {max_retries} attempts")
        
        # EMERGENCY FALLBACK: Try registering critical commands individually as last resort
        logger.warning("Attempting emergency fallback: registering ping command directly")
        try:
            critical_command = {
                "name": "ping",
                "description": "Check bot response time",
                "type": 1
            }
            route = Route("POST", f"/applications/{bot.application_id}/commands")
            await bot.http.request(route, json=critical_command)
            logger.info("✅ Emergency ping command registered")
        except Exception as e:
            logger.error(f"Even emergency fallback failed: {e}")
            
        return False
    
    except Exception as e:
        logger.error(f"Critical error in slash command registration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False