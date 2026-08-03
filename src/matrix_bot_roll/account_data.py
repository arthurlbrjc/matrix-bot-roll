"""
Generic get/put of a JSON blob stored as this bot's own Matrix account data.

Any feature that needs data to survive a restart (the hosting platform gives
the bot no persistent volume) can use this as its storage, namespaced by its
own `account_data_type` — one blob per type, so one feature's growth or
read-modify-write races can't collide with another's. A bot can only write
to its own account, never a caller's, so per-user data has to be namespaced
inside the blob's own content instead of using separate per-user account
data — see saved_patterns.py for an example.

matrix-nio has no `set_account_data`/`get_account_data` API (checked against
the source of the latest release, 0.26.0, not just its docs), so this talks
to the `/user/{userId}/account_data/{type}` endpoint directly via
`AsyncClient.send()`.
"""

import json
from typing import Any, Dict
from urllib.parse import quote

from nio import AsyncClient


async def get_for_user(
    client: AsyncClient, account_data_type: str, user_id: str
) -> Dict[str, Any]:
    """
    Fetch just `user_id`'s namespaced sub-dict from the blob stored under
    `account_data_type`, or {} if nothing's been saved for them yet.

    For the read-only "look up this user's data" case — see the module
    docstring for why per-user data lives namespaced inside one shared blob
    rather than separate per-user account data. A read-modify-write (like a
    save or delete) should use `put_for_user` instead, which takes care of
    writing back the rest of the blob untouched.
    """
    all_data = await _get_blob(client, account_data_type)
    return all_data.get("users", {}).get(user_id, {})


async def put_for_user(
    client: AsyncClient, account_data_type: str, user_id: str, data: Dict[str, Any]
) -> None:
    """
    Overwrite `user_id`'s namespaced sub-dict in the blob stored under
    `account_data_type` with `data`, leaving every other user's data
    untouched.

    Read-modify-write against the whole blob: not safe against concurrent
    writers (two bot instances, or two writes racing in-process) — there's
    no compare-and-swap on the account-data endpoint, so the last write wins
    and can clobber a concurrent change.
    """
    all_data = await _get_blob(client, account_data_type)
    users = all_data.setdefault("users", {})
    users[user_id] = data
    await _put_blob(client, account_data_type, all_data)


async def _get_blob(client: AsyncClient, account_data_type: str) -> Dict[str, Any]:
    """Fetch the whole blob stored under `account_data_type`, or {} if nothing's been saved yet."""
    response = await client.send(
        "GET", _path(client, account_data_type), headers=_auth_headers(client)
    )
    if response.status == 404:
        return {}
    response.raise_for_status()
    return await response.json()


async def _put_blob(
    client: AsyncClient, account_data_type: str, data: Dict[str, Any]
) -> None:
    """Overwrite the whole blob stored under `account_data_type` with `data`."""
    response = await client.send(
        "PUT",
        _path(client, account_data_type),
        data=json.dumps(data),
        headers=_auth_headers(client),
    )
    response.raise_for_status()


def _path(client: AsyncClient, account_data_type: str) -> str:
    """`/_matrix/client/v3/user/{botUserId}/account_data/{account_data_type}`."""
    assert client.user_id is not None  # set by a successful login
    return (
        f"/_matrix/client/v3/user/{quote(client.user_id, safe='')}"
        f"/account_data/{quote(account_data_type, safe='')}"
    )


def _auth_headers(client: AsyncClient) -> Dict[str, str]:
    assert client.access_token is not None  # set by a successful login
    return {
        "Authorization": f"Bearer {client.access_token}",
        "Content-Type": "application/json",
    }
