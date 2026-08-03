"""Unit tests for the bounded LRU dict in lru_dict.py."""

from matrix_bot_roll.lru_dict import LRUDict


class TestLRUDict:
    def test_get_returns_none_for_missing_key(self):
        cache: LRUDict[str] = LRUDict(max_size=2)
        assert cache.get("missing") is None

    def test_set_then_get_returns_value(self):
        cache: LRUDict[str] = LRUDict(max_size=2)
        cache["a"] = "value-a"
        assert cache.get("a") == "value-a"

    def test_set_over_capacity_evicts_least_recently_used(self):
        cache: LRUDict[str] = LRUDict(max_size=2)
        cache["a"] = "value-a"
        cache["b"] = "value-b"
        cache["c"] = "value-c"
        assert cache.get("a") is None
        assert cache.get("b") == "value-b"
        assert cache.get("c") == "value-c"

    def test_get_refreshes_recency_and_saves_entry_from_eviction(self):
        cache: LRUDict[str] = LRUDict(max_size=2)
        cache["a"] = "value-a"
        cache["b"] = "value-b"
        cache.get("a")
        cache["c"] = "value-c"
        assert cache.get("a") == "value-a"
        assert cache.get("b") is None
        assert cache.get("c") == "value-c"

    def test_overwriting_existing_key_refreshes_recency(self):
        cache: LRUDict[str] = LRUDict(max_size=2)
        cache["a"] = "value-a"
        cache["b"] = "value-b"
        cache["a"] = "value-a-updated"
        cache["c"] = "value-c"
        assert cache.get("a") == "value-a-updated"
        assert cache.get("b") is None
