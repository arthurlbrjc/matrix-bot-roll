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


def test_get_blob_returns_empty_dict_when_nothing_stored():
    client, _ = fake_client(initial_blob=None)

    async def run():
        return await account_data.get_blob(client, "roll.matrix-bot.some_feature")

    assert asyncio.run(run()) == {}


def test_put_blob_then_get_blob_round_trips():
    client, _ = fake_client(initial_blob=None)

    async def run():
        await account_data.put_blob(client, "roll.matrix-bot.some_feature", {"x": 1})
        return await account_data.get_blob(client, "roll.matrix-bot.some_feature")

    assert asyncio.run(run()) == {"x": 1}


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
        await account_data.put_blob(client, "roll.matrix-bot.feature_a", {"a": 1})
        await account_data.put_blob(client, "roll.matrix-bot.feature_b", {"b": 2})
        return (
            await account_data.get_blob(client, "roll.matrix-bot.feature_a"),
            await account_data.get_blob(client, "roll.matrix-bot.feature_b"),
        )

    blob_a, blob_b = asyncio.run(run())
    assert blob_a == {"a": 1}
    assert blob_b == {"b": 2}


def test_get_blob_sends_authorization_header():
    client, _ = fake_client(initial_blob=None)

    async def run():
        await account_data.get_blob(client, "roll.matrix-bot.some_feature")

    asyncio.run(run())
    _, kwargs = client.send.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"
