import asyncio
import logging
import os
import signal

from dotenv import load_dotenv
from nio import AsyncClient, AsyncClientConfig, MatrixRoom, MegolmEvent, RoomMessageText
from nio.exceptions import LocalProtocolError
from nio.responses import LoginResponse, WhoamiResponse

from session_store import SavedSession, load_session, save_session

load_dotenv()

logger = logging.getLogger(__name__)

HOMESERVER = os.environ["MATRIX_BASE_URL"]
USER_ID = os.environ["MATRIX_USER_ID"]
PASSWORD = os.environ["MATRIX_PASSWORD"]
STORE_PATH = os.environ["MATRIX_STORE_PATH"]
DEVICE_NAME = os.environ["MATRIX_DEVICE_NAME"]
SESSION_MODE = os.environ.get("MATRIX_SESSION_MODE", "fresh")
SESSION_ENCRYPTION_KEY = os.environ.get("MATRIX_SESSION_ENCRYPTION_KEY")
os.makedirs(STORE_PATH, exist_ok=True)
SESSION_FILE = os.path.join(STORE_PATH, "session.enc")

if SESSION_MODE not in ("fresh", "persistent"):
    raise ValueError(
        f"MATRIX_SESSION_MODE must be 'fresh' or 'persistent', got {SESSION_MODE!r}"
    )
if SESSION_MODE == "persistent" and not SESSION_ENCRYPTION_KEY:
    raise ValueError(
        "MATRIX_SESSION_ENCRYPTION_KEY is required when MATRIX_SESSION_MODE=persistent"
    )


async def run_client(message_callback):
    """
    Log in, wire up event callbacks, and run the sync loop until a
    shutdown signal (SIGINT/SIGTERM) is received.

    `message_callback` is called as `message_callback(client, room, event)`.
    """
    config = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)
    client = AsyncClient(HOMESERVER, USER_ID, config=config, store_path=STORE_PATH)

    stop_event = asyncio.Event()

    def request_shutdown():
        logger.info("Shutdown requested, closing connections")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    try:
        if not await _authenticate(client):
            return

        logger.info("Logged in", extra={"user_id": client.user_id})

        client.add_event_callback(
            lambda room, event: message_callback(client, room, event), RoomMessageText
        )
        client.add_event_callback(
            lambda room, event: _request_missing_session_key(client, room, event),
            MegolmEvent,
        )

        await client.sync(timeout=30000, full_state=True)

        # Run sync_forever as a background task so we can race it
        # against the shutdown signal instead of blocking on it.
        sync_task = asyncio.create_task(
            client.sync_forever(timeout=30000, full_state=False)
        )
        stop_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            {sync_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Surface any real error sync_forever raised (not just cancellation)
        if sync_task in done:
            exc = sync_task.exception()
            if exc is not None:
                raise exc

    finally:
        logger.info("Closing Matrix client")
        if SESSION_MODE == "persistent":
            logger.info("Keeping session for reuse on next start (persistent mode)")
        else:
            try:
                await client.logout()
            except Exception:
                logger.warning("Failed to log out cleanly", exc_info=True)
        await client.close()
        logger.info("Done")


async def _authenticate(client: AsyncClient) -> bool:
    """Log `client` in, reusing a saved session in persistent mode when it's still valid.

    Returns True on success. On failure, logs the reason and returns False.
    """
    if SESSION_MODE == "persistent":
        assert SESSION_ENCRYPTION_KEY is not None  # enforced at module load
        saved = load_session(SESSION_FILE, SESSION_ENCRYPTION_KEY)
        if saved is None:
            logger.info("No session found, logging in fresh")
        elif await _restore_saved_session(client, saved):
            return True

    login_response = await client.login(PASSWORD, device_name=DEVICE_NAME)
    if not isinstance(login_response, LoginResponse):
        logger.error("Failed to authenticate", extra={"response": str(login_response)})
        return False
    assert client.device_id is not None  # set by a successful login
    assert client.access_token is not None  # set by a successful login

    if SESSION_MODE == "persistent":
        assert SESSION_ENCRYPTION_KEY is not None  # enforced at module load
        save_session(
            SESSION_FILE,
            SESSION_ENCRYPTION_KEY,
            SavedSession(
                user_id=client.user_id,
                device_id=client.device_id,
                access_token=client.access_token,
            ),
        )

    return True


async def _restore_saved_session(client: AsyncClient, saved: SavedSession) -> bool:
    """Try restoring a saved session, verifying the token is still valid with the server."""
    client.restore_login(
        user_id=saved.user_id,
        device_id=saved.device_id,
        access_token=saved.access_token,
    )
    whoami_response = await client.whoami()
    if not isinstance(whoami_response, WhoamiResponse):
        logger.warning(
            "Saved session is no longer valid, logging in fresh instead",
            extra={"response": str(whoami_response)},
        )
        return False
    logger.info("Reusing saved session", extra={"user_id": client.user_id})
    return True


async def _request_missing_session_key(
    client: AsyncClient, room: MatrixRoom, event: MegolmEvent
) -> None:
    """Ask the sending device to (re)share a Megolm session we failed to decrypt.

    Needed because a fresh/reset crypto store has no Olm session with devices
    it talked to before, so senders won't proactively re-share the session.
    """
    logger.warning(
        "Requesting missing room key",
        extra={"room_id": room.room_id, "session_id": event.session_id},
    )
    try:
        await client.request_room_key(event)
    except LocalProtocolError:
        logger.info(
            "Room key already requested for this session",
            extra={"session_id": event.session_id},
        )
