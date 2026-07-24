"""Unit tests for the `!roll`/`!reroll` command handling in main.py."""

import os

os.environ.setdefault("MATRIX_BASE_URL", "https://example.invalid")
os.environ.setdefault("MATRIX_USER_ID", "@bot:example.invalid")
os.environ.setdefault("MATRIX_PASSWORD", "unused-test-password")
os.environ.setdefault("MATRIX_DEVICE_NAME", "matrix-bot-roll-test")
os.environ.setdefault("MATRIX_STORE_PATH", "/tmp/matrix-bot-roll-test-store")

from main import _handle_reroll, _handle_roll  # noqa: E402
from messages import NO_PREVIOUS_ROLL, ROLL_HELP, USAGE  # noqa: E402


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
