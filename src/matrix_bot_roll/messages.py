"""User-facing reply strings sent back to Matrix rooms."""

USAGE = "\n".join(
    [
        "• `!roll <expression> [expression ...] [target] [-v] [| message]` "
        "(or `!r`) — roll dice",
        "• `!roll --help` — detailed roll syntax and examples",
        "• `!reroll [| message]` (or `!rr`) — repeat the last roll",
        "• `!detail` (or `!d`) — show the full breakdown of the last roll in this room",
    ]
)

ROLL_HELP = "\n".join(
    [
        "**!roll <expression> [expression ...] [target] [-v] [| message]** "
        "(alias: `!r`)",
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
        "• `!roll d20+5 >15` — compare the total against a target number "
        "(`>`, `<`, `>=`, `<=`, `=`, `!=`) for pass/fail",
        "• `!roll 3d8+4 | attack` — attach a message to the roll",
        "• `!roll 4d6kh3 -v` (or `--verbose`) — show the full per-die breakdown "
        "(terse by default); the flag can go anywhere in the command",
    ]
)

NO_PREVIOUS_ROLL = "No previous roll in this room — use `!roll <expression>` first."

INVALID_ROLL = "Invalid roll expression — see `!roll --help` for syntax."
