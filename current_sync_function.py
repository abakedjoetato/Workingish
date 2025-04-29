async def sync_slash_commands():
    """Register all slash commands to Discord with detailed error handling"""
    try:
        logger.info("📝 STARTING COMMAND REGISTRATION")
        
        # First, fix any issues with command objects using our command_fix utilities
        try:
            from utils.command_fix import patch_discord_internals, apply_command_fixes
            
            # Apply the monkey patch to Discord internals
            if patch_discord_internals():
                logger.info("✅ Successfully patched Discord.py internals for improved command handling")
            else:
                logger.warning("⚠️ Could not patch Discord.py internals, will rely on command-by-command fixes")
            
            # Apply fixes to all command groups in all cogs
            fixed_count = apply_command_fixes(bot)
            logger.info(f"🔧 Applied fixes to {fixed_count} command objects")
        except Exception as e:
            logger.error(f"❌ Error applying command fixes: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Check if we can use the enhanced sync_retry module
        try:
            from utils.sync_retry import safe_command_sync
            logger.info("Enhanced command sync available via sync_retry module")
            use_enhanced_sync = True
        except ImportError:
            logger.warning("Enhanced command sync not available, falling back to standard approach")
            use_enhanced_sync = False
        
        # Import all command groups to make sure they're available
        logger.info("Step 1: Importing all command groups")
        from cogs.server_commands_refactored import server_group 
        from cogs.connection_commands import connection_group
        from cogs.killfeed_commands_refactored import killfeed_group
        from cogs.mission_commands_refactored import mission_group
        from cogs.faction_commands import faction_group
        from cogs.stats_commands_refactored import stats_group
        
        # Register all command groups to the bot - without clearing existing ones first
        logger.info("Step 2: Registering all command groups to bot")
        command_groups = [
            (server_group, "server"),
            (connection_group, "connections"),
            (killfeed_group, "killfeed"),
            (mission_group, "missions"),
            (faction_group, "faction"),
            (stats_group, "stats")
        ]
        
        # First clear the duplicates that might be causing our issues
        logger.info("Removing any duplicate command registrations first")
        unique_names = set()
        kept_commands = []
        
        for cmd in bot.application_commands:
            if cmd.name not in unique_names:
                unique_names.add(cmd.name)
                kept_commands.append(cmd)
            else:
                logger.warning(f"Removing duplicate command: {cmd.name}")
        
        # Replace application_commands with deduplicated list
        # We can't modify bot.application_commands directly, so we'll clear and re-add
        bot.application_commands.clear()
        for cmd in kept_commands:
            bot.application_commands.append(cmd)
        
        # Register each command group directly to the application commandment tree
        for group, name in command_groups:
            try:
                # First, ensure the group has the correct name
                if hasattr(group, 'name') and group.name != name:
                    logger.warning(f"🔄 Correcting command group name from '{group.name}' to '{name}'")
                    group.name = name
                
                # Check if already registered
                existing = next((cmd for cmd in bot.application_commands if cmd.name == name), None)
                if not existing:
                    try:
                        # Add it directly to the bot's command list
                        bot.add_application_command(group)
                        # Verify it was added
                        if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                            logger.info(f"✅ Successfully registered {name} command group to bot")
                        else:
                            logger.error(f"❌ Failed to register {name} command group - not found after adding")
                            # Try alternative method
                            logger.info(f"Attempting alternative registration for {name}")
                            bot.application_commands.append(group)
                            # Verify again
                            if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                                logger.info(f"✅ Successfully registered {name} using alternative method")
                            else:
                                logger.error(f"❌ All methods failed to register {name}")
                    except Exception as add_err:
                        logger.error(f"Error adding {name} via main method: {add_err}")
                        # Try alternative method
                        try:
                            logger.info(f"Trying alternative registration for {name}")
                            bot.application_commands.append(group)
                            # Verify it worked
                            if next((cmd for cmd in bot.application_commands if cmd.name == name), None):
                                logger.info(f"✅ Successfully registered {name} using alternative method")
                            else:
                                logger.error(f"❌ Alternative method also failed for {name}")
                        except Exception as alt_err:
                            logger.error(f"Alternative method also failed: {alt_err}")
                else:
                    logger.info(f"⏩ {name} command group already registered (skipping)")
            except Exception as e:
                logger.error(f"❌ Failed to register {name} command group: {e}")
                # Try a more direct approach as last resort
                try:
                    bot.application_commands.append(group)
                    logger.info(f"✅ Last resort registration attempt for {name}")
                except Exception as e2:
                    logger.error(f"All registration methods failed for {name}: {e2}")
        
        # Add utility commands
        logger.info("Step 3: Adding utility commands")
        
        # Add ping command if needed
        try:
            ping_cmd = next((cmd for cmd in bot.application_commands if cmd.name == "ping"), None)
            if not ping_cmd:
                bot.add_application_command(ping)
                logger.info("✅ Added ping command")
            else:
                logger.info("⏩ ping command already registered (skipping)")
        except Exception as e:
            logger.error(f"Failed to add ping command: {e}")
            
        # Add commands command if needed
        try:
            commands_cmd = next((cmd for cmd in bot.application_commands if cmd.name == "commands"), None)
            if not commands_cmd:
                bot.add_application_command(commands_menu)
                logger.info("✅ Added commands menu command")
            else:
                logger.info("⏩ commands menu command already registered (skipping)")
        except Exception as e:
            logger.error(f"Failed to add commands menu command: {e}")
            
        # Log what we have registered locally before sync
        logger.info("Local command state before sync:")
        local_cmds = bot.application_commands
        logger.info(f"Bot has {len(local_cmds)} local commands registered")
        
        if local_cmds:
            cmd_names = [cmd.name for cmd in local_cmds]
            logger.info(f"Local commands: {', '.join(cmd_names)}")
            
            # Log group commands and their subcommands
            for cmd in local_cmds:
                if hasattr(cmd, 'subcommands') and cmd.subcommands:
                    subcmd_names = [subcmd.name for subcmd in cmd.subcommands]
                    logger.info(f"• '{cmd.name}' subcommands: {', '.join(subcmd_names)}")
                    
        # Double-check we have all our main command groups before sync
        key_commands = ["server", "stats", "connections", "killfeed", "missions", "faction", "ping", "commands"]
        missing = []
        
        for key in key_commands:
            if not next((cmd for cmd in bot.application_commands if cmd.name == key), None):
                missing.append(key)
                
        if missing:
            logger.warning(f"⚠️ Missing commands before sync: {', '.join(missing)}")
        else:
            logger.info("✅ All key commands are registered locally")
        
        # NEW APPROACH: Direct JSON registration to bypass duplicate issues
        logger.info("Step 6: Using direct API registration approach")
        logger.info("This will make all commands available in Discord via direct registration")
        
        # Prepare a complete list of commands to register in raw JSON format
        # This bypasses the local application_commands list and works directly with Discord's API
        logger.info("Preparing direct command registration payload")
        
        try:
            # Get the list of all existing global commands
            existing_cmds = await bot.http.get_global_commands(bot.application_id)
            existing_cmd_names = [cmd.get('name') for cmd in existing_cmds]
            logger.info(f"Current commands on Discord: {', '.join(existing_cmd_names)}")
            
            # Register missing commands directly via HTTP
            # For simplicity, we'll just use what bot.sync_commands() would use
            # But we'll check each command group to ensure it's registered
            
            # NEW APPROACH: Register commands one by one via direct JSON payload
            logger.info("Attempting to register command groups directly via Discord API")
            
            # First check what's currently registered
            registered_cmds = await bot.http.get_global_commands(bot.application_id)
            registered_cmd_names = [cmd.get('name') for cmd in registered_cmds]
            logger.info(f"Current commands on Discord: {', '.join(registered_cmd_names)}")
            
            # If we don't have stats, server and other key commands, clear all and start fresh
            key_command_count = sum(1 for cmd in key_commands if cmd in registered_cmd_names)
            
            # Determine if we need a full command refresh using a cooldown system
            from pathlib import Path
            import time
            
            # Create a marker file to track the last full refresh
            last_refresh_file = Path(".last_command_refresh")
            current_time = time.time()
            refresh_interval = 3600 * 6  # 6 hours in seconds
            
            # Check if we've done a full refresh recently
            needs_refresh = True
            if last_refresh_file.exists():
                try:
                    # Read the timestamp from file
                    with open(last_refresh_file, "r") as f:
                        last_refresh = float(f.read().strip())
                    
                    # Check if we're still within the cooldown period
                    time_since_refresh = current_time - last_refresh
                    if time_since_refresh < refresh_interval:
                        # Only refresh if we're missing critical commands
                        if key_command_count >= len(key_commands) - 1:  # Allow one missing command
                            logger.info(f"Last command refresh was {time_since_refresh:.2f}s ago (<{refresh_interval}s). Skipping refresh.")
                            needs_refresh = False
                        else:
                            logger.warning(f"Missing critical commands despite recent refresh ({time_since_refresh:.2f}s ago)")
                    else:
                        logger.info(f"Last command refresh was {time_since_refresh:.2f}s ago (>{refresh_interval}s). Time for a refresh.")
                except Exception as e:
                    logger.error(f"Error reading last refresh timestamp: {e}")
            else:
                logger.info("No previous command refresh data found. Performing initial refresh.")
            
            # Always use the nuclear option to ensure all commands are properly registered
            if needs_refresh:
                
                # Step 1: Clear all commands from Discord with retry logic
                try:
                    # This is the nuclear option - clear ALL commands
                    try:
                        await bot.http.bulk_upsert_global_commands(bot.application_id, [])
                        logger.info("✅ Successfully cleared all global commands")
                    except discord.errors.HTTPException as rate_err:
                        if hasattr(rate_err, 'status') and rate_err.status == 429:
                            # If rate limited, log and wait before continuing
                            retry_after = getattr(rate_err, 'retry_after', 10)
                            logger.warning(f"Rate limited when clearing commands. Waiting {retry_after + 2}s")
                            await asyncio.sleep(retry_after + 2)
                            # Try again after waiting
                            await bot.http.bulk_upsert_global_commands(bot.application_id, [])
                            logger.info("✅ Successfully cleared all global commands after rate limit wait")
                        else:
                            # Other HTTP error
                            raise rate_err
                    
                    # Wait longer for Discord to process
                    logger.info("Waiting for Discord to process command clearing...")
                    await asyncio.sleep(5)
                    
                    # Step 2: Register them all fresh using bulk registration
                    if use_enhanced_sync:
                        logger.info("Using enhanced bulk registration from sync_retry")
                        success = await safe_command_sync(bot, force=True)
                        if success:
                            logger.info("✅ Bulk command registration successful")
                            
                            # Save registration timestamp to prevent frequent re-registration
                            with open(last_refresh_file, "w") as f:
                                f.write(str(time.time()))
