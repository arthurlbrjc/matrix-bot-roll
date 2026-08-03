"""
Invoke tasks for the Tchap bot.

Usage:
    poetry run invoke <task>

Examples:
    poetry run invoke run
    poetry run invoke clean
"""

import os
import re
import shlex
import shutil
from datetime import date

from invoke import task

BOT_MODULE = "matrix_bot_roll.main"


@task
def env_check(c):
    """Verify required .env variables are set (without printing secrets)."""
    from dotenv import load_dotenv

    load_dotenv()
    required = [
        "MATRIX_BASE_URL",
        "MATRIX_DEVICE_NAME",
        "MATRIX_PASSWORD",
        "MATRIX_USER_ID",
        "MATRIX_STORE_PATH",
    ]
    if os.environ.get("MATRIX_SESSION_MODE") == "persistent":
        required.append("MATRIX_SESSION_ENCRYPTION_KEY")
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print("Missing or empty .env variables:")
        for var in missing:
            print(f"  - {var}")
        raise SystemExit(1)
    print("All required .env variables are set.")


@task(pre=[env_check])
def run(c):
    """Run the bot."""
    c.run(f"poetry run python -m {BOT_MODULE}", pty=True, env={"PYTHONPATH": "src"})


@task(pre=[env_check])
def watch(c):
    """Run the bot, auto-restarting on .py and .env changes."""
    c.run(
        "poetry run watchfiles "
        f"'poetry run python -m {BOT_MODULE}' "
        "--filter python "
        "src",
        pty=True,
        env={"PYTHONPATH": "src"},
    )


@task
def check(c):
    """Format code with black, then lint with flake8, then type-check with mypy."""
    c.run("poetry run black .", pty=True)
    c.run("poetry run flake8 .", pty=True)
    c.run("poetry run mypy .", pty=True)


@task
def ci_check(c):
    """Verify formatting with black, lint with flake8, and type-check with mypy (no fixing)."""
    c.run("poetry run black --check .", pty=True)
    c.run("poetry run flake8 .", pty=True)
    c.run("poetry run mypy .", pty=True)


@task
def test(c):
    """Run the test suite."""
    c.run("poetry run pytest", pty=True)


@task
def generate_session_key(c):
    """Generate a key for MATRIX_SESSION_ENCRYPTION_KEY (used by MATRIX_SESSION_MODE=persistent)."""
    from cryptography.fernet import Fernet

    print(Fernet.generate_key().decode())


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
        c.run(
            f"find . -path './.venv' -prune -o -name '{os.path.basename(pattern)}' -print0 | xargs -0 rm -rf",
            warn=True,
        )


@task(
    help={
        "release": "Target release, must be a valid semver string or a valid bump rule. Default to patch",
        "changelog": "Draft a CHANGELOG.md entry for this release via the local `claude` CLI, "
        "and pause for review before committing. Default: off",
    }
)
def version(ctx, release="patch", changelog=False):
    """
    Bump package version and create commit with corresponding tag
    """
    new_version = ctx.run(
        f"poetry version {release} --dry-run -s", hide="out"
    ).stdout.strip()
    with open("CHANGELOG.md") as file:
        changelog_has_entry = f"[{new_version}]" in file.read()
    if not changelog_has_entry:
        if changelog:
            # Before pyproject.toml is touched: an aborted draft (Ctrl-C)
            # then leaves nothing to undo.
            draft_changelog_entry(ctx, new_version)
        else:
            print(
                f"Warning: CHANGELOG.md has no entry for {new_version} — "
                f"`!changes` will be stale until one is added."
            )
    bumpversion(ctx, release)
    ctx.run("git add --all")
    ctx.run(f"git commit --message='v{new_version}'")
    ctx.run(f"git tag --annotate 'v{new_version}' --message='v{new_version}'")


def draft_changelog_entry(ctx, new_version):
    """
    Ask the local `claude` CLI to draft a Keep a Changelog entry for
    `new_version` from the commit messages since the last tag, print the
    draft, then either insert it into CHANGELOG.md on confirmation or pause
    for the user to paste it in manually — the draft is never written
    without an explicit yes.
    """
    last_tag = ctx.run(
        "git describe --tags --abbrev=0", hide="out", warn=True
    ).stdout.strip()
    log_range = f"{last_tag}.." if last_tag else ""
    commits = ctx.run(
        f"git log --format='- %s' {log_range}HEAD", hide="out"
    ).stdout.strip()
    prompt = (
        f"Draft a Keep a Changelog (https://keepachangelog.com) entry for "
        f"matrix-bot-roll version {new_version}, dated {date.today().isoformat()}, "
        f"based on these gitmoji-prefixed commit messages since the last release:\n\n"
        f"{commits}\n\n"
        f"Output only the section, in this exact shape (see CHANGELOG.md in the "
        f"repo for the style and section headings already in use):\n\n"
        f"## [{new_version}] - {date.today().isoformat()}\n\n### Added/Changed/Fixed\n\n- ...\n\n"
        f"Skip pure refactor/docs/tooling commits unless they're user-facing. "
        f"Keep bullets terse, matching the existing entries. "
        f"Output nothing else — no preamble, no explanation of your reasoning, "
        f"no text before or after the section."
    )
    raw_draft = ctx.run(
        f"claude -p {shlex.quote(prompt)} < /dev/null", hide="out"
    ).stdout.strip()
    draft = extract_changelog_section(raw_draft)
    print("\n--- Draft CHANGELOG.md entry ---\n")
    print(draft)
    print("\n--- end draft ---\n")

    if input("Add this entry to CHANGELOG.md now? [y/N]: ").strip().lower() == "y":
        insert_changelog_entry(draft)
        print("Added to CHANGELOG.md.")
    else:
        input("Add it manually, then press Enter to continue (Ctrl-C to abort): ")


def extract_changelog_section(raw_draft):
    """
    Strip any preamble/commentary `claude -p` wrote before the `## [` heading —
    it's asked not to, but isn't always obedient. Falls back to the raw
    output, untouched, if no heading is found at all.
    """
    match = re.search(r"^## \[", raw_draft, re.MULTILINE)
    if not match:
        return raw_draft
    start = match.start()
    return raw_draft[start:].strip()


def insert_changelog_entry(draft):
    """Insert `draft` into CHANGELOG.md just above the first existing `## [` release heading, or at the end of the file if there isn't one yet."""
    with open("CHANGELOG.md") as file:
        text = file.read()

    match = re.search(r"^## \[", text, re.MULTILINE)
    insertion_point = match.start() if match else len(text)
    new_text = f"{text[:insertion_point]}{draft.strip()}\n\n{text[insertion_point:]}"

    with open("CHANGELOG.md", "w") as file:
        file.write(new_text)


@task(
    help={
        "release": "Target release, must be a valid semver string or a valid bump rule. Default to patch"
    }
)
def bumpversion(ctx, release="patch"):
    """
    Bump package version
    """
    ctx.run(f"poetry version {release}")
