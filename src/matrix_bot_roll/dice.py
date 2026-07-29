import random
from typing import Callable, List, Optional, Set, Tuple

from matrix_bot_roll.models import Crit, Die, DiceRollResult, DiceSpec, KeepMode
from matrix_bot_roll.typevars import T


def roll_spec(spec: DiceSpec) -> DiceRollResult:
    """Roll dice for an already-validated `DiceSpec`, dispatching on its modifier mode."""
    if spec.modifier_mode == "per_die":
        dice, kept_raws, total = _roll_with_die_modifier(spec)
    else:
        dice, kept_raws, total = _roll_with_total_modifier(spec)

    return DiceRollResult(
        total=total,
        dice=dice,
        sides=spec.sides,
        modifier=spec.modifier,
        modifier_mode=spec.modifier_mode,
        keep_mode=spec.keep_mode,
        keep_n=spec.keep_n,
        adv_dis=spec.adv_dis,
        crit=_natural_crit(kept_raws, spec.sides),
    )


def _roll_with_total_modifier(spec: DiceSpec) -> Tuple[List[Die], List[int], int]:
    """
    Roll dice for the plain syntax (e.g. '2d6+4'), applying `spec.modifier` once to the
    summed total. Returns (dice, kept raw faces, total).
    """
    raws = [random.randint(1, spec.sides) for _ in range(spec.count)]
    kept_indices = _select_kept_indices(
        raws, spec.keep_mode, spec.keep_n, key=lambda r: r
    )
    dice = [Die(raw=r, value=r, kept=i in kept_indices) for i, r in enumerate(raws)]

    kept_raws = [raws[i] for i in kept_indices]
    total = max(0, sum(kept_raws) + spec.modifier)

    return dice, kept_raws, total


def _roll_with_die_modifier(spec: DiceSpec) -> Tuple[List[Die], List[int], int]:
    """
    Roll dice for the per-die-modifier syntax (e.g. '4(d10+2)'), applying `spec.modifier`
    to each die individually, then optionally keep/advantage-select among the modified
    values via `spec.keep_mode`/`spec.keep_n`. Returns (dice, kept raw faces, total).
    """
    raws = [random.randint(1, spec.sides) for _ in range(spec.count)]
    values = [max(0, r + spec.modifier) for r in raws]
    kept_indices = _select_kept_indices(
        values, spec.keep_mode, spec.keep_n, key=lambda v: v
    )
    dice = [
        Die(raw=r, value=v, kept=i in kept_indices)
        for i, (r, v) in enumerate(zip(raws, values))
    ]

    kept_raws = [raws[i] for i in kept_indices]
    total = sum(values[i] for i in kept_indices)

    return dice, kept_raws, total


def _select_kept_indices(
    items: List[T],
    keep_mode: Optional[KeepMode],
    keep_n: Optional[int],
    key: Callable[[T], int],
) -> Set[int]:
    """Indices of the highest/lowest `keep_n` items by `key`, or all indices if no keep mode."""
    if keep_mode is None:
        return set(range(len(items)))

    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: key(pair[1]), reverse=(keep_mode == "highest"))
    return {i for i, _ in indexed[:keep_n]}


def _natural_crit(kept_raws: List[int], sides: int) -> Optional[Crit]:
    """A single kept die at its raw max/min face is a natural crit/fumble."""
    if len(kept_raws) != 1:
        return None
    raw = kept_raws[0]
    if raw == sides:
        return "crit"
    elif raw == 1:
        return "fumble"
    return None
