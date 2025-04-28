const { createLogger, format, transports } = require('winston');
const { combine, timestamp, printf, colorize } = format;

// Define log format
const logFormat = printf(({ level, message, timestamp, ...metadata }) => {
  let metaStr = '';
  
  if (Object.keys(metadata).length > 0 && metadata.stack) {
    // Format error stacks nicely
    metaStr = `\n${metadata.stack}`;
  } else if (Object.keys(metadata).length > 0) {
    metaStr = Object.keys(metadata).length ? `\n${JSON.stringify(metadata, null, 2)}` : '';
  }
  
  return `[${timestamp}] ${level}: ${message}${metaStr}`;
});

// Create the logger
const logger = createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: combine(
    timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    format.errors({ stack: true }),
    logFormat
  ),
  transports: [
    // Console transport with colors
    new transports.Console({
      format: combine(
        colorize(),
        timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
        format.errors({ stack: true }),
        logFormat
      )
    }),
    // File transport for persistent logs
    new transports.File({ 
      filename: 'error.log', 
      level: 'error' 
    }),
    new transports.File({ 
      filename: 'combined.log' 
    })
  ]
});

// Add a stream for Morgan HTTP logging integration if needed
logger.stream = {
  write: (message) => {
    logger.info(message.trim());
  }
};

module.exports = logger;
