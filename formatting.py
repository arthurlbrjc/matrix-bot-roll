import html
import re
from typing import List, Optional, Tuple

from dice import Die, RollResult


def format_roll_results(results: List[Tuple[str, Optional[RollResult]]]) -> str:
    """
    Turn roll() output into a human-readable string.
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
        suffix = (
            " 🎯 CRIT!"
            if result.crit == "crit"
            else " 💥 FUMBLE!" if result.crit == "fumble" else ""
        )
        lines.append(
            f"🎲 {expr} → {_format_detail(result)} = **{result.total}**{suffix}"
        )
        grand_total += result.total
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


def _format_detail(result: RollResult) -> str:
    """Build the '[rolls] keep highest N → [kept] +mod' detail string for one roll."""
    detail = f"[{', '.join(_format_die(d, result) for d in result.dice)}]"

    kept = [d for d in result.dice if d.kept]
    if result.adv_dis:
        detail += f" with {result.adv_dis} → [{_join_kept(kept, result)}]"
    elif result.keep_mode:
        word = "highest" if result.keep_mode == "h" else "lowest"
        detail += f" keep {word} {result.keep_n} → [{_join_kept(kept, result)}]"

    if result.modifier_mode == "total" and result.modifier:
        sign = "+" if result.modifier > 0 else ""
        detail += f" {sign}{result.modifier}"

    return detail


def _join_kept(kept: List[Die], result: RollResult) -> str:
    return ", ".join(_kept_repr(d, result) for d in kept)


def _format_die(die: Die, result: RollResult) -> str:
    """Render one rolled die as shown in the initial roll list."""
    if result.modifier_mode == "per_die":
        sign = "+" if result.modifier > 0 else "-"
        return f"{_mark(die.raw, result.sides)}{sign}{abs(result.modifier)}=**{die.value}**"
    return _mark(die.raw, result.sides)


def _kept_repr(die: Die, result: RollResult) -> str:
    """Render one kept die as shown in the keep/advantage suffix."""
    if result.modifier_mode == "per_die":
        return f"**{die.value}**"
    return _mark(die.raw, result.sides)


def _mark(n: int, sides: int) -> str:
    if n == sides:
        return f"{n}🎯"
    elif n == 1:
        return f"{n}💥"
    return str(n)
