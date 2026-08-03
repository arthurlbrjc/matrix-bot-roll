import asyncio
import logging
import os
from typing import Dict, Optional, Tuple, Union

from nio import AsyncClient, MatrixRoom, RoomMessageText

from matrix_bot_roll import saved_patterns
from matrix_bot_roll.command_handler import handle
from matrix_bot_roll.commands import (
    ListSavedCommand,
    ParsedRoll,
    build_dice_command,
    build_forget_command,
    build_save_command,
    build_saved_pattern_command,
)
from matrix_bot_roll.formatting import format_detail, markdown_to_html
from matrix_bot_roll.health_check import serve_health_check
from matrix_bot_roll.logging_setup import configure_logging
from matrix_bot_roll.matrix_client import run_client
from matrix_bot_roll.messages import (
    NO_PREVIOUS_ROLL,
    pattern_forgotten,
    pattern_not_found,
    pattern_save_limit_reached,
    pattern_saved,
    saved_patterns_list,
)
from matrix_bot_roll.models import DiceRollResult, RollResult

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Starting bot", extra={"pid": os.getpid()})

# The last `!roll`/`!reroll` result shown per room, for `!detail` to redisplay
# without rolling again — display-only memory, kept out of the rolling domain
# (`RollCommand`/`RollResult`/`command_handler`).
_last_details: Dict[str, Tuple[RollResult, Optional[str]]] = {}

# Every command family's recognized aliases, so adding a new alias is a
# one-line change here rather than touching both the guard clause below and
# its dispatch branch separately.
_ROLL_ALIASES = ("!roll", "!r", "!reroll", "!rr")
_DETAIL_ALIASES = ("!detail", "!d")
_SAVE_ALIASES = ("!save", "!s")
_FORGET_ALIASES = ("!forget", "!f")


async def message_callback(
    client: AsyncClient, room: MatrixRoom, event: RoomMessageText
):
    body = event.body.strip()
    command_name = body.split(maxsplit=1)[0] if body else ""
    if command_name not in (
        *_ROLL_ALIASES,
        *_DETAIL_ALIASES,
        *_SAVE_ALIASES,
        *_FORGET_ALIASES,
    ):
        return

    if command_name in _DETAIL_ALIASES:
        stored = _last_details.get(room.room_id)
        if stored is None:
            reply = NO_PREVIOUS_ROLL
        else:
            result, message = stored
            reply = _format_result(result, verbose=True, message=message)
    elif command_name in _SAVE_ALIASES:
        reply = await _handle_save(client, event.sender, body)
    elif command_name in _FORGET_ALIASES:
        reply = await _handle_forget(client, event.sender, body)
    else:
        parsed = await _resolve_dice_command(client, room.room_id, event.sender, body)
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


async def _resolve_dice_command(
    client: AsyncClient, room_id: str, user_id: str, body: str
) -> Union[ParsedRoll, str]:
    """
    Build a `!roll`/`!r`/`!reroll`/`!rr` command. Literal dice syntax is tried
    first via `build_dice_command` — cheap and synchronous — and returned
    immediately if it parses. Only when that fails (and the command is a bare
    `!roll`/`!r`, not a `!reroll`/`!rr`) do we consider whether its first
    argument token is a syntactically legal pattern name (see
    `saved_patterns.is_valid_name`) that `user_id` has actually saved; if so,
    that pattern's saved expression is rolled instead. This ordering means an
    ordinary roll, `--help`, bare usage, or `!reroll` never pays for the
    account-data lookup, and a name that turns out not to be saved falls back
    to `build_dice_command`'s original (already-computed) error instead of
    re-parsing the body a second time.
    """
    parsed = build_dice_command(room_id, body)
    if not isinstance(parsed, str):
        return parsed

    parts = body.split(maxsplit=1)
    command_name = parts[0] if parts else ""
    if command_name in ("!roll", "!r") and len(parts) > 1:
        name_token, _, override_arg = parts[1].strip().partition(" ")
        pattern_name = name_token.lower()
        if saved_patterns.is_valid_name(pattern_name):
            stored_expr = await saved_patterns.get_pattern(
                client, user_id, pattern_name
            )
            if stored_expr is not None:
                return build_saved_pattern_command(
                    room_id, stored_expr, override_arg.strip() or None
                )
    return parsed


async def _handle_save(client: AsyncClient, user_id: str, body: str) -> str:
    """Parse and persist a `!save` command, or list `user_id`'s saved patterns for `!save --list`, returning the reply text."""
    parsed = build_save_command(body)
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, ListSavedCommand):
        patterns = await saved_patterns.list_patterns(client, user_id)
        return saved_patterns_list(patterns)

    saved = await saved_patterns.save_pattern(client, user_id, parsed.name, parsed.expr)
    if not saved:
        return pattern_save_limit_reached(parsed.name)
    return pattern_saved(parsed.name, parsed.expr)


async def _handle_forget(client: AsyncClient, user_id: str, body: str) -> str:
    """Parse and delete a `!forget` command, returning the reply text."""
    parsed = build_forget_command(body)
    if isinstance(parsed, str):
        return parsed

    forgotten = await saved_patterns.forget_pattern(client, user_id, parsed.name)
    if not forgotten:
        return pattern_not_found(parsed.name)
    return pattern_forgotten(parsed.name)


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
