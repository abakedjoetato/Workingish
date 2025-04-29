import csv
import os
import aiofiles
import logging
import asyncio
from datetime import datetime
from database.connection import Database
from database.models import Kill, Player, ParserState, ParserMemory
from utils.log_access import get_all_csv_files
from utils.embeds import create_batch_progress_embed

logger = logging.getLogger('deadside_bot.parsers.batch_csv')

class BatchCSVParser:
    """
    Parser for processing multiple historical Deadside CSV log files containing kill data.
    
    This parser is designed to process all historical CSV files from a server's logs,
    tracking progress and providing status updates as it runs.
    """
    
    def __init__(self, server_id, server_name, channel=None, guild_id=None, message=None):
        """
        Initialize batch CSV parser for a specific server
        
        Args:
            server_id: MongoDB ObjectId of the server
            server_name: Name of the server for display purposes
            channel: Discord channel to send progress updates to (optional)
            guild_id: Discord guild ID (optional)
            message: Discord message to edit for progress updates (optional)
        """
        self.server_id = server_id
        self.server_name = server_name
        self.channel = channel
        self.guild_id = guild_id
        self.message = message
        self.files = []
        self.total_files = 0
        self.processed_files = 0
        self.total_lines = 0
        self.processed_lines = 0
        self.current_file = ""
        self.is_running = False
        self.last_update = None
        self.start_time = None
        self.last_file = None
        self.last_position = 0
        
    async def load_state(self):
        """Load parser state from the database"""
        db = await Database.get_instance()
        state = await ParserState.get_or_create(
            db, 
            self.server_id, 
            "csv", 
            True
        )
        self.last_position = state.last_position
        self.last_file = state.last_filename
        
        # Also load memory state
        memory = await ParserMemory.get_or_create(
            db,
            self.server_id,
            "batch_csv"
        )
        
        # Update parser state with memory values
        self.total_files = memory.total_files
        self.processed_files = memory.processed_files
        self.total_lines = memory.total_lines
        self.processed_lines = memory.processed_lines
        self.current_file = memory.current_file
        self.is_running = memory.is_running
        self.start_time = memory.start_time
        
        return state, memory
    
    async def save_state(self, filename=None, position=0):
        """
        Save parser state and update memory in the database
        
        Args:
            filename: Current CSV file being processed
            position: Current position in the file
        """
        db = await Database.get_instance()
        
        # Update parser state
        state = await ParserState.get_or_create(
            db, 
            self.server_id, 
            "csv", 
            True
        )
        state.last_position = position
        state.last_filename = filename or self.last_file
        await state.update(db)
        
        # Update parser memory
        memory = await ParserMemory.get_or_create(
            db,
            self.server_id,
            "batch_csv"
        )
        
        memory.total_files = self.total_files
        memory.processed_files = self.processed_files
        memory.total_lines = self.total_lines
        memory.processed_lines = self.processed_lines
        memory.current_file = self.current_file
        memory.percent_complete = self.get_percent_complete()
        memory.is_running = self.is_running
        memory.start_time = self.start_time or datetime.utcnow()
        memory.updated_at = datetime.utcnow()
        
        await memory.update(db)
        
        return state, memory
    
    async def reset_state(self):
        """Reset the parser state to start fresh"""
        self.last_position = 0
        self.last_file = None
        self.processed_files = 0
        self.processed_lines = 0
        self.current_file = ""
        self.is_running = False
        
        # Save the reset state
        await self.save_state()
        
    def get_percent_complete(self):
        """Calculate percentage of completion"""
        if self.total_lines <= 0:
            return 0
        
        percent = int((self.processed_lines / max(1, self.total_lines)) * 100)
        return min(100, percent)  # Cap at 100%
    
    async def update_progress(self, force=False):
        """
        Update progress information in Discord
        
        Args:
            force: If True, update even if not due for an update
        """
        if not self.channel or not self.guild_id:
            return
        
        now = datetime.utcnow()
        
        # Only update every 60 seconds unless forced
        if not force and self.last_update and (now - self.last_update).total_seconds() < 60:
            return
            
        self.last_update = now
        
        # Save current state
        _, memory = await self.save_state()
        
        # Create progress embed with proper description
        server_description = f"Processing historical data for server: {self.server_name}"
        embed = create_batch_progress_embed(memory, server_description)
        
        try:
            if self.message:
                await self.message.edit(embed=embed)
            else:
                self.message = await self.channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")
    
    async def count_total_lines(self, files):
        """
        Count total lines across all CSV files
        
        Args:
            files: List of CSV file paths
            
        Returns:
            int: Total line count
        """
        total = 0
        for file_path in files:
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                    lines = await file.read()
                    total += len(lines.split('\n'))
            except Exception as e:
                logger.error(f"Error counting lines in {file_path}: {e}")
        
        return total
    
    async def parse_batch(self, server, channel=None):
        """
        Parse all CSV files for a server and track progress
        
        Args:
            server: Server object
            channel: Discord channel to send updates to (optional)
            
        Returns:
            dict: Summary of batch processing
        """
        db = await Database.get_instance()
        self.channel = channel
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        # Set status as initializing
        await self.save_state()
        
        try:
            # Get all CSV files
            self.files = await get_all_csv_files(server)
            self.total_files = len(self.files)
            
            if not self.files:
                logger.warning(f"No CSV files found for server {server.name}")
                memory = await ParserMemory.get_or_create(db, self.server_id, "batch_csv")
                memory.status = "No CSV files found"
                memory.is_running = False
                await memory.update(db)
                await self.update_progress(force=True)
                return {"success": False, "message": "No CSV files found"}
            
            # Count total lines
            memory = await ParserMemory.get_or_create(db, self.server_id, "batch_csv")
            memory.status = "Counting lines in files"
            await memory.update(db)
            await self.update_progress(force=True)
            
            self.total_lines = await self.count_total_lines(self.files)
            
            # Update status to processing
            memory.status = "Processing files"
            memory.total_files = self.total_files
            memory.total_lines = self.total_lines
            await memory.update(db)
            await self.update_progress(force=True)
            
            # Start from the most recent file not processed before
            if self.last_file:
                try:
                    last_file_index = self.files.index(self.last_file)
                    self.processed_files = last_file_index
                    self.files = self.files[last_file_index:]
                    
                    # Add lines from previously processed files to processed count
                    for i in range(last_file_index):
                        async with aiofiles.open(self.files[i], 'r', encoding='utf-8') as file:
                            lines = await file.read()
                            self.processed_lines += len(lines.split('\n'))
                    
                except ValueError:
                    # Last file not found in current list, start from beginning
                    self.processed_files = 0
                    self.processed_lines = 0
            
            # Process each file
            total_kills = 0
            for file_path in self.files:
                self.current_file = os.path.basename(file_path)
                
                # Skip already fully processed files (in case of restarting)
                if file_path == self.last_file and self.last_position > 0:
                    continue
                
                # Update status
                memory.status = f"Processing {self.current_file}"
                memory.current_file = self.current_file
                await memory.update(db)
                await self.update_progress()
                
                # Process the file
                kills = await self.parse_file(file_path, db)
                total_kills += len(kills)
                
                # Update processed files count
                self.processed_files += 1
                self.last_file = file_path
                
                # Save state after each file
                await self.save_state(file_path, 0)
                
                # Important: Update the auto parser state to match this file
                # This prevents the auto parser from reprocessing the same file
                auto_state = await ParserState.get_or_create(
                    db,
                    self.server_id,
                    "csv",
                    False  # Auto parser uses is_historical=False
                )
                auto_state.last_filename = os.path.basename(file_path)
                auto_state.last_position = 0  # Start at beginning of next file
                await auto_state.update(db)
                logger.info(f"Updated auto parser state for server {self.server_id} to file {file_path}")
            
            # Mark as completed
            memory = await ParserMemory.get_or_create(db, self.server_id, "batch_csv")
            memory.status = "Complete"
            memory.is_running = False
            memory.percent_complete = 100
            memory.processed_files = self.total_files
            memory.processed_lines = self.total_lines
            await memory.update(db)
            
            # Final update
            await self.update_progress(force=True)
            
            self.is_running = False
            return {
                "success": True,
                "total_files": self.total_files,
                "total_lines": self.total_lines,
                "total_kills": total_kills
            }
            
        except Exception as e:
            logger.error(f"Error in batch CSV parsing: {e}")
            
            # Update status to error
            memory = await ParserMemory.get_or_create(db, self.server_id, "batch_csv")
            memory.status = f"Error: {str(e)}"
            memory.is_running = False
            await memory.update(db)
            
            try:
                await self.update_progress(force=True)
            except:
                pass
                
            self.is_running = False
            return {"success": False, "message": str(e)}
    
    async def parse_file(self, file_path, db):
        """
        Parse a single CSV file and store kill events
        
        Args:
            file_path: Path to the CSV file
            db: Database instance
            
        Returns:
            list: Processed kill records
        """
        kills = []
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                # Read all lines at once for processing
                content = await file.read()
                lines = content.strip().split('\n')
                
                for i, line in enumerate(lines):
                    try:
                        # Skip empty lines
                        if not line.strip():
                            continue
                            
                        # Parse the CSV line
                        row = line.split(',')
                        if len(row) < 7:  # Ensure we have enough fields
                            logger.warning(f"Skipping invalid line in {file_path} - not enough fields: {line}")
                            continue
                        
                        # Extract data
                        timestamp_str = row[0].strip()
                        killer_name = row[1].strip()
                        killer_id = row[2].strip()
                        victim_name = row[3].strip()
                        victim_id = row[4].strip()
                        weapon = row[5].strip()
                        distance = float(row[6].strip()) if row[6].strip() else 0
                        
                        # Parse timestamp
                        try:
                            timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
                        except ValueError:
                            logger.warning(f"Invalid timestamp format in {file_path}: {timestamp_str}")
                            continue
                        
                        # Determine kill type
                        is_suicide = killer_id == victim_id
                        is_menu_suicide = is_suicide and weapon.lower() == "menu"
                        is_fall_death = is_suicide and weapon.lower() == "fall damage"
                        
                        # Create and store kill record with batch processing flag to prevent killfeed spam
                        kill = await Kill.create(
                            db,
                            timestamp=timestamp,
                            killer_id=killer_id,
                            killer_name=killer_name,
                            victim_id=victim_id,
                            victim_name=victim_name,
                            weapon=weapon,
                            distance=distance,
                            server_id=self.server_id,
                            is_suicide=is_suicide,
                            is_menu_suicide=is_menu_suicide,
                            is_fall_death=is_fall_death,
                            from_batch_process=True  # Flag to indicate this kill was from batch processing
                        )
                        
                        # Update player stats
                        await self.update_player_stats(db, killer_id, killer_name, victim_id, victim_name)
                        
                        kills.append(kill)
                        
                    except Exception as e:
                        logger.error(f"Error processing line in {file_path}: {e}")
                    
                    # Update progress every 100 lines
                    self.processed_lines += 1
                    if i % 100 == 0:
                        # Update if it's time but don't force
                        await self.update_progress()
                
        except Exception as e:
            logger.error(f"Error opening or reading {file_path}: {e}")
        
        return kills
    
    async def update_player_stats(self, db, killer_id, killer_name, victim_id, victim_name):
        """
        Update player statistics for both killer and victim
        
        Args:
            db: Database instance
            killer_id: SteamID of the killer
            killer_name: Name of the killer
            victim_id: SteamID of the victim
            victim_name: Name of the victim
        """
        # Skip processing if this is self-inflicted (suicide)
        is_suicide = killer_id == victim_id
        
        # Get or create the kill object for rivalry tracking (using Kill object in memory only, not persisting)
        kill_event = None
        if not is_suicide:
            # We'll use this kill event object to update rivalry data
            kill_event = Kill(
                timestamp=datetime.utcnow(),  # This is just for the object, not for storage
                killer_id=killer_id,
                killer_name=killer_name,
                victim_id=victim_id, 
                victim_name=victim_name,
                weapon="",  # Not needed for rivalry tracking
                distance=0, # Not needed for rivalry tracking
                server_id=self.server_id,
                is_suicide=is_suicide
            )
            
        # Process killer stats
        killer = await Player.get_by_player_id(db, killer_id)
        if killer:
            # Only increment kills if not a suicide
            if not is_suicide:
                killer.total_kills += 1
                
            # Always update timestamps and names
            killer.last_seen = datetime.utcnow()
            if killer.player_name != killer_name:
                killer.player_name = killer_name  # Update name if changed
                
            await killer.update(db)
        else:
            # Create new player record
            killer = await Player.create(
                db,
                player_id=killer_id,
                player_name=killer_name,
                total_kills=(0 if is_suicide else 1),
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow()
            )
            
        # Update rivalry tracking for killer (when they kill someone)
        if kill_event and not is_suicide:
            await killer.update_rivalry_data(db, kill_event=kill_event)
        
        # Process victim stats (only if different from killer)
        if killer_id != victim_id:
            victim = await Player.get_by_player_id(db, victim_id)
            if victim:
                victim.total_deaths += 1
                victim.last_seen = datetime.utcnow()
                if victim.player_name != victim_name:
                    victim.player_name = victim_name  # Update name if changed
                await victim.update(db)
            else:
                # Create new player record
                victim = await Player.create(
                    db,
                    player_id=victim_id,
                    player_name=victim_name,
                    total_deaths=1,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow()
                )
                
            # Update rivalry tracking for victim (when they are killed)
            if kill_event:
                await victim.update_rivalry_data(db, death_event=kill_event)