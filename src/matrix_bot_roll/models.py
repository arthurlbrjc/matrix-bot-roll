from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

ModifierMode = Literal["total", "per_die"]
KeepMode = Literal["highest", "lowest"]
AdvDis = Literal["advantage", "disadvantage"]
Crit = Literal["crit", "fumble"]
TargetOperator = Literal[">", "<", ">=", "<=", "=", "!="]


@dataclass
class Die:
    """A single rolled die: its raw face, its value after any per-die modifier, and whether it was kept."""

    raw: int
    value: int
    kept: bool


@dataclass
class DiceRollResult:
    """The outcome of rolling one dice expression, free of any display formatting."""

    total: int
    dice: List[Die]
    sides: int
    modifier: int
    modifier_mode: ModifierMode
    keep_mode: Optional[KeepMode]
    keep_n: Optional[int]
    adv_dis: Optional[AdvDis]
    crit: Optional[Crit]


@dataclass
class DiceSpec:
    """A validated, fully resolved pre-roll request for one dice expression."""

    count: int
    sides: int
    modifier: int
    modifier_mode: ModifierMode
    keep_mode: Optional[KeepMode]
    keep_n: Optional[int]
    adv_dis: Optional[AdvDis]


@dataclass
class Target:
    """A target-number comparison (e.g. '>15') applied to a `RollCommand`'s aggregate total."""

    operator: TargetOperator
    value: int


@dataclass
class RollResult:
    """The aggregate outcome of rolling every expression in a `!roll` command — the rolling domain only, with no display concerns."""

    rolls: List[Tuple[str, DiceRollResult]]
    total: int
    target: Optional[Target]
    success: Optional[bool]
