const GameServer = require('../database/models/GameServer');
const Player = require('../database/models/Player');
const Kill = require('../database/models/Kill');
const logger = require('./logger');

/**
 * Generate statistics for a game server
 * @param {Object} server - Game server document or server ID
 * @returns {Promise<Object>} Server statistics
 */
async function generateServerStats(server) {
  try {
    // If server is a string (serverId), fetch the server document
    if (typeof server === 'string') {
      server = await GameServer.findOne({ serverId: server });
      
      if (!server) {
        throw new Error('Server not found');
      }
    }
    
    // Basic stats from the server document
    const stats = {
      online: server.status.online,
      currentPlayers: server.status.currentPlayers,
      maxPlayers: server.status.maxPlayers,
      map: server.status.currentMap,
      game: server.game,
      totalKills: server.stats.totalKills,
      uptime: formatUptime(server.status.uptime),
      lastUpdated: server.status.lastUpdated,
      ip: server.ip,
      port: server.port,
      name: server.name,
      topPlayers: []
    };
    
    // Get top players for this server
    const topPlayers = await Player.find({ serverId: server.serverId })
      .sort({ 'stats.kills': -1 })
      .limit(5)
      .lean();
    
    stats.topPlayers = topPlayers.map(player => ({
      name: player.name,
      kills: player.stats.kills,
      deaths: player.stats.deaths,
      kd: player.stats.deaths > 0 ? (player.stats.kills / player.stats.deaths).toFixed(2) : player.stats.kills.toFixed(2)
    }));
    
    // Get weapon stats
    const weaponStats = await Kill.aggregate([
      { $match: { serverId: server.serverId, weapon: { $ne: null } } },
      { $group: { _id: '$weapon', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 5 }
    ]);
    
    stats.topWeapons = weaponStats.map(weapon => ({
      name: weapon._id,
      kills: weapon.count
    }));
    
    // Get map stats
    const mapStats = await Kill.aggregate([
      { $match: { serverId: server.serverId, map: { $ne: null } } },
      { $group: { _id: '$map', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 5 }
    ]);
    
    stats.topMaps = mapStats.map(map => ({
      name: map._id,
      kills: map.count
    }));
    
    return stats;
  } catch (error) {
    logger.error('Error generating server stats:', error);
    throw error;
  }
}

/**
 * Generate statistics for a player
 * @param {Object} player - Player document or player name/ID
 * @param {String} serverId - Optional server ID to filter stats
 * @returns {Promise<Object>} Player statistics
 */
async function generatePlayerStats(player, serverId = null) {
  try {
    // If player is a string (name or ID), fetch the player document
    if (typeof player === 'string') {
      const query = { 
        $or: [
          { name: { $regex: new RegExp(player, 'i') } },
          { playerId: player }
        ]
      };
      
      if (serverId) {
        query.serverId = serverId;
      }
      
      player = await Player.findOne(query);
      
      if (!player) {
        throw new Error('Player not found');
      }
    }
    
    // Basic stats from the player document
    const stats = {
      name: player.name,
      playerId: player.playerId,
      totalKills: player.stats.kills,
      totalDeaths: player.stats.deaths,
      kdRatio: player.stats.deaths > 0 ? player.stats.kills / player.stats.deaths : player.stats.kills,
      headshots: player.stats.headshots,
      headshotRatio: player.stats.kills > 0 ? player.stats.headshots / player.stats.kills : 0,
      playtime: formatPlaytime(player.stats.playtime),
      firstSeen: player.firstSeen,
      lastSeen: player.lastSeen,
    };
    
    // Get favorite weapon (most kills)
    if (player.weaponStats && player.weaponStats.length > 0) {
      const favoriteWeapon = [...player.weaponStats].sort((a, b) => b.kills - a.kills)[0];
      stats.favoriteWeapon = favoriteWeapon.weaponName;
    }
    
    // Get stats per server if not filtering for a specific server
    if (!serverId) {
      const playerServers = await Player.find({ 
        guildId: player.guildId,
        name: player.name 
      }).populate('serverId');
      
      stats.servers = [];
      
      for (const serverPlayer of playerServers) {
        const server = await GameServer.findOne({ serverId: serverPlayer.serverId });
        
        if (server) {
          stats.servers.push({
            name: server.name,
            kills: serverPlayer.stats.kills,
            deaths: serverPlayer.stats.deaths,
            kd: serverPlayer.stats.deaths > 0 ? 
              (serverPlayer.stats.kills / serverPlayer.stats.deaths).toFixed(2) : 
              serverPlayer.stats.kills.toFixed(2)
          });
        }
      }
      
      // Sort servers by kill count
      stats.servers.sort((a, b) => b.kills - a.kills);
    }
    
    // Get recent kills
    const recentKills = await Kill.find({
      killerId: player.playerId,
      ...(serverId ? { serverId } : { guildId: player.guildId })
    })
    .sort({ timestamp: -1 })
    .limit(5)
    .populate('gameServer')
    .lean();
    
    stats.recentKills = recentKills.map(kill => ({
      victim: kill.victimName,
      weapon: kill.weapon,
      headshot: kill.headshot,
      timestamp: kill.timestamp,
      serverName: kill.gameServer?.name || 'Unknown Server',
      map: kill.map
    }));
    
    // Get recent deaths
    const recentDeaths = await Kill.find({
      victimId: player.playerId,
      ...(serverId ? { serverId } : { guildId: player.guildId })
    })
    .sort({ timestamp: -1 })
    .limit(5)
    .populate('gameServer')
    .lean();
    
    stats.recentDeaths = recentDeaths.map(kill => ({
      killer: kill.killerName,
      weapon: kill.weapon,
      headshot: kill.headshot,
      timestamp: kill.timestamp,
      serverName: kill.gameServer?.name || 'Unknown Server',
      map: kill.map
    }));
    
    return stats;
  } catch (error) {
    logger.error('Error generating player stats:', error);
    throw error;
  }
}

/**
 * Format uptime in seconds to a human-readable string
 * @param {Number} uptime - Uptime in seconds
 * @returns {String} Formatted uptime string
 */
function formatUptime(uptime) {
  if (!uptime) return 'Unknown';
  
  const days = Math.floor(uptime / 86400);
  const hours = Math.floor((uptime % 86400) / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);
  
  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0 || days > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  
  return parts.join(' ');
}

/**
 * Format playtime in seconds to a human-readable string
 * @param {Number} playtime - Playtime in seconds
 * @returns {String} Formatted playtime string
 */
function formatPlaytime(playtime) {
  if (!playtime) return 'Unknown';
  
  const hours = Math.floor(playtime / 3600);
  const minutes = Math.floor((playtime % 3600) / 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else {
    return `${minutes}m`;
  }
}

// Export the functions
module.exports = {
  generateServerStats,
  generatePlayerStats,
  formatUptime,
  formatPlaytime
};
