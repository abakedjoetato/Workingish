const mongoose = require('mongoose');

// Define the kill schema
const killSchema = new mongoose.Schema({
  guildId: {
    type: String,
    required: true,
    index: true
  },
  serverId: {
    type: String,
    required: true,
    index: true
  },
  gameServer: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'GameServer',
    required: true
  },
  killerId: {
    type: String,
    required: true,
    index: true
  },
  killerName: {
    type: String,
    required: true
  },
  victimId: {
    type: String,
    required: true,
    index: true
  },
  victimName: {
    type: String,
    required: true
  },
  weapon: {
    type: String,
    default: null
  },
  headshot: {
    type: Boolean,
    default: false
  },
  distance: {
    type: Number,
    default: null
  },
  map: {
    type: String,
    default: null
  },
  timestamp: {
    type: Date,
    default: Date.now,
    index: true
  },
  killMessage: {
    type: String,
    default: null
  },
  teamKill: {
    type: Boolean,
    default: false
  },
  killerTeam: {
    type: String,
    default: null
  },
  victimTeam: {
    type: String,
    default: null
  },
  suicide: {
    type: Boolean,
    default: false
  },
  gameMode: {
    type: String,
    default: null
  },
  processed: {
    type: Boolean,
    default: false,
    index: true
  },
  killfeedSent: {
    type: Boolean,
    default: false
  }
});

// Add indexes for common queries
killSchema.index({ serverId: 1, timestamp: -1 });
killSchema.index({ killerId: 1, timestamp: -1 });
killSchema.index({ victimId: 1, timestamp: -1 });
killSchema.index({ guildId: 1, processed: 1 });
killSchema.index({ guildId: 1, killfeedSent: 1 });

// Virtual for killing spree calculation
killSchema.virtual('isKillingSpree').get(function() {
  return this._isKillingSpree || false;
});

killSchema.virtual('spreeCount').get(function() {
  return this._spreeCount || 0;
});

// Static method to find recent kills for a server
killSchema.statics.getRecentKills = function(serverId, limit = 10) {
  return this.find({ serverId })
    .sort({ timestamp: -1 })
    .limit(limit)
    .populate('gameServer')
    .exec();
};

// Static method to find kills for a player
killSchema.statics.getPlayerKills = function(guildId, playerName, serverId = null) {
  const query = { 
    guildId, 
    killerName: { $regex: new RegExp(playerName, 'i') }
  };
  
  if (serverId) {
    query.serverId = serverId;
  }
  
  return this.find(query)
    .sort({ timestamp: -1 })
    .populate('gameServer')
    .exec();
};

// Static method to find deaths for a player
killSchema.statics.getPlayerDeaths = function(guildId, playerName, serverId = null) {
  const query = { 
    guildId, 
    victimName: { $regex: new RegExp(playerName, 'i') }
  };
  
  if (serverId) {
    query.serverId = serverId;
  }
  
  return this.find(query)
    .sort({ timestamp: -1 })
    .populate('gameServer')
    .exec();
};

// Static method to find unprocessed kills for stats update
killSchema.statics.getUnprocessedKills = function(guildId, limit = 100) {
  return this.find({ guildId, processed: false })
    .sort({ timestamp: 1 })
    .limit(limit)
    .exec();
};

// Static method to find unsent kills for killfeed update
killSchema.statics.getUnsentKillFeedKills = function(guildId, serverId = null, limit = 20) {
  const query = { guildId, killfeedSent: false };
  
  if (serverId) {
    query.serverId = serverId;
  }
  
  return this.find(query)
    .sort({ timestamp: 1 })
    .limit(limit)
    .populate('gameServer')
    .exec();
};

// Create and export the model
const Kill = mongoose.model('Kill', killSchema);

module.exports = Kill;
