"""Unit tests for the account-data storage layer in saved_patterns.py."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from matrix_bot_roll import saved_patterns
from matrix_bot_roll.constants import MAX_SAVED_PATTERNS_PER_USER


def fake_client(initial_blob=None):
    """
    A fake `AsyncClient` whose `send` serves GET/PUT against an in-memory
    account-data blob, mimicking the real `/user/{id}/account_data/{type}`
    endpoint closely enough for `saved_patterns.py`'s helpers to exercise.

    The returned `store` dict's `"data"` key always reflects the latest PUT
    (or the `initial_blob` if nothing's been written yet), so tests can
    assert on stored state without needing a read-side helper of their own.
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

    client = MagicMock()
    client.user_id = "@bot:example.invalid"
    client.access_token = "test-token"
    client.send = AsyncMock(side_effect=send)
    return client, store


def user_patterns(store, user_id):
    """Pull one user's patterns dict out of a `fake_client` store, or {} if none."""
    return (store["data"] or {}).get("users", {}).get(user_id, {})


@pytest.mark.parametrize(
    "name,expected",
    [
        ("attack", True),
        ("saving-throw", True),
        ("saving_throw", True),
        ("dice", True),
        ("a" * 32, True),
        ("", False),
        ("Attack", False),  # must already be lowercase
        ("1attack", False),  # must start with a letter
        ("has space", False),
        ("a" * 33, False),  # exceeds MAX_PATTERN_NAME_LENGTH
        ("a1", False),  # no digits allowed, so it can't collide with dice notation
        ("d20", False),  # no digits allowed, so it can't collide with dice notation
    ],
)
def test_is_valid_name(name, expected):
    assert saved_patterns.is_valid_name(name) is expected


def test_get_pattern_returns_none_when_nothing_saved():
    client, _ = fake_client(initial_blob=None)

    async def run():
        return await saved_patterns.get_pattern(
            client, "@alice:example.invalid", "attack"
        )

    assert asyncio.run(run()) is None


def test_get_pattern_returns_none_for_unknown_name():
    initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.get_pattern(
            client, "@alice:example.invalid", "defend"
        )

    assert asyncio.run(run()) is None


def test_get_pattern_returns_the_saved_expression():
    initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.get_pattern(
            client, "@alice:example.invalid", "attack"
        )

    assert asyncio.run(run()) == "3d8+4"


def test_get_pattern_does_not_leak_across_users():
    initial_blob = {
        "users": {
            "@alice:example.invalid": {"attack": "3d8+4"},
            "@bob:example.invalid": {"attack": "1d20+7"},
        }
    }
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.get_pattern(
            client, "@bob:example.invalid", "attack"
        )

    assert asyncio.run(run()) == "1d20+7"


def test_list_patterns_returns_empty_dict_when_nothing_saved():
    client, _ = fake_client(initial_blob=None)

    async def run():
        return await saved_patterns.list_patterns(client, "@alice:example.invalid")

    assert asyncio.run(run()) == {}


def test_list_patterns_returns_the_saved_patterns():
    initial_blob = {
        "users": {"@alice:example.invalid": {"attack": "3d8+4", "defend": "1d20+2"}}
    }
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.list_patterns(client, "@alice:example.invalid")

    assert asyncio.run(run()) == {"attack": "3d8+4", "defend": "1d20+2"}


def test_list_patterns_does_not_leak_across_users():
    initial_blob = {
        "users": {
            "@alice:example.invalid": {"attack": "3d8+4"},
            "@bob:example.invalid": {"attack": "1d20+7"},
        }
    }
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.list_patterns(client, "@bob:example.invalid")

    assert asyncio.run(run()) == {"attack": "1d20+7"}


def test_save_pattern_then_stores_it():
    client, store = fake_client(initial_blob=None)

    async def run():
        await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "3d8+4"
        )

    asyncio.run(run())
    assert user_patterns(store, "@alice:example.invalid") == {"attack": "3d8+4"}


def test_save_pattern_overwrites_existing_name():
    client, store = fake_client(initial_blob=None)

    async def run():
        await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "3d8+4"
        )
        await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "1d20+7"
        )

    asyncio.run(run())
    assert user_patterns(store, "@alice:example.invalid") == {"attack": "1d20+7"}


def test_save_pattern_skips_the_write_when_value_is_unchanged():
    """Saving the same name with the expression it already has is a true
    no-op: `save_pattern` should skip the PUT rather than round-trip an
    identical blob back to the homeserver."""
    client, _ = fake_client(initial_blob=None)

    async def run():
        await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "3d8+4"
        )
        client.send.reset_mock()
        saved = await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "3d8+4"
        )
        return saved

    saved = asyncio.run(run())
    assert saved is True
    put_calls = [call for call in client.send.call_args_list if call.args[0] == "PUT"]
    assert put_calls == []


def test_save_pattern_does_not_leak_across_users():
    client, store = fake_client(initial_blob=None)

    async def run():
        await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "attack", "3d8+4"
        )
        await saved_patterns.save_pattern(
            client, "@bob:example.invalid", "attack", "1d20+7"
        )

    asyncio.run(run())
    assert user_patterns(store, "@alice:example.invalid") == {"attack": "3d8+4"}
    assert user_patterns(store, "@bob:example.invalid") == {"attack": "1d20+7"}


def test_save_pattern_rejects_new_name_past_the_cap():
    initial_blob = {
        "users": {
            "@alice:example.invalid": {
                f"pattern{i}": "1d20" for i in range(MAX_SAVED_PATTERNS_PER_USER)
            }
        }
    }
    client, store = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "one-too-many", "1d20"
        )

    saved = asyncio.run(run())
    assert saved is False
    patterns = user_patterns(store, "@alice:example.invalid")
    assert "one-too-many" not in patterns
    assert len(patterns) == MAX_SAVED_PATTERNS_PER_USER


def test_save_pattern_overwrite_at_the_cap_still_succeeds():
    initial_blob = {
        "users": {
            "@alice:example.invalid": {
                f"pattern{i}": "1d20" for i in range(MAX_SAVED_PATTERNS_PER_USER)
            }
        }
    }
    client, store = fake_client(initial_blob=initial_blob)

    async def run():
        return await saved_patterns.save_pattern(
            client, "@alice:example.invalid", "pattern0", "2d6+1"
        )

    saved = asyncio.run(run())
    assert saved is True
    patterns = user_patterns(store, "@alice:example.invalid")
    assert patterns["pattern0"] == "2d6+1"
    assert len(patterns) == MAX_SAVED_PATTERNS_PER_USER
