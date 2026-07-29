"""Unit tests for the roll orchestration logic in command_handler.py."""

from matrix_bot_roll import command_handler, dice
from matrix_bot_roll.commands import RollCommand
from matrix_bot_roll.models import DiceSpec, Target


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
        command = RollCommand(specs=[("1d6", total_spec())], message=None, target=None)
        result = command_handler.handle(command)
        assert [expr for expr, _ in result.rolls] == ["1d6"]
        assert result.total == 4
        assert result.message is None

    def test_total_sums_every_roll(self, monkeypatch):
        fixed_rolls(monkeypatch, [4, 2])
        command = RollCommand(
            specs=[("1d6", total_spec()), ("1d4", total_spec(sides=4))],
            message=None,
            target=None,
        )
        result = command_handler.handle(command)
        assert result.total == 6

    def test_message_is_passed_through(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        command = RollCommand(
            specs=[("1d6", total_spec())], message="attack", target=None
        )
        result = command_handler.handle(command)
        assert result.message == "attack"

    def test_empty_specs_yields_zero_total(self):
        command = RollCommand(specs=[], message="just a message", target=None)
        result = command_handler.handle(command)
        assert result.rolls == []
        assert result.total == 0

    def test_no_target_leaves_success_none(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        command = RollCommand(specs=[("1d6", total_spec())], message=None, target=None)
        result = command_handler.handle(command)
        assert result.target is None
        assert result.success is None


class TestHandleTarget:
    def test_greater_than_success(self, monkeypatch):
        fixed_rolls(monkeypatch, [5])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator=">", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_greater_than_failure(self, monkeypatch):
        fixed_rolls(monkeypatch, [2])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator=">", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is False

    def test_less_than(self, monkeypatch):
        fixed_rolls(monkeypatch, [2])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator="<", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_greater_than_or_equal(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator=">=", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_less_than_or_equal(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator="<=", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_equal(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator="=", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_target_applies_to_summed_total(self, monkeypatch):
        fixed_rolls(monkeypatch, [4, 2])
        command = RollCommand(
            specs=[("1d6", total_spec()), ("1d4", total_spec(sides=4))],
            message=None,
            target=Target(operator=">=", value=6),
        )
        result = command_handler.handle(command)
        assert result.total == 6
        assert result.success is True
