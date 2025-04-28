import re
import aiofiles
import logging
from datetime import datetime
from database.connection import Database
from database.models import ServerEvent, ConnectionEvent, Player, ParserState

logger = logging.getLogger('deadside_bot.parsers.log')

class LogParser:
    """
    Parser for deadside.log files containing server events and player connections.
    
    Log format examples:
    [2023.05.20-15.30.45] Mission spawned: Cargo Plane (Level 3)
    [2023.05.20-15.31.10] PlayerName connected
    [2023.05.20-15.45.20] PlayerName disconnected
    """
    
    def __init__(self, server_id, is_historical=False):
        """
        Initialize log parser for a specific server
        
        Args:
            server_id: MongoDB ObjectId of the server
            is_historical: If True, parse entire file, otherwise only new entries
        """
        self.server_id = server_id
        self.is_historical = is_historical
        self.last_position = 0
        
        # Compile regex patterns for better performance
        self.timestamp_pattern = r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})\]'
        self.mission_regex = re.compile(f'{self.timestamp_pattern} Mission spawned: (.+) \(Level (\d+)\)')
        self.helicrash_regex = re.compile(f'{self.timestamp_pattern} Helicopter crash at (.+)')
        self.airdrop_regex = re.compile(f'{self.timestamp_pattern} Airdrop at (.+)')
        self.trader_regex = re.compile(f'{self.timestamp_pattern} Trader appeared at (.+)')
        self.connect_regex = re.compile(f'{self.timestamp_pattern} (.+) connected')
        self.disconnect_regex = re.compile(f'{self.timestamp_pattern} (.+) disconnected')
        self.kick_regex = re.compile(f'{self.timestamp_pattern} (.+) was kicked: (.+)')
        self.server_start_regex = re.compile(f'{self.timestamp_pattern} Server started')
        self.server_stop_regex = re.compile(f'{self.timestamp_pattern} Server stopped')
        
    async def load_state(self):
        """Load the last parser position from the database"""
        db = await Database.get_instance()
        state = await ParserState.get_or_create(
            db, 
            self.server_id, 
            "log", 
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
        logger.info(f"Reset log parser state for server {self.server_id}")
    
    async def parse_file(self, file_path):
        """
        Parse the deadside.log file and store events in the database
        
        Args:
            file_path: Path to the log file
            
        Returns:
            dict: Summary of processed events by type
        """
        await self.load_state()
        db = await Database.get_instance()
        events_summary = {
            "mission": 0,
            "helicrash": 0,
            "airdrop": 0,
            "trader": 0,
            "connect": 0,
            "disconnect": 0,
            "kick": 0,
            "server_start": 0,
            "server_stop": 0
        }
        
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
                logger.debug(f"No new content in log file for server {self.server_id}")
                return events_summary
                
            # Process each line
            for line in lines:
                # Mission events
                mission_match = self.mission_regex.match(line)
                if mission_match:
                    timestamp_str, mission_name, mission_level = mission_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="mission",
                        server_id=self.server_id,
                        details={
                            "name": mission_name,
                            "level": int(mission_level)
                        }
                    )
                    events_summary["mission"] += 1
                    continue
                
                # Helicopter crash events
                helicrash_match = self.helicrash_regex.match(line)
                if helicrash_match:
                    timestamp_str, location = helicrash_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="helicrash",
                        server_id=self.server_id,
                        details={
                            "location": location
                        }
                    )
                    events_summary["helicrash"] += 1
                    continue
                
                # Airdrop events
                airdrop_match = self.airdrop_regex.match(line)
                if airdrop_match:
                    timestamp_str, location = airdrop_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="airdrop",
                        server_id=self.server_id,
                        details={
                            "location": location
                        }
                    )
                    events_summary["airdrop"] += 1
                    continue
                
                # Trader events
                trader_match = self.trader_regex.match(line)
                if trader_match:
                    timestamp_str, location = trader_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="trader",
                        server_id=self.server_id,
                        details={
                            "location": location
                        }
                    )
                    events_summary["trader"] += 1
                    continue
                
                # Player connect events
                connect_match = self.connect_regex.match(line)
                if connect_match:
                    timestamp_str, player_name = connect_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    # In logs we may not have player ID, just record the event with name
                    await ConnectionEvent.create(db,
                        timestamp=timestamp,
                        player_name=player_name,
                        player_id=None,  # We don't have the ID from the log
                        server_id=self.server_id,
                        event_type="connect"
                    )
                    
                    # Update or create player
                    # Try to find player by name
                    cursor = db.get_collection("players").find({"player_name": player_name})
                    player = None
                    async for p in cursor:
                        player = Player(**{**p, "_id": p["_id"]})
                        break
                        
                    if not player:
                        await Player.create(db,
                            player_id=None,  # Unknown at this point
                            player_name=player_name
                        )
                    
                    events_summary["connect"] += 1
                    continue
                
                # Player disconnect events
                disconnect_match = self.disconnect_regex.match(line)
                if disconnect_match:
                    timestamp_str, player_name = disconnect_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ConnectionEvent.create(db,
                        timestamp=timestamp,
                        player_name=player_name,
                        player_id=None,  # We don't have the ID from the log
                        server_id=self.server_id,
                        event_type="disconnect"
                    )
                    events_summary["disconnect"] += 1
                    continue
                
                # Player kick events
                kick_match = self.kick_regex.match(line)
                if kick_match:
                    timestamp_str, player_name, reason = kick_match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ConnectionEvent.create(db,
                        timestamp=timestamp,
                        player_name=player_name,
                        player_id=None,  # We don't have the ID from the log
                        server_id=self.server_id,
                        event_type="kick",
                        reason=reason
                    )
                    events_summary["kick"] += 1
                    continue
                
                # Server start events
                server_start_match = self.server_start_regex.match(line)
                if server_start_match:
                    timestamp_str = server_start_match.group(1)
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="server_start",
                        server_id=self.server_id
                    )
                    events_summary["server_start"] += 1
                    continue
                
                # Server stop events
                server_stop_match = self.server_stop_regex.match(line)
                if server_stop_match:
                    timestamp_str = server_stop_match.group(1)
                    timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                    
                    await ServerEvent.create(db,
                        timestamp=timestamp,
                        event_type="server_stop",
                        server_id=self.server_id
                    )
                    events_summary["server_stop"] += 1
                    continue
            
            # Update parser state
            await self.save_state(current_position)
            
            # Log summary
            total_events = sum(events_summary.values())
            if total_events > 0:
                logger.info(f"Parsed {total_events} events from log file for server {self.server_id}")
            
            return events_summary
            
        except Exception as e:
            logger.error(f"Error parsing log file for server {self.server_id}: {e}")
            return events_summary
