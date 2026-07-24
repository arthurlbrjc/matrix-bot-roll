"""Unit tests for the login/logout flow in matrix_client.py."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("MATRIX_BASE_URL", "https://example.invalid")
os.environ.setdefault("MATRIX_USER_ID", "@bot:example.invalid")
os.environ.setdefault("MATRIX_PASSWORD", "unused-test-password")
os.environ.setdefault("MATRIX_DEVICE_NAME", "matrix-bot-roll-test")
os.environ.setdefault("MATRIX_STORE_PATH", "/tmp/matrix-bot-roll-test-store")

from nio.responses import (  # noqa: E402
    LoginError,
    LoginResponse,
    WhoamiError,
    WhoamiResponse,
)

import matrix_client  # noqa: E402
from session_store import SavedSession  # noqa: E402


def fake_client(monkeypatch, login_response):
    """Patch matrix_client.AsyncClient to return a fake client instance.

    The fake client's `login` resolves to `login_response`; `sync_forever`
    completes immediately so `run_client` doesn't block indefinitely.
    """
    client = MagicMock()
    client.login = AsyncMock(return_value=login_response)
    client.logout = AsyncMock()
    client.close = AsyncMock()
    client.sync = AsyncMock()
    client.sync_forever = AsyncMock(return_value=None)
    client.add_event_callback = MagicMock()
    client.restore_login = MagicMock()
    client.whoami = AsyncMock()

    monkeypatch.setattr(matrix_client, "AsyncClient", MagicMock(return_value=client))
    return client


def use_persistent_mode(monkeypatch):
    """Switch matrix_client (already imported) into MATRIX_SESSION_MODE=persistent."""
    monkeypatch.setattr(matrix_client, "SESSION_MODE", "persistent")
    monkeypatch.setattr(matrix_client, "SESSION_ENCRYPTION_KEY", "test-key")


def test_run_client_logs_in_and_logs_out(monkeypatch):
    login_response = LoginResponse(
        user_id="@bot:example.invalid", device_id="ABCDEF", access_token="tok"
    )
    client = fake_client(monkeypatch, login_response)
    client.user_id = login_response.user_id

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.login.assert_awaited_once_with(
        matrix_client.PASSWORD, device_name=matrix_client.DEVICE_NAME
    )
    client.sync.assert_awaited_once()
    client.logout.assert_awaited_once()
    client.close.assert_awaited_once()


def test_run_client_returns_early_on_login_failure(monkeypatch):
    login_error = LoginError(message="invalid credentials")
    client = fake_client(monkeypatch, login_error)

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.sync.assert_not_awaited()
    client.close.assert_awaited_once()


def test_run_client_logout_failure_does_not_block_close(monkeypatch):
    login_response = LoginResponse(
        user_id="@bot:example.invalid", device_id="ABCDEF", access_token="tok"
    )
    client = fake_client(monkeypatch, login_response)
    client.user_id = login_response.user_id
    client.logout.side_effect = asyncio.TimeoutError("logout timed out")

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.close.assert_awaited_once()


def test_run_client_persistent_mode_reuses_valid_saved_session(monkeypatch):
    use_persistent_mode(monkeypatch)
    saved = SavedSession(
        user_id="@bot:example.invalid", device_id="ABCDEF", access_token="saved-tok"
    )
    monkeypatch.setattr(matrix_client, "load_session", MagicMock(return_value=saved))
    save_session = MagicMock()
    monkeypatch.setattr(matrix_client, "save_session", save_session)

    client = fake_client(monkeypatch, login_response=None)
    client.user_id = saved.user_id
    client.whoami.return_value = WhoamiResponse(
        user_id=saved.user_id, device_id=saved.device_id, is_guest=False
    )

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.restore_login.assert_called_once_with(
        user_id=saved.user_id,
        device_id=saved.device_id,
        access_token=saved.access_token,
    )
    client.login.assert_not_awaited()
    save_session.assert_not_called()
    client.logout.assert_not_awaited()
    client.close.assert_awaited_once()


def test_run_client_persistent_mode_falls_back_when_saved_session_invalid(monkeypatch):
    use_persistent_mode(monkeypatch)
    saved = SavedSession(
        user_id="@bot:example.invalid", device_id="STALE", access_token="stale-tok"
    )
    monkeypatch.setattr(matrix_client, "load_session", MagicMock(return_value=saved))
    save_session = MagicMock()
    monkeypatch.setattr(matrix_client, "save_session", save_session)

    login_response = LoginResponse(
        user_id="@bot:example.invalid", device_id="NEWDEV", access_token="new-tok"
    )
    client = fake_client(monkeypatch, login_response)
    client.user_id = login_response.user_id
    client.device_id = login_response.device_id
    client.access_token = login_response.access_token
    client.whoami.return_value = WhoamiError(message="unknown token")

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.login.assert_awaited_once()
    save_session.assert_called_once()
    saved_arg = save_session.call_args.args[2]
    assert saved_arg.device_id == "NEWDEV"
    client.logout.assert_not_awaited()
    client.close.assert_awaited_once()


def test_run_client_persistent_mode_saves_session_on_fresh_login(monkeypatch):
    use_persistent_mode(monkeypatch)
    monkeypatch.setattr(matrix_client, "load_session", MagicMock(return_value=None))
    save_session = MagicMock()
    monkeypatch.setattr(matrix_client, "save_session", save_session)

    login_response = LoginResponse(
        user_id="@bot:example.invalid", device_id="NEWDEV", access_token="new-tok"
    )
    client = fake_client(monkeypatch, login_response)
    client.user_id = login_response.user_id
    client.device_id = login_response.device_id
    client.access_token = login_response.access_token

    asyncio.run(matrix_client.run_client(AsyncMock()))

    client.restore_login.assert_not_called()
    save_session.assert_called_once()
    client.logout.assert_not_awaited()
    client.close.assert_awaited_once()
