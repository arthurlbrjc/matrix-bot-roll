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


def total_spec(
    count=1,
    sides=6,
    modifier=0,
    modifier_mode="total",
    keep_mode=None,
    keep_n=None,
    adv_dis=None,
):
    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode=modifier_mode,
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
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

    def test_not_equal(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator="!=", value=4),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_not_equal_fails_when_equal(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        command = RollCommand(
            specs=[("1d6", total_spec())],
            message=None,
            target=Target(operator="!=", value=3),
        )
        result = command_handler.handle(command)
        assert result.success is False

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


class TestHandleTargetCritFumbleOverride:
    def test_nat_crit_auto_succeeds_ascending_gt(self, monkeypatch):
        fixed_rolls(monkeypatch, [20])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator=">", value=100),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_nat_crit_auto_succeeds_ascending_gte(self, monkeypatch):
        fixed_rolls(monkeypatch, [20])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator=">=", value=100),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_nat_fumble_auto_fails_ascending_despite_passing_total(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20, modifier=12))],
            message=None,
            target=Target(operator=">", value=10),
        )
        result = command_handler.handle(command)
        assert result.total == 13
        assert result.success is False

    def test_nat_fumble_auto_succeeds_descending_lt(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="<", value=-100),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_nat_fumble_auto_succeeds_descending_lte(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="<=", value=-100),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_nat_crit_auto_fails_descending_despite_passing_total(self, monkeypatch):
        fixed_rolls(monkeypatch, [100])
        command = RollCommand(
            specs=[("1d100", total_spec(sides=100, modifier=-50))],
            message=None,
            target=Target(operator="<=", value=30),
        )
        result = command_handler.handle(command)
        assert result.total == 50
        assert result.success is False

    def test_equal_operator_ignores_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [20])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="=", value=20),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_equal_operator_ignores_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="=", value=1),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_not_equal_operator_ignores_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [20])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="!=", value=1),
        )
        result = command_handler.handle(command)
        assert result.success is True

    def test_not_equal_operator_ignores_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        command = RollCommand(
            specs=[("1d20", total_spec(sides=20))],
            message=None,
            target=Target(operator="!=", value=1),
        )
        result = command_handler.handle(command)
        assert result.success is False

    def test_multi_expression_crit_does_not_override_combined_target(self, monkeypatch):
        fixed_rolls(monkeypatch, [20, 6, 6])
        command = RollCommand(
            specs=[
                ("1d20", total_spec(sides=20)),
                ("2d6", total_spec(count=2, sides=6)),
            ],
            message=None,
            target=Target(operator=">", value=100),
        )
        result = command_handler.handle(command)
        assert result.total == 32
        assert result.success is False

    def test_nat_crit_on_kept_die_overrides_despite_low_total(self, monkeypatch):
        """A single-expression keep-highest-1-of-4 roll still overrides on its kept die."""
        fixed_rolls(monkeypatch, [6, 3, 2, 1])
        command = RollCommand(
            specs=[
                (
                    "4d6kh1",
                    total_spec(count=4, sides=6, keep_mode="highest", keep_n=1),
                )
            ],
            message=None,
            target=Target(operator=">", value=100),
        )
        result = command_handler.handle(command)
        assert result.total == 6
        assert result.success is True

    def test_nat_fumble_on_kept_die_overrides_despite_passing_total(self, monkeypatch):
        """A single-expression keep-highest-1-of-4 roll still overrides on its kept die."""
        fixed_rolls(monkeypatch, [1, 1, 1, 1])
        command = RollCommand(
            specs=[
                (
                    "4d6kh1",
                    total_spec(
                        count=4,
                        sides=6,
                        modifier=12,
                        keep_mode="highest",
                        keep_n=1,
                    ),
                )
            ],
            message=None,
            target=Target(operator=">", value=10),
        )
        result = command_handler.handle(command)
        assert result.total == 13
        assert result.success is False

    def test_nat_crit_on_advantage_roll_overrides(self, monkeypatch):
        """A single-expression advantage roll (2 dice, 1 kept) still overrides on its kept die."""
        fixed_rolls(monkeypatch, [3, 20])
        command = RollCommand(
            specs=[
                (
                    "1d20adv",
                    total_spec(
                        count=2,
                        sides=20,
                        keep_mode="highest",
                        keep_n=1,
                        adv_dis="advantage",
                    ),
                )
            ],
            message=None,
            target=Target(operator=">", value=100),
        )
        result = command_handler.handle(command)
        assert result.total == 20
        assert result.success is True
