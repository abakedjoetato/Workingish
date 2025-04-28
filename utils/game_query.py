"""
Game Query Utilities

This module provides utilities for querying game servers using the Gamedig protocol.
It supports a variety of game servers, but is primarily focused on Deadside servers.
"""

import asyncio
import json
import logging
import socket
import time
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.utils.game_query')

# Cache for server query results
query_cache = {}
CACHE_DURATION = 60  # seconds

async def query_game_server(host, port, game_type="deadside"):
    """
    Query a game server for status information
    
    Args:
        host: Server hostname or IP
        port: Server port
        game_type: Game type (default: deadside)
        
    Returns:
        dict: Server status information or error
    """
    if not host or not port:
        logger.error("Missing host or port in query_game_server")
        return create_error_response("Missing host or port")
        
    # Check cache first
    cache_key = f"{host}:{port}"
    if cache_key in query_cache:
        cache_entry = query_cache[cache_key]
        # If the cache entry is still fresh, return it
        if time.time() - cache_entry["timestamp"] < CACHE_DURATION:
            logger.debug(f"Returning cached result for {cache_key}")
            return cache_entry["data"]
    
    # No cache hit, perform the query
    try:
        # For Deadside, use Steam query protocol (A2S)
        if game_type.lower() == "deadside":
            result = await query_steam_server(host, port)
        else:
            # Fallback to Steam query for now
            result = await query_steam_server(host, port)
        
        # Cache the result
        query_cache[cache_key] = {
            "timestamp": time.time(),
            "data": result
        }
        
        return result
    except Exception as e:
        logger.error(f"Error querying game server {host}:{port}: {e}")
        return create_error_response(f"Query failed: {str(e)}")

async def query_steam_server(host, port):
    """
    Query a Steam server using the A2S protocol
    
    Args:
        host: Server hostname or IP
        port: Server port
        
    Returns:
        dict: Server status information
    """
    # Initialize sock as None to handle potential LSP errors about unbound variables
    sock = None
    try:
        # Use timeout to avoid hanging
        socket.setdefaulttimeout(5)
        
        # Create the query payload (A2S_INFO)
        # Steam A2S_INFO query packet: FF FF FF FF 54 53 6F 75 72 63 65 20 45 6E 67 69 6E 65 20 51 75 65 72 79 00
        query_packet = b"\xFF\xFF\xFF\xFF\x54Source Engine Query\0"
        
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Convert hostname to IP if needed
        if not is_ip_address(host):
            try:
                ip = socket.gethostbyname(host)
            except socket.gaierror:
                return create_error_response(f"Unable to resolve hostname: {host}")
        else:
            ip = host
        
        # Send the query
        sock.sendto(query_packet, (ip, int(port)))
        
        # Receive the response
        response, _ = sock.recvfrom(4096)
        
        # Parse the response
        result = parse_steam_response(response)
        result["online"] = True
        result["query_time"] = datetime.utcnow().isoformat()
        result["error"] = None
        
        return result
    except socket.timeout:
        return create_error_response("Connection timed out")
    except ConnectionRefusedError:
        return create_error_response("Connection refused")
    except Exception as e:
        return create_error_response(f"Query failed: {str(e)}")
    finally:
        # Check if sock was initialized before trying to close it
        if sock is not None:
            try:
                sock.close()
            except:
                pass

def parse_steam_response(response):
    """
    Parse a Steam A2S_INFO response
    
    Args:
        response: Binary response data
        
    Returns:
        dict: Parsed server information
    """
    result = {
        "name": "Unknown",
        "map": "Unknown",
        "players": 0,
        "maxplayers": 0,
        "raw": {}
    }
    
    try:
        # Skip the header (4 bytes) and response type (1 byte)
        pos = 5
        
        # Protocol version (1 byte)
        protocol = response[pos]
        pos += 1
        result["raw"]["protocol"] = protocol
        
        # Server name (null-terminated string)
        name_end = response.find(b'\0', pos)
        if name_end != -1:
            result["name"] = response[pos:name_end].decode('utf-8', errors='replace')
            pos = name_end + 1
        
        # Map name (null-terminated string)
        map_end = response.find(b'\0', pos)
        if map_end != -1:
            result["map"] = response[pos:map_end].decode('utf-8', errors='replace')
            pos = map_end + 1
        
        # Skip game directory and game description (both null-terminated strings)
        for _ in range(2):
            skip_end = response.find(b'\0', pos)
            if skip_end != -1:
                pos = skip_end + 1
        
        # App ID (2 bytes, little endian)
        if pos + 2 <= len(response):
            app_id = int.from_bytes(response[pos:pos+2], byteorder='little')
            result["raw"]["app_id"] = app_id
            pos += 2
        
        # Players (1 byte)
        if pos < len(response):
            result["players"] = response[pos]
            pos += 1
        
        # Max players (1 byte)
        if pos < len(response):
            result["maxplayers"] = response[pos]
            pos += 1
        
        # The rest of the data we'll skip for now
    except Exception as e:
        logger.error(f"Error parsing Steam response: {e}")
    
    return result

def create_error_response(error_message):
    """
    Create an error response object
    
    Args:
        error_message: Error message
        
    Returns:
        dict: Error response
    """
    return {
        "online": False,
        "name": "Unknown",
        "map": "Unknown",
        "players": 0,
        "maxplayers": 0,
        "query_time": datetime.utcnow().isoformat(),
        "error": error_message,
        "raw": {}
    }

def is_ip_address(host):
    """
    Check if a host is an IP address
    
    Args:
        host: Host to check
        
    Returns:
        bool: True if the host is an IP address, False otherwise
    """
    try:
        socket.inet_aton(host)
        return True
    except socket.error:
        return False

async def query_server_batch(servers):
    """
    Query multiple servers in parallel
    
    Args:
        servers: List of server dictionaries with host and port
        
    Returns:
        dict: Dictionary of server IDs to query results
    """
    if not servers:
        return {}
        
    tasks = []
    for server in servers:
        if "host" in server and "port" in server:
            tasks.append(query_game_server(server["host"], server["port"]))
        else:
            logger.warning(f"Invalid server object: {server}")
    
    # Run all queries in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Match results with server IDs
    result_dict = {}
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            server_id = servers[i].get("_id", f"unknown_{i}")
            result_dict[server_id] = create_error_response(str(result))
        else:
            server_id = servers[i].get("_id", f"unknown_{i}")
            result_dict[server_id] = result
    
    return result_dict