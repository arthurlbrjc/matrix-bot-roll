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
    INVALID_ROLL,
    NO_PREVIOUS_ROLL,
    ROLL_HELP,
    USAGE,
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
        assert _send_body("!room:example.org", "!roll bogus") == INVALID_ROLL

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
