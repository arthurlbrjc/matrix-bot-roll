import random
import re
from typing import Callable, List, Optional, Set, Tuple

from constants import DICE_WITH_DIE_MODIFIER_RE, DICE_WITH_TOTAL_MODIFIER_RE
from models import Die, RollResult
from typevars import T


def roll(input_str: str) -> List[Tuple[str, Optional[RollResult]]]:
    """
    Parse and roll multiple space-separated dice expressions, e.g. '4d20 1d6+2'.

    Returns a list of (expr, result) tuples, where result is a RollResult, or
    None if expr is not a valid dice expression.
    """
    exprs = input_str.split()
    if not exprs:
        return []

    return [(expr, _roll_dice(expr)) for expr in exprs]


def _roll_dice(expr: str) -> Optional[RollResult]:
    """Parse and roll a dice expression like '2d6+4' or '2d20kh1'."""
    expr = expr.strip()

    die_modifier_match = DICE_WITH_DIE_MODIFIER_RE.match(expr)
    if die_modifier_match:
        return _roll_with_die_modifier(die_modifier_match)

    total_modifier_match = DICE_WITH_TOTAL_MODIFIER_RE.match(expr)
    if total_modifier_match:
        return _roll_with_total_modifier(total_modifier_match)

    return None


def _roll_with_total_modifier(
    total_modifier_match: "re.Match[str]",
) -> Optional[RollResult]:
    """Roll dice for the plain syntax (e.g. '2d6+4'), applying `modifier` once to the summed total."""
    count_str, sides_str, keep_str, modifier_str = total_modifier_match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0

    resolved = _validate(count, sides, keep_str)
    if resolved is None:
        return None
    keep_mode, keep_n, adv_dis, count = resolved

    raws = [random.randint(1, sides) for _ in range(count)]
    kept_indices = _select_kept_indices(raws, keep_mode, keep_n, key=lambda r: r)
    dice = [Die(raw=r, value=r, kept=i in kept_indices) for i, r in enumerate(raws)]

    kept_raws = [raws[i] for i in kept_indices]
    total = max(0, sum(kept_raws) + modifier)

    crit = _natural_crit(kept_raws, sides)

    return RollResult(
        total=total,
        dice=dice,
        sides=sides,
        modifier=modifier,
        modifier_mode="total" if modifier else None,
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
        crit=crit,
    )


def _roll_with_die_modifier(
    die_modifier_match: "re.Match[str]",
) -> Optional[RollResult]:
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

    raws = [random.randint(1, sides) for _ in range(count)]
    values = [max(0, r + modifier) for r in raws]
    kept_indices = _select_kept_indices(values, keep_mode, keep_n, key=lambda v: v)
    dice = [
        Die(raw=r, value=v, kept=i in kept_indices)
        for i, (r, v) in enumerate(zip(raws, values))
    ]

    kept_raws = [raws[i] for i in kept_indices]
    total = sum(values[i] for i in kept_indices)

    crit = _natural_crit(kept_raws, sides)

    return RollResult(
        total=total,
        dice=dice,
        sides=sides,
        modifier=modifier,
        modifier_mode="per_die",
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
        crit=crit,
    )


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


def _select_kept_indices(
    items: List[T],
    keep_mode: Optional[str],
    keep_n: Optional[int],
    key: Callable[[T], int],
) -> Set[int]:
    """Indices of the highest/lowest `keep_n` items by `key`, or all indices if no keep mode."""
    if keep_mode is None:
        return set(range(len(items)))

    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: key(pair[1]), reverse=(keep_mode == "h"))
    return {i for i, _ in indexed[:keep_n]}


def _natural_crit(kept_raws: List[int], sides: int) -> Optional[str]:
    """A single kept die at its raw max/min face is a natural crit/fumble."""
    if len(kept_raws) != 1:
        return None
    raw = kept_raws[0]
    if raw == sides:
        return "crit"
    elif raw == 1:
        return "fumble"
    return None
