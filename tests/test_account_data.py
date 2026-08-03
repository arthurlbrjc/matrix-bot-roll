"""Unit tests for the generic account-data GET/PUT helpers in account_data.py."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from matrix_bot_roll import account_data


def fake_client(initial_blob=None):
    """A fake `AsyncClient` whose `send` serves GET/PUT against an in-memory blob."""
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


def test_different_types_do_not_share_storage():
    """Two features (two `account_data_type`s) hitting the same fake homeserver
    shouldn't clobber each other — each PUT targets its own type's path."""
    stores = {}

    async def send(method, path, data=None, headers=None):
        response = MagicMock()
        if method == "GET":
            if path not in stores:
                response.status = 404
            else:
                response.status = 200
                response.json = AsyncMock(return_value=stores[path])
            response.raise_for_status = MagicMock()
        else:
            stores[path] = json.loads(data)
            response.status = 200
            response.raise_for_status = MagicMock()
        return response

    client = MagicMock()
    client.user_id = "@bot:example.invalid"
    client.access_token = "test-token"
    client.send = AsyncMock(side_effect=send)

    async def run():
        await account_data.put_for_user(
            client, "roll.matrix-bot.feature_a", "@alice:example.invalid", {"a": 1}
        )
        await account_data.put_for_user(
            client, "roll.matrix-bot.feature_b", "@alice:example.invalid", {"b": 2}
        )
        return (
            await account_data.get_for_user(
                client, "roll.matrix-bot.feature_a", "@alice:example.invalid"
            ),
            await account_data.get_for_user(
                client, "roll.matrix-bot.feature_b", "@alice:example.invalid"
            ),
        )

    data_a, data_b = asyncio.run(run())
    assert data_a == {"a": 1}
    assert data_b == {"b": 2}


def test_get_for_user_sends_authorization_header():
    client, _ = fake_client(initial_blob=None)

    async def run():
        await account_data.get_for_user(
            client, "roll.matrix-bot.some_feature", "@alice:example.invalid"
        )

    asyncio.run(run())
    _, kwargs = client.send.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_get_for_user_returns_empty_dict_when_nothing_stored():
    client, _ = fake_client(initial_blob=None)

    async def run():
        return await account_data.get_for_user(
            client, "roll.matrix-bot.some_feature", "@alice:example.invalid"
        )

    assert asyncio.run(run()) == {}


def test_get_for_user_returns_only_that_users_data():
    initial_blob = {
        "users": {
            "@alice:example.invalid": {"attack": "3d8+4"},
            "@bob:example.invalid": {"attack": "1d20+7"},
        }
    }
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await account_data.get_for_user(
            client, "roll.matrix-bot.some_feature", "@alice:example.invalid"
        )

    assert asyncio.run(run()) == {"attack": "3d8+4"}


def test_get_for_user_returns_empty_dict_for_unknown_user():
    initial_blob = {"users": {"@alice:example.invalid": {"attack": "3d8+4"}}}
    client, _ = fake_client(initial_blob=initial_blob)

    async def run():
        return await account_data.get_for_user(
            client, "roll.matrix-bot.some_feature", "@bob:example.invalid"
        )

    assert asyncio.run(run()) == {}


def test_put_for_user_then_get_for_user_round_trips():
    client, _ = fake_client(initial_blob=None)

    async def run():
        await account_data.put_for_user(
            client,
            "roll.matrix-bot.some_feature",
            "@alice:example.invalid",
            {"attack": "3d8+4"},
        )
        return await account_data.get_for_user(
            client, "roll.matrix-bot.some_feature", "@alice:example.invalid"
        )

    assert asyncio.run(run()) == {"attack": "3d8+4"}


def test_put_for_user_does_not_affect_other_users():
    initial_blob = {"users": {"@bob:example.invalid": {"attack": "1d20+7"}}}
    client, store = fake_client(initial_blob=initial_blob)

    async def run():
        await account_data.put_for_user(
            client,
            "roll.matrix-bot.some_feature",
            "@alice:example.invalid",
            {"attack": "3d8+4"},
        )

    asyncio.run(run())
    assert store["data"]["users"]["@alice:example.invalid"] == {"attack": "3d8+4"}
    assert store["data"]["users"]["@bob:example.invalid"] == {"attack": "1d20+7"}
