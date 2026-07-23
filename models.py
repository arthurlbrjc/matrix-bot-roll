from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Die:
    """A single rolled die: its raw face, its value after any per-die modifier, and whether it was kept."""

    raw: int
    value: int
    kept: bool


@dataclass
class RollResult:
    """The outcome of rolling one dice expression, free of any display formatting."""

    total: int
    dice: List[Die]
    sides: int
    modifier: int
    modifier_mode: Optional[str]  # "total", "per_die", or None
    keep_mode: Optional[str]  # "h", "l", or None
    keep_n: Optional[int]
    adv_dis: Optional[str]  # "advantage", "disadvantage", or None
    crit: Optional[str]  # "crit", "fumble", or None
