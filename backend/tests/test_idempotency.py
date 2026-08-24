"""Tests for the idempotency-key cache."""

from __future__ import annotations

import time

from services.idempotency import IdempotencyCache


class TestBasics:
    def test_a_missing_key_returns_none(self) -> None:
        assert IdempotencyCache().get("nope") is None

    def test_a_cached_value_is_returned(self) -> None:
        cache: IdempotencyCache = IdempotencyCache()
        cache.set("key-1", {"slice_id": "abc"})
        assert cache.get("key-1") == {"slice_id": "abc"}

    def test_setting_the_same_key_twice_overwrites(self) -> None:
        cache: IdempotencyCache = IdempotencyCache()
        cache.set("key-1", "first")
        cache.set("key-1", "second")
        assert cache.get("key-1") == "second"


class TestExpiry:
    def test_an_expired_entry_is_treated_as_absent(self) -> None:
        cache: IdempotencyCache = IdempotencyCache(ttl_seconds=0.05)
        cache.set("key-1", "value")
        time.sleep(0.1)
        assert cache.get("key-1") is None

    def test_reading_an_expired_entry_removes_it(self) -> None:
        cache: IdempotencyCache = IdempotencyCache(ttl_seconds=0.05)
        cache.set("key-1", "value")
        time.sleep(0.1)
        cache.get("key-1")
        assert cache.size() == 0


class TestBoundedGrowth:
    def test_the_cache_does_not_grow_past_its_configured_limit(self) -> None:
        cache: IdempotencyCache = IdempotencyCache(ttl_seconds=60, max_entries=10)
        for i in range(50):
            cache.set(f"key-{i}", i)
        assert cache.size() <= 10

    def test_eviction_prefers_dropping_expired_entries_first(self) -> None:
        # A long TTL for the cache as a whole avoids any timing race in this
        # test; the existing batch is forced stale directly rather than by
        # sleeping past a short TTL, which would make the test flaky under
        # load.
        cache: IdempotencyCache = IdempotencyCache(ttl_seconds=60, max_entries=5)
        for i in range(5):
            cache.set(f"stale-{i}", i)
        for entry in cache._entries.values():
            entry.expires_at = time.monotonic() - 1  # force-expire the whole batch

        # At capacity, so this insert triggers eviction. A full sweep of the
        # expired batch (rather than the oldest-half fallback) leaves
        # exactly the one entry just inserted.
        cache.set("keeper", "kept")

        assert cache.get("keeper") == "kept"
        assert cache.size() == 1


class TestClear:
    def test_clear_empties_the_cache(self) -> None:
        cache: IdempotencyCache = IdempotencyCache()
        cache.set("key-1", "value")
        cache.clear()
        assert cache.size() == 0
        assert cache.get("key-1") is None
