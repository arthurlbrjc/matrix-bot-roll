import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union, cast

from matrix_bot_roll.constants import MAX_DICE_COUNT, MAX_DICE_SIDES
from matrix_bot_roll.messages import (
    INVALID_ROLL,
    NO_PREVIOUS_ROLL,
    ROLL_HELP,
    SAVE_USAGE,
    USAGE,
    invalid_expr,
    invalid_pattern_name,
)
from matrix_bot_roll.models import AdvDis, DiceSpec, KeepMode, Target, TargetOperator
from matrix_bot_roll.saved_patterns import is_valid_name

# Matches things like: 1d20, 2d6+4, d8, 3d10-2, 2d20kh1, 4d6kl3, 2d20adv, 2d20dis
DICE_WITH_TOTAL_MODIFIER_RE = re.compile(
    r"^(\d*)\s*d\s*(\d+)\s*(kh\d+|kl\d+|adv|dis)?\s*([+-]\s*\d+)?$", re.IGNORECASE
)

# Matches a per-die modifier group like: 4(d10+2), 3(d6-1), 4(d10+2)kh1 — the
# modifier is applied to each die individually rather than once to the summed
# total; an optional keep/advantage suffix (outside the parens) then selects
# among the modified values.
DICE_WITH_DIE_MODIFIER_RE = re.compile(
    r"^(\d+)\(\s*d\s*(\d+)\s*([+-]\s*\d+)\s*\)\s*(kh\d+|kl\d+|adv|dis)?$",
    re.IGNORECASE,
)

# Matches a trailing target-number comparison for the whole line, e.g. '>15',
# '>=8', '=10', '!=3' — applied to the summed total across every dice expression
# on the line (see `_parse_command`). May appear anywhere among the
# space-separated tokens, like the verbose flag.
TARGET_RE = re.compile(r"^(>=|<=|!=|>|<|=)(-?\d+)$")

# The verbose flag may appear anywhere among the space-separated tokens (like
# a normal CLI flag), rather than in a fixed position.
VERBOSE_FLAGS = {"-v", "--verbose"}

_last_rolls: Dict[str, str] = {}


@dataclass
class RollCommand:
    """A fully parsed and validated `!roll`/`!reroll` request, ready to be rolled — the rolling domain only, with no display concerns."""

    specs: List[Tuple[str, DiceSpec]]
    target: Optional[Target]


@dataclass
class ParsedRoll:
    """A successfully parsed `!roll`/`!reroll` request: the `command` to roll, plus display-only extras it carries no knowledge of."""

    command: RollCommand
    verbose: bool
    message: Optional[str]


@dataclass
class SaveCommand:
    """
    A fully parsed and validated `!save <name> <expr>` request, ready for the
    caller to persist.

    `expr` is kept as the original raw string rather than a parsed
    `RollCommand`, mirroring how `!reroll` remembers its stored expression
    (see `_last_rolls`) — it's re-parsed fresh whenever the saved pattern is
    rolled, so a pattern saved today automatically picks up any dice syntax
    added later.
    """

    name: str
    expr: str


def build_dice_command(room_id: str, body: str) -> Union[ParsedRoll, str]:
    """
    Parse a full `!roll`/`!r`/`!reroll`/`!rr` message body.

    Returns a `ParsedRoll` if the body contains at least one dice expression and
    every expression in it parses and validates successfully. Otherwise returns a
    plain-text reply string (usage, help, "no previous roll", or "invalid roll").
    """
    parts = body.split(maxsplit=1)
    command = parts[0] if parts else ""
    if command in ("!reroll", "!rr"):
        arg = parts[1].strip() if len(parts) > 1 else None
        return _build_reroll_command(room_id, arg)
    return _build_roll_command(room_id, parts)


def _build_roll_command(room_id: str, parts: List[str]) -> Union[ParsedRoll, str]:
    """Handle `!roll`/`!r`: bare usage, `--help` for detailed syntax, or an expression to parse and remember for `!reroll`."""
    if len(parts) < 2:
        return USAGE

    arg = parts[1].strip()
    if arg == "--help":
        return ROLL_HELP

    result = _parse_command(arg)
    if isinstance(result, ParsedRoll):
        _last_rolls[room_id] = arg
    return result


def _build_reroll_command(room_id: str, arg: Optional[str]) -> Union[ParsedRoll, str]:
    """
    Handle a `!reroll`/`!rr` message by re-parsing the last `!roll` expression in
    this room. An optional leading target (e.g. '>15') replaces the target the
    original roll had; an optional `| message` suffix replaces its message. Both
    are remembered for subsequent bare `!reroll`s in this room; whichever isn't
    given is replayed unchanged from the original roll. The original roll's
    `-v`/`--verbose` flag is never inherited: a reroll is terse unless it carries
    its own verbose flag.
    """
    stored = _last_rolls.get(room_id)
    if stored is None:
        return NO_PREVIOUS_ROLL
    if not arg:
        return _parse_command(_strip_verbose_flags(stored))

    prefix, separator, message = arg.partition("|")
    prefix_tokens = prefix.split()
    verbose = any(token.lower() in VERBOSE_FLAGS for token in prefix_tokens)
    target_tokens = [
        token for token in prefix_tokens if token.lower() not in VERBOSE_FLAGS
    ]
    if len(target_tokens) > 1 or (
        target_tokens and _parse_target(target_tokens[0]) is None
    ):
        return INVALID_ROLL

    new_arg = _apply_reroll_overrides(
        stored,
        target_tokens[0] if target_tokens else None,
        verbose,
        bool(separator),
        message,
    )
    result = _parse_command(new_arg)
    if isinstance(result, ParsedRoll):
        _last_rolls[room_id] = new_arg
    return result


def build_save_command(body: str) -> Union[SaveCommand, str]:
    """
    Parse a full `!save <name> <expr...>` message body: validate the pattern
    name, then validate `<expr...>` using the same syntax `!roll` accepts
    (target/message/verbose flags included). The expression is kept as-is
    (see `SaveCommand`) — only its validity is checked here, not its parsed
    form.

    Kept separate from `build_dice_command` — a save is a write with its own
    reply shape, not another kind of roll — so callers that only handle
    `!roll`/`!reroll` (i.e. everywhere until `!save` is wired up) are
    unaffected by this command existing.
    """
    parts = body.split(maxsplit=2)
    if len(parts) < 3:
        return SAVE_USAGE

    name = parts[1].lower()
    if not is_valid_name(name):
        return invalid_pattern_name(name)

    expr = parts[2].strip()
    result = _parse_command(expr)
    if isinstance(result, str):
        return result

    return SaveCommand(name=name, expr=expr)


def _apply_reroll_overrides(
    stored: str,
    new_target_token: Optional[str],
    verbose: bool,
    has_pipe: bool,
    message: str,
) -> str:
    """
    Rebuild the stored roll string with an optional target override and/or message
    override applied. The original roll's verbose flag is dropped; `verbose` (from
    this reroll's own arg) decides whether the rebuilt string carries one.
    """
    stored_dice_part, stored_separator, stored_message = stored.partition("|")
    stored_tokens = stored_dice_part.split()
    kept_tokens = [
        token
        for token in stored_tokens
        if _parse_target(token) is None and token.lower() not in VERBOSE_FLAGS
    ]

    target_token = new_target_token or next(
        (token for token in stored_tokens if _parse_target(token) is not None), None
    )
    if target_token:
        kept_tokens.append(target_token)
    if verbose:
        kept_tokens.append("-v")
    dice_part = " ".join(kept_tokens)

    if has_pipe:
        return f"{dice_part} | {message}"
    if stored_separator:
        return f"{dice_part} | {stored_message}"
    return dice_part


def _strip_verbose_flags(text: str) -> str:
    """Drop any `-v`/`--verbose` tokens from the dice part of `text`, leaving the message part untouched."""
    dice_part, separator, message = text.partition("|")
    kept_tokens = [
        token for token in dice_part.split() if token.lower() not in VERBOSE_FLAGS
    ]
    dice_part = " ".join(kept_tokens)
    if separator:
        return f"{dice_part} | {message}"
    return dice_part


def _parse_command(arg: str) -> Union[ParsedRoll, str]:
    """
    Split `arg` into dice expressions, an optional target (e.g. '>15') applied to
    their summed total, an optional `-v`/`--verbose` flag, and an optional
    `| message` suffix, then validate all expressions. The target and verbose flag
    may appear anywhere among the space-separated tokens, in any order; a repeated
    verbose flag is harmless, but a second target token is rejected as ambiguous.
    At least one dice expression is required.
    """
    dice_part, _, message = arg.partition("|")

    verbose = False
    target: Optional[Target] = None
    exprs = []
    for token in dice_part.split():
        if token.lower() in VERBOSE_FLAGS:
            verbose = True
            continue
        parsed_target = _parse_target(token)
        if parsed_target is not None:
            if target is not None:
                return INVALID_ROLL
            target = parsed_target
            continue
        exprs.append(token)

    if not exprs:
        return INVALID_ROLL

    specs = []
    for expr in exprs:
        spec = _parse_expr(expr)
        if isinstance(spec, str):
            return spec
        specs.append((expr, spec))

    command = RollCommand(specs=specs, target=target)
    return ParsedRoll(command=command, verbose=verbose, message=message.strip() or None)


def _parse_target(token: str) -> Optional[Target]:
    """Parse a trailing '>15'-style token into a `Target`, or None if it isn't one."""
    match = TARGET_RE.match(token)
    if match is None:
        return None
    operator, value_str = match.groups()
    return Target(operator=cast(TargetOperator, operator), value=int(value_str))


def _parse_expr(expr: str) -> Union[DiceSpec, str]:
    """Parse and validate a dice expression like '2d6+4' or '2d20kh1' into a `DiceSpec`, or an error string naming what's wrong."""
    expr = expr.strip()

    die_modifier_match = DICE_WITH_DIE_MODIFIER_RE.match(expr)
    if die_modifier_match:
        result: Union[DiceSpec, str] = _build_die_modifier_spec(die_modifier_match)
    else:
        total_modifier_match = DICE_WITH_TOTAL_MODIFIER_RE.match(expr)
        if total_modifier_match:
            result = _build_total_modifier_spec(total_modifier_match)
        else:
            return invalid_expr(expr, "not a recognized dice expression")

    if isinstance(result, str):
        return invalid_expr(expr, result)
    return result


def _build_total_modifier_spec(
    total_modifier_match: "re.Match[str]",
) -> Union[DiceSpec, str]:
    """Build the `DiceSpec` for the plain syntax (e.g. '2d6+4'), where `modifier` applies once to the summed total."""
    count_str, sides_str, keep_str, modifier_str = total_modifier_match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0

    resolved = _validate(count, sides, keep_str)
    if isinstance(resolved, str):
        return resolved
    keep_mode, keep_n, adv_dis, count = resolved

    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode="total",
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
    )


def _build_die_modifier_spec(
    die_modifier_match: "re.Match[str]",
) -> Union[DiceSpec, str]:
    """
    Build the `DiceSpec` for the per-die-modifier syntax (e.g. '4(d10+2)'), where `modifier`
    applies to each die individually, then optionally keep/advantage-selects among the
    modified values via the keep suffix (kh#, kl#, adv, dis).
    """
    count_str, sides_str, modifier_str, keep_str = die_modifier_match.groups()
    count = int(count_str)
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", ""))

    resolved = _validate(count, sides, keep_str)
    if isinstance(resolved, str):
        return resolved
    keep_mode, keep_n, adv_dis, count = resolved

    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode="per_die",
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
    )


def _validate(
    count: int, sides: int, keep_str: Optional[str]
) -> Union[Tuple[Optional[KeepMode], Optional[int], Optional[AdvDis], int], str]:
    """Combine `_in_bounds` and `_resolve_keep`, short-circuiting on the first error string."""
    bounds_error = _in_bounds(count, sides)
    if bounds_error is not None:
        return bounds_error
    return _resolve_keep(keep_str, count)


def _in_bounds(count: int, sides: int) -> Optional[str]:
    """
    Sanity limits so nobody rolls 999999d999999 and hangs the bot.

    Checked against the requested count only — adv/dis are allowed to add one
    extra die on top of MAX_DICE_COUNT (see `_resolve_keep`) by design. Returns
    an error string describing the first bound violated, or None if in bounds.
    """
    if not 1 <= count <= MAX_DICE_COUNT:
        return f"dice count must be between 1 and {MAX_DICE_COUNT}"
    if not 2 <= sides <= MAX_DICE_SIDES:
        return f"sides must be between 2 and {MAX_DICE_SIDES}"
    return None


def _resolve_keep(
    keep_str: Optional[str], count: int
) -> Union[Tuple[Optional[KeepMode], Optional[int], Optional[AdvDis], int], str]:
    """
    Parse a keep/advantage/disadvantage suffix (kh#, kl#, adv, dis) against `count`
    dice. Returns (keep_mode, keep_n, adv_dis, count) — with `count` bumped by one
    for adv/dis — or an error string if there is a suffix and it resolves to an
    invalid keep_n.
    """
    if not keep_str:
        return None, None, None, count

    keep_str = keep_str.lower()
    keep_mode: KeepMode
    adv_dis: Optional[AdvDis]
    if keep_str == "adv":
        keep_mode, keep_n = "highest", count
        count += 1  # adv/dis roll one extra die, then drop the single worst/best
        adv_dis = "advantage"
    elif keep_str == "dis":
        keep_mode, keep_n = "lowest", count
        count += 1
        adv_dis = "disadvantage"
    else:
        keep_mode = "highest" if keep_str[1] == "h" else "lowest"
        keep_n = int(keep_str[2:])
        adv_dis = None

    if keep_n < 1:
        return f"`{keep_str}` needs a keep count of at least 1"
    if keep_n > count:
        return f"`{keep_str}` keeps more dice than were rolled ({count})"

    return keep_mode, keep_n, adv_dis, count
