"""
Invoke tasks for the Tchap bot.

Usage:
    poetry run invoke <task>

Examples:
    poetry run invoke run
    poetry run invoke clean
"""

import os
import shutil

from invoke import task

BOT_SCRIPT = "matrix-bot-roll.py"  # adjust if your entrypoint file has a different name


@task
def run(c):
    """Run the bot."""
    c.run(f"poetry run python {BOT_SCRIPT}", pty=True)


@task
def watch(c):
    """Run the bot, auto-restarting on .py and .env changes."""
    c.run(
        "poetry run watchfiles "
        f"'poetry run python {BOT_SCRIPT}' "
        "--filter python "
        ".",
        pty=True,
    )


@task
def clean_store(c):
    """
    Wipe the local nio store (encryption keys + sync tokens).

    WARNING: this forces a full re-sync and can break decryption
    of previously-seen encrypted messages. Use only if the store
    is corrupted or you're resetting the bot's session.
    """
    from dotenv import load_dotenv

    load_dotenv()
    store_path = os.environ["MATRIX_STORE_PATH"]

    if os.path.isdir(store_path):
        confirm = input(f"This will empty {store_path}. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            for entry in os.scandir(store_path):
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
            print(f"Emptied {store_path}")
        else:
            print("Aborted.")
    else:
        print(f"No store directory found at {store_path}")


@task
def clean(c):
    """Remove caches and build artifacts (not the nio store — see clean-store)."""
    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        "*.egg-info",
    ]
    for pattern in patterns:
        c.run(f"find . -path './.venv' -prune -o -name '{os.path.basename(pattern)}' -print0 | xargs -0 rm -rf", warn=True)


@task
def env_check(c):
    """Verify required .env variables are set (without printing secrets)."""
    from dotenv import load_dotenv

    load_dotenv()
    required = [
        "MATRIX_ACCESS_TOKEN",
        "MATRIX_BASE_URL",
        "MATRIX_DEVICE_ID",
        "MATRIX_USER_ID",
        "MATRIX_STORE_PATH",
    ]
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print("Missing or empty .env variables:")
        for var in missing:
            print(f"  - {var}")
        raise SystemExit(1)
    print("All required .env variables are set.")


@task
def pingtest(c):
    c.run("python3 -c \"import time; print('start'); time.sleep(30); print('end')\"", pty=True)
