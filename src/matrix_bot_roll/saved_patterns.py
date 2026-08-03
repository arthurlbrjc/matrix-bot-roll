"""
Named dice-roll patterns a user has saved, so they can reuse `3d8+4` as
`attack` instead of retyping it (see `!save`).

Stored via `account_data.py` under `SAVED_PATTERNS_TYPE`, with the schema:

    {"users": {"<matrix user id>": {"<pattern name>": "<dice expression>"}}}

One blob for every user the bot has ever seen, all under the bot's own
account — nio (and the Matrix API in general) give a bot no way to write
into a caller's account, so per-user data has to be namespaced inside the
bot's own blob instead of using separate per-user account data.
"""

import logging
import re
from typing import Any, Dict, Optional

from nio import AsyncClient

from matrix_bot_roll import account_data
from matrix_bot_roll.constants import (
    MAX_PATTERN_NAME_LENGTH,
    MAX_SAVED_PATTERNS_PER_USER,
)

logger = logging.getLogger(__name__)

# Reverse-DNS namespaced per Matrix convention for custom account data types,
# to avoid colliding with a client's or the spec's own `m.*` types.
SAVED_PATTERNS_TYPE = "roll.matrix-bot.saved_patterns"

# Lowercase letters, `_`, and `-` only — no digits. Every dice expression the
# parser accepts (see commands.py's DICE_WITH_*_MODIFIER_RE) requires at least
# one digit (a side count, at minimum), so barring digits entirely keeps a
# saved name from ever colliding with dice notation (e.g. `d20`) without this
# module needing to know anything about dice syntax.
_NAME_RE = re.compile(r"^[a-z][a-z_-]*$")


def is_valid_name(name: str) -> bool:
    """Whether `name` is a legal saved-pattern name: lowercase, starts with a
    letter, only letters/`_`/`-` (no digits, so it can never collide with dice
    notation), at most `MAX_PATTERN_NAME_LENGTH` characters."""
    return len(name) <= MAX_PATTERN_NAME_LENGTH and bool(_NAME_RE.match(name))


async def get_pattern(client: AsyncClient, user_id: str, name: str) -> Optional[str]:
    """Fetch `user_id`'s saved expression for `name`, or None if they have no pattern by that name."""
    all_data = await account_data.get_blob(client, SAVED_PATTERNS_TYPE)
    return all_data.get("users", {}).get(user_id, {}).get(name)


async def save_pattern(client: AsyncClient, user_id: str, name: str, expr: str) -> bool:
    """
    Add `name` for `user_id`, or overwrite it if already saved.

    Returns False (without writing anything) if `name` is new and `user_id`
    already has `MAX_SAVED_PATTERNS_PER_USER` patterns saved — every user
    shares the same account-data blob (see module docstring), so this cap
    protects the whole blob's size budget from any single user, not just
    that user's own data.

    Not safe against concurrent writers (two bot instances, or two saves
    racing in-process): there's no compare-and-swap on the account-data
    endpoint, so the last write wins and can clobber a concurrent change.
    Fine for a single bot instance handling messages one at a time; would
    need real locking (or a different store) before running more than one
    instance.
    """
    all_data = await account_data.get_blob(client, SAVED_PATTERNS_TYPE)
    users = all_data.setdefault("users", {})
    patterns = users.get(user_id, {})

    if name not in patterns and len(patterns) >= MAX_SAVED_PATTERNS_PER_USER:
        return False

    new_patterns = {**patterns, name: expr}
    if new_patterns == patterns:
        return True  # already saved with this exact expression — nothing to write

    users[user_id] = new_patterns
    await _update_patterns(client, all_data)
    return True


async def _update_patterns(client: AsyncClient, all_data: Dict[str, Any]) -> None:
    """
    Persist `all_data` as the new saved-patterns blob.

    Call only once the caller has confirmed there's an actual change to
    write — this always performs the write, unconditionally.
    """
    await account_data.put_blob(client, SAVED_PATTERNS_TYPE, all_data)
