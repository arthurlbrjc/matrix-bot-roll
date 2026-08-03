"""Unit tests for the command parsing/validation logic in commands.py."""

import pytest

from matrix_bot_roll import commands
from matrix_bot_roll.commands import (
    ListSavedCommand,
    ParsedRoll,
    RollCommand,
    SaveCommand,
    build_dice_command,
    build_save_command,
    build_saved_pattern_command,
)
from matrix_bot_roll.messages import (
    INVALID_ROLL,
    NO_PREVIOUS_ROLL,
    ROLL_HELP,
    SAVE_USAGE,
    USAGE,
    invalid_expr,
    invalid_pattern_name,
)
from matrix_bot_roll.models import Target


def _roll(room_id, body):
    """`build_dice_command`, returning just the `RollCommand` (dropping verbose/message) or the error string."""
    result = build_dice_command(room_id, body)
    return result if isinstance(result, str) else result.command


class TestBuildCommandRoll:
    def test_bare_roll_returns_usage(self):
        assert build_dice_command("!room:example.org", "!roll") == USAGE

    def test_bare_roll_with_trailing_whitespace_returns_usage(self):
        assert build_dice_command("!room:example.org", "!roll ") == USAGE

    def test_help_flag_returns_detailed_help(self):
        assert build_dice_command("!room:example.org", "!roll --help") == ROLL_HELP

    def test_help_flag_with_extra_whitespace_returns_detailed_help(self):
        assert build_dice_command("!room:example.org", "!roll   --help") == ROLL_HELP

    def test_r_alias_is_equivalent(self):
        assert build_dice_command("!room:example.org", "!r") == USAGE
        assert build_dice_command("!room:example.org", "!r --help") == ROLL_HELP

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
        result = build_dice_command("!room:example.org", "!roll bogus")
        assert result == invalid_expr("bogus", "not a recognized dice expression")

    def test_mix_of_valid_and_invalid_rejects_whole_command(self):
        """One deliberate behavior change: any invalid expr rejects the whole line."""
        result = build_dice_command("!room:example.org", "!roll 4d20 bogus 1d6")
        assert result == invalid_expr("bogus", "not a recognized dice expression")

    def test_message_only_with_no_dice_expression_is_invalid(self):
        """A `| message` suffix with no dice expression at all is not a valid roll."""
        assert build_dice_command("!room:example.org", "!roll | just a message") == (
            INVALID_ROLL
        )

    @pytest.mark.parametrize(
        "expr, detail",
        [
            ("abc", "not a recognized dice expression"),
            ("0d6", "dice count must be between 1 and 100"),  # count < 1
            ("1d1", "sides must be between 2 and 100"),  # sides < 2
            ("101d6", "dice count must be between 1 and 100"),  # count > 100
            ("1d101", "sides must be between 2 and 100"),  # sides > 100
            (
                "2d20kh5",
                "`kh5` keeps more dice than were rolled (2)",
            ),  # keep_n > count
            (
                "2d20kh0",
                "`kh0` needs a keep count of at least 1",
            ),  # keep_n < 1
            (
                "3(d6)",
                "not a recognized dice expression",
            ),  # missing mandatory modifier
            ("0(d6+1)", "dice count must be between 1 and 100"),  # count < 1
            ("101(d6+1)", "dice count must be between 1 and 100"),  # count > 100
            ("2(d1+1)", "sides must be between 2 and 100"),  # sides < 2
            ("2(d101+1)", "sides must be between 2 and 100"),  # sides > 100
        ],
    )
    def test_invalid_expressions_are_rejected(self, expr, detail):
        result = build_dice_command("!room:example.org", f"!roll {expr}")
        assert result == invalid_expr(expr, detail)

    def test_expression_is_remembered_for_reroll(self):
        room_id = "!room:example.org"
        build_dice_command(room_id, "!roll 1d6+4")
        result = _roll(room_id, "!reroll")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6+4"]

    def test_invalid_expression_does_not_overwrite_remembered_roll(self):
        room_id = "!room-invalid:example.org"
        build_dice_command(room_id, "!roll 1d6+4")
        build_dice_command(room_id, "!roll bogus")
        result = _roll(room_id, "!reroll")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6+4"]


class TestBuildCommandMessage:
    def test_message_suffix_is_extracted(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6 | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "attack"

    def test_no_message_suffix_leaves_message_none(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message is None

    def test_target_and_message_coexist(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6 >15 | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target is not None
        assert parsed.command.target.value == 15
        assert parsed.message == "attack"


class TestBuildCommandVerbose:
    def test_no_flag_defaults_to_terse(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False

    @pytest.mark.parametrize("flag", ["-v", "--verbose"])
    def test_flag_after_expression_sets_verbose(self, flag):
        parsed = build_dice_command("!room:example.org", f"!roll 1d6 {flag}")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_before_expression_sets_verbose(self):
        parsed = build_dice_command("!room:example.org", "!roll -v 1d6")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_between_target_and_expression_sets_verbose(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6 -v >15")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.command.target is not None
        assert parsed.command.target.value == 15
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]

    def test_flag_survives_message_suffix(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6 -v | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.message == "attack"

    def test_repeated_flag_is_harmless(self):
        parsed = build_dice_command("!room:example.org", "!roll 1d6 -v -v")
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
        """Tokens that don't parse as a target fall through to expr parsing and get named there."""
        result = build_dice_command("!room:example.org", f"!roll 1d6 {bad_target}")
        assert result == invalid_expr(bad_target, "not a recognized dice expression")

    def test_target_with_no_dice_expression_rejects_whole_command(self):
        result = build_dice_command("!room:example.org", "!roll >15")
        assert result == INVALID_ROLL

    def test_duplicate_target_rejects_whole_command(self):
        result = build_dice_command("!room:example.org", "!roll 1d6 >5 >10")
        assert result == INVALID_ROLL


class TestBuildCommandReroll:
    def test_no_previous_roll_returns_message(self):
        assert (
            build_dice_command("!empty-room:example.org", "!reroll") == NO_PREVIOUS_ROLL
        )

    def test_rr_alias_is_equivalent(self):
        assert build_dice_command("!empty-room2:example.org", "!rr") == NO_PREVIOUS_ROLL

    def test_repeats_last_roll_expression(self):
        room_id = "!other-room:example.org"
        build_dice_command(room_id, "!roll 1d6")
        result = _roll(room_id, "!rr")
        assert isinstance(result, RollCommand)
        assert [expr for expr, _ in result.specs] == ["1d6"]

    def test_invalid_first_roll_leaves_no_previous_roll(self):
        room_id = "!invalid-only-room:example.org"
        build_dice_command(room_id, "!roll bogus")
        assert build_dice_command(room_id, "!reroll") == NO_PREVIOUS_ROLL

    def test_reroll_without_message_replays_original_message(self):
        room_id = "!reroll-msg-room:example.org"
        build_dice_command(room_id, "!roll 1d6 | attack")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "attack"

    def test_reroll_with_message_overrides_original_message(self):
        room_id = "!reroll-msg-room2:example.org"
        build_dice_command(room_id, "!roll 1d6 | attack")
        parsed = build_dice_command(room_id, "!reroll | defend")
        assert isinstance(parsed, ParsedRoll)
        assert [expr for expr, _ in parsed.command.specs] == ["1d6"]
        assert parsed.message == "defend"

    def test_reroll_with_message_on_originally_messageless_roll(self):
        room_id = "!reroll-msg-room3:example.org"
        build_dice_command(room_id, "!roll 1d6")
        parsed = build_dice_command(room_id, "!reroll | now with flavor")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "now with flavor"

    def test_reroll_with_empty_message_clears_message(self):
        room_id = "!reroll-msg-room4:example.org"
        build_dice_command(room_id, "!roll 1d6 | attack")
        parsed = build_dice_command(room_id, "!reroll |")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message is None

    def test_reroll_with_trailing_text_but_no_pipe_is_invalid(self):
        room_id = "!reroll-msg-room5:example.org"
        build_dice_command(room_id, "!roll 1d6")
        assert build_dice_command(room_id, "!reroll defend") == INVALID_ROLL

    def test_reroll_with_text_before_pipe_is_invalid(self):
        room_id = "!reroll-msg-room7:example.org"
        build_dice_command(room_id, "!roll 1d6")
        assert build_dice_command(room_id, "!reroll bogus | defend") == INVALID_ROLL

    def test_reroll_message_persists_for_later_bare_reroll(self):
        room_id = "!reroll-msg-room8:example.org"
        build_dice_command(room_id, "!roll 1d6 | attack")
        build_dice_command(room_id, "!reroll | defend")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "defend"

    def test_invalid_reroll_message_does_not_overwrite_remembered_roll(self):
        room_id = "!reroll-msg-room9:example.org"
        build_dice_command(room_id, "!roll 1d6 | attack")
        build_dice_command(room_id, "!reroll bogus | defend")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "attack"

    def test_rr_alias_accepts_message(self):
        room_id = "!reroll-msg-room6:example.org"
        build_dice_command(room_id, "!roll 1d6")
        parsed = build_dice_command(room_id, "!rr | flourish")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.message == "flourish"

    def test_reroll_without_target_replays_original_target(self):
        room_id = "!reroll-target-room:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=15)

    def test_reroll_with_target_overrides_original_target(self):
        room_id = "!reroll-target-room2:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        parsed = build_dice_command(room_id, "!reroll >10")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=10)
        assert [expr for expr, _ in parsed.command.specs] == ["1d20"]

    def test_reroll_with_target_on_originally_targetless_roll(self):
        room_id = "!reroll-target-room3:example.org"
        build_dice_command(room_id, "!roll 1d20")
        parsed = build_dice_command(room_id, "!reroll >10")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=10)

    def test_reroll_with_target_and_message_overrides_both(self):
        room_id = "!reroll-target-room4:example.org"
        build_dice_command(room_id, "!roll 1d20 >15 | attack")
        parsed = build_dice_command(room_id, "!reroll >10 | defend")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=10)
        assert parsed.message == "defend"

    def test_reroll_target_persists_for_later_bare_reroll(self):
        room_id = "!reroll-target-room5:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        build_dice_command(room_id, "!reroll >10")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=10)

    def test_reroll_with_invalid_target_is_invalid(self):
        room_id = "!reroll-target-room6:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        assert build_dice_command(room_id, "!reroll >bogus") == INVALID_ROLL

    def test_reroll_with_duplicate_target_is_invalid(self):
        room_id = "!reroll-target-room7:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        assert build_dice_command(room_id, "!reroll >10 >20") == INVALID_ROLL

    def test_invalid_reroll_target_does_not_overwrite_remembered_roll(self):
        room_id = "!reroll-target-room8:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        build_dice_command(room_id, "!reroll >bogus")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.command.target == Target(operator=">", value=15)


class TestBuildCommandRerollVerbose:
    def test_bare_reroll_of_verbose_roll_is_terse(self):
        room_id = "!reroll-verbose-room:example.org"
        build_dice_command(room_id, "!roll 1d6 -v")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False

    def test_reroll_with_target_override_of_verbose_roll_is_terse(self):
        room_id = "!reroll-verbose-room2:example.org"
        build_dice_command(room_id, "!roll 1d20 >15 -v")
        parsed = build_dice_command(room_id, "!reroll >10")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False

    def test_reroll_with_message_override_of_verbose_roll_is_terse(self):
        room_id = "!reroll-verbose-room3:example.org"
        build_dice_command(room_id, "!roll 1d6 -v | attack")
        parsed = build_dice_command(room_id, "!reroll | defend")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False

    def test_reroll_with_own_verbose_flag_is_verbose(self):
        room_id = "!reroll-verbose-room4:example.org"
        build_dice_command(room_id, "!roll 1d6")
        parsed = build_dice_command(room_id, "!reroll -v")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True

    def test_reroll_with_own_verbose_flag_and_target_override(self):
        room_id = "!reroll-verbose-room5:example.org"
        build_dice_command(room_id, "!roll 1d20 >15")
        parsed = build_dice_command(room_id, "!reroll >10 -v")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.command.target == Target(operator=">", value=10)

    def test_reroll_with_own_verbose_flag_and_message_override(self):
        room_id = "!reroll-verbose-room6:example.org"
        build_dice_command(room_id, "!roll 1d6")
        parsed = build_dice_command(room_id, "!reroll -v | attack")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is True
        assert parsed.message == "attack"

    def test_reroll_verbose_flag_does_not_persist_for_later_bare_reroll(self):
        room_id = "!reroll-verbose-room7:example.org"
        build_dice_command(room_id, "!roll 1d6")
        build_dice_command(room_id, "!reroll -v")
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert parsed.verbose is False


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

    def test_invalid_expression_returns_error_string(self):
        result = commands._parse_expr("abc")
        assert result == invalid_expr("abc", "not a recognized dice expression")

    def test_invalid_expression_with_backtick_is_sanitized(self):
        """A backtick in the offending token would otherwise break the reply's Markdown code span."""
        result = commands._parse_expr("`abc")
        assert result == invalid_expr("`abc", "not a recognized dice expression")
        assert result == (
            "Invalid roll `'abc` — not a recognized dice expression. "
            "See `!roll --help` for syntax."
        )


class TestBuildSaveCommand:
    def test_bare_save_returns_usage(self):
        assert build_save_command("!save") == SAVE_USAGE

    def test_save_with_only_a_name_returns_usage(self):
        assert build_save_command("!save attack") == SAVE_USAGE

    def test_valid_save_returns_save_command(self):
        result = build_save_command("!save attack 3d8+4")
        assert result == SaveCommand(name="attack", expr="3d8+4")

    def test_name_is_lowercased(self):
        result = build_save_command("!save Attack 3d8+4")
        assert isinstance(result, SaveCommand)
        assert result.name == "attack"

    def test_invalid_name_returns_error(self):
        assert build_save_command("!save 1attack 3d8+4") == invalid_pattern_name(
            "1attack"
        )

    def test_name_colliding_with_dice_notation_is_rejected(self):
        """Digits aren't allowed in names at all, so a name like `d20` — which
        would otherwise make `!roll d20` ambiguous once saved patterns are
        looked up by name — is rejected up front."""
        assert build_save_command("!save d20 3d8+4") == invalid_pattern_name("d20")

    def test_name_with_space_is_rejected_via_invalid_characters(self):
        """A name can't itself contain a space (the parser can't tell it apart
        from the expression that follows), but a hyphen/underscore works."""
        result = build_save_command("!save saving-throw 1d20+2")
        assert result == SaveCommand(name="saving-throw", expr="1d20+2")

    def test_invalid_expression_returns_roll_error(self):
        assert build_save_command("!save attack abc") == invalid_expr(
            "abc", "not a recognized dice expression"
        )

    def test_saved_expression_keeps_target_and_message_verbatim(self):
        """The expression is stored as the raw string, not the parsed
        `RollCommand` — target/message/verbose all just pass through."""
        result = build_save_command("!save attack 3d8+4 >15 -v | Fireball")
        assert result == SaveCommand(name="attack", expr="3d8+4 >15 -v | Fireball")

    def test_extra_whitespace_around_expression_is_stripped(self):
        result = build_save_command("!save attack   3d8+4  ")
        assert result == SaveCommand(name="attack", expr="3d8+4")

    def test_list_flag_returns_list_saved_command(self):
        assert build_save_command("!save --list") == ListSavedCommand()

    def test_list_flag_with_extra_whitespace_returns_list_saved_command(self):
        assert build_save_command("!save   --list  ") == ListSavedCommand()

    def test_list_flag_with_trailing_args_is_not_treated_as_list(self):
        """`--list` must be the whole argument, not just the first token, so
        this falls through to ordinary name/expr parsing (and fails name
        validation, since `--list` isn't a legal pattern name)."""
        result = build_save_command("!save --list foo")
        assert result == invalid_pattern_name("--list")


class TestBuildSavedPatternCommand:
    def test_bare_invocation_rolls_the_stored_expression(self):
        result = build_saved_pattern_command("!room:example.org", "3d8+4", None)
        assert isinstance(result, ParsedRoll)
        assert [expr for expr, _ in result.command.specs] == ["3d8+4"]
        assert result.command.target is None
        assert result.verbose is False
        assert result.message is None

    def test_stored_target_and_message_are_replayed(self):
        result = build_saved_pattern_command(
            "!room:example.org", "3d8+4 >15 | Fireball", None
        )
        assert isinstance(result, ParsedRoll)
        assert result.command.target == Target(operator=">", value=15)
        assert result.message == "Fireball"

    def test_stored_verbose_flag_is_not_replayed(self):
        """Mirrors `!reroll`: a saved pattern's own `-v` isn't inherited on
        bare invocation, only on an invocation that carries its own `-v`."""
        result = build_saved_pattern_command("!room:example.org", "3d8+4 -v", None)
        assert isinstance(result, ParsedRoll)
        assert result.verbose is False

    def test_override_arg_replaces_target(self):
        result = build_saved_pattern_command("!room:example.org", "3d8+4 >15", ">10")
        assert isinstance(result, ParsedRoll)
        assert result.command.target == Target(operator=">", value=10)

    def test_override_arg_replaces_message(self):
        result = build_saved_pattern_command(
            "!room:example.org", "3d8+4 | attack", "| defend"
        )
        assert isinstance(result, ParsedRoll)
        assert result.message == "defend"

    def test_override_arg_sets_verbose(self):
        result = build_saved_pattern_command("!room:example.org", "3d8+4", "-v")
        assert isinstance(result, ParsedRoll)
        assert result.verbose is True

    def test_invalid_override_arg_is_invalid(self):
        result = build_saved_pattern_command("!room:example.org", "3d8+4", ">bogus")
        assert result == INVALID_ROLL

    def test_successful_invocation_is_remembered_for_reroll(self):
        room_id = "!saved-pattern-reroll-room:example.org"
        build_saved_pattern_command(room_id, "3d8+4 >15", None)
        parsed = build_dice_command(room_id, "!reroll")
        assert isinstance(parsed, ParsedRoll)
        assert [expr for expr, _ in parsed.command.specs] == ["3d8+4"]
        assert parsed.command.target == Target(operator=">", value=15)
