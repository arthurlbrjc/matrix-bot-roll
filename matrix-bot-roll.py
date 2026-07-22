import asyncio
import os
import random
import re
import signal
import sys

from dotenv import load_dotenv
from nio import (
    AsyncClient,
    AsyncClientConfig,
    InviteMemberEvent,
    MatrixRoom,
    RoomMessageText,
)

print(f"Starting bot, PID={os.getpid()}", flush=True)

# --- Load config from .env ---
load_dotenv()

HOMESERVER = os.environ["MATRIX_BASE_URL"]
USER_ID = os.environ["MATRIX_USER_ID"]
ACCESS_TOKEN = os.environ["MATRIX_ACCESS_TOKEN"]
DEVICE_ID = os.environ["MATRIX_DEVICE_ID"]
STORE_PATH = os.environ["MATRIX_STORE_PATH"]
os.makedirs(STORE_PATH, exist_ok=True)

# Matches things like: 1d20, 2d6+4, d8, 3d10-2 (tolerates stray whitespace)
DICE_RE = re.compile(r"^(\d*)\s*d\s*(\d+)\s*([+-]\s*\d+)?$", re.IGNORECASE)


def roll_multiple(input_str: str):
    """
    Parse and roll multiple space-separated dice expressions, e.g. '4d20 1d6+2'.

    Returns a list of tuples: (expr, result_or_None)
    where result_or_None is (total, detail_str) from roll_dice, or None if invalid.
    """
    exprs = input_str.split()
    if not exprs:
        return []

    return [(expr, roll_dice(expr)) for expr in exprs]


def roll_dice(expr: str):
    """Parse and roll a dice expression like '2d6+4'. Returns (total, detail_str) or None."""
    match = DICE_RE.match(expr.strip())
    if not match:
        return None

    count_str, sides_str, modifier_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0

    # Sanity limits so nobody rolls 999999d999999 and hangs the bot
    if count < 1 or count > 100 or sides < 2 or sides > 1000:
        return None

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    detail = f"[{', '.join(map(str, rolls))}]"
    if modifier:
        sign = "+" if modifier > 0 else ""
        detail += f" {sign}{modifier}"

    return total, detail


def format_roll_results(results):
    """
    Turn roll_multiple() output into a human-readable string.
    Invalid expressions are flagged; valid ones show total + detail.
    Also appends a grand total across all valid rolls if there's more than one.
    """
    lines = []
    grand_total = 0
    valid_count = 0

    for expr, result in results:
        if result is None:
            lines.append(f"`{expr}` → invalid expression")
            continue
        total, detail = result
        lines.append(f"🎲 {expr} → {detail} = **{total}**")
        grand_total += total
        valid_count += 1

    if valid_count > 1:
        lines.append(f"**Total: {grand_total}**")

    return "\n".join(lines)


def markdown_bold_to_html(text: str) -> str:
    """Convert all **bold** markers to <b>bold</b>, not just the first pair."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


async def message_callback(client: AsyncClient, room: MatrixRoom, event: RoomMessageText):
    # Ignore our own messages
    if event.sender == client.user_id:
        return

    body = event.body.strip()
    if not body.startswith("!roll"):
        return

    parts = body.split(maxsplit=1)
    if len(parts) < 2:
        reply = "Usage: !roll 1d20, !roll 2d6+4, !roll 4d20 1d6, etc."
    else:
        expr = parts[1].strip()
        results = roll_multiple(expr)
        reply = format_roll_results(results)

    content = {
        "msgtype": "m.text",
        "body": reply,
        "format": "org.matrix.custom.html",
        "formatted_body": markdown_bold_to_html(reply).replace("\n", "<br/>"),
    }

    await client.room_send(
        room_id=room.room_id,
        message_type="m.room.message",
        content=content,
        ignore_unverified_devices=True
    )


async def invite_callback(client: AsyncClient, room):
    await client.join(room.room_id)
    print(f"Joined room {room.room_id}")


async def main():
    config = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)
    client = AsyncClient(HOMESERVER, USER_ID, device_id=DEVICE_ID, config=config, store_path=STORE_PATH)

    client.restore_login(
        user_id=USER_ID,
        device_id=DEVICE_ID,
        access_token=ACCESS_TOKEN,
    )

    stop_event = asyncio.Event()

    def request_shutdown():
        print(f"\nShutdown requested, closing connections...")
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback in case signal handlers didn't fire in time (e.g. Windows)
        print("\nInterrupted.")
