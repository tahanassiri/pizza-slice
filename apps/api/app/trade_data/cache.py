"""Simple TTL cache + circuit breaker for trade providers."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TtlCache:
    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 256):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._store: dict[str, _CacheEntry] = {}

    @staticmethod
    def make_key(prefix: str, payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}:{digest}"

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self.max_entries:
                # Drop oldest-ish: first key
                oldest = next(iter(self._store), None)
                if oldest:
                    self._store.pop(oldest, None)
            self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + self.ttl)


class CircuitBreaker:
    """Skip a provider after N consecutive failures for a cooldown window."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 120.0):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def allow(self, provider_id: str) -> bool:
        with self._lock:
            until = self._open_until.get(provider_id, 0.0)
            return time.monotonic() >= until

    def record_success(self, provider_id: str) -> None:
        with self._lock:
            self._failures[provider_id] = 0
            self._open_until.pop(provider_id, None)

    def record_failure(self, provider_id: str) -> None:
        with self._lock:
            n = self._failures.get(provider_id, 0) + 1
            self._failures[provider_id] = n
            if n >= self.failure_threshold:
                self._open_until[provider_id] = time.monotonic() + self.cooldown


# Process-wide shared instances (safe for single-worker API; clears on restart)
trade_cache = TtlCache(ttl_seconds=3600.0)
trade_breaker = CircuitBreaker()
