from collections import OrderedDict
from typing import Generic, Optional

from matrix_bot_roll.typevars import T


class LRUDict(Generic[T]):
    """A dict capped at `max_size` entries, evicting the least-recently-used
    one (by `get`/`set`, not just `set`) once that cap is exceeded — keeps
    per-room state bounded for a bot that may be invited into arbitrarily
    many rooms over its lifetime."""

    def __init__(self, max_size: int):
        self._max_size = max_size
        self._entries: "OrderedDict[str, T]" = OrderedDict()

    def get(self, key: str) -> Optional[T]:
        value = self._entries.get(key)
        if value is not None:
            self._entries.move_to_end(key)
        return value

    def __setitem__(self, key: str, value: T) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        if len(self._entries) > self._max_size:
            self._entries.popitem(last=False)
