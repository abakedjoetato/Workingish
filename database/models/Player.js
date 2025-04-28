const mongoose = require('mongoose');

// Define the weapon stats schema
const weaponStatsSchema = new mongoose.Schema({
  weaponName: {
    type: String,
    required: true
  },
  kills: {
    type: Number,
    default: 0
  },
  deaths: {
    type: Number,
    default: 0
  },
  headshots: {
    type: Number,
    default: 0
  }
});

// Define the map stats schema
const mapStatsSchema = new mongoose.Schema({
  mapName: {
    type: String,
    required: true
  },
  kills: {
    type: Number,
    default: 0
  },
  deaths: {
    type: Number,
    default: 0
  },
  playtime: {
    type: Number, // in seconds
    default: 0
  }
});

// Define the player schema
const playerSchema = new mongoose.Schema({
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
  playerId: {
    type: String,
    required: true,
    index: true
  },
  name: {
    type: String,
    required: true
  },
  steamId: {
    type: String,
    default: null
  },
  discordId: {
    type: String,
    default: null,
    index: true
  },
  stats: {
    kills: {
      type: Number,
      default: 0
    },
    deaths: {
      type: Number,
      default: 0
    },
    assists: {
      type: Number,
      default: 0
    },
    headshots: {
      type: Number,
      default: 0
    },
    playtime: {
      type: Number, // in seconds
      default: 0
    },
    longestKill: {
      type: Number, // in meters
      default: 0
    },
    killStreak: {
      type: Number,
      default: 0
    },
    bestKillStreak: {
      type: Number,
      default: 0
    },
    suicides: {
      type: Number,
      default: 0
    },
    teamkills: {
      type: Number,
      default: 0
    }
  },
  weaponStats: [weaponStatsSchema],
  mapStats: [mapStatsSchema],
  firstSeen: {
    type: Date,
    default: Date.now
  },
  lastSeen: {
    type: Date,
    default: Date.now
  },
  lastKnownTeam: {
    type: String,
    default: null
  },
  notes: {
    type: String,
    default: null
  },
  status: {
    isBanned: {
      type: Boolean,
      default: false
    },
    isAdmin: {
      type: Boolean,
      default: false
    }
  }
}, {
  timestamps: true
});

// Add a unique compound index
playerSchema.index({ guildId: 1, serverId: 1, playerId: 1 }, { unique: true });

// Add indexes for common queries
playerSchema.index({ guildId: 1, name: 1 });
playerSchema.index({ guildId: 1, 'stats.kills': -1 });
playerSchema.index({ serverId: 1, 'stats.kills': -1 });

// Add instance methods
playerSchema.methods.updateKillStats = function(kill) {
  // Update basic kill stats
  this.stats.kills += 1;
  this.lastSeen = new Date();
  
  // Update headshot count
  if (kill.headshot) {
    this.stats.headshots += 1;
  }
  
  // Update kill streak
  this.stats.killStreak += 1;
  
  // Update best kill streak if current is better
  if (this.stats.killStreak > this.stats.bestKillStreak) {
    this.stats.bestKillStreak = this.stats.killStreak;
  }
  
  // Update longest kill if this one is longer
  if (kill.distance && kill.distance > this.stats.longestKill) {
    this.stats.longestKill = kill.distance;
  }
  
  // Update teamkill count
  if (kill.teamKill) {
    this.stats.teamkills += 1;
  }
  
  // Update weapon stats
  if (kill.weapon) {
    let weaponStat = this.weaponStats.find(w => w.weaponName === kill.weapon);
    
    if (!weaponStat) {
      weaponStat = {
        weaponName: kill.weapon,
        kills: 0,
        deaths: 0,
        headshots: 0
      };
      this.weaponStats.push(weaponStat);
    }
    
    weaponStat.kills += 1;
    
    if (kill.headshot) {
      weaponStat.headshots += 1;
    }
  }
  
  // Update map stats
  if (kill.map) {
    let mapStat = this.mapStats.find(m => m.mapName === kill.map);
    
    if (!mapStat) {
      mapStat = {
        mapName: kill.map,
        kills: 0,
        deaths: 0,
        playtime: 0
      };
      this.mapStats.push(mapStat);
    }
    
    mapStat.kills += 1;
  }
  
  return this;
};

playerSchema.methods.updateDeathStats = function(kill) {
  // Update basic death stats
  this.stats.deaths += 1;
  this.lastSeen = new Date();
  
  // Reset kill streak on death
  this.stats.killStreak = 0;
  
  // Update suicide count
  if (kill.suicide) {
    this.stats.suicides += 1;
  }
  
  // Update weapon stats for death
  if (kill.weapon) {
    let weaponStat = this.weaponStats.find(w => w.weaponName === kill.weapon);
    
    if (!weaponStat) {
      weaponStat = {
        weaponName: kill.weapon,
        kills: 0,
        deaths: 0,
        headshots: 0
      };
      this.weaponStats.push(weaponStat);
    }
    
    weaponStat.deaths += 1;
  }
  
  // Update map stats for death
  if (kill.map) {
    let mapStat = this.mapStats.find(m => m.mapName === kill.map);
    
    if (!mapStat) {
      mapStat = {
        mapName: kill.map,
        kills: 0,
        deaths: 0,
        playtime: 0
      };
      this.mapStats.push(mapStat);
    }
    
    mapStat.deaths += 1;
  }
  
  return this;
};

// Static methods
playerSchema.statics.findOrCreatePlayer = async function(guildId, serverId, playerId, playerName) {
  let player = await this.findOne({ guildId, serverId, playerId });
  
  if (!player) {
    player = new this({
      guildId,
      serverId,
      playerId,
      name: playerName
    });
  } else if (player.name !== playerName) {
    // Update name if it changed
    player.name = playerName;
  }
  
  return player;
};

playerSchema.statics.getTopPlayers = function(guildId, serverId = null, limit = 10) {
  const query = { guildId };
  
  if (serverId) {
    query.serverId = serverId;
  }
  
  return this.find(query)
    .sort({ 'stats.kills': -1 })
    .limit(limit)
    .exec();
};

// Create and export the model
const Player = mongoose.model('Player', playerSchema);

module.exports = Player;
