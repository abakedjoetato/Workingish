const { Events } = require('discord.js');
const config = require('../config');
const logger = require('../utils/logger');
const Guild = require('../database/models/Guild');

module.exports = {
  name: Events.MessageCreate,
  async execute(message, client) {
    // Ignore bot messages and messages without content
    if (message.author.bot || !message.content) return;
    
    // Only process commands with the prefix
    if (!message.content.startsWith(config.prefix)) return;
    
    // Extract the command name and arguments
    const args = message.content.slice(config.prefix.length).trim().split(/ +/);
    const commandName = args.shift().toLowerCase();
    
    // Find the command by name or alias
    const command = client.commands.get(commandName)
      || client.commands.find(cmd => cmd.aliases && cmd.aliases.includes(commandName));
    
    // If no command is found, return
    if (!command) return;
    
    // Check if command is guild-only and being used in DMs
    if (command.guildOnly && message.channel.type === 'DM') {
      return message.reply('I can\'t execute that command inside DMs!');
    }
    
    // Check for required permissions (if any)
    if (message.guild && command.permissions) {
      const authorPerms = message.channel.permissionsFor(message.author);
      if (!authorPerms || !authorPerms.has(command.permissions)) {
        return message.reply('You do not have permission to use this command!');
      }
    }
    
    // Check if guild is initialized for guild-specific commands
    if (message.guild && command.requiresInit) {
      const guild = await Guild.findOne({ guildId: message.guild.id });
      if (!guild) {
        return message.reply('This Discord server is not set up yet! An admin needs to run `/setup initialize` first.');
      }
    }
    
    // Check cooldowns
    const { cooldowns } = client;
    
    if (!cooldowns.has(command.data.name)) {
      cooldowns.set(command.data.name, new Map());
    }
    
    const now = Date.now();
    const timestamps = cooldowns.get(command.data.name);
    const cooldownAmount = (command.cooldown || config.defaultCooldown) * 1000;
    
    if (timestamps.has(message.author.id)) {
      const expirationTime = timestamps.get(message.author.id) + cooldownAmount;
      
      if (now < expirationTime) {
        const timeLeft = (expirationTime - now) / 1000;
        return message.reply(`Please wait ${timeLeft.toFixed(1)} more second(s) before reusing the \`${command.data.name}\` command.`);
      }
    }
    
    timestamps.set(message.author.id, now);
    setTimeout(() => timestamps.delete(message.author.id), cooldownAmount);
    
    // Execute the command
    try {
      logger.info(`User ${message.author.tag} executed command: ${commandName} ${args.join(' ')}`);
      await command.execute(message, args);
    } catch (error) {
      logger.error(`Error executing command ${commandName}:`, error);
      message.reply('There was an error trying to execute that command!');
    }
  },
};
