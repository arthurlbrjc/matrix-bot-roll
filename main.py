import asyncio
import os

from nio import AsyncClient, MatrixRoom, RoomMessageText

from dice import roll
from formatting import format_roll_results, markdown_to_html
from matrix_client import run_client

print(f"Starting bot, PID={os.getpid()}", flush=True)

_last_rolls: dict[str, str] = {}


async def message_callback(
    client: AsyncClient, room: MatrixRoom, event: RoomMessageText
):
    # Ignore our own messages
    if event.sender == client.user_id:
        return

    body = event.body.strip()
    if body.startswith("!reroll"):
        reply = _handle_reroll(room.room_id)
    elif body.startswith("!roll"):
        reply = _handle_roll(room.room_id, body)
    else:
        return

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
        ignore_unverified_devices=True,
    )


def _handle_roll(room_id: str, body: str) -> str:
    """Handle a `!roll <expression>` message, remembering the expression for `!reroll`."""
    parts = body.split(maxsplit=1)
    if len(parts) < 2:
        return "\n".join(
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
                "• `!reroll` — repeat the last `!roll` expression in this room",
            ]
        )

    expr = parts[1].strip()
    _last_rolls[room_id] = expr
    return format_roll_results(roll(expr))


def _handle_reroll(room_id: str) -> str:
    """Handle a `!reroll` message by re-running the last `!roll` expression in this room."""
    expr = _last_rolls.get(room_id)
    if expr is None:
        return (
            "No previous roll to repeat in this room — use `!roll <expression>` first."
        )
    return format_roll_results(roll(expr))


async def invite_callback(client: AsyncClient, room):
    await client.join(room.room_id)
    print(f"Joined room {room.room_id}")


async def main():
    await run_client(message_callback, invite_callback)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback in case signal handlers didn't fire in time (e.g. Windows)
        print("\nInterrupted.")
