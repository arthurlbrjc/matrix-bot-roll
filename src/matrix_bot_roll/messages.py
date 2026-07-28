"""User-facing reply strings sent back to Matrix rooms."""

USAGE = "\n".join(
    [
        "• `!roll <expression> [expression ...] [| message]` (or `!r`) — roll dice",
        "• `!roll --help` — detailed roll syntax and examples",
        "• `!reroll` (or `!rr`) — repeat the last `!roll` expression in this room",
    ]
)

ROLL_HELP = "\n".join(
    [
        "**!roll <expression> [expression ...] [| message]** (alias: `!r`)",
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
        "• `!roll 3d8+4 | attack` — attach a message to the roll",
    ]
)

NO_PREVIOUS_ROLL = (
    "No previous roll to repeat in this room — use `!roll <expression>` first."
)
