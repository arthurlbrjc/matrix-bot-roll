import random
import re
from typing import Callable, List, Optional, Tuple, TypeVar

T = TypeVar("T")

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


def roll(input_str: str):
    """
    Parse and roll multiple space-separated dice expressions, e.g. '4d20 1d6+2'.

    Returns a list of tuples: (expr, result_or_None)
    where result_or_None is (total, detail_str, crit) from roll_dice, or None if invalid.
    """
    exprs = input_str.split()
    if not exprs:
        return []

    return [(expr, _roll_dice(expr)) for expr in exprs]


def _roll_dice(expr: str):
    """Parse and roll a dice expression like '2d6+4' or '2d20kh1'. Returns (total, detail_str, crit) or None."""
    expr = expr.strip()

    die_modifier_match = DICE_WITH_DIE_MODIFIER_RE.match(expr)
    if die_modifier_match:
        return _roll_with_die_modifier(die_modifier_match)

    total_modifier_match = DICE_WITH_TOTAL_MODIFIER_RE.match(expr)
    if total_modifier_match:
        return _roll_with_total_modifier(total_modifier_match)

    return None


def _roll_with_total_modifier(total_modifier_match: "re.Match[str]"):
    """Roll dice for the plain syntax (e.g. '2d6+4'), applying `modifier` once to the summed total."""
    count_str, sides_str, keep_str, modifier_str = total_modifier_match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0

    resolved = _validate(count, sides, keep_str)
    if resolved is None:
        return None
    keep_mode, keep_n, adv_dis, count = resolved

    rolls = [random.randint(1, sides) for _ in range(count)]

    kept = _select_kept(rolls, keep_mode, keep_n, key=lambda r: r)
    total = max(0, sum(kept) + modifier)

    detail = f"[{', '.join(_mark(r, sides) for r in rolls)}]"
    detail += _keep_suffix(keep_mode, keep_n, adv_dis, [_mark(r, sides) for r in kept])
    if modifier:
        sign = "+" if modifier > 0 else ""
        detail += f" {sign}{modifier}"

    crit = _natural_crit(kept, sides)

    return total, detail, crit


def _roll_with_die_modifier(die_modifier_match: "re.Match[str]"):
    """
    Roll dice for the per-die-modifier syntax (e.g. '4(d10+2)'), applying `modifier`
    to each die individually, then optionally keep/advantage-select among the
    modified values via the keep suffix (kh#, kl#, adv, dis).
    """
    count_str, sides_str, modifier_str, keep_str = die_modifier_match.groups()
    count = int(count_str)
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", ""))

    resolved = _validate(count, sides, keep_str)
    if resolved is None:
        return None
    keep_mode, keep_n, adv_dis, count = resolved

    rolls = [random.randint(1, sides) for _ in range(count)]

    sign = "+" if modifier > 0 else "-"
    modified = [max(0, r + modifier) for r in rolls]
    pairs = list(zip(rolls, modified))
    detail = f"[{', '.join(f'{_mark(r, sides)}{sign}{abs(modifier)}=**{m}**' for r, m in pairs)}]"

    kept = _select_kept(pairs, keep_mode, keep_n, key=lambda p: p[1])
    total = sum(m for _, m in kept)
    detail += _keep_suffix(keep_mode, keep_n, adv_dis, [f"**{m}**" for _, m in kept])

    crit = _natural_crit([raw for raw, _ in kept], sides)

    return total, detail, crit


def _validate(
    count: int, sides: int, keep_str: Optional[str]
) -> Optional[Tuple[Optional[str], Optional[int], Optional[str], int]]:
    """Combine `_in_bounds` and `_resolve_keep` into a single validate-or-None step."""
    if not _in_bounds(count, sides):
        return None
    return _resolve_keep(keep_str, count)


def _in_bounds(count: int, sides: int) -> bool:
    """Sanity limits so nobody rolls 999999d999999 and hangs the bot."""
    return 1 <= count <= 100 and 2 <= sides <= 1000


def _resolve_keep(
    keep_str: Optional[str], count: int
) -> Optional[Tuple[Optional[str], Optional[int], Optional[str], int]]:
    """
    Parse a keep/advantage/disadvantage suffix (kh#, kl#, adv, dis) against `count`
    dice. Returns (keep_mode, keep_n, adv_dis, count) — with `count` bumped by one
    for adv/dis — or None if there is no suffix or it resolves to an invalid keep_n.
    """
    if not keep_str:
        return None, None, None, count

    keep_str = keep_str.lower()
    if keep_str == "adv":
        keep_mode, keep_n = "h", count
        count += 1  # adv/dis roll one extra die, then drop the single worst/best
        adv_dis = "advantage"
    elif keep_str == "dis":
        keep_mode, keep_n = "l", count
        count += 1
        adv_dis = "disadvantage"
    else:
        keep_mode, keep_n = keep_str[1], int(keep_str[2:])
        adv_dis = None

    if count > 100 or keep_n < 1 or keep_n > count:
        return None

    return keep_mode, keep_n, adv_dis, count


def _select_kept(
    items: List[T],
    keep_mode: Optional[str],
    keep_n: Optional[int],
    key: Callable[[T], int],
) -> List[T]:
    """Select the highest/lowest `keep_n` items by `key`, or all items if no keep mode."""
    if keep_mode == "h":
        return sorted(items, key=key, reverse=True)[:keep_n]
    elif keep_mode == "l":
        return sorted(items, key=key)[:keep_n]
    return items


def _mark(n: int, sides: int) -> str:
    if n == sides:
        return f"{n}🎯"
    elif n == 1:
        return f"{n}💥"
    return str(n)


def _keep_suffix(
    keep_mode: Optional[str],
    keep_n: Optional[int],
    adv_dis: Optional[str],
    formatted_kept: List[str],
) -> str:
    """Build the ' with {adv_dis} → [...]' / ' keep {word} {n} → [...]' detail suffix."""
    if adv_dis:
        return f" with {adv_dis} → [{', '.join(formatted_kept)}]"
    elif keep_mode:
        word = "highest" if keep_mode == "h" else "lowest"
        return f" keep {word} {keep_n} → [{', '.join(formatted_kept)}]"
    return ""


def _natural_crit(raw_values: list, sides: int) -> Optional[str]:
    """A single kept die at its raw max/min face is a natural crit/fumble."""
    if len(raw_values) != 1:
        return None
    raw = raw_values[0]
    if raw == sides:
        return "crit"
    elif raw == 1:
        return "fumble"
    return None
