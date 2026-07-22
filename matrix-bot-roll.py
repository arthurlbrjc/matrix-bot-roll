import asyncio
import html
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

# Matches things like: 1d20, 2d6+4, d8, 3d10-2, 2d20kh1, 4d6kl3, 2d20adv, 2d20dis
DICE_RE = re.compile(
    r"^(\d*)\s*d\s*(\d+)\s*(kh\d+|kl\d+|adv|dis)?\s*([+-]\s*\d+)?$", re.IGNORECASE
)

# Matches a per-die modifier group like: 4(d10+2), 3(d6-1), 4(d10+2)kh1 — the
# modifier is applied to each die individually rather than once to the summed
# total; an optional keep/advantage suffix (outside the parens) then selects
# among the modified values.
GROUP_DICE_RE = re.compile(
    r"^(\d+)\(\s*d\s*(\d+)\s*([+-]\s*\d+)\s*\)\s*(kh\d+|kl\d+|adv|dis)?$",
    re.IGNORECASE,
)


def roll_multiple(input_str: str):
    """
    Parse and roll multiple space-separated dice expressions, e.g. '4d20 1d6+2'.

    Returns a list of tuples: (expr, result_or_None)
    where result_or_None is (total, detail_str, crit) from roll_dice, or None if invalid.
    """
    exprs = input_str.split()
    if not exprs:
        return []

    return [(expr, roll_dice(expr)) for expr in exprs]


def roll_dice_group(count: int, sides: int, modifier: int, keep_str: str = None):
    """
    Roll `count` dice of `sides`, applying `modifier` to each die individually,
    then optionally keep/advantage-select among the modified values via `keep_str`
    (kh#, kl#, adv, dis) exactly like the plain dice syntax does with raw rolls.
    """
    if count < 1 or count > 100 or sides < 2 or sides > 1000:
        return None

    keep_mode = None
    keep_n = None
    adv_dis = None
    if keep_str:
        keep_str = keep_str.lower()
        if keep_str == "adv":
            keep_mode, keep_n = "h", count
            count += 1  # adv/dis roll one extra die, then drop the single worst/best
            adv_dis = "advantage"
        elif keep_str == "dis":
            keep_mode, keep_n = "l", count
            count += 1
            adv_dis = "disadvantage"
        else:
            keep_mode, keep_n = keep_str[1], int(keep_str[2:])

        if count > 100 or keep_n < 1 or keep_n > count:
            return None

    rolls = [random.randint(1, sides) for _ in range(count)]

    def mark(n):
        if n == sides:
            return f"{n}🎯"
        elif n == 1:
            return f"{n}💥"
        return str(n)

    sign = "+" if modifier > 0 else "-"
    modified = [max(0, r + modifier) for r in rolls]
    pairs = list(zip(rolls, modified))
    detail = f"[{', '.join(f'{mark(r)}{sign}{abs(modifier)}=**{m}**' for r, m in pairs)}]"

    if keep_mode == "h":
        kept = sorted(pairs, key=lambda p: p[1], reverse=True)[:keep_n]
    elif keep_mode == "l":
        kept = sorted(pairs, key=lambda p: p[1])[:keep_n]
    else:
        kept = pairs

    total = sum(m for _, m in kept)

    if adv_dis:
        detail += f" with {adv_dis} → [{', '.join(f'**{m}**' for _, m in kept)}]"
    elif keep_mode:
        word = "highest" if keep_mode == "h" else "lowest"
        detail += f" keep {word} {keep_n} → [{', '.join(f'**{m}**' for _, m in kept)}]"

    # A single kept die at its raw max/min face is a natural crit/fumble.
    crit = None
    if len(kept) == 1:
        raw = kept[0][0]
        if raw == sides:
            crit = "crit"
        elif raw == 1:
            crit = "fumble"

    return total, detail, crit


def roll_dice(expr: str):
    """Parse and roll a dice expression like '2d6+4' or '2d20kh1'. Returns (total, detail_str, crit) or None."""
    expr = expr.strip()

    group_match = GROUP_DICE_RE.match(expr)
    if group_match:
        count_str, sides_str, modifier_str, keep_str = group_match.groups()
        return roll_dice_group(
            int(count_str),
            int(sides_str),
            int(modifier_str.replace(" ", "")),
            keep_str,
        )

    match = DICE_RE.match(expr)
    if not match:
        return None

    count_str, sides_str, keep_str, modifier_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0

    # Sanity limits so nobody rolls 999999d999999 and hangs the bot
    if count < 1 or count > 100 or sides < 2 or sides > 1000:
        return None

    keep_mode = None
    keep_n = None
    adv_dis = None
    if keep_str:
        keep_str = keep_str.lower()
        if keep_str == "adv":
            keep_mode, keep_n = "h", count
            count += 1  # adv/dis roll one extra die, then drop the single worst/best
            adv_dis = "advantage"
        elif keep_str == "dis":
            keep_mode, keep_n = "l", count
            count += 1
            adv_dis = "disadvantage"
        else:
            keep_mode, keep_n = keep_str[1], int(keep_str[2:])

        if count > 100 or keep_n < 1 or keep_n > count:
            return None

    rolls = [random.randint(1, sides) for _ in range(count)]

    if keep_mode == "h":
        kept = sorted(rolls, reverse=True)[:keep_n]
    elif keep_mode == "l":
        kept = sorted(rolls)[:keep_n]
    else:
        kept = rolls

    total = max(0, sum(kept) + modifier)

    def mark(n):
        if n == sides:
            return f"{n}🎯"
        elif n == 1:
            return f"{n}💥"
        return str(n)

    detail = f"[{', '.join(mark(r) for r in rolls)}]"
    if adv_dis:
        detail += f" with {adv_dis} → [{', '.join(mark(r) for r in kept)}]"
    elif keep_mode:
        word = "highest" if keep_mode == "h" else "lowest"
        detail += f" keep {word} {keep_n} → [{', '.join(mark(r) for r in kept)}]"
    if modifier:
        sign = "+" if modifier > 0 else ""
        detail += f" {sign}{modifier}"

    # A single kept die at its max/min face is a natural crit/fumble.
    crit = None
    if len(kept) == 1:
        if kept[0] == sides:
            crit = "crit"
        elif kept[0] == 1:
            crit = "fumble"

    return total, detail, crit


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
        total, detail, crit = result
        suffix = " 🎯 CRIT!" if crit == "crit" else " 💥 FUMBLE!" if crit == "fumble" else ""
        lines.append(f"🎲 {expr} → {detail} = **{total}**{suffix}")
        grand_total += total
        valid_count += 1

    if valid_count > 1:
        lines.append(f"**Total: {grand_total}**")

    return "\n".join(lines)


def markdown_to_html(text: str) -> str:
    """Convert **bold** and `code` markers to HTML, coloring crit/fumble totals green/red."""
    text = html.escape(text, quote=False)
    text = re.sub(
        r"\*\*(.+?)\*\* 🎯 CRIT!",
        r'<b><font color="green">\1 CRIT!</font></b>',
        text,
    )
    text = re.sub(
        r"\*\*(.+?)\*\* 💥 FUMBLE!",
        r'<b><font color="red">\1 FUMBLE!</font></b>',
        text,
    )
    text = re.sub(r"(\d+)🎯", r'<b><font color="green">\1</font></b>🎯', text)
    text = re.sub(r"(\d+)💥", r'<b><font color="red">\1</font></b>💥', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


async def message_callback(client: AsyncClient, room: MatrixRoom, event: RoomMessageText):
    # Ignore our own messages
    if event.sender == client.user_id:
        return

    body = event.body.strip()
    if not body.startswith("!roll"):
        return

    parts = body.split(maxsplit=1)
    if len(parts) < 2:
        reply = "\n".join(
            [
                "**Usage: !roll <expression> [expression ...]**",
                "",
                "• `!roll d20` — roll one die",
                "• `!roll 4d6` — roll multiple dice",
                "• `!roll 2d6+4` — add +/- modifiers",
                "• `!roll 4d6kh3`, `!roll 4d6kl3` — keep highest/lowest dice",
                "• `!roll 2d20adv`, `!roll 2d20dis` — advantage/disadvantage "
                "(add one die then keep X highest/lowest)",
                "• `!roll 4(d10+2)`, `!roll 4(d10+2)kh1`, `!roll 2(d20+3)adv` "
                "— per-die modifier and adv/dis/kh/kl",
                "• `!roll 2d6kh1+4 3(d10-2)adv` — combine everything",
            ]
        )
    else:
        expr = parts[1].strip()
        results = roll_multiple(expr)
        reply = format_roll_results(results)

    content = {
        "msgtype": "m.text",
        "body": reply,
        "format": "org.matrix.custom.html",
        "formatted_body": markdown_to_html(reply).replace("\n", "<br/>"),
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
