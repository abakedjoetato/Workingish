const { EmbedBuilder } = require('discord.js');
const Kill = require('../database/models/Kill');
const Guild = require('../database/models/Guild');
const config = require('../config');
const logger = require('./logger');

let isUpdating = false;
let updateInterval = null;

/**
 * Start the kill feed update process
 * @param {Object} client - Discord client
 */
function startKillFeedUpdater(client) {
  if (isUpdating) return;
  
  isUpdating = true;
  
  // Start the update interval
  updateInterval = setInterval(async () => {
    try {
      await updateKillFeeds(client);
    } catch (error) {
      logger.error('Error in kill feed update:', error);
    }
  }, config.killFeedChannelUpdateInterval);
  
  // Run an immediate update on start
  updateKillFeeds(client).catch(err => {
    logger.error('Error in initial kill feed update:', err);
  });
}

/**
 * Stop the kill feed update process
 */
function stopKillFeedUpdater() {
  if (!isUpdating) return;
  
  clearInterval(updateInterval);
  isUpdating = false;
  logger.info('Kill feed updater stopped');
}

/**
 * Update all kill feeds across all guilds
 * @param {Object} client - Discord client
 */
async function updateKillFeeds(client) {
  // Get all guilds
  const guilds = await Guild.find({
    killFeedChannels: { $exists: true, $not: { $size: 0 } }
  });
  
  if (guilds.length === 0) return;
  
  // Process each guild
  for (const guild of guilds) {
    try {
      await updateGuildKillFeeds(client, guild);
    } catch (error) {
      logger.error(`Error updating kill feeds for guild ${guild.name} (${guild.guildId}):`, error);
    }
  }
}

/**
 * Update kill feeds for a specific guild
 * @param {Object} client - Discord client
 * @param {Object} guild - Guild document
 */
async function updateGuildKillFeeds(client, guild) {
  // Get the Discord guild
  const discordGuild = client.guilds.cache.get(guild.guildId);
  
  if (!discordGuild) {
    logger.warn(`Discord guild ${guild.guildId} not found in client cache`);
    return;
  }
  
  // Process each kill feed channel
  for (const killFeedConfig of guild.killFeedChannels) {
    if (!killFeedConfig.enabled) continue;
    
    try {
      // Get the Discord channel
      const channel = await discordGuild.channels.fetch(killFeedConfig.channelId).catch(() => null);
      
      if (!channel) {
        logger.warn(`Kill feed channel ${killFeedConfig.channelId} not found in guild ${guild.name}`);
        continue;
      }
      
      // Get unsent kills for this channel
      const query = { 
        guildId: guild.guildId,
        killfeedSent: false 
      };
      
      // If this channel is for a specific server, filter by serverId
      if (killFeedConfig.serverId) {
        query.serverId = killFeedConfig.serverId;
      }
      
      // Get kills that haven't been sent to kill feed yet
      const kills = await Kill.find(query)
        .sort({ timestamp: 1 })
        .limit(10) // Process in batches of 10
        .populate('gameServer');
      
      if (kills.length === 0) continue;
      
      // Send kills to the channel
      await sendKillsToChannel(channel, kills);
      
      // Mark kills as sent
      const killIds = kills.map(kill => kill._id);
      await Kill.updateMany(
        { _id: { $in: killIds } },
        { $set: { killfeedSent: true } }
      );
    } catch (error) {
      logger.error(`Error updating kill feed channel ${killFeedConfig.channelId} in guild ${guild.name}:`, error);
    }
  }
}

/**
 * Send kills to a Discord channel
 * @param {Object} channel - Discord channel
 * @param {Array} kills - Array of kill documents
 */
async function sendKillsToChannel(channel, kills) {
  if (kills.length === 0) return;
  
  // Group kills by server for better organization
  const killsByServer = {};
  
  for (const kill of kills) {
    const serverName = kill.gameServer?.name || 'Unknown Server';
    
    if (!killsByServer[serverName]) {
      killsByServer[serverName] = [];
    }
    
    killsByServer[serverName].push(kill);
  }
  
  // Create separate embeds for each server
  for (const [serverName, serverKills] of Object.entries(killsByServer)) {
    // Create embed for this batch of kills
    const embed = new EmbedBuilder()
      .setColor(config.colors.killFeed)
      .setTitle(`☠️ Kill Feed - ${serverName}`)
      .setTimestamp();
    
    // Format each kill for the embed
    for (const kill of serverKills) {
      let killDetails = formatKillMessage(kill);
      
      // Add the kill to the embed
      embed.addFields({
        name: `<t:${Math.floor(kill.timestamp.getTime() / 1000)}:R>`,
        value: killDetails
      });
    }
    
    // Send the embed to the channel
    await channel.send({ embeds: [embed] });
  }
}

/**
 * Format a kill event into a readable message
 * @param {Object} kill - Kill document
 * @returns {String} Formatted kill message
 */
function formatKillMessage(kill) {
  let message = '';
  
  // Handle suicide
  if (kill.suicide) {
    message = `💥 **${kill.killerName}** committed suicide`;
    if (kill.weapon) {
      message += ` with ${kill.weapon}`;
    }
    return message;
  }
  
  // Handle team kills
  if (kill.teamKill) {
    message = `🔴 **${kill.killerName}** team-killed **${kill.victimName}**`;
  } else {
    message = `**${kill.killerName}** killed **${kill.victimName}**`;
  }
  
  // Add weapon if available
  if (kill.weapon) {
    message += ` with ${kill.weapon}`;
  }
  
  // Add headshot indicator
  if (kill.headshot) {
    message += " 🎯";
  }
  
  // Add distance if available
  if (kill.distance) {
    message += ` (${kill.distance}m)`;
  }
  
  return message;
}

/**
 * Post a single kill to appropriate kill feed channels
 * @param {Object} client - Discord client
 * @param {Object} kill - Kill document
 */
async function postKillToFeeds(client, kill) {
  try {
    // Get the guild
    const guild = await Guild.findOne({ guildId: kill.guildId });
    
    if (!guild) return;
    
    // Get Discord guild
    const discordGuild = client.guilds.cache.get(guild.guildId);
    
    if (!discordGuild) return;
    
    // Find channels to post to
    const channelsToPost = guild.killFeedChannels.filter(kf => 
      kf.enabled && (!kf.serverId || kf.serverId === kill.serverId)
    );
    
    if (channelsToPost.length === 0) return;
    
    // Create the kill feed embed
    const embed = new EmbedBuilder()
      .setColor(config.colors.killFeed)
      .setTitle('☠️ Kill Feed')
      .setTimestamp(kill.timestamp);
    
    const killDetails = formatKillMessage(kill);
    embed.setDescription(killDetails);
    
    // Map details
    if (kill.map) {
      embed.setFooter({ text: `Map: ${kill.map}` });
    }
    
    // Send to each channel
    for (const killFeedConfig of channelsToPost) {
      try {
        const channel = await discordGuild.channels.fetch(killFeedConfig.channelId).catch(() => null);
        
        if (channel) {
          await channel.send({ embeds: [embed] });
        }
      } catch (error) {
        logger.error(`Error posting kill to channel ${killFeedConfig.channelId}:`, error);
      }
    }
    
    // Mark as sent
    kill.killfeedSent = true;
    await kill.save();
  } catch (error) {
    logger.error('Error posting kill to feeds:', error);
  }
}

// Export the functions
module.exports = {
  startKillFeedUpdater,
  stopKillFeedUpdater,
  postKillToFeeds,
  formatKillMessage
};
