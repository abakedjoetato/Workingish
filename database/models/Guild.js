const mongoose = require('mongoose');

// Define the kill feed channel schema
const killFeedChannelSchema = new mongoose.Schema({
  channelId: {
    type: String,
    required: true
  },
  serverId: {
    type: String,
    default: null
  },
  enabled: {
    type: Boolean,
    default: true
  },
  lastMessageId: {
    type: String,
    default: null
  }
});

// Define the guild schema
const guildSchema = new mongoose.Schema({
  guildId: {
    type: String,
    required: true,
    unique: true
  },
  name: {
    type: String,
    required: true
  },
  ownerId: {
    type: String,
    required: true
  },
  setupBy: {
    type: String,
    required: true
  },
  killFeedChannels: [killFeedChannelSchema],
  prefix: {
    type: String,
    default: '!'
  },
  settings: {
    disableCommands: {
      type: [String],
      default: []
    },
    statsUpdateInterval: {
      type: Number,
      default: 300000 // 5 minutes
    },
    killFeedUpdateInterval: {
      type: Number,
      default: 15000 // 15 seconds
    },
    language: {
      type: String,
      default: 'en'
    }
  }
}, {
  timestamps: true
});

// Add any instance methods to the schema
guildSchema.methods.getKillFeedChannelForServer = function(serverId) {
  // If serverId is null, find a channel configured for all servers
  if (!serverId) {
    return this.killFeedChannels.find(kf => !kf.serverId && kf.enabled);
  }
  
  // First, try to find an exact match for the server
  const exactMatch = this.killFeedChannels.find(
    kf => kf.serverId === serverId && kf.enabled
  );
  
  if (exactMatch) {
    return exactMatch;
  }
  
  // If no exact match, fall back to a channel for all servers
  return this.killFeedChannels.find(kf => !kf.serverId && kf.enabled);
};

// Create the model and export it
const Guild = mongoose.model('Guild', guildSchema);

module.exports = Guild;
