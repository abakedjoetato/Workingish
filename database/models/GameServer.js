const mongoose = require('mongoose');

// Define the game server schema
const gameServerSchema = new mongoose.Schema({
  serverId: {
    type: String,
    required: true,
    unique: true
  },
  guildId: {
    type: String,
    required: true,
    index: true
  },
  name: {
    type: String,
    required: true
  },
  ip: {
    type: String,
    required: true
  },
  port: {
    type: Number,
    required: true
  },
  game: {
    type: String,
    required: true
  },
  queryPort: {
    type: Number
  },
  rconPassword: {
    type: String,
    default: null
  },
  addedBy: {
    type: String,
    required: true
  },
  status: {
    online: {
      type: Boolean,
      default: false
    },
    lastCheck: {
      type: Date,
      default: Date.now
    },
    currentMap: {
      type: String,
      default: null
    },
    currentPlayers: {
      type: Number,
      default: 0
    },
    maxPlayers: {
      type: Number,
      default: 0
    },
    version: {
      type: String,
      default: null
    },
    lastUpdated: {
      type: Date,
      default: Date.now
    },
    uptime: {
      type: Number, // in seconds
      default: 0
    },
    restartCount: {
      type: Number,
      default: 0
    }
  },
  stats: {
    totalKills: {
      type: Number,
      default: 0
    },
    totalDeaths: {
      type: Number,
      default: 0
    },
    uniquePlayers: {
      type: Number,
      default: 0
    },
    peakPlayers: {
      type: Number,
      default: 0
    },
    peakTime: {
      type: Date,
      default: null
    },
    mostPlayedMap: {
      type: String,
      default: null
    },
    topWeapon: {
      type: String,
      default: null
    }
  }
}, {
  timestamps: true
});

// Add indexes for query performance
gameServerSchema.index({ guildId: 1, ip: 1, port: 1 }, { unique: true });

// Add instance methods
gameServerSchema.methods.updateStatus = function(statusData) {
  // Update the status field with new data
  this.status.online = statusData.online || false;
  this.status.lastCheck = new Date();
  
  if (statusData.online) {
    this.status.currentMap = statusData.map || this.status.currentMap;
    this.status.currentPlayers = statusData.players?.online || 0;
    this.status.maxPlayers = statusData.players?.max || 0;
    this.status.version = statusData.version || this.status.version;
    
    // If the server was previously offline and is now online, increment restart count
    if (!this.status.online) {
      this.status.restartCount += 1;
    }
    
    // Update peak players
    if (this.status.currentPlayers > this.stats.peakPlayers) {
      this.stats.peakPlayers = this.status.currentPlayers;
      this.stats.peakTime = new Date();
    }
  }
  
  this.status.lastUpdated = new Date();
  return this;
};

// Static methods
gameServerSchema.statics.findByServerId = function(guildId, serverId) {
  return this.findOne({ guildId, serverId });
};

gameServerSchema.statics.findByGuild = function(guildId) {
  return this.find({ guildId });
};

// Create and export the model
const GameServer = mongoose.model('GameServer', gameServerSchema);

module.exports = GameServer;
