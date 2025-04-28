const mongoose = require('mongoose');
const logger = require('../utils/logger');

/**
 * Establishes connection to MongoDB database
 * @returns {Promise} A promise that resolves when the connection is established
 */
async function connectToDatabase() {
  const mongoURI = process.env.MONGODB_URI;
  
  if (!mongoURI) {
    logger.error('MongoDB URI is not defined in environment variables');
    throw new Error('MongoDB URI is not defined');
  }
  
  try {
    // Configure Mongoose options
    const options = {
      useNewUrlParser: true,
      useUnifiedTopology: true,
      serverSelectionTimeoutMS: 5000, // Timeout after 5s instead of 30s
      heartbeatFrequencyMS: 10000, // Check connection every 10s
    };
    
    // Connect to MongoDB
    await mongoose.connect(mongoURI, options);
    
    // Log successful connection
    logger.info('Connected to MongoDB');
    
    // Set up connection event handlers
    mongoose.connection.on('error', (err) => {
      logger.error('MongoDB connection error:', err);
    });
    
    mongoose.connection.on('disconnected', () => {
      logger.warn('MongoDB disconnected, attempting to reconnect...');
    });
    
    mongoose.connection.on('reconnected', () => {
      logger.info('Reconnected to MongoDB');
    });
    
    return mongoose.connection;
  } catch (error) {
    logger.error('Failed to connect to MongoDB:', error);
    throw error;
  }
}

/**
 * Closes the MongoDB connection
 * @returns {Promise} A promise that resolves when the connection is closed
 */
async function closeDatabaseConnection() {
  try {
    await mongoose.connection.close();
    logger.info('MongoDB connection closed');
  } catch (error) {
    logger.error('Error closing MongoDB connection:', error);
    throw error;
  }
}

module.exports = {
  connectToDatabase,
  closeDatabaseConnection,
  getConnection: () => mongoose.connection
};
