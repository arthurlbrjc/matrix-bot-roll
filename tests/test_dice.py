"""Unit tests for the dice rolling logic in dice.py."""

from matrix_bot_roll import dice
from matrix_bot_roll.models import DiceSpec


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


def total_spec(
    count=1,
    sides=6,
    modifier=0,
    modifier_mode="total",
    keep_mode=None,
    keep_n=None,
    adv_dis=None,
):
    """A `DiceSpec` for the plain/total-modifier syntax (e.g. '2d6+4')."""
    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode=modifier_mode,
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
    )


def die_modifier_spec(
    count,
    sides,
    modifier,
    keep_mode=None,
    keep_n=None,
    adv_dis=None,
):
    """A `DiceSpec` for the per-die-modifier syntax (e.g. '4(d10+2)')."""
    return DiceSpec(
        count=count,
        sides=sides,
        modifier=modifier,
        modifier_mode="per_die",
        keep_mode=keep_mode,
        keep_n=keep_n,
        adv_dis=adv_dis,
    )


class TestRollSpecTotalModifier:
    def test_simple_roll(self, monkeypatch):
        fixed_rolls(monkeypatch, [4])
        result = dice.roll_spec(total_spec(count=1, sides=6))
        assert result.total == 4
        assert raws(result) == [4]
        assert result.crit is None

    def test_positive_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        result = dice.roll_spec(
            total_spec(count=2, sides=6, modifier=4, modifier_mode="total")
        )
        assert result.total == 12
        assert raws(result) == [3, 5]
        assert result.modifier == 4
        assert result.modifier_mode == "total"
        assert result.crit is None

    def test_negative_modifier(self, monkeypatch):
        fixed_rolls(monkeypatch, [3, 5])
        result = dice.roll_spec(
            total_spec(count=2, sides=6, modifier=-2, modifier_mode="total")
        )
        assert result.total == 6
        assert result.modifier == -2

    def test_result_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [2])
        result = dice.roll_spec(
            total_spec(count=1, sides=4, modifier=-10, modifier_mode="total")
        )
        assert result.total == 0

    def test_single_die_natural_max_is_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        result = dice.roll_spec(total_spec(count=1, sides=6))
        assert result.crit == "crit"

    def test_single_die_natural_min_is_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        result = dice.roll_spec(total_spec(count=1, sides=6))
        assert result.crit == "fumble"

    def test_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice.roll_spec(
            total_spec(count=3, sides=6, keep_mode="highest", keep_n=2)
        )
        assert result.total == 10
        assert result.keep_mode == "highest"
        assert result.keep_n == 2
        assert sorted(kept_raws(result)) == [4, 6]
        assert result.crit is None

    def test_keep_lowest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice.roll_spec(
            total_spec(count=3, sides=6, keep_mode="lowest", keep_n=2)
        )
        assert result.total == 5
        assert result.keep_mode == "lowest"
        assert sorted(kept_raws(result)) == [1, 4]

    def test_advantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 20])
        result = dice.roll_spec(
            total_spec(
                count=2, sides=20, keep_mode="highest", keep_n=1, adv_dis="advantage"
            )
        )
        assert result.total == 20
        assert result.adv_dis == "advantage"
        assert result.crit == "crit"

    def test_disadvantage(self, monkeypatch):
        fixed_rolls(monkeypatch, [15, 1])
        result = dice.roll_spec(
            total_spec(
                count=2, sides=20, keep_mode="lowest", keep_n=1, adv_dis="disadvantage"
            )
        )
        assert result.total == 1
        assert result.adv_dis == "disadvantage"
        assert result.crit == "fumble"

    def test_advantage_at_max_count_allows_one_extra_die(self, monkeypatch):
        """adv/dis are allowed to exceed MAX_DICE_COUNT by one die, by design."""
        fixed_rolls(monkeypatch, [3] * 101)
        result = dice.roll_spec(
            total_spec(
                count=101, sides=6, keep_mode="highest", keep_n=100, adv_dis="advantage"
            )
        )
        assert len(result.dice) == 101


class TestRollSpecDieModifier:
    def test_per_die_modifier_applied_individually(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 5, 9, 10])
        result = dice.roll_spec(die_modifier_spec(4, 10, 2))
        assert result.total == (1 + 2) + (5 + 2) + (9 + 2) + (10 + 2)
        assert [d.value for d in result.dice] == [3, 7, 11, 12]
        assert result.crit is None  # more than one kept die

    def test_per_die_modifier_clamped_to_zero(self, monkeypatch):
        fixed_rolls(monkeypatch, [3])
        result = dice.roll_spec(die_modifier_spec(1, 4, -10))
        assert result.total == 0

    def test_single_die_group_crit(self, monkeypatch):
        fixed_rolls(monkeypatch, [6])
        result = dice.roll_spec(die_modifier_spec(1, 6, 3))
        assert result.total == 9
        assert result.crit == "crit"

    def test_single_die_group_fumble(self, monkeypatch):
        fixed_rolls(monkeypatch, [1])
        result = dice.roll_spec(die_modifier_spec(1, 6, 3))
        assert result.total == 4
        assert result.crit == "fumble"

    def test_group_with_keep_highest(self, monkeypatch):
        fixed_rolls(monkeypatch, [1, 4, 6])
        result = dice.roll_spec(
            die_modifier_spec(3, 6, 2, keep_mode="highest", keep_n=2)
        )
        # modified values: 3, 6, 8 -> keep highest 2 -> 8 + 6
        assert result.total == 14
        assert result.keep_mode == "highest"
        assert result.keep_n == 2
