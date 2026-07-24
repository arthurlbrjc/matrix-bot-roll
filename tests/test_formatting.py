"""Unit tests for the result formatting logic in formatting.py."""

from models import Die, RollResult

from formatting import format_roll_results


def _result(total: int = 4) -> RollResult:
    """A minimal valid RollResult for a '1d6' style roll."""
    return RollResult(
        total=total,
        dice=[Die(raw=total, value=total, kept=True)],
        sides=6,
        modifier=0,
        modifier_mode=None,
        keep_mode=None,
        keep_n=None,
        adv_dis=None,
        crit=None,
    )


class TestFormatRollResultsMessage:
    def test_no_message_by_default(self):
        output = format_roll_results([("1d6", _result())])
        assert "💬" not in output

    def test_message_is_appended(self):
        output = format_roll_results([("1d6", _result())], "attack")
        assert output.endswith("💬 attack")

    def test_empty_message_is_omitted(self):
        output = format_roll_results([("1d6", _result())], "")
        assert "💬" not in output

    def test_message_with_special_characters(self):
        output = format_roll_results(
            [("1d6", _result())], "attack <vs> AC 15 & *sneak*"
        )
        assert output.endswith("💬 attack <vs> AC 15 & *sneak*")

    def test_message_shown_even_for_invalid_expression(self):
        output = format_roll_results([("abc", None)], "attack")
        assert "invalid expression" in output
        assert output.endswith("💬 attack")
