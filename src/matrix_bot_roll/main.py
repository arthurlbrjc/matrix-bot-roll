import asyncio
import logging
import os

from nio import AsyncClient, MatrixRoom, RoomMessageText

from matrix_bot_roll.command_handler import handle
from matrix_bot_roll.commands import build_command
from matrix_bot_roll.formatting import format_detail, markdown_to_html
from matrix_bot_roll.health_check import serve_health_check
from matrix_bot_roll.logging_setup import configure_logging
from matrix_bot_roll.matrix_client import run_client
from matrix_bot_roll.models import DiceRollResult, RollResult

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Starting bot", extra={"pid": os.getpid()})


async def message_callback(
    client: AsyncClient, room: MatrixRoom, event: RoomMessageText
):
    body = event.body.strip()
    command = body.split(maxsplit=1)[0] if body else ""
    if command not in ("!roll", "!r", "!reroll", "!rr"):
        return

    parsed = build_command(room.room_id, body)
    reply = parsed if isinstance(parsed, str) else _format_result(handle(parsed))

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


def _format_result(result: RollResult) -> str:
    """
    Turn a RollResult into a human-readable string.

    Also appends a grand total across all rolls if there's more than one, and
    the optional `message` attached to the roll, if any.
    """
    lines = [_format_roll_line(expr, roll) for expr, roll in result.rolls]

    if len(result.rolls) > 1:
        lines.append(f"**Total: {result.total}**")

    if result.message:
        lines.append(f"💬 {result.message}")

    return "\n".join(lines)


def _format_roll_line(expr: str, roll: DiceRollResult) -> str:
    """Render one '🎲 expr → detail = **total**' line, with a crit/fumble suffix if applicable."""
    suffix = (
        " 🎯 CRIT!"
        if roll.crit == "crit"
        else " 💥 FUMBLE!" if roll.crit == "fumble" else ""
    )
    return f"🎲 {expr} → {format_detail(roll)} = **{roll.total}**{suffix}"


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
