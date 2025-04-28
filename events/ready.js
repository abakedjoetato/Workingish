const { Events } = require('discord.js');
const { startGameServerPolling } = require('../utils/gameServerConnector');
const { startKillFeedUpdater } = require('../utils/killFeedManager');
const logger = require('../utils/logger');

module.exports = {
  name: Events.ClientReady,
  once: true,
  execute(client) {
    logger.info(`Logged in as ${client.user.tag}`);
    logger.info(`Serving ${client.guilds.cache.size} guilds`);
    
    // Update bot status
    client.user.setActivity('game servers | /stats', { type: 'WATCHING' });
    
    // Start game server polling
    startGameServerPolling(client);
    logger.info('Game server polling started');
    
    // Start kill feed manager
    startKillFeedUpdater(client);
    logger.info('Kill feed updater started');
    
    console.log(`
    ┌───────────────────────────────────────┐
    │                                       │
    │   Game Server Stats Bot is Online!    │
    │                                       │
    └───────────────────────────────────────┘
    `);
  },
};
