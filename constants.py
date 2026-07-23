import re

# Matches things like: 1d20, 2d6+4, d8, 3d10-2, 2d20kh1, 4d6kl3, 2d20adv, 2d20dis
DICE_WITH_TOTAL_MODIFIER_RE = re.compile(
    r"^(\d*)\s*d\s*(\d+)\s*(kh\d+|kl\d+|adv|dis)?\s*([+-]\s*\d+)?$", re.IGNORECASE
)

# Matches a per-die modifier group like: 4(d10+2), 3(d6-1), 4(d10+2)kh1 — the
# modifier is applied to each die individually rather than once to the summed
# total; an optional keep/advantage suffix (outside the parens) then selects
# among the modified values.
DICE_WITH_DIE_MODIFIER_RE = re.compile(
    r"^(\d+)\(\s*d\s*(\d+)\s*([+-]\s*\d+)\s*\)\s*(kh\d+|kl\d+|adv|dis)?$",
    re.IGNORECASE,
)
