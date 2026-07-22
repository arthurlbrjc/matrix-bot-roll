# matrix-bot-roll

![AI-Generated License Badge](vibe-coded-badge.svg)


A single-file Matrix bot that listens for `!roll` commands and replies with dice roll results. Built on [matrix-nio](https://github.com/matrix-nio/matrix-nio) with E2E encryption support.

## Features

- `!roll 2d6+4` — roll dice with an optional `+`/`-` modifier
- `!roll d20` — omit the count to roll a single die (`dX` is shorthand for `1dX`)
- `!roll 4d20 1d6+2` — roll multiple expressions in one message, with a grand total
- Auto-joins any room it's invited to
- Sanity limits on dice count (1–100) and sides (2–1000) to prevent abuse
- Replies as both plain text and formatted HTML

## Requirements

- Python >= 3.14
- [Poetry](https://python-poetry.org/) for dependency management
- A Matrix account/access token for the bot to use

## Setup

1. Install dependencies:

   ```bash
   poetry install
   ```

2. Create a `.env` file (gitignored) with the following variables:

   ```
   MATRIX_BASE_URL=https://your.homeserver
   MATRIX_USER_ID=@your-bot:your.homeserver
   MATRIX_ACCESS_TOKEN=your-access-token
   MATRIX_DEVICE_ID=your-device-id
   MATRIX_STORE_PATH=./store
   ```

3. Verify your `.env` is complete:

   ```bash
   poetry run invoke env-check
   ```

## Usage

```bash
invoke run          # run the bot
invoke watch         # run the bot, auto-restarting on .py/.env changes
```

Or run directly without invoke:

```bash
poetry run python matrix-bot-roll.py
```

In a room the bot has joined:

```
!roll 1d20
!roll d20
!roll 2d6+4
!roll 4d20 1d6+2
```

## Other tasks

```bash
poetry run invoke clean        # remove __pycache__, caches, build artifacts
poetry run invoke clean-store  # wipe ./store (encryption keys + sync tokens); prompts for confirmation
```

`clean-store` forces a full re-sync on next run and can break decryption of previously-seen messages — only use it if the store is corrupted or you're resetting the bot's session.

## Local test homeserver

`docker-compose.yml` spins up a local Synapse homeserver and an Element web client, useful for testing the bot without a real Matrix account:

```bash
docker compose up
```

- Synapse: http://localhost:8008
- Element: http://localhost:8080

## Architecture

State (encryption keys, sync tokens) persists to `MATRIX_STORE_PATH` between runs.

## 🤖 AI Transparency

This project is made with ai.

- **AI Model**: Anthropic Claude Sonnet 5
- **License**: MIT

We believe in transparency about AI usage in software development.
