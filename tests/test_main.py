"""Unit tests for the `!roll`/`!reroll` message handling in main.py."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("MATRIX_BASE_URL", "https://example.invalid")
os.environ.setdefault("MATRIX_USER_ID", "@bot:example.invalid")
os.environ.setdefault("MATRIX_PASSWORD", "unused-test-password")
os.environ.setdefault("MATRIX_DEVICE_NAME", "matrix-bot-roll-test")
os.environ.setdefault("MATRIX_STORE_PATH", "/tmp/matrix-bot-roll-test-store")

from matrix_bot_roll.main import message_callback  # noqa: E402
from matrix_bot_roll.messages import (  # noqa: E402
    NO_PREVIOUS_ROLL,
    ROLL_HELP,
    USAGE,
    invalid_expr,
)


def _send_body(room_id: str, body: str) -> str | None:
    """Run `message_callback` with a stub client/room/event and return the sent reply body, if any."""
    client = AsyncMock()
    room = SimpleNamespace(room_id=room_id)
    event = SimpleNamespace(body=body)
    asyncio.run(message_callback(client, room, event))
    if not client.room_send.called:
        return None
    return client.room_send.call_args.kwargs["content"]["body"]


class TestRoll:
    def test_bare_roll_returns_usage(self):
        assert _send_body("!room:example.org", "!roll") == USAGE

    def test_help_flag_returns_detailed_help(self):
        assert _send_body("!room:example.org", "!roll --help") == ROLL_HELP

    def test_expression_is_rolled(self):
        output = _send_body("!room:example.org", "!roll 1d6")
        assert "🎲 1d6" in output
        assert "**" in output

    def test_invalid_expression_returns_invalid_roll(self):
        assert _send_body("!room:example.org", "!roll bogus") == invalid_expr(
            "bogus", "not a recognized dice expression"
        )

    def test_multiple_expressions_include_grand_total(self):
        output = _send_body("!room:example.org", "!roll 1d6 1d4")
        assert output.count("🎲") == 2
        assert "**Total:" in output

    def test_single_expression_has_no_grand_total(self):
        output = _send_body("!room:example.org", "!roll 1d6")
        assert "**Total:" not in output

    def test_message_suffix_is_appended(self):
        output = _send_body("!room:example.org", "!roll 1d6 | attack")
        assert output.endswith("💬 attack")

    def test_r_alias_rolls(self):
        output = _send_body("!r-room:example.org", "!r 1d6")
        assert "🎲 1d6" in output

    def test_target_success_is_inlined_on_the_roll_line(self):
        """2d6 is always > 0, so this deterministically succeeds.

        Two dice are always kept here, so no natural crit/fumble override can
        apply (unlike `1d6`, which keeps a single die and could otherwise flip
        the outcome on a roll of 1 or 6). A single expression compared to a
        target is inlined onto its own line rather than getting a separate
        '**Total:**' line.
        """
        output = _send_body("!room:example.org", "!roll 2d6 >0")
        assert output.count("🎲") == 1
        assert "**Total:" not in output
        assert ">0" in output
        assert "✅" in output
        assert "❌" not in output

    def test_target_failure_is_inlined_on_the_roll_line(self):
        """2d6 can never exceed 100, so this deterministically fails.

        Two dice are always kept here, so no natural crit/fumble override can
        apply (unlike `1d6`, which keeps a single die and could otherwise flip
        the outcome on a roll of 1 or 6).
        """
        output = _send_body("!room:example.org", "!roll 2d6 >100")
        assert output.count("🎲") == 1
        assert "**Total:" not in output
        assert ">100" in output
        assert "❌" in output
        assert "✅" not in output

    def test_multi_expression_target_keeps_separate_total_line(self):
        """With more than one expression, the target isn't tied to any single roll, so it keeps its own '**Total:**' line."""
        output = _send_body("!room:example.org", "!roll 1d6 1d4 >0")
        assert output.count("🎲") == 2
        assert "**Total:" in output
        assert "✅" in output

    def test_verbose_target_keeps_separate_total_line(self):
        """In verbose mode the roll line is already busy with the per-die breakdown, so the target keeps its own dedicated line rather than being inlined."""
        output = _send_body("!room:example.org", "!roll 2d6 >0 -v")
        assert output.count("🎲") == 1
        assert "**Total:" in output
        assert "✅" in output

    def test_no_target_has_no_marker(self):
        output = _send_body("!room:example.org", "!roll 1d6")
        assert "✅" not in output
        assert "❌" not in output

    def test_malformed_target_returns_invalid_roll(self):
        assert _send_body("!room:example.org", "!roll 1d6 >") == invalid_expr(
            ">", "not a recognized dice expression"
        )

    def test_default_output_is_terse(self):
        output = _send_body("!room:example.org", "!roll 4d6kh3")
        assert "keep" not in output
        assert "[" not in output

    def test_verbose_flag_shows_full_breakdown(self):
        output = _send_body("!room:example.org", "!roll 4d6kh3 -v")
        assert "keep highest 3" in output
        assert "[" in output

    def test_verbose_flag_placement_does_not_matter(self):
        before = _send_body("!room:example.org", "!roll -v 4d6kh3")
        assert "keep highest 3" in before


class TestDetail:
    def test_no_previous_roll_returns_message(self):
        assert _send_body("!detail-empty:example.org", "!detail") == NO_PREVIOUS_ROLL

    def test_d_alias_with_no_previous_roll_returns_message(self):
        assert _send_body("!d-empty:example.org", "!d") == NO_PREVIOUS_ROLL

    def test_shows_full_breakdown_of_last_roll(self):
        room_id = "!detail-room:example.org"
        _send_body(room_id, "!roll 4d6kh3")
        output = _send_body(room_id, "!detail")
        assert "keep highest 3" in output
        assert "[" in output

    def test_target_keeps_separate_total_line(self):
        """`!detail` always renders verbose, so a single-expression target keeps its own dedicated line rather than being inlined."""
        room_id = "!detail-target-room:example.org"
        _send_body(room_id, "!roll 2d6 >0")
        output = _send_body(room_id, "!detail")
        assert output.count("🎲") == 1
        assert "**Total:" in output
        assert "✅" in output

    def test_does_not_roll_again(self):
        room_id = "!detail-no-reroll:example.org"
        first = _send_body(room_id, "!roll 1d6 -v")
        second = _send_body(room_id, "!detail")
        assert first == second

    def test_d_alias_shows_last_roll(self):
        room_id = "!detail-d-alias:example.org"
        _send_body(room_id, "!roll 1d6")
        output = _send_body(room_id, "!d")
        assert "🎲 1d6" in output


class TestReroll:
    def test_no_previous_roll_returns_message(self):
        assert _send_body("!empty-room:example.org", "!reroll") == NO_PREVIOUS_ROLL

    def test_repeats_last_roll_expression(self):
        room_id = "!other-room:example.org"
        _send_body(room_id, "!roll 1d6")
        assert "1d6" in _send_body(room_id, "!reroll")

    def test_rr_alias_with_no_previous_roll_returns_message(self):
        assert _send_body("!rr-empty:example.org", "!rr") == NO_PREVIOUS_ROLL

    def test_reroll_is_not_swallowed_by_r_alias(self):
        room_id = "!reroll-not-swallowed:example.org"
        assert "1d6" in _send_body(room_id, "!roll 1d6")
        assert _send_body(room_id, "!reroll") != USAGE


class TestMessageCallbackDispatch:
    def test_unrelated_command_is_ignored(self):
        room_id = "!unrelated:example.org"
        assert _send_body(room_id, "!rollout") is None
        assert _send_body(room_id, "!rerolled") is None
        assert _send_body(room_id, "hello") is None
