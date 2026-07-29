from matrix_bot_roll.commands import RollCommand
from matrix_bot_roll.dice import roll_spec
from matrix_bot_roll.models import RollResult, Target


def handle(command: RollCommand) -> RollResult:
    """Roll every dice spec in `command`, aggregate the outcomes, and evaluate its target (if any)."""
    rolls = [(expr, roll_spec(spec)) for expr, spec in command.specs]
    total = sum(result.total for _, result in rolls)
    success = (
        _evaluate_target(total, command.target) if command.target is not None else None
    )
    return RollResult(
        rolls=rolls,
        message=command.message,
        total=total,
        target=command.target,
        success=success,
    )


def _evaluate_target(total: int, target: Target) -> bool:
    """Compare `total` against `target` using its operator."""
    if target.operator == ">":
        return total > target.value
    elif target.operator == "<":
        return total < target.value
    elif target.operator == ">=":
        return total >= target.value
    elif target.operator == "<=":
        return total <= target.value
    return total == target.value
