"""Unit tests for the dice rolling logic in dice.py."""

import pytest

import dice


def fixed_rolls(monkeypatch, values):
    """Make random.randint(1, sides) return `values` in order, one call at a time."""
    queue = list(values)

    def fake_randint(a, b):
        return queue.pop(0)

    monkeypatch.setattr(dice.random, "randint", fake_randint)


def raws(result):
    """The raw face values of every rolled die, in roll order."""
    return [d.raw for d in result.dice]


def kept_raws(result):
    """The raw face values of the kept dice, in roll order."""
    return [d.raw for d in result.dice if d.kept]


class TestRollDicePlain:
    def test_simple_roll(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        result = dice._roll_dice("1d6")
        assert result.total == 4
        assert raws(result) == [4]
        assert result.crit is None

    def test_default_count_is_one(self, monkeypatch):
        fixed_rolls(monkeypatch, [5])
        result = dice._roll_dice("d8")
        assert result.total == 5
        assert result.crit is None

    def test_positive_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        result = dice._roll_dice("2d6+4")
        assert result.total == 12
        assert raws(result) == [3, 5]
        assert result.modifier == 4
        assert result.modifier_mode == "total"
        assert result.crit is None

    def test_negative_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        result = dice._roll_dice("2d6-2")
        assert result.total == 6
        assert result.modifier == -2

    def test_result_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [2])
        result = dice._roll_dice("1d4-10")
        assert result.total == 0

    def test_single_die_natural_max_is_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        result = dice._roll_dice("1d6")
        assert result.crit == "crit"

    def test_single_die_natural_min_is_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        result = dice._roll_dice("1d6")
        assert result.crit == "fumble"

    def test_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice._roll_dice("3d6kh2")
        assert result.total == 10
        assert result.keep_mode == "h"
        assert result.keep_n == 2
        assert sorted(kept_raws(result)) == [4, 6]
        assert result.crit is None

    def test_keep_lowest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice._roll_dice("3d6kl2")
        assert result.total == 5
        assert result.keep_mode == "l"
        assert sorted(kept_raws(result)) == [1, 4]

    def test_advantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 20])
        result = dice._roll_dice("1d20adv")
        assert result.total == 20
        assert result.adv_dis == "advantage"
        assert result.crit == "crit"

    def test_disadvantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 1])
        result = dice._roll_dice("1d20dis")
        assert result.total == 1
        assert result.adv_dis == "disadvantage"
        assert result.crit == "fumble"

    @pytest.mark.parametrize(
        "expr",
        [
            "abc",
            "0d6",  # count < 1
            "1d1",  # sides < 2
            "101d6",  # count > 100
            "1d1001",  # sides > 1000
            "2d20kh5",  # keep_n > count
            "2d20kh0",  # keep_n < 1
        ],
    )
    def test_invalid_expressions_return_none(self, expr):
        assert dice._roll_dice(expr) is None


class TestRollDiceGroup:
    def test_per_die_modifier_applied_individually(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 5, 9, 10])
        result = dice._roll_dice("4(d10+2)")
        assert result.total == (1 + 2) + (5 + 2) + (9 + 2) + (10 + 2)
        assert [d.value for d in result.dice] == [3, 7, 11, 12]
        assert result.crit is None  # more than one kept die

    def test_per_die_modifier_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        result = dice._roll_dice("1(d4-10)")
        assert result.total == 0

    def test_single_die_group_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        result = dice._roll_dice("1(d6+3)")
        assert result.total == 9
        assert result.crit == "crit"

    def test_single_die_group_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        result = dice._roll_dice("1(d6+3)")
        assert result.total == 4
        assert result.crit == "fumble"

    def test_group_with_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice._roll_dice("3(d6+2)kh2")
        # modified values: 3, 6, 8 -> keep highest 2 -> 8 + 6
        assert result.total == 14
        assert result.keep_mode == "h"
        assert result.keep_n == 2

    @pytest.mark.parametrize(
        "expr",
        [
            "3(d6)",  # missing mandatory modifier
            "0(d6+1)",  # count < 1
            "101(d6+1)",  # count > 100
            "2(d1+1)",  # sides < 2
            "2(d1001+1)",  # sides > 1000
        ],
    )
    def test_invalid_group_expressions_return_none(self, expr):
        assert dice._roll_dice(expr) is None


class TestRollMultiple:
    def test_empty_input(self):
        assert dice.roll("") == []
        assert dice.roll("   ") == []

    def test_multiple_expressions(self, monkeypatch):
        fixed_rolls(monkeypatch, [4, 2])
        results = dice.roll("1d6 1d4")
        assert [expr for expr, _ in results] == ["1d6", "1d4"]
        assert results[0][1].total == 4
        assert results[1][1].total == 2

    def test_mix_of_valid_and_invalid(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        results = dice.roll("1d6 abc")
        assert results[0][1] is not None
        assert results[1] == ("abc", None)
