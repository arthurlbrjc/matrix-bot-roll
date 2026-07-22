import asyncio
import os
import signal
import sys

from dotenv import load_dotenv
from nio import AsyncClient, AsyncClientConfig, InviteMemberEvent, RoomMessageText

load_dotenv()

HOMESERVER = os.environ["MATRIX_BASE_URL"]
USER_ID = os.environ["MATRIX_USER_ID"]
ACCESS_TOKEN = os.environ["MATRIX_ACCESS_TOKEN"]
DEVICE_ID = os.environ["MATRIX_DEVICE_ID"]
STORE_PATH = os.environ["MATRIX_STORE_PATH"]
os.makedirs(STORE_PATH, exist_ok=True)


async def run_client(message_callback, invite_callback):
    """
    Log in, wire up event callbacks, and run the sync loop until a
    shutdown signal (SIGINT/SIGTERM) is received.

    `message_callback` and `invite_callback` are called as
    `message_callback(client, room, event)` and `invite_callback(client, room)`.
    """
    config = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)
    client = AsyncClient(
        HOMESERVER, USER_ID, device_id=DEVICE_ID, config=config, store_path=STORE_PATH
    )

    client.restore_login(
        user_id=USER_ID,
        device_id=DEVICE_ID,
        access_token=ACCESS_TOKEN,
    )

    stop_event = asyncio.Event()

    def request_shutdown():
        print("\nShutdown requested, closing connections...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    try:
        whoami = await client.whoami()
        if not hasattr(whoami, "user_id"):
            print(f"Failed to authenticate: {whoami}", file=sys.stderr)
            return

        print(f"Logged in as {whoami.user_id}")

        client.add_event_callback(
            lambda room, event: message_callback(client, room, event), RoomMessageText
        )
        client.add_event_callback(
            lambda room, event: invite_callback(client, room), InviteMemberEvent
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
        print("Closing Matrix client...")
        await client.close()
        print("Done.")
