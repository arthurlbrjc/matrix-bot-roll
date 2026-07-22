# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Matrix bot (`matrix-bot-roll.py`) that listens for `!roll` commands in Matrix rooms (e.g. `!roll 2d6+4`, `!roll 4d20 1d6+2`) and replies with the roll results. Built on `matrix-nio` with E2E encryption enabled. There is no test suite.

## Commands

Dependency management is via Poetry; task running via `invoke` (see `tasks.py`).

```bash
poetry install      # install dependencies
invoke run          # run the bot
invoke watch        # run the bot, auto-restart on .py/.env changes
poetry run invoke env-check    # verify required .env vars are present (no secrets printed)
poetry run invoke clean        # remove __pycache__, caches, build artifacts
poetry run invoke clean-store  # wipe ./store (encryption keys + sync tokens) — prompts for confirmation; forces full re-sync and can break decryption of previously-seen messages
```

Run directly without invoke: `poetry run python matrix-bot-roll.py`.

## Configuration

Config is loaded from `.env` (gitignored) via `python-dotenv`. Required variables, checked by `invoke env-check`:

- `MATRIX_BASE_URL`
- `MATRIX_USER_ID`
- `MATRIX_ACCESS_TOKEN`
- `MATRIX_DEVICE_ID`
- `MATRIX_STORE_PATH`

The bot fails fast at startup (`os.environ[...]`) if any are missing.

## Architecture

Everything lives in `matrix-bot-roll.py`, structured as:

- **Dice parsing/rolling** (`roll_dice`, `roll_multiple`): regex-based parser (`DICE_RE`) for expressions like `2d6+4`; enforces sanity limits (count 1–100, sides 2–1000) to prevent abuse/hangs. Pure functions, no I/O — easiest place to add new dice syntax.
- **Formatting** (`format_roll_results`, `markdown_bold_to_html`): turns roll results into a Markdown reply, then converts `**bold**` to `<b>` for the Matrix `formatted_body` (HTML) alongside the plain-text `body`.
- **Matrix event handling** (`message_callback`, `invite_callback`): `message_callback` ignores the bot's own messages, requires a `!roll` prefix, and sends replies as both plain text and HTML. `invite_callback` auto-joins any room the bot is invited to.
- **Lifecycle** (`main`): logs in via `restore_login` with a pre-existing access token (no interactive login flow), registers callbacks, then races `client.sync_forever()` against a `SIGINT`/`SIGTERM`-triggered shutdown event so Ctrl+C/termination closes the client cleanly instead of being killed mid-sync.

State (encryption keys, sync tokens) persists to `MATRIX_STORE_PATH` between runs — don't delete it casually (see `clean-store` warning above).