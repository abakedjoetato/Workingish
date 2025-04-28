"""
Game server query utilities for checking server status and player count.
Uses GameDig to query different game servers like Steam/Source, Minecraft, etc.
"""
import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger('deadside_bot.utils.game_query')

async def query_game_server(host: str, port: int) -> Dict[str, Any]:
    """
    Query a game server using GameDig via Node.js.
    
    Args:
        host: The server hostname or IP
        port: The server port
        
    Returns:
        Dict with server info (name, map, player_count, max_players, etc.)
        
    Raises:
        Exception: If the query fails
    """
    try:
        # Use gamedig package through Node.js
        # Create a temporary query file
        query_file = 'temp_query.js'
        
        # Write a simple Node.js script to query the server
        with open(query_file, 'w') as f:
            f.write("""
            const Gamedig = require('gamedig');
            
            // Server details from arguments
            const host = process.argv[2];
            const port = parseInt(process.argv[3]);
            
            Gamedig.query({
                type: 'protocol-valve',  // Valve/Source protocol (works for most Steam games)
                host: host,
                port: port,
                maxAttempts: 2,
                attemptTimeout: 5000
            }).then((state) => {
                // Return the results as JSON
                console.log(JSON.stringify(state));
                process.exit(0);
            }).catch((error) => {
                // Return the error
                console.error(JSON.stringify({ error: error.message }));
                process.exit(1);
            });
            """)
            
        # Run the query with Node.js
        cmd = f"node {query_file} {host} {port}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # Clean up the temporary file
        try:
            os.remove(query_file)
        except:
            pass
        
        # Check for errors
        if proc.returncode != 0:
            error_text = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Game server query failed: {error_text}")
            raise Exception(f"Failed to query server: {error_text}")
        
        # Parse the result
        result = json.loads(stdout.decode().strip())
        
        # Check if there's an error in the result
        if "error" in result:
            logger.error(f"Game server query returned error: {result['error']}")
            raise Exception(f"Server query error: {result['error']}")
            
        # Extract the important information
        server_info = {
            "name": result.get("name", "Unknown Server"),
            "map": result.get("map", "Unknown"),
            "player_count": len(result.get("players", [])),
            "max_players": result.get("maxplayers", 0),
            "ping": result.get("ping", 0),
            "connect": f"{host}:{port}",
            "raw": result.get("raw", {})
        }
        
        return server_info
        
    except json.JSONDecodeError:
        logger.error(f"Failed to parse server query result: {stdout.decode() if stdout else 'No output'}")
        raise Exception("Invalid response from server query")
        
    except Exception as e:
        logger.error(f"Error querying game server {host}:{port}: {str(e)}")
        raise