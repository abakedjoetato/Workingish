const Gamedig = require('gamedig');
const GameServer = require('../database/models/GameServer');
const Kill = require('../database/models/Kill');
const Player = require('../database/models/Player');
const logger = require('./logger');
const config = require('../config');

let isPolling = false;
let pollInterval = null;

/**
 * Start polling game servers for status updates
 * @param {Object} client - Discord client
 */
function startGameServerPolling(client) {
  if (isPolling) return;
  
  isPolling = true;
  
  // Start the polling process
  pollInterval = setInterval(async () => {
    try {
      await pollGameServers(client);
    } catch (error) {
      logger.error('Error in game server polling:', error);
    }
  }, config.gameServerPollInterval);
  
  // Run an immediate poll on start
  pollGameServers(client).catch(err => {
    logger.error('Error in initial game server polling:', err);
  });
}

/**
 * Stop polling game servers
 */
function stopGameServerPolling() {
  if (!isPolling) return;
  
  clearInterval(pollInterval);
  isPolling = false;
  logger.info('Game server polling stopped');
}

/**
 * Poll all game servers for status updates and log data
 * @param {Object} client - Discord client
 */
async function pollGameServers(client) {
  // Get all servers from the database
  const servers = await GameServer.find({});
  
  if (servers.length === 0) {
    return;
  }
  
  logger.info(`Polling ${servers.length} game servers...`);
  
  // Process each server
  for (const server of servers) {
    try {
      // Get the current status of the server
      const status = await getServerStatus(server);
      
      // Update server status in the database
      server.updateStatus(status);
      await server.save();
      
      // If server is online, process players and potentially extract kill feed data
      if (status.online && status.players && status.players.list) {
        await processServerPlayers(server, status.players.list);
        
        // Extract potential kill feed info if available
        // Note: This is game-specific logic and would need to be adjusted per game type
        if (status.raw) {
          await extractKillFeedInfo(server, status.raw);
        }
      }
    } catch (error) {
      logger.error(`Error polling game server ${server.name} (${server.ip}:${server.port}):`, error);
      
      // Mark server as offline
      server.status.online = false;
      server.status.lastCheck = new Date();
      await server.save();
    }
  }
}

/**
 * Get real-time status of a game server
 * @param {Object} server - Game server document
 * @returns {Promise<Object>} Server status information
 */
async function getServerStatus(server) {
  try {
    // Determine the query options based on game type
    const gameType = server.game;
    const queryOptions = {
      type: config.supportedGames[gameType]?.protocol || gameType,
      host: server.ip,
      port: server.queryPort || server.port,
      maxAttempts: config.maxRetries,
      attemptTimeout: config.queryTimeout
    };
    
    // Execute query to the game server
    const result = await Gamedig.query(queryOptions);
    
    // Format the result
    return {
      online: true,
      name: result.name,
      map: result.map,
      game: gameType,
      version: result.version || null,
      players: {
        online: result.players.length,
        max: result.maxplayers,
        list: result.players.map(p => ({
          name: p.name,
          score: p.score,
          time: p.time,
          id: p.id || p.name,
          team: p.team
        }))
      },
      connect: `${server.ip}:${server.port}`,
      ping: result.ping,
      raw: result.raw // Store raw data for game-specific processing
    };
  } catch (error) {
    // If query fails, return offline status
    return {
      online: false,
      error: error.message
    };
  }
}

/**
 * Process players from server status and update database
 * @param {Object} server - Game server document
 * @param {Array} playerList - List of players from status query
 */
async function processServerPlayers(server, playerList) {
  if (!playerList || playerList.length === 0) return;
  
  // Update or create players in the database
  for (const playerData of playerList) {
    try {
      if (!playerData.name) continue; // Skip players without names
      
      // Find or create player
      const player = await Player.findOrCreatePlayer(
        server.guildId,
        server.serverId,
        playerData.id || playerData.name,
        playerData.name
      );
      
      // Update player's last seen time
      player.lastSeen = new Date();
      
      // If the player has a team, update it
      if (playerData.team) {
        player.lastKnownTeam = playerData.team;
      }
      
      await player.save();
    } catch (error) {
      logger.error(`Error processing player ${playerData.name} for server ${server.name}:`, error);
    }
  }
}

/**
 * Extract kill feed information from raw server data if available
 * This is game-specific logic and would need to be adapted per game
 * @param {Object} server - Game server document
 * @param {Object} rawData - Raw data from game server query
 */
async function extractKillFeedInfo(server, rawData) {
  // This is a placeholder for game-specific kill feed extraction logic
  // For example, some games provide recent kill events in their query response
  
  // Implementation would depend on the specific game and what data is available
  
  // Example for a hypothetical game that includes kill events in raw data:
  if (server.game === 'csgo' && rawData && rawData.kills) {
    for (const killEvent of rawData.kills) {
      try {
        await processKillEvent(server, killEvent);
      } catch (error) {
        logger.error(`Error processing kill event for server ${server.name}:`, error);
      }
    }
  }
}

/**
 * Process a kill event and store it in the database
 * @param {Object} server - Game server document
 * @param {Object} killEvent - Kill event data
 */
async function processKillEvent(server, killEvent) {
  // Create a new kill record
  const kill = new Kill({
    guildId: server.guildId,
    serverId: server.serverId,
    gameServer: server._id,
    killerId: killEvent.killerId || 'unknown',
    killerName: killEvent.killerName || 'Unknown',
    victimId: killEvent.victimId || 'unknown',
    victimName: killEvent.victimName || 'Unknown',
    weapon: killEvent.weapon,
    headshot: killEvent.headshot || false,
    map: server.status.currentMap,
    timestamp: new Date(),
    killMessage: killEvent.message,
    teamKill: killEvent.teamKill || false,
    killerTeam: killEvent.killerTeam,
    victimTeam: killEvent.victimTeam,
    distance: killEvent.distance,
    suicide: killEvent.suicide || false,
    gameMode: killEvent.gameMode || null
  });
  
  // Save the kill record
  await kill.save();
  
  // Now update the player statistics
  // Find or create the killer and victim
  const killer = await Player.findOrCreatePlayer(
    server.guildId,
    server.serverId,
    killEvent.killerId || killEvent.killerName,
    killEvent.killerName
  );
  
  const victim = await Player.findOrCreatePlayer(
    server.guildId,
    server.serverId,
    killEvent.victimId || killEvent.victimName,
    killEvent.victimName
  );
  
  // Update killer stats
  killer.updateKillStats(kill);
  await killer.save();
  
  // Update victim stats
  victim.updateDeathStats(kill);
  await victim.save();
  
  // Update server stats
  server.stats.totalKills += 1;
  await server.save();
  
  return kill;
}

// Export the functions
module.exports = {
  startGameServerPolling,
  stopGameServerPolling,
  getServerStatus,
  processKillEvent
};
