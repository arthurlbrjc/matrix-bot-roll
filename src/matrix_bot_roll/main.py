import asyncio
import logging
import os

from nio import AsyncClient, MatrixRoom, RoomMessageText

from matrix_bot_roll.dice import roll
from matrix_bot_roll.formatting import format_roll_results, markdown_to_html
from matrix_bot_roll.health_check import serve_health_check
from matrix_bot_roll.logging_setup import configure_logging
from matrix_bot_roll.matrix_client import run_client
from matrix_bot_roll.messages import NO_PREVIOUS_ROLL, ROLL_HELP, USAGE

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Starting bot", extra={"pid": os.getpid()})

_last_rolls: dict[str, str] = {}


async def message_callback(
    client: AsyncClient, room: MatrixRoom, event: RoomMessageText
):
    body = event.body.strip()
    if body.startswith("!reroll"):
        reply = _handle_reroll(room.room_id)
    elif body.startswith("!roll"):
        reply = _handle_roll(room.room_id, body)
    else:
        return

    content = {
        "msgtype": "m.text",
        "body": reply,
        "format": "org.matrix.custom.html",
        "formatted_body": markdown_to_html(reply).replace("\n", "<br/>"),
    }

    await client.room_send(
        room_id=room.room_id,
        message_type="m.room.message",
        content=content,
        ignore_unverified_devices=True,
    )


def _handle_roll(room_id: str, body: str) -> str:
    """Handle `!roll`: bare usage, `--help` for detailed syntax, or an expression to roll and remember for `!reroll`."""
    parts = body.split(maxsplit=1)
    if len(parts) < 2:
        return USAGE

    arg = parts[1].strip()
    if arg == "--help":
        return ROLL_HELP

    _last_rolls[room_id] = arg
    return _roll_and_format(arg)


def _handle_reroll(room_id: str) -> str:
    """Handle a `!reroll` message by re-running the last `!roll` expression in this room."""
    expr = _last_rolls.get(room_id)
    if expr is None:
        return NO_PREVIOUS_ROLL
    return _roll_and_format(expr)


def _roll_and_format(expr: str) -> str:
    """Split `expr` into dice expressions and an optional `| message` suffix, roll, and format."""
    dice_part, _, message = expr.partition("|")
    return format_roll_results(roll(dice_part.strip()), message.strip() or None)


async def main():
    tasks = [run_client(message_callback)]
    if os.environ.get("ENABLE_HEALTH_CHECK", "").lower() in ("1", "true", "yes"):
        tasks.append(serve_health_check())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback in case signal handlers didn't fire in time (e.g. Windows)
        logger.info("Interrupted")
    except Exception:
        # Last resort so a crash is a JSON log line, not a bare stderr traceback.
        logger.exception("Unhandled exception, shutting down")
        raise SystemExit(1)
