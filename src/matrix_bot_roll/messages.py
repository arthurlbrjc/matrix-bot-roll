"""User-facing reply strings sent back to Matrix rooms."""

from typing import Dict

from matrix_bot_roll.constants import (
    MAX_PATTERN_NAME_LENGTH,
    MAX_SAVED_PATTERNS_PER_USER,
    VERBOSE_FLAGS,
)

USAGE = "\n".join(
    [
        "• `!roll (<expression> [expression ...] | <saved name>) [target] [-v] "
        "[| message]` (or `!r`) — roll dice",
        "• `!reroll [target] [-v] [| message]` (or `!rr`) — repeat the last roll "
        "(always terse unless `-v` is given here)",
        "• `!save <name> <expression> [target] [-v] [| message]` (or `!s`) "
        "— save a roll pattern to reuse with `!roll <name>`",
        "• `!forget <name>` (or `!f`) — remove a saved pattern",
        "• `!detail` (or `!d`) — show the full breakdown of the last roll in this room",
    ]
)

ROLL_HELP = "\n".join(
    [
        "**!roll (<expression> [expression ...] | <saved name>) [target] [-v] "
        "[| message]** (alias: `!r`)",
        "",
        "• `!roll d20`, `!roll 4d6` — roll dice",
        "• `!roll 2d6+4` — add +/- modifiers",
        "• `!roll 4d6kh3`, `!roll 4d6kl3` — keep highest/lowest dice",
        "• `!roll 2d20adv`, `!roll 2d20dis` — advantage/disadvantage "
        "(add one die then keep X highest/lowest)",
        "• `!roll 4(d10+2)`, `!roll 4(d10+2)kh1`, `!roll 2(d20+3)adv` "
        "— per-die modifier and adv/dis/kh/kl",
        "• `!roll d20+5 >15` — compare the total against a target number "
        "(`>`, `<`, `>=`, `<=`, `=`, `!=`) for pass/fail",
        "• `!roll 3d8+4 | attack` — attach a message to the roll",
        "• `!roll 4d6kh3 -v` (or `--verbose`) — show the full per-die breakdown "
        "(terse by default); the flag can go anywhere in the command",
        "• `!roll attack` — roll a pattern saved with `!save`",
    ]
)

NO_PREVIOUS_ROLL = "No previous roll in this room — use `!roll <expression>` first."

INVALID_ROLL = "Invalid roll expression — see `!roll --help` for syntax."

SAVE_USAGE = (
    "Usage: `!save <name> <expression> [target] [-v] [| message]` (or `!s`) "
    "— e.g. `!save attack 3d8+4`. Use `!save --list` to list your saved patterns."
)

NO_SAVED_PATTERNS = (
    "You have no saved patterns yet — use `!save <name> <expression>` to save one."
)

FORGET_USAGE = "Usage: `!forget <name>` (or `!f`) — e.g. `!forget attack`."


def invalid_expr(expr: str, detail: str) -> str:
    """Build a per-expression invalid-roll error naming the offending token and why it failed."""
    safe_expr = expr.replace("`", "'")  # backticks would break the Markdown code span
    return f"Invalid roll `{safe_expr}` — {detail}. See `!roll --help` for syntax."


def invalid_pattern_name(name: str) -> str:
    """Build an error naming why `name` isn't a legal `!save` pattern name."""
    safe_name = name.replace("`", "'")  # backticks would break the Markdown code span
    return (
        f"Invalid pattern name `{safe_name}` — must start with a lowercase letter "
        f"and contain only lowercase letters, `_`, or `-`, max {MAX_PATTERN_NAME_LENGTH} "
        f"characters."
    )


def pattern_saved(name: str, expr: str) -> str:
    """Build a confirmation reply for a successful `!save`, showing the dice
    pattern and (if any) the saved message on their own lines, with the
    `-v`/`--verbose` flag dropped since it isn't part of what's remembered."""
    dice_part, _, message = expr.partition("|")
    dice_tokens = [
        token for token in dice_part.split() if token.lower() not in VERBOSE_FLAGS
    ]
    dice = " ".join(dice_tokens)
    lines = [f"✅ Saved `{name}`:", f"🎲 {dice}"]
    message = message.strip()
    if message:
        safe_message = message.replace("`", "'")
        lines.append(f"💬 {safe_message}")
    return "\n".join(lines)


def pattern_save_limit_reached(name: str) -> str:
    """Build an error reply for a `!save` rejected by the per-user cap."""
    return (
        f"Can't save `{name}` — you already have the maximum of "
        f"{MAX_SAVED_PATTERNS_PER_USER} saved patterns."
    )


def pattern_forgotten(name: str) -> str:
    """Build a confirmation reply for a successful `!forget`."""
    return f"🗑️ Forgot `{name}`."


def pattern_not_found(name: str) -> str:
    """Build an error reply for a `!forget` naming a pattern the caller hasn't saved."""
    return f"You have no saved pattern named `{name}`."


def saved_patterns_list(patterns: Dict[str, str]) -> str:
    """Build a `!save --list` reply: one `name` — expression bullet per saved
    pattern, sorted alphabetically by name, or `NO_SAVED_PATTERNS` if the
    caller has none."""
    if not patterns:
        return NO_SAVED_PATTERNS
    lines = ["📋 Saved patterns:"]
    for name in sorted(patterns):
        safe_expr = patterns[name].replace(
            "`", "'"
        )  # backticks would break the Markdown code span
        lines.append(f"• `{name}` — {safe_expr}")
    return "\n".join(lines)
