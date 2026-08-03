import html
import re
from typing import List

from matrix_bot_roll.models import Die, DiceRollResult


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


def format_detail(result: DiceRollResult) -> str:
    """Build the '[rolls] keep highest N → [kept] +mod' detail string for one roll."""
    detail = f"[{', '.join(_format_die(d, result) for d in result.dice)}]"

    kept = [d for d in result.dice if d.kept]
    if result.adv_dis:
        detail += f" with {result.adv_dis} → [{_join_kept(kept, result)}]"
    elif result.keep_mode:
        detail += (
            f" keep {result.keep_mode} {result.keep_n} → [{_join_kept(kept, result)}]"
        )

    if result.modifier_mode == "total" and result.modifier:
        sign = "+" if result.modifier > 0 else ""
        detail += f" {sign}{result.modifier}"

    return detail


def _join_kept(kept: List[Die], result: DiceRollResult) -> str:
    """Render the comma-separated list of kept dice shown in the keep/advantage suffix."""
    return ", ".join(_kept_repr(d, result) for d in kept)


def _format_die(die: Die, result: DiceRollResult) -> str:
    """Render one rolled die as shown in the initial roll list."""
    if result.modifier_mode == "per_die":
        sign = "+" if result.modifier > 0 else "-"
        return f"{_mark(die.raw, result.sides)}{sign}{abs(result.modifier)}=**{die.value}**"
    return _mark(die.raw, result.sides)


def _kept_repr(die: Die, result: DiceRollResult) -> str:
    """Render one kept die as shown in the keep/advantage suffix."""
    if result.modifier_mode == "per_die":
        return f"**{die.value}**"
    return _mark(die.raw, result.sides)


def _mark(n: int, sides: int) -> str:
    """Render a raw die face, suffixed with 🎯/💥 if it's the max/min possible face on a die with `sides` sides."""
    if n == sides:
        return f"{n}🎯"
    elif n == 1:
        return f"{n}💥"
    return str(n)
