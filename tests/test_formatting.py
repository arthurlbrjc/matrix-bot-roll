"""Unit tests for the shared formatting helpers in formatting.py."""

from dataclasses import replace

from matrix_bot_roll.formatting import _mark, format_detail, markdown_to_html
from matrix_bot_roll.models import Die, DiceRollResult


def _result(**overrides) -> DiceRollResult:
    """A minimal valid DiceRollResult for a '1d6' style roll, with overridable fields."""
    base = DiceRollResult(
        total=4,
        dice=[Die(raw=4, value=4, kept=True)],
        sides=6,
        modifier=0,
        modifier_mode="total",
        keep_mode=None,
        keep_n=None,
        adv_dis=None,
        crit=None,
    )
    return replace(base, **overrides)


class TestMarkdownToHtml:
    def test_bold_is_converted(self):
        assert markdown_to_html("**bold**") == "<b>bold</b>"

    def test_code_is_converted(self):
        assert markdown_to_html("`code`") == "<code>code</code>"

    def test_crit_total_is_colored_green(self):
        output = markdown_to_html("🎲 1d6 → [6] = **6** 🎯 CRIT!")
        assert '<font color="green">6 CRIT!</font>' in output

    def test_fumble_total_is_colored_red(self):
        output = markdown_to_html("🎲 1d6 → [1] = **1** 💥 FUMBLE!")
        assert '<font color="red">1 FUMBLE!</font>' in output


class TestMark:
    def test_max_face_is_marked_with_target(self):
        assert _mark(6, 6) == "6🎯"

    def test_min_face_is_marked_with_bomb(self):
        assert _mark(1, 6) == "1💥"

    def test_other_face_is_unmarked(self):
        assert _mark(3, 6) == "3"


class TestFormatDetail:
    def test_plain_roll_has_no_modifier_suffix(self):
        assert format_detail(_result()) == "[4]"

    def test_total_modifier_is_appended(self):
        result = _result(modifier=4, modifier_mode="total")
        assert format_detail(result) == "[4] +4"

    def test_negative_total_modifier_is_appended(self):
        result = _result(modifier=-2, modifier_mode="total")
        assert format_detail(result) == "[4] -2"

    def test_keep_highest_shows_kept_dice(self):
        dice = [
            Die(raw=1, value=1, kept=False),
            Die(raw=4, value=4, kept=True),
            Die(raw=6, value=6, kept=True),
        ]
        result = _result(dice=dice, keep_mode="highest", keep_n=2)
        assert format_detail(result) == "[1💥, 4, 6🎯] keep highest 2 → [4, 6🎯]"

    def test_advantage_shows_advantage_label(self):
        dice = [
            Die(raw=15, value=15, kept=False),
            Die(raw=20, value=20, kept=True),
        ]
        result = _result(dice=dice, sides=20, adv_dis="advantage")
        assert format_detail(result) == "[15, 20🎯] with advantage → [20🎯]"

    def test_per_die_modifier_shows_computed_values(self):
        dice = [Die(raw=8, value=10, kept=True)]
        result = _result(dice=dice, modifier=2, modifier_mode="per_die")
        assert format_detail(result) == "[8+2=**10**]"
