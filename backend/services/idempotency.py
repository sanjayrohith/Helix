"""Idempotency key support for the provisioning endpoint.

A retried request - a client-side timeout, a double-click, a proxy that
retries on a dropped connection - looks identical to a genuine second
request. Without something to recognise the retry, HELIX provisions a second
slice for the same intent. An Idempotency-Key header lets the caller mark a
request as a retry of a specific attempt: the first request with a given key
runs normally and its result is cached; every subsequent request with the
same key returns that cached result instead of provisioning again.

Kept deliberately simple: an in-memory TTL cache, not a database table. A
provisioning retry happens within seconds of the original, not hours later,
so nothing here needs to survive a restart - and adding a table for it would
be the kind of premature durability this codebase avoids elsewhere too.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")

# How long a key is remembered. Long enough to cover a retried request from a
# slow client or a proxy's own retry budget, short enough that the cache
# never grows unbounded in a long-running process.
DEFAULT_TTL_SECONDS = 600.0
MAX_ENTRIES = 10_000


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class IdempotencyCache(Generic[T]):
    """A small TTL cache keyed by client-supplied idempotency key."""

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS, max_entries: int = MAX_ENTRIES) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, _Entry[T]] = {}
        self._lock = RLock()

    def get(self, key: str) -> T | None:
        """Return the cached result for ``key``, or None if absent/expired."""
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at < now:
                del self._entries[key]
                return None
            return entry.value

    def set(self, key: str, value: T) -> None:
        """Cache ``value`` under ``key`` for the configured TTL."""
        with self._lock:
            if len(self._entries) >= self.max_entries:
                self._evict_expired()
            self._entries[key] = _Entry(value=value, expires_at=time.monotonic() + self.ttl_seconds)

    def _evict_expired(self) -> None:
        """Drop expired entries. Caller must hold the lock."""
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at < now]
        for key in expired:
            del self._entries[key]
        # If eviction did not free enough room (a burst of still-live keys),
        # drop the oldest half rather than let the cache grow unbounded -
        # a stale idempotency guarantee is a smaller problem than an
        # unbounded process memory leak.
        if len(self._entries) >= self.max_entries:
            oldest = sorted(self._entries.items(), key=lambda item: item[1].expires_at)
            for key, _ in oldest[: len(oldest) // 2]:
                del self._entries[key]

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


provision_idempotency_cache: IdempotencyCache = IdempotencyCache()
