"""Unit tests for the `!roll`/`!reroll` command handling in main.py."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("MATRIX_BASE_URL", "https://example.invalid")
os.environ.setdefault("MATRIX_USER_ID", "@bot:example.invalid")
os.environ.setdefault("MATRIX_PASSWORD", "unused-test-password")
os.environ.setdefault("MATRIX_DEVICE_NAME", "matrix-bot-roll-test")
os.environ.setdefault("MATRIX_STORE_PATH", "/tmp/matrix-bot-roll-test-store")

from matrix_bot_roll.main import (  # noqa: E402
    _handle_reroll,
    _handle_roll,
    message_callback,
)
from matrix_bot_roll.messages import NO_PREVIOUS_ROLL, ROLL_HELP, USAGE  # noqa: E402


def _send_body(room_id: str, body: str) -> str | None:
    """Run `message_callback` with a stub client/room/event and return the sent reply body, if any."""
    client = AsyncMock()
    room = SimpleNamespace(room_id=room_id)
    event = SimpleNamespace(body=body)
    asyncio.run(message_callback(client, room, event))
    if not client.room_send.called:
        return None
    return client.room_send.call_args.kwargs["content"]["body"]


class TestHandleRoll:
    def test_bare_roll_returns_usage(self):
        assert _handle_roll("!room:example.org", "!roll") == USAGE

    def test_bare_roll_with_trailing_whitespace_returns_usage(self):
        assert _handle_roll("!room:example.org", "!roll ") == USAGE

    def test_help_flag_returns_detailed_help(self):
        assert _handle_roll("!room:example.org", "!roll --help") == ROLL_HELP

    def test_help_flag_with_extra_whitespace_returns_detailed_help(self):
        assert _handle_roll("!room:example.org", "!roll   --help") == ROLL_HELP

    def test_expression_is_rolled(self):
        output = _handle_roll("!room:example.org", "!roll 1d6")
        assert "🎲 1d6" in output
        assert "**" in output

    def test_expression_is_remembered_for_reroll(self):
        room_id = "!room:example.org"
        _handle_roll(room_id, "!roll 1d6+4")
        assert "1d6+4" in _handle_reroll(room_id)


class TestHandleReroll:
    def test_no_previous_roll_returns_message(self):
        assert _handle_reroll("!empty-room:example.org") == NO_PREVIOUS_ROLL

    def test_repeats_last_roll_expression(self):
        room_id = "!other-room:example.org"
        _handle_roll(room_id, "!roll 1d1")
        assert "1d1" in _handle_reroll(room_id)


class TestMessageCallbackDispatch:
    def test_r_alias_bare_returns_usage(self):
        assert _send_body("!r-bare:example.org", "!r") == USAGE

    def test_r_alias_help_returns_detailed_help(self):
        assert _send_body("!r-help:example.org", "!r --help") == ROLL_HELP

    def test_r_alias_rolls_and_remembers_expression(self):
        room_id = "!r-remember:example.org"
        assert "1d1" in _send_body(room_id, "!r 1d1")
        assert "1d1" in _send_body(room_id, "!rr")

    def test_rr_alias_with_no_previous_roll_returns_message(self):
        assert _send_body("!rr-empty:example.org", "!rr") == NO_PREVIOUS_ROLL

    def test_reroll_is_not_swallowed_by_r_alias(self):
        room_id = "!reroll-not-swallowed:example.org"
        assert "1d1" in _send_body(room_id, "!roll 1d1")
        assert _send_body(room_id, "!reroll") != USAGE

    def test_unrelated_command_is_ignored(self):
        room_id = "!unrelated:example.org"
        assert _send_body(room_id, "!rollout") is None
        assert _send_body(room_id, "!rerolled") is None
        assert _send_body(room_id, "hello") is None
