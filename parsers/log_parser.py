import re
import logging
import aiofiles
from datetime import datetime
from database.connection import Database
from database.models import ParserState, ServerEvent, Mission

logger = logging.getLogger('deadside_bot.parsers.log')

class LogParser:
    """
    Parser for Deadside log files containing server events.
    
    This parser extracts information about:
    - Server starts/stops
    - Mission changes
    - Helicopter crashes
    - Airdrops
    - Trader events
    """
    
    # Regular expressions for parsing log entries
    RE_SERVER_START = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Server started'
    RE_SERVER_STOP = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Server stopping'
    RE_MISSION = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Mission\s+(?P<mission_name>[^:]+):\s+(?P<status>started|finished|completed)'
    RE_HELICOPTER = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Helicopter crash.*at\s+(?P<location>[\d\., ]+)'
    RE_AIRDROP = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Airdrop.*at\s+(?P<location>[\d\., ]+)'
    RE_TRADER = r'(?P<timestamp>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}).*Trader\s+(?P<trader_name>[^:]+):\s+(?P<status>appeared|disappeared)'
    
    def __init__(self, server_id):
        """
        Initialize log parser for a specific server
        
        Args:
            server_id: MongoDB ObjectId of the server
        """
        self.server_id = server_id
        self.last_position = 0
        
    async def load_state(self):
        """Load the last parser position from the database"""
        db = await Database.get_instance()
        state = await ParserState.get_or_create(
            db, 
            self.server_id, 
            "log", 
            False  # is_historical = False
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
        logger.info(f"Reset log parser state for server {self.server_id}")
        
    async def parse_file(self, file_path):
        """
        Parse the log file and store server events in the database
        
        Args:
            file_path: Path to the log file
            
        Returns:
            list: Processed event records
        """
        await self.load_state()
        db = await Database.get_instance()
        processed_events = []
        
        try:
            async with aiofiles.open(file_path, mode='r') as f:
                # Seek to last position
                if self.last_position > 0:
                    await f.seek(self.last_position)
                    
                content = await f.read()
                current_position = await f.tell()
            
            if not content.strip():
                # No new content
                logger.debug(f"No new content in log file for server {self.server_id}")
                return []
                
            # Process each line
            for line in content.strip().split('\n'):
                event = await self.parse_line(line, db)
                if event:
                    processed_events.append(event)
            
            # Update parser state
            await self.save_state(current_position)
            
            if processed_events:
                logger.info(f"Parsed {len(processed_events)} server events for server {self.server_id}")
            
            return processed_events
            
        except Exception as e:
            logger.error(f"Error parsing log file for server {self.server_id}: {e}")
            return []
    
    async def parse_line(self, line, db):
        """
        Parse a single log line and create an event record if it matches
        
        Args:
            line: Log line to parse
            db: Database instance
            
        Returns:
            ServerEvent or None: Created event record, or None if line doesn't match
        """
        try:
            # Try to match each event type
            server_start = re.search(self.RE_SERVER_START, line)
            if server_start:
                return await self.create_event(db, server_start, "server_start")
                
            server_stop = re.search(self.RE_SERVER_STOP, line)
            if server_stop:
                return await self.create_event(db, server_stop, "server_stop")
                
            mission = re.search(self.RE_MISSION, line)
            if mission:
                return await self.create_mission_event(db, mission)
                
            helicopter = re.search(self.RE_HELICOPTER, line)
            if helicopter:
                return await self.create_event(db, helicopter, "helicrash", location=helicopter.group("location"))
                
            airdrop = re.search(self.RE_AIRDROP, line)
            if airdrop:
                return await self.create_event(db, airdrop, "airdrop", location=airdrop.group("location"))
                
            trader = re.search(self.RE_TRADER, line)
            if trader:
                return await self.create_trader_event(db, trader)
                
            # No match
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing log line: {e} - Line: {line}")
            return None
    
    async def create_event(self, db, match, event_type, **kwargs):
        """
        Create a server event record
        
        Args:
            db: Database instance
            match: Regex match object
            event_type: Type of event
            **kwargs: Additional event data
            
        Returns:
            ServerEvent: Created event record
        """
        timestamp_str = match.group("timestamp")
        timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
        
        event = await ServerEvent.create(
            db,
            server_id=self.server_id,
            timestamp=timestamp,
            event_type=event_type,
            **kwargs
        )
        
        return event
    
    async def create_mission_event(self, db, match):
        """
        Create a mission event record
        
        Args:
            db: Database instance
            match: Regex match object
            
        Returns:
            ServerEvent: Created event record
        """
        timestamp_str = match.group("timestamp")
        timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
        mission_name = match.group("mission_name")
        status = match.group("status")
        
        # Create server event
        event = await ServerEvent.create(
            db,
            server_id=self.server_id,
            timestamp=timestamp,
            event_type="mission",
            mission_name=mission_name,
            mission_status=status
        )
        
        # Also create or update mission record
        if status == "started":
            # New mission started
            mission = await Mission.create(
                db,
                server_id=self.server_id,
                mission_name=mission_name,
                start_time=timestamp,
                is_active=True
            )
        elif status in ["finished", "completed"]:
            # Find active mission with this name
            mission = await Mission.get_active_by_name(db, self.server_id, mission_name)
            if mission:
                mission.is_active = False
                mission.end_time = timestamp
                await mission.update(db)
        
        return event
    
    async def create_trader_event(self, db, match):
        """
        Create a trader event record
        
        Args:
            db: Database instance
            match: Regex match object
            
        Returns:
            ServerEvent: Created event record
        """
        timestamp_str = match.group("timestamp")
        timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
        trader_name = match.group("trader_name")
        status = match.group("status")
        
        event = await ServerEvent.create(
            db,
            server_id=self.server_id,
            timestamp=timestamp,
            event_type="trader",
            trader_name=trader_name,
            trader_status=status
        )
        
        return event