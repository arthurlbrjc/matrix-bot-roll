import random
import re

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