from matrix_bot_roll.commands import RollCommand
from matrix_bot_roll.dice import roll_spec
from matrix_bot_roll.models import RollResult


def handle(command: RollCommand) -> RollResult:
    """Roll every dice spec in `command` and aggregate the outcomes into a `RollResult`."""
    rolls = [(expr, roll_spec(spec)) for expr, spec in command.specs]
    total = sum(result.total for _, result in rolls)
    return RollResult(rolls=rolls, message=command.message, total=total)
