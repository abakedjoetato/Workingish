# Emerald Discord Bot - Docker Deployment Guide

This guide explains how to deploy the Emerald Discord Bot using Docker for reliable and consistent operation across any environment.

## Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) installed on your server
2. [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)
3. Your Discord Bot Token
4. MongoDB connection string

## Quick Start

### 1. Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```
DISCORD_TOKEN=your_discord_bot_token_here
MONGODB_URI=your_mongodb_connection_string_here
```

### 2. Build and Start the Bot

Run the following command in the project root directory:

```bash
docker-compose up -d
```

This will:
- Build the Docker image based on the Dockerfile
- Start the bot in detached mode (running in the background)
- Set up automatic restart if the bot crashes

### 3. View Logs

To see the bot's logs:

```bash
docker-compose logs -f
```

Press `Ctrl+C` to exit the log view.

## Management Commands

### Stop the Bot

```bash
docker-compose down
```

### Restart the Bot

```bash
docker-compose restart
```

### Rebuild and Update

If you've made changes to the code:

```bash
docker-compose up -d --build
```

## Configuration

The Docker setup includes:

- **Persistent Logs**: Stored in the `./logs` directory on your host
- **Automatic Restart**: The bot will restart automatically if it crashes
- **Timezone**: Set to UTC by default (change in docker-compose.yml if needed)

## Troubleshooting

1. **Bot not connecting to Discord**: Check your `DISCORD_TOKEN` in the .env file
2. **Database connection issues**: Verify your `MONGODB_URI` is correct and accessible
3. **Container not starting**: Check logs with `docker-compose logs`

## Server Requirements

The bot is designed to be lightweight:

- **CPU**: 1 core minimum (2+ recommended)
- **RAM**: 512MB minimum (1GB+ recommended)
- **Disk**: 1GB for the bot and dependencies

---

For questions or support, refer to the main documentation or contact the development team.