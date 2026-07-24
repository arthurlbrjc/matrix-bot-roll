# matrix-bot-roll

![AI-Generated License Badge](vibe-coded-badge.svg)


A Matrix bot that listens for `!roll` commands and replies with dice roll results. Built on [matrix-nio](https://github.com/matrix-nio/matrix-nio) with E2E encryption support.

## Features

- `!roll 2d6+4` — roll dice with an optional `+`/`-` modifier
- `!roll d20` — omit the count to roll a single die (`dX` is shorthand for `1dX`)
- `!roll 4d20 1d6+2` — roll multiple expressions in one message, with a grand total
- `!roll 4d6kh3` / `!roll 4d6kl3` — keep only the highest/lowest 3 of the 4 dice rolled
- `!roll 2d20adv` / `!roll 2d20dis` — advantage/disadvantage: roll one extra die, then keep the best/worst 2 of the 3
- `!roll 4(d10+2)` — group modifier: apply `+2` to each of the 4 dice individually, instead of once to the total
- `!roll 4(d10+2)kh1` / `!roll 2(d20+3)adv` — group modifiers also combine with `kh`/`kl`/`adv`/`dis`, keeping among the modified values
- `!roll 3d8+4 | attack` — attach an optional message to the roll, shown alongside the result
- `!reroll` — repeat the last `!roll` expression sent in the room (message included)
- Auto-joins any room it's invited to
- Sanity limits on dice count (1–100) and sides (2–100) to prevent abuse, overridable via `MAX_DICE_COUNT`/`MAX_DICE_SIDES`
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
   MATRIX_PASSWORD=your-bot-password
   MATRIX_DEVICE_NAME=matrix-bot-roll
   MATRIX_STORE_PATH=./store
   ```

   `MATRIX_DEVICE_NAME` is the device name shown to other clients.

   By default (`MATRIX_SESSION_MODE=fresh`, or unset) the bot logs in fresh on every start and logs out on shutdown — see [Architecture](#architecture). If your host persists `MATRIX_STORE_PATH` across restarts (e.g. local development), you can instead reuse the same login/device between runs:

   ```
   MATRIX_SESSION_MODE=persistent
   MATRIX_SESSION_ENCRYPTION_KEY=your-generated-key
   ```

   Generate a key for `MATRIX_SESSION_ENCRYPTION_KEY` with:

   ```bash
   poetry run invoke generate-session-key
   ```

   Optionally, override the dice sanity limits (defaults: 100 and 100):

   ```
   MAX_DICE_COUNT=100
   MAX_DICE_SIDES=100
   ```

   Optionally, override the logging levels (defaults: `INFO` and `WARNING`):

   ```
   LOG_LEVEL=INFO
   EXTERNAL_LOG_LEVEL=WARNING
   ```

   `LOG_LEVEL` controls the bot's own logs; `EXTERNAL_LOG_LEVEL` controls third-party libraries (e.g. nio's device-tracking/key-claiming/room-handling logs, which are noisy at `INFO`).

3. Verify your `.env` is complete:

   ```bash
   poetry run invoke env-check
   ```

## Usage

```bash
invoke run           # run the bot
invoke watch         # run the bot, auto-restarting on .py/.env changes
```

Or run directly without invoke:

```bash
poetry run python main.py
```

In a room the bot has joined:

```
!roll 1d20
!roll d20
!roll 2d6+4
!roll 4d20 1d6+2
!roll 4d6kh3
!roll 1d20adv
!roll 1d20dis
!roll 4(d10+2)
!roll 4(d10+2)kh1
!roll 3d8+4 | attack
!reroll
```

## Other tasks

```bash
invoke check                   # format with black, lint with flake8, type-check with mypy
invoke ci-check                # verify formatting/lint/types without modifying files (used in CI)
invoke test                    # run the test suite
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

Login behavior is controlled by `MATRIX_SESSION_MODE`:

- **`fresh`** (default): the bot logs in with a password login (`MATRIX_PASSWORD`) on every start and logs out on shutdown, so a new device and matching encryption keys are created each run rather than reusing a fixed access token/device ID. `MATRIX_STORE_PATH` only needs to hold state (encryption keys, sync tokens) for the lifetime of a single run — it's not expected to persist across restarts. This is the right choice for the bot's hosting platform, Scaleway Serverless Containers, which does not persist local disk across container restarts — relying on a long-lived device identity there would leave other clients with stale keys for a device ID that no longer matches them.
- **`persistent`**: the bot saves its login (user ID, device ID, access token) to an encrypted file inside `MATRIX_STORE_PATH`, encrypted with `MATRIX_SESSION_ENCRYPTION_KEY` (a [Fernet](https://cryptography.io/en/latest/fernet/) key). On each start it tries to restore and verify that saved session before falling back to a fresh login; on shutdown it does *not* log out, so the same device persists across restarts. Only use this where `MATRIX_STORE_PATH` genuinely survives restarts (e.g. local development) — on ephemeral storage it degrades to always logging in fresh anyway, but without ever cleaning up the resulting devices.

The bot also binds a minimal HTTP endpoint on `PORT` (default `8080`) that always replies `200 OK`. It exists solely to satisfy cloud platforms that health-check a port before considering a container alive (e.g. Scaleway Serverless Containers) — it is not a real API and shouldn't be treated as one.

## 🤖 AI Transparency

This project is made with ai.

- **AI Model**: Anthropic Claude Sonnet 5
- **License**: MIT

We believe in transparency about AI usage in software development.
