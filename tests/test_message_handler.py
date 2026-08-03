"""Unit tests for the `!roll`/`!reroll`/`!save` message handling in message_handler.py."""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("MATRIX_BASE_URL", "https://example.invalid")
os.environ.setdefault("MATRIX_USER_ID", "@bot:example.invalid")
os.environ.setdefault("MATRIX_PASSWORD", "unused-test-password")
os.environ.setdefault("MATRIX_DEVICE_NAME", "matrix-bot-roll-test")
os.environ.setdefault("MATRIX_STORE_PATH", "/tmp/matrix-bot-roll-test-store")

from matrix_bot_roll import message_handler  # noqa: E402
from matrix_bot_roll.changelog import Release  # noqa: E402
from matrix_bot_roll.constants import MAX_SAVED_PATTERNS_PER_USER  # noqa: E402
from matrix_bot_roll.message_handler import handle_room_message  # noqa: E402
from matrix_bot_roll.messages import (  # noqa: E402
    FORGET_USAGE,
    INVALID_GRANULARITY,
    NO_PREVIOUS_ROLL,
    ROLL_HELP,
    SAVE_USAGE,
    USAGE,
    invalid_expr,
    invalid_pattern_name,
    pattern_forgotten,
    pattern_not_found,
    pattern_save_limit_reached,
    pattern_saved,
    saved_patterns_list,
)


def _fake_matrix_client(initial_blob=None):
    """
    A fake `AsyncClient` whose `send` serves GET/PUT against an in-memory
    account-data blob, mimicking the real `/user/{id}/account_data/{type}`
    endpoint (see tests/test_saved_patterns.py's `fake_client`) — needed by
    both `!save` (persists via `saved_patterns.save_pattern`) and `!roll
    <name>` (looks up via `saved_patterns.get_pattern`), so a bare `AsyncMock`
    client isn't enough for either.
    """
    store = {"data": initial_blob}

    async def send(method, path, data=None, headers=None):
        response = MagicMock()
        if method == "GET":
            if store["data"] is None:
                response.status = 404
            else:
                response.status = 200
                response.json = AsyncMock(return_value=store["data"])
            response.raise_for_status = MagicMock()
        else:
            store["data"] = json.loads(data)
            response.status = 200
            response.raise_for_status = MagicMock()
        return response

    client = AsyncMock()
    client.user_id = "@bot:example.invalid"
    client.access_token = "test-token"
    client.send = AsyncMock(side_effect=send)
    return client, store


def _send_body(room_id, body, sender="@alice:example.invalid", client=None):
    """Run `handle_room_message` with a fake client/room/event and return the sent reply body, if any."""
    if client is None:
        client, _ = _fake_matrix_client()
    room = SimpleNamespace(room_id=room_id)
    event = SimpleNamespace(body=body, sender=sender)
    asyncio.run(handle_room_message(client, room, event))
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


class TestSave:
    def test_bare_save_returns_usage(self):
        assert _send_body("!room:example.org", "!save") == SAVE_USAGE

    def test_save_with_only_a_name_returns_usage(self):
        assert _send_body("!room:example.org", "!save attack") == SAVE_USAGE

    def test_s_alias_saves(self):
        output = _send_body("!room:example.org", "!s attack 3d8+4")
        assert output == pattern_saved("attack", "3d8+4")

    def test_valid_save_confirms(self):
        output = _send_body("!room:example.org", "!save attack 3d8+4")
        assert output == pattern_saved("attack", "3d8+4")

    def test_invalid_name_returns_error(self):
        output = _send_body("!room:example.org", "!save 1attack 3d8+4")
        assert output == invalid_pattern_name("1attack")

    def test_invalid_expression_returns_error(self):
        output = _send_body("!room:example.org", "!save attack bogus")
        assert output == invalid_expr("bogus", "not a recognized dice expression")

    def test_save_persists_under_the_sender(self):
        client, store = _fake_matrix_client()
        _send_body(
            "!room:example.org",
            "!save attack 3d8+4",
            sender="@alice:example.invalid",
            client=client,
        )
        patterns = store["data"]["users"]["@alice:example.invalid"]
        assert patterns == {"attack": "3d8+4"}

    def test_different_senders_do_not_share_patterns(self):
        client, store = _fake_matrix_client()
        _send_body(
            "!room:example.org",
            "!save attack 3d8+4",
            sender="@alice:example.invalid",
            client=client,
        )
        _send_body(
            "!room:example.org",
            "!save attack 1d20+7",
            sender="@bob:example.invalid",
            client=client,
        )
        assert store["data"]["users"]["@alice:example.invalid"] == {"attack": "3d8+4"}
        assert store["data"]["users"]["@bob:example.invalid"] == {"attack": "1d20+7"}

    def test_save_rejected_past_the_cap_returns_limit_message(self):
        initial_blob = {
            "users": {
                "@alice:example.invalid": {
                    f"pattern{i}": "1d20" for i in range(MAX_SAVED_PATTERNS_PER_USER)
                }
            }
        }
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!save one-too-many 1d20",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == pattern_save_limit_reached("one-too-many")

    def test_list_with_no_saved_patterns_returns_empty_list_message(self):
        output = _send_body(
            "!room:example.org", "!save --list", sender="@alice:example.invalid"
        )
        assert output == saved_patterns_list({})

    def test_list_returns_the_senders_saved_patterns(self):
        initial_blob = {
            "users": {
                "@alice:example.invalid": {"attack": "3d8+4", "defend": "1d20+2"},
                "@bob:example.invalid": {"attack": "1d20+7"},
            }
        }
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!save --list",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == saved_patterns_list({"attack": "3d8+4", "defend": "1d20+2"})

    def test_list_escapes_backticks_in_saved_expressions(self):
        """A saved expression's message part isn't restricted from containing
        backticks, so `!save --list` must escape them like `pattern_saved`
        does, or they'd break the Markdown code span."""
        initial_blob = {
            "users": {"@alice:example.invalid": {"trick": "1d6 | say `boom`"}}
        }
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!save --list",
            sender="@alice:example.invalid",
            client=client,
        )
        assert "`boom`" not in output
        assert "'boom'" in output


class TestForget:
    def test_bare_forget_returns_usage(self):
        assert _send_body("!room:example.org", "!forget") == FORGET_USAGE

    def test_invalid_name_returns_error(self):
        output = _send_body("!room:example.org", "!forget 1attack")
        assert output == invalid_pattern_name("1attack")

    def test_unknown_name_returns_not_found(self):
        output = _send_body(
            "!room:example.org", "!forget attack", sender="@alice:example.invalid"
        )
        assert output == pattern_not_found("attack")

    def test_valid_forget_confirms_and_removes_it(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
        client, store = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!forget attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == pattern_forgotten("attack")
        assert store["data"]["users"]["@alice:example.invalid"] == {}

    def test_f_alias_forgets(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!f attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == pattern_forgotten("attack")

    def test_different_senders_do_not_share_patterns(self):
        initial_blob = {
            "users": {
                "@alice:example.invalid": {"attack": "3d8+4"},
                "@bob:example.invalid": {"attack": "1d20+7"},
            }
        }
        client, store = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!forget attack",
            sender="@bob:example.invalid",
            client=client,
        )
        assert output == pattern_forgotten("attack")
        assert store["data"]["users"]["@alice:example.invalid"] == {"attack": "3d8+4"}
        assert store["data"]["users"]["@bob:example.invalid"] == {}


class TestChanges:
    _RELEASES = [
        Release(
            version=(1, 4, 1), date="2026-07-31", body="### Fixed\n- clarify error"
        ),
        Release(
            version=(1, 4, 0), date="2026-07-31", body="### Added\n- reroll overrides"
        ),
        Release(
            version=(1, 3, 0), date="2026-07-30", body="### Changed\n- terse by default"
        ),
    ]

    def _with_fake_changelog(self, monkeypatch):
        monkeypatch.setattr(
            message_handler, "parse_changelog", lambda: list(self._RELEASES)
        )

    def test_bare_changes_defaults_to_minor(self, monkeypatch):
        self._with_fake_changelog(monkeypatch)
        output = _send_body("!room:example.org", "!changes")
        assert "1.4.1" in output
        assert "1.4.0" in output
        assert "1.3.0" not in output

    def test_explicit_granularity(self, monkeypatch):
        self._with_fake_changelog(monkeypatch)
        output = _send_body("!room:example.org", "!changes major")
        assert "1.4.1" in output
        assert "1.4.0" in output
        assert "1.3.0" in output

    def test_c_alias_defaults_to_minor(self, monkeypatch):
        self._with_fake_changelog(monkeypatch)
        output = _send_body("!room:example.org", "!c")
        assert "1.4.1" in output
        assert "1.4.0" in output
        assert "1.3.0" not in output

    def test_invalid_granularity_returns_error(self, monkeypatch):
        self._with_fake_changelog(monkeypatch)
        output = _send_body("!room:example.org", "!changes bogus")
        assert output == INVALID_GRANULARITY


class TestRollSavedPattern:
    def test_rolls_the_saved_expression_by_name(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!roll attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert "🎲 3d8+4" in output

    def test_r_alias_rolls_the_saved_expression(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!r attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert "🎲 3d8+4" in output

    def test_unsaved_name_falls_through_to_a_literal_expression(self):
        """No saved pattern named `attack` for this sender — falls back to the
        usual (invalid) dice-expression parsing, unchanged from before `!roll
        <name>` existed."""
        client, _ = _fake_matrix_client()
        output = _send_body(
            "!room:example.org",
            "!roll attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == invalid_expr("attack", "not a recognized dice expression")

    def test_lookup_is_scoped_to_the_sender(self):
        initial_blob = {"users": {"@bob:example.invalid": {"attack": "1d20+7"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!roll attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert output == invalid_expr("attack", "not a recognized dice expression")

    def test_stored_target_and_message_are_replayed(self):
        initial_blob = {
            "users": {"@alice:example.invalid": {"attack": "3d8+4 >15 | Fireball"}}
        }
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!roll attack",
            sender="@alice:example.invalid",
            client=client,
        )
        assert ">15" in output
        assert "💬 Fireball" in output

    def test_override_target_on_invocation(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4 >15"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        output = _send_body(
            "!room:example.org",
            "!roll attack >10",
            sender="@alice:example.invalid",
            client=client,
        )
        assert ">10" in output

    def test_invoked_roll_is_remembered_for_reroll(self):
        initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
        client, _ = _fake_matrix_client(initial_blob=initial_blob)
        room_id = "!saved-pattern-reroll-room:example.org"
        _send_body(
            room_id, "!roll attack", sender="@alice:example.invalid", client=client
        )
        output = _send_body(
            room_id, "!reroll", sender="@alice:example.invalid", client=client
        )
        assert "🎲 3d8+4" in output


class TestMessageCallbackDispatch:
    def test_unrelated_command_is_ignored(self):
        room_id = "!unrelated:example.org"
        assert _send_body(room_id, "!rollout") is None
        assert _send_body(room_id, "!rerolled") is None
        assert _send_body(room_id, "hello") is None
