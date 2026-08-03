# matrix-bot-roll

![AI-Generated License Badge](vibe-coded-badge.svg)


A Matrix bot that listens for `!roll` commands and replies with dice roll results. Built on [matrix-nio](https://github.com/matrix-nio/matrix-nio) with E2E encryption support.

## Features

- `!roll <expression> [expression ...] [target] [| message]` (or `!r`) — roll dice, e.g. `!roll 2d6+4`, `!roll 4d20 1d6+2 | attack`, `!roll d20+5 >15`
- `!roll --help` — detailed roll syntax and examples (modifiers, kh/kl, adv/dis, group modifiers)
- `!reroll [target] [-v] [| message]` (or `!rr`) — repeat the last `!roll` expression sent in the room, optionally overriding its target and/or message, e.g. `!reroll >15`, `!reroll | defend`; always terse, even if the original roll used `-v` — add `-v` to the reroll itself to get a verbose reroll
- Auto-joins any room it's invited to
- Sanity limits on dice count (1–100), sides (2–100), and expressions per roll (up to 3) to prevent abuse, overridable via `MAX_DICE_COUNT`/`MAX_DICE_SIDES`/`MAX_DICE_EXPRESSIONS`
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

2. Copy `.env.example` to `.env` (gitignored) and fill in the values.

   By default (`MATRIX_SESSION_MODE=fresh`, or unset) the bot logs in fresh on every start and logs out on shutdown — see [Architecture](#architecture). If your host persists `MATRIX_STORE_PATH` across restarts (e.g. local development), you can instead reuse the same login/device between runs:

   ```
   MATRIX_SESSION_MODE=persistent
   MATRIX_SESSION_ENCRYPTION_KEY=your-generated-key
   ```

   Generate a key for `MATRIX_SESSION_ENCRYPTION_KEY` with:

   ```bash
   poetry run invoke generate-session-key
   ```

3. Verify your `.env` is complete:

   ```bash
   poetry run invoke env-check
   ```

## Usage

```bash
poetry run invoke run           # run the bot
poetry run invoke watch         # run the bot, auto-restarting on .py/.env changes
```

Or run directly without invoke:

```bash
PYTHONPATH=src poetry run python -m matrix_bot_roll.main
```

In a room the bot has joined:

```
!roll 2d6+4
!roll --help
!reroll
!r 2d6+4
!rr
```

## Other tasks

```bash
poetry run invoke check        # format with black, lint with flake8, type-check with mypy
poetry run invoke ci-check     # verify formatting/lint/types without modifying files (used in CI)
poetry run invoke test         # run the test suite
poetry run invoke clean        # remove __pycache__, caches, build artifacts
poetry run invoke clean-store  # wipe ./dev/store (encryption keys + sync tokens); prompts for confirmation
```

`clean-store` forces a full re-sync on next run and can break decryption of previously-seen messages — only use it if the store is corrupted or you're resetting the bot's session.

### Skipping the `poetry run` prefix

`invoke` and its task dependencies (e.g. `python-dotenv`) are installed in Poetry's virtualenv, not globally, so a bare `invoke <task>` normally fails to find them. To activate that venv for your current shell and drop the prefix for the rest of the session:

```bash
eval $(poetry env activate)
invoke test    # now works without poetry run, for this shell only
```

Notes:

- This only affects the shell it's run in — other terminals, and new shells, are unaffected.
- It doesn't spawn a subshell (unlike the older `poetry shell` plugin); it modifies `PATH`/`VIRTUAL_ENV` in place, so if you `cd` into another project in the same shell you'll still be using this project's venv unless you deactivate.
- To leave the venv, run `deactivate`, or just close the shell.
- Not useful for non-interactive contexts (CI, Docker, cron) — those should keep using `poetry run <cmd>` explicitly.

## Local test homeserver

`dev/docker-compose.yml` spins up a local Synapse homeserver and an Element web client, useful for testing the bot without a real Matrix account:

```bash
docker compose -f dev/docker-compose.yml up
```

- Synapse: http://localhost:8008
- Element: http://localhost:8080

## Architecture

Login behavior is controlled by `MATRIX_SESSION_MODE`:

- **`fresh`** (default): the bot logs in with a password login (`MATRIX_PASSWORD`) on every start and logs out on shutdown, so a new device and matching encryption keys are created each run rather than reusing a fixed access token/device ID. `MATRIX_STORE_PATH` only needs to hold state (encryption keys, sync tokens) for the lifetime of a single run — it's not expected to persist across restarts. This is the right choice for the bot's hosting platform, Scaleway Serverless Containers, which does not persist local disk across container restarts — relying on a long-lived device identity there would leave other clients with stale keys for a device ID that no longer matches them.
- **`persistent`**: the bot saves its login (user ID, device ID, access token) to an encrypted file inside `MATRIX_STORE_PATH`, encrypted with `MATRIX_SESSION_ENCRYPTION_KEY` (a [Fernet](https://cryptography.io/en/latest/fernet/) key). On each start it tries to restore and verify that saved session before falling back to a fresh login; on shutdown it does *not* log out, so the same device persists across restarts. Only use this where `MATRIX_STORE_PATH` genuinely survives restarts (e.g. local development) — on ephemeral storage it degrades to always logging in fresh anyway, but without ever cleaning up the resulting devices.

When `ENABLE_HEALTH_CHECK` is set to `1`/`true`/`yes`, the bot also binds a minimal HTTP endpoint on `PORT` (default `8080`) that always replies `200 OK`. It exists solely to satisfy cloud platforms that health-check a port before considering a container alive (e.g. Scaleway Serverless Containers) — it is not a real API and shouldn't be treated as one. Off by default, since it's unneeded for local development.

## 🤖 AI Transparency

This project is made with ai.

- **AI Model**: Anthropic Claude Sonnet 5
- **License**: MIT

We believe in transparency about AI usage in software development.
