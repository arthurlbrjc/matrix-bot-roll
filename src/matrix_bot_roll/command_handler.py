import operator
from typing import Callable, Dict, Optional

from matrix_bot_roll.commands import RollCommand
from matrix_bot_roll.dice import roll_spec
from matrix_bot_roll.models import Crit, RollResult, Target


def handle(command: RollCommand) -> RollResult:
    """Roll every dice spec in `command`, aggregate the outcomes, and evaluate its target (if any)."""
    rolls = [(expr, roll_spec(spec)) for expr, spec in command.specs]
    total = sum(result.total for _, result in rolls)
    crit = rolls[0][1].crit if len(rolls) == 1 else None
    success = (
        _evaluate_target(total, command.target, crit)
        if command.target is not None
        else None
    )
    return RollResult(
        rolls=rolls,
        message=command.message,
        total=total,
        target=command.target,
        success=success,
    )


def _evaluate_target(total: int, target: Target, crit: Optional[Crit]) -> bool:
    """
    Compare `total` against `target` using its operator.

    `crit` is the natural crit/fumble of the command's single kept die, only when
    the whole command is a single dice expression that keeps exactly one die (see
    `handle`) — e.g. plain `1d20`, but also keep-highest/advantage expressions
    like `4d6kh1` or `1d20adv`, where several dice are physically rolled but only
    one is kept. It auto-overrides ascending (`>`, `>=`) and descending (`<`,
    `<=`) operators regardless of the numeric total, but never overrides `=`
    or `!=` — those stay purely numeric comparisons.
    """
    ascending = target.operator in (">", ">=")
    descending = target.operator in ("<", "<=")
    if crit is not None and (ascending or descending):
        return crit == "crit" if ascending else crit == "fumble"
    return _COMPARATORS[target.operator](total, target.value)


_COMPARATORS: Dict[str, Callable[[int, int], bool]] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "=": operator.eq,
    "!=": operator.ne,
}
