import asyncio
import logging
import os
from typing import Dict, Optional, Tuple

from nio import AsyncClient, MatrixRoom, RoomMessageText

from matrix_bot_roll.command_handler import handle
from matrix_bot_roll.commands import build_command
from matrix_bot_roll.formatting import format_detail, markdown_to_html
from matrix_bot_roll.health_check import serve_health_check
from matrix_bot_roll.logging_setup import configure_logging
from matrix_bot_roll.matrix_client import run_client
from matrix_bot_roll.messages import NO_PREVIOUS_ROLL
from matrix_bot_roll.models import DiceRollResult, RollResult

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Starting bot", extra={"pid": os.getpid()})

# The last `!roll`/`!reroll` result shown per room, for `!detail` to redisplay
# without rolling again — display-only memory, kept out of the rolling domain
# (`RollCommand`/`RollResult`/`command_handler`).
_last_details: Dict[str, Tuple[RollResult, Optional[str]]] = {}


async def message_callback(
    client: AsyncClient, room: MatrixRoom, event: RoomMessageText
):
    body = event.body.strip()
    command_name = body.split(maxsplit=1)[0] if body else ""
    if command_name not in ("!roll", "!r", "!reroll", "!rr", "!detail", "!d"):
        return

    if command_name in ("!detail", "!d"):
        stored = _last_details.get(room.room_id)
        if stored is None:
            reply = NO_PREVIOUS_ROLL
        else:
            result, message = stored
            reply = _format_result(result, verbose=True, message=message)
    else:
        parsed = build_command(room.room_id, body)
        if isinstance(parsed, str):
            reply = parsed
        else:
            result = handle(parsed.command)
            _last_details[room.room_id] = (result, parsed.message)
            reply = _format_result(
                result, verbose=parsed.verbose, message=parsed.message
            )

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


def _format_result(result: RollResult, verbose: bool, message: Optional[str]) -> str:
    """
    Turn a RollResult into a human-readable string.

    Each roll line shows only the expression, total, and crit/fumble marker
    unless `verbose` is set, in which case it also shows the full per-die
    breakdown. In terse mode, a single rolled expression compared to a target
    is inlined onto that same line (e.g. '🎲 5d8 → **24** >20 → ✅ Success!');
    otherwise (verbose, or more than one expression) the target instead gets
    its own dedicated result line, since in verbose mode the roll line is
    already busy with the per-die breakdown, and with more than one expression
    the target isn't tied to any single roll. Also appends the optional
    `message` attached to the roll, if any.
    """
    inline_target = result.target is not None and len(result.rolls) == 1 and not verbose
    if inline_target:
        expr, roll = result.rolls[0]
        lines = [_format_roll_line_with_target(expr, roll, result)]
    else:
        lines = [_format_roll_line(expr, roll, verbose) for expr, roll in result.rolls]
        if result.target is not None:
            lines.append(_format_target_line(result))
        elif len(result.rolls) > 1:
            lines.append(f"**Total: {result.total}**")

    if message:
        lines.append(f"💬 {message}")

    return "\n".join(lines)


def _format_target_line(result: RollResult) -> str:
    """Render '**Total: X** vs <operator><value> → ✅/❌' as its own dedicated line."""
    assert result.target is not None
    marker = "✅ Success!" if result.success else "❌ Failure!"
    return (
        f"**Total: {result.total}** vs {result.target.operator}{result.target.value} "
        f"→ {marker}"
    )


def _format_roll_line(expr: str, roll: DiceRollResult, verbose: bool) -> str:
    """Render one '🎲 expr → **total**' line (or, if `verbose`, '🎲 expr → detail = **total**'), with a crit/fumble suffix if applicable."""
    detail = f"{format_detail(roll)} = " if verbose else ""
    return f"🎲 {expr} → {detail}**{roll.total}**{_crit_suffix(roll)}"


def _format_roll_line_with_target(
    expr: str, roll: DiceRollResult, result: RollResult
) -> str:
    """Render a single terse roll's line with its target comparison inlined, e.g. '🎲 5d8 → **24** >20 → ✅ Success!'."""
    assert result.target is not None
    marker = "✅ Success!" if result.success else "❌ Failure!"
    return (
        f"🎲 {expr} → **{roll.total}**{_crit_suffix(roll)} "
        f"{result.target.operator}{result.target.value} → {marker}"
    )


def _crit_suffix(roll: DiceRollResult) -> str:
    """Render the trailing ' 🎯 CRIT!'/' 💥 FUMBLE!' marker for a roll, or '' if neither applies."""
    if roll.crit == "crit":
        return " 🎯 CRIT!"
    if roll.crit == "fumble":
        return " 💥 FUMBLE!"
    return ""


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
