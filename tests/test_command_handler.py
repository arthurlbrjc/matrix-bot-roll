"""Unit tests for the roll orchestration logic in command_handler.py."""

from matrix_bot_roll import command_handler, dice
from matrix_bot_roll.commands import RollCommand
from matrix_bot_roll.models import DiceSpec


def fixed_rolls(monkeypatch, values):
    """Make random.randint(1, sides) return `values` in order, one call at a time."""
    queue = list(values)

    def fake_randint(a, b):
        return queue.pop(0)

    monkeypatch.setattr(dice.random, "randint", fake_randint)


def total_spec(count=1, sides=6, modifier=0, modifier_mode="total"):
    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode=modifier_mode,
        keep_mode=None,
        keep_n=None,
        adv_dis=None,
    )


class TestHandle:
    def test_single_roll_result(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        command = RollCommand(specs=[("1d6", total_spec())], message=None)
        result = command_handler.handle(command)
        assert [expr for expr, _ in result.rolls] == ["1d6"]
        assert result.total == 4
        assert result.message is None

    def test_total_sums_every_roll(self, monkeypatch):
        fixed_rolls(monkeypatch, [4, 2])
        command = RollCommand(
            specs=[("1d6", total_spec()), ("1d4", total_spec(sides=4))],
            message=None,
        )
        result = command_handler.handle(command)
        assert result.total == 6

    def test_message_is_passed_through(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        command = RollCommand(specs=[("1d6", total_spec())], message="attack")
        result = command_handler.handle(command)
        assert result.message == "attack"

    def test_empty_specs_yields_zero_total(self):
        command = RollCommand(specs=[], message="just a message")
        result = command_handler.handle(command)
        assert result.rolls == []
        assert result.total == 0
