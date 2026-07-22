import html
import re


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