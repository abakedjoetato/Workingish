import csv
import os
import aiofiles
import logging
from datetime import datetime
from database.connection import Database
from database.models import Kill, Player, ParserState
from utils.log_access import get_newest_csv_file

logger = logging.getLogger('deadside_bot.parsers.csv')

class CSVParser:
    """
    Parser for Deadside CSV log files containing kill data.
    
    CSV format example:
    2023.05.20-15.30.45,PlayerKiller,76561198012345678,PlayerVictim,76561198087654321,M4A1,250
    timestamp,killer_name,killer_id,victim_name,victim_id,weapon,distance
    """
    
    def __init__(self, server_id, is_historical=False, auto_parsing_enabled=True):
        """
        Initialize CSV parser for a specific server
        
        Args:
            server_id: MongoDB ObjectId of the server
            is_historical: If True, parse entire file, otherwise only new entries
            auto_parsing_enabled: Whether auto-parsing is enabled for this server
        """
        self.server_id = server_id
        self.is_historical = is_historical
        self.auto_parsing_enabled = auto_parsing_enabled
        self.last_position = 0
        self.last_file = None
        
    async def load_state(self):
        """Load the last parser position from the database"""
        db = await Database.get_instance()
        state = await ParserState.get_or_create(
            db, 
            self.server_id, 
            "csv", 
            self.is_historical
        )
        self.last_position = state.last_position
        return state
    
    async def save_state(self, position):
        """Save the current parser position to the database"""
        db = await Database.get_instance()
        state = await self.load_state()
        state.last_position = position
        await state.update(db)
    
    async def reset_state(self):
        """Reset the parser position to the beginning of the file"""
        self.last_position = 0
        await self.save_state(0)
        logger.info(f"Reset CSV parser state for server {self.server_id}")
    
    async def parse_newest_csv(self, server):
        """
        Parse only the newest CSV file for a server
        
        Args:
            server: Server object
            
        Returns:
            list: Processed kill records
        """
        try:
            # Get the newest CSV file
            file_path = await get_newest_csv_file(server)
            if not file_path:
                logger.warning(f"No newest CSV file found for server {server.get('name', self.server_id)}")
                return []
            
            # Load the parser state
            state = await self.load_state()
            
            # Check if this is a new file
            if state.last_filename and state.last_filename != os.path.basename(file_path):
                logger.info(f"New CSV file detected for server {self.server_id}: {file_path}")
                # Reset position for new file
                self.last_position = 0
                state.last_position = 0
                state.last_filename = os.path.basename(file_path)
                db = await Database.get_instance()
                await state.update(db)
            
            # Parse the file
            return await self.parse_file(file_path)
        
        except Exception as e:
            logger.error(f"Error parsing newest CSV file for server {self.server_id}: {e}")
            return []
    
    async def parse_file(self, file_path):
        """
        Parse the CSV log file and store kill events in the database
        
        Args:
            file_path: Path to the CSV log file
            
        Returns:
            list: Processed kill records
        """
        await self.load_state()
        db = await Database.get_instance()
        processed_records = []
        
        try:
            async with aiofiles.open(file_path, mode='r') as f:
                # Seek to last position if not historical
                if not self.is_historical and self.last_position > 0:
                    await f.seek(self.last_position)
                    
                content = await f.read()
                current_position = await f.tell()
            
            lines = content.strip().split('\n')
            if not lines or (len(lines) == 1 and not lines[0]):
                # No new content
                logger.debug(f"No new content in CSV log for server {self.server_id}")
                return []
                
            # Process CSV data
            reader = csv.reader(lines)
            
            for row in reader:
                if len(row) < 7:  # Ensure we have all required fields
                    logger.warning(f"Invalid CSV row (not enough fields): {row}")
                    continue
                    
                try:
                    timestamp_str, killer_name, killer_id, victim_name, victim_id, weapon, distance = row[:7]
                    
                    # Parse timestamp and distance
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    distance = float(distance) if distance else 0
                    
                    # Handle special cases
                    is_suicide = killer_id == victim_id
                    is_menu_suicide = weapon == "suicide_by_relocation"
                    is_fall_death = weapon == "falling"
                    
                    # Create kill record
                    kill = await Kill.create(db, 
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
                        is_fall_death=is_fall_death
                    )
                    
                    processed_records.append(kill)
                    
                    # Update player stats
                    await self.update_player_stats(db, killer_id, killer_name, victim_id, victim_name)
                    
                except ValueError as e:
                    logger.warning(f"Error parsing CSV row {row}: {e}")
                    continue
            
            # Update parser state
            await self.save_state(current_position)
            
            if processed_records:
                logger.info(f"Parsed {len(processed_records)} kill events from CSV for server {self.server_id}")
            
            return processed_records
            
        except Exception as e:
            logger.error(f"Error parsing CSV file for server {self.server_id}: {e}")
            return []
    
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
        
        # Get or create the kill object for rivalry tracking
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
        
        # Update killer stats
        if killer_id:
            killer = await Player.get_by_player_id(db, killer_id)
            if not killer:
                killer = await Player.create(db,
                    player_id=killer_id,
                    player_name=killer_name
                )
            else:
                # Update name if it has changed
                if killer.player_name != killer_name:
                    killer.player_name = killer_name
                
                # Increment kills (only if not a suicide)
                if not is_suicide:
                    killer.total_kills += 1
                
                await killer.update(db)
            
            # Update rivalry tracking for killer (when they kill someone)
            if kill_event and not is_suicide:
                await killer.update_rivalry_data(db, kill_event=kill_event)
        
        # Update victim stats
        if victim_id:
            victim = await Player.get_by_player_id(db, victim_id)
            if not victim:
                victim = await Player.create(db,
                    player_id=victim_id,
                    player_name=victim_name,
                    total_deaths=1
                )
            else:
                # Update name if it has changed
                if victim.player_name != victim_name:
                    victim.player_name = victim_name
                
                # Increment deaths
                victim.total_deaths += 1
                
                await victim.update(db)
            
            # Update rivalry tracking for victim (when they are killed)
            if kill_event and not is_suicide:
                await victim.update_rivalry_data(db, death_event=kill_event)
            
    async def set_auto_parsing(self, enabled):
        """
        Enable or disable auto-parsing for this server
        
        Args:
            enabled: Boolean indicating whether auto-parsing should be enabled
            
        Returns:
            bool: The new state
        """
        self.auto_parsing_enabled = enabled
        
        # Update state in database
        db = await Database.get_instance()
        state = await self.load_state()
        state.auto_parsing_enabled = enabled
        await state.update(db)
        
        logger.info(f"Auto-parsing for server {self.server_id} set to: {enabled}")
        return enabled
