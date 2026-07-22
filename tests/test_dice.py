"""Unit tests for the dice rolling logic in dice.py."""

import pytest

import dice


def fixed_rolls(monkeypatch, values):
    """Make random.randint(1, sides) return `values` in order, one call at a time."""
    queue = list(values)

    def fake_randint(a, b):
        return queue.pop(0)

    monkeypatch.setattr(dice.random, "randint", fake_randint)


class TestRollDicePlain:
    def test_simple_roll(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        total, detail, crit = dice.roll_dice("1d6")
        assert total == 4
        assert detail == "[4]"
        assert crit is None

    def test_default_count_is_one(self, monkeypatch):
        fixed_rolls(monkeypatch, [5])
        total, detail, crit = dice.roll_dice("d8")
        assert total == 5
        assert crit is None

    def test_positive_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        total, detail, crit = dice.roll_dice("2d6+4")
        assert total == 12
        assert "[3, 5]" in detail
        assert "+4" in detail
        assert crit is None

    def test_negative_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        total, detail, crit = dice.roll_dice("2d6-2")
        assert total == 6
        assert "-2" in detail

    def test_result_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [2])
        total, detail, crit = dice.roll_dice("1d4-10")
        assert total == 0

    def test_single_die_natural_max_is_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        total, detail, crit = dice.roll_dice("1d6")
        assert crit == "crit"
        assert "🎯" in detail

    def test_single_die_natural_min_is_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        total, detail, crit = dice.roll_dice("1d6")
        assert crit == "fumble"
        assert "💥" in detail

    def test_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        total, detail, crit = dice.roll_dice("3d6kh2")
        assert total == 10
        assert "keep highest 2" in detail
        assert crit is None

    def test_keep_lowest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        total, detail, crit = dice.roll_dice("3d6kl2")
        assert total == 5
        assert "keep lowest 2" in detail

    def test_advantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 20])
        total, detail, crit = dice.roll_dice("1d20adv")
        assert total == 20
        assert "with advantage" in detail
        assert crit == "crit"

    def test_disadvantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 1])
        total, detail, crit = dice.roll_dice("1d20dis")
        assert total == 1
        assert "with disadvantage" in detail
        assert crit == "fumble"

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
        assert dice.roll_dice(expr) is None


class TestRollDiceGroup:
    def test_per_die_modifier_applied_individually(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 5, 9, 10])
        total, detail, crit = dice.roll_dice("4(d10+2)")
        assert total == (1 + 2) + (5 + 2) + (9 + 2) + (10 + 2)
        assert "🎯" in detail  # the 10 (max face) is marked
        assert "💥" in detail  # the 1 (min face) is marked
        assert crit is None  # more than one kept die

    def test_per_die_modifier_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        total, detail, crit = dice.roll_dice("1(d4-10)")
        assert total == 0

    def test_single_die_group_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        total, detail, crit = dice.roll_dice("1(d6+3)")
        assert total == 9
        assert crit == "crit"

    def test_single_die_group_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        total, detail, crit = dice.roll_dice("1(d6+3)")
        assert total == 4
        assert crit == "fumble"

    def test_group_with_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        total, detail, crit = dice.roll_dice("3(d6+2)kh2")
        # modified values: 3, 6, 8 -> keep highest 2 -> 8 + 6
        assert total == 14
        assert "keep highest 2" in detail

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
        assert dice.roll_dice(expr) is None


class TestRollMultiple:
    def test_empty_input(self):
        assert dice.roll_multiple("") == []
        assert dice.roll_multiple("   ") == []

    def test_multiple_expressions(self, monkeypatch):
        fixed_rolls(monkeypatch, [4, 2])
        results = dice.roll_multiple("1d6 1d4")
        assert [expr for expr, _ in results] == ["1d6", "1d4"]
        assert results[0][1][0] == 4
        assert results[1][1][0] == 2

    def test_mix_of_valid_and_invalid(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        results = dice.roll_multiple("1d6 abc")
        assert results[0][1] is not None
        assert results[1] == ("abc", None)
