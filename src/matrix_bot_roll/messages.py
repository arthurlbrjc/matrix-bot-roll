"""User-facing reply strings sent back to Matrix rooms."""

from matrix_bot_roll.constants import (
    MAX_PATTERN_NAME_LENGTH,
    MAX_SAVED_PATTERNS_PER_USER,
)

USAGE = "\n".join(
    [
        "• `!roll <expression> [expression ...] [target] [-v] [| message]` "
        "(or `!r`) — roll dice",
        "• `!roll --help` — detailed roll syntax and examples",
        "• `!reroll [target] [-v] [| message]` (or `!rr`) — repeat the last roll "
        "(always terse unless `-v` is given here)",
        "• `!detail` (or `!d`) — show the full breakdown of the last roll in this room",
    ]
)

ROLL_HELP = "\n".join(
    [
        "**!roll <expression> [expression ...] [target] [-v] [| message]** "
        "(alias: `!r`)",
        "",
        "• `!roll d20` — roll one die",
        "• `!roll 4d6` — roll multiple dice",
        "• `!roll 2d6+4` — add +/- modifiers",
        "• `!roll 4d6kh3`, `!roll 4d6kl3` — keep highest/lowest dice",
        "• `!roll 2d20adv`, `!roll 2d20dis` — advantage/disadvantage "
        "(add one die then keep X highest/lowest)",
        "• `!roll 4(d10+2)`, `!roll 4(d10+2)kh1`, `!roll 2(d20+3)adv` "
        "— per-die modifier and adv/dis/kh/kl",
        "• `!roll 2d6kh1+4 3(d10-2)adv` — combine everything",
        "• `!roll d20+5 >15` — compare the total against a target number "
        "(`>`, `<`, `>=`, `<=`, `=`, `!=`) for pass/fail",
        "• `!roll 3d8+4 | attack` — attach a message to the roll",
        "• `!roll 4d6kh3 -v` (or `--verbose`) — show the full per-die breakdown "
        "(terse by default); the flag can go anywhere in the command",
        "• `!reroll -v` — repeat the last roll verbosely; a reroll never inherits "
        "the original roll's own `-v`, so add it again if you want it",
    ]
)

NO_PREVIOUS_ROLL = "No previous roll in this room — use `!roll <expression>` first."

INVALID_ROLL = "Invalid roll expression — see `!roll --help` for syntax."

SAVE_USAGE = (
    "Usage: `!save <name> <expression> [target] [-v] [| message]` (or `!s`) "
    "— e.g. `!save attack 3d8+4`."
)


def invalid_expr(expr: str, detail: str) -> str:
    """Build a per-expression invalid-roll error naming the offending token and why it failed."""
    safe_expr = expr.replace("`", "'")  # backticks would break the Markdown code span
    return f"Invalid roll `{safe_expr}` — {detail}. See `!roll --help` for syntax."


def invalid_pattern_name(name: str) -> str:
    """Build an error naming why `name` isn't a legal `!save` pattern name."""
    safe_name = name.replace("`", "'")  # backticks would break the Markdown code span
    return (
        f"Invalid pattern name `{safe_name}` — must start with a lowercase letter "
        f"and contain only lowercase letters, `_`, or `-` (no digits, so it can't "
        f"collide with dice notation like `d20`), max {MAX_PATTERN_NAME_LENGTH} "
        f"characters."
    )


def pattern_saved(name: str, expr: str) -> str:
    """Build a confirmation reply for a successful `!save`."""
    safe_expr = expr.replace("`", "'")  # backticks would break the Markdown code span
    return f"✅ Saved `{name}` = `{safe_expr}`."


def pattern_save_limit_reached(name: str) -> str:
    """Build an error reply for a `!save` rejected by the per-user cap."""
    return (
        f"Can't save `{name}` — you already have the maximum of "
        f"{MAX_SAVED_PATTERNS_PER_USER} saved patterns."
    )
