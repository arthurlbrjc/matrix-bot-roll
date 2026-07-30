"""Unit tests for the command parsing/validation logic in commands.py."""

import pytest

from matrix_bot_roll import commands
from matrix_bot_roll.commands import ParsedRoll, RollCommand, build_command
from matrix_bot_roll.messages import INVALID_ROLL, NO_PREVIOUS_ROLL, ROLL_HELP, USAGE


def _roll(room_id, body):
    """`build_command`, returning just the `RollCommand` (dropping verbose/message) or the error string."""
    result = build_command(room_id, body)
    return result if isinstance(result, str) else result.command


class TestBuildCommandRoll:
    def test_bare_roll_returns_usage(self):
        assert build_command("!room:example.org", "!roll") == USAGE

    def test_bare_roll_with_trailing_whitespace_returns_usage(self):
        assert build_command("!room:example.org", "!roll ") == USAGE

    def test_help_flag_returns_detailed_help(self):
        assert build_command("!room:example.org", "!roll --help") == ROLL_HELP

    def test_help_flag_with_extra_whitespace_returns_detailed_help(self):
        assert build_command("!room:example.org", "!roll   --help") == ROLL_HELP

    def test_r_alias_is_equivalent(self):
        assert build_command("!room:example.org", "!r") == USAGE
        assert build_command("!room:example.org", "!r --help") == ROLL_HELP

    def test_single_expression_is_parsed(self):
        result = _roll("!room:example.org", "!roll 1d6")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6"]

    def test_multiple_expressions_are_parsed(self):
        result = _roll("!room:example.org", "!roll 1d6 1d4+2")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6", "1d4+2"]

    def test_no_target_leaves_target_none(self):
        result = _roll("!room:example.org", "!roll 1d6")
        assert isinstance(result, RollCommand)
        assert result.target is None

    def test_invalid_expression_returns_invalid_roll(self):
        assert build_command("!room:example.org", "!roll bogus") == INVALID_ROLL

    def test_mix_of_valid_and_invalid_rejects_whole_command(self):
        """One deliberate behavior change: any invalid expr rejects the whole line."""
        result = build_command("!room:example.org", "!roll 4d20 bogus 1d6")
        assert result == INVALID_ROLL

    def test_message_only_with_no_dice_expression_is_invalid(self):
        """A `| message` suffix with no dice expression at all is not a valid roll."""
        assert build_command("!room:example.org", "!roll | just a message") == (
            INVALID_ROLL
        )

    @pytest.mark.parametrize(
        "expr",
        [
            "abc",
            "0d6",  # count < 1
            "1d1",  # sides < 2
            "101d6",  # count > 100
            "1d101",  # sides > 100
            "2d20kh5",  # keep_n > count
            "2d20kh0",  # keep_n < 1
            "3(d6)",  # missing mandatory modifier
            "0(d6+1)",  # count < 1
            "101(d6+1)",  # count > 100
            "2(d1+1)",  # sides < 2
            "2(d101+1)",  # sides > 100
        ],
    )
    def test_invalid_expressions_are_rejected(self, expr):
        assert build_command("!room:example.org", f"!roll {expr}") == INVALID_ROLL

    def test_expression_is_remembered_for_reroll(self):
        room_id = "!room:example.org"
        build_command(room_id, "!roll 1d6+4")
        result = _roll(room_id, "!reroll")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6+4"]


class TestBuildCommandMessage:
    def test_message_suffix_is_extracted(self):
        parsed = build_command("!room:example.org", "!roll 1d6 | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "attack"

    def test_no_message_suffix_leaves_message_none(self):
        parsed = build_command("!room:example.org", "!roll 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message is None

    def test_target_and_message_coexist(self):
        parsed = build_command("!room:example.org", "!roll 1d6 >15 | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target is not None
        assert parsed.command.target.value == 15
        assert parsed.message == "attack"


class TestBuildCommandVerbose:
    def test_no_flag_defaults_to_terse(self):
        parsed = build_command("!room:example.org", "!roll 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False

    @pytest.mark.parametrize("flag", ["-v", "--verbose"])
    def test_flag_after_expression_sets_verbose(self, flag):
        parsed = build_command("!room:example.org", f"!roll 1d6 {flag}")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_before_expression_sets_verbose(self):
        parsed = build_command("!room:example.org", "!roll -v 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_between_target_and_expression_sets_verbose(self):
        parsed = build_command("!room:example.org", "!roll 1d6 -v >15")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.command.target is not None
        assert parsed.command.target.value == 15
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_survives_message_suffix(self):
        parsed = build_command("!room:example.org", "!roll 1d6 -v | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.message == "attack"

    def test_repeated_flag_is_harmless(self):
        parsed = build_command("!room:example.org", "!roll 1d6 -v -v")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]


class TestBuildCommandTarget:
    @pytest.mark.parametrize(
        "operator",
        [">", "<", ">=", "<=", "=", "!="],
    )
    def test_each_operator_is_parsed(self, operator):
        result = _roll("!room:example.org", f"!roll 1d6 {operator}15")
        assert isinstance(result, RollCommand)
        assert result.target is not None
        assert result.target.operator == operator
        assert result.target.value == 15

    def test_target_applies_to_whole_line_not_per_expression(self):
        result = _roll("!room:example.org", "!roll 1d6 1d4 >15")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6", "1d4"]
        assert result.target is not None
        assert result.target.value == 15

    def test_negative_target_value_is_parsed(self):
        result = _roll("!room:example.org", "!roll 1d20 >-5")
        assert isinstance(result, RollCommand)
        assert result.target is not None
        assert result.target.operator == ">"
        assert result.target.value == -5

    def test_negative_target_value_is_parsed_for_not_equal(self):
        result = _roll("!room:example.org", "!roll 1d20 !=-5")
        assert isinstance(result, RollCommand)
        assert result.target is not None
        assert result.target.operator == "!="
        assert result.target.value == -5

    @pytest.mark.parametrize(
        "bad_target",
        [
            ">",  # operator with no value
            ">=",
            "><15",  # not a real operator
            "15",  # bare number, not a comparison
            ">abc",  # non-numeric target
        ],
    )
    def test_malformed_target_rejects_whole_command(self, bad_target):
        result = build_command("!room:example.org", f"!roll 1d6 {bad_target}")
        assert result == INVALID_ROLL

    def test_target_with_no_dice_expression_rejects_whole_command(self):
        result = build_command("!room:example.org", "!roll >15")
        assert result == INVALID_ROLL

    def test_duplicate_target_rejects_whole_command(self):
        result = build_command("!room:example.org", "!roll 1d6 >5 >10")
        assert result == INVALID_ROLL


class TestBuildCommandReroll:
    def test_no_previous_roll_returns_message(self):
        assert build_command("!empty-room:example.org", "!reroll") == NO_PREVIOUS_ROLL

    def test_rr_alias_is_equivalent(self):
        assert build_command("!empty-room2:example.org", "!rr") == NO_PREVIOUS_ROLL

    def test_repeats_last_roll_expression(self):
        room_id = "!other-room:example.org"
        build_command(room_id, "!roll 1d6")
        result = _roll(room_id, "!rr")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6"]


class TestParseExpr:
    def test_default_count_is_one(self):
        spec = commands._parse_expr("d8")
        assert spec is not None
        assert spec.count == 1
        assert spec.sides == 8

    def test_advantage_bumps_count_by_one(self):
        spec = commands._parse_expr("1d20adv")
        assert spec is not None
        assert spec.count == 2
        assert spec.keep_mode == "highest"
        assert spec.keep_n == 1
        assert spec.adv_dis == "advantage"

    def test_disadvantage_bumps_count_by_one(self):
        spec = commands._parse_expr("1d20dis")
        assert spec is not None
        assert spec.count == 2
        assert spec.keep_mode == "lowest"
        assert spec.keep_n == 1
        assert spec.adv_dis == "disadvantage"

    def test_advantage_at_max_count_allows_one_extra_die(self):
        """adv/dis are allowed to exceed MAX_DICE_COUNT by one die, by design."""
        spec = commands._parse_expr("100d6adv")
        assert spec is not None
        assert spec.count == 101

    def test_die_modifier_syntax(self):
        spec = commands._parse_expr("4(d10+2)")
        assert spec is not None
        assert spec.count == 4
        assert spec.sides == 10
        assert spec.modifier == 2
        assert spec.modifier_mode == "per_die"

    def test_invalid_expression_returns_none(self):
        assert commands._parse_expr("abc") is None
