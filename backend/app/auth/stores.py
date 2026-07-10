"""Ephemeral state store for the auth flows (SRS §13.20, §13.19, §23).

Short-lived, high-churn state — OAuth authorization codes, device-flow codes and
their approval status, and per-token rate-limit counters — is kept here rather
than in the database. Two implementations share one protocol:

- :class:`InMemoryEphemeralStore` — process-local; correct for single-instance
  dev and hermetic tests (no Redis needed in the gate).
- :class:`RedisEphemeralStore` — backed by the shared async Redis client
  (SRS §23), required when running more than one API instance.

The store keeps opaque JSON documents keyed by string, each with a TTL, plus an
atomic ``incr`` used by the rate limiter (SRS §13.19).
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol, runtime_checkable

import redis.asyncio as aioredis


@runtime_checkable
class EphemeralStore(Protocol):
    """Key/value store for expiring auth state and counters."""

    async def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None: ...

    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def delete(self, key: str) -> None: ...

    async def incr(self, key: str, ttl_seconds: int) -> int: ...


class InMemoryEphemeralStore:
    """Process-local ephemeral store (dev + tests)."""

    def __init__(self) -> None:
        # key -> (value, expiry_epoch)
        self._data: dict[str, tuple[dict[str, Any], float]] = {}
        # key -> (count, expiry_epoch)
        self._counters: dict[str, tuple[int, float]] = {}

    def _sweep(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._data.items() if exp <= now]
        for k in expired:
            del self._data[k]
        expired_c = [k for k, (_, exp) in self._counters.items() if exp <= now]
        for k in expired_c:
            del self._counters[k]

    async def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._data[key] = (dict(value), time.time() + ttl_seconds)

    async def get(self, key: str) -> dict[str, Any] | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry <= time.time():
            self._data.pop(key, None)
            return None
        return dict(value)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        now = time.time()
        self._sweep(now)  # keep the process-local store bounded over long runs
        count, expiry = self._counters.get(key, (0, 0.0))
        if expiry <= now:
            count, expiry = 0, now + ttl_seconds
        count += 1
        self._counters[key] = (count, expiry)
        return count


class RedisEphemeralStore:
    """Redis-backed ephemeral store (SRS §23)."""

    def __init__(self, client: aioredis.Redis, *, namespace: str = "terra:auth:") -> None:
        self._redis = client
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}{key}"

    async def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        await self._redis.set(self._k(key), json.dumps(value), ex=ttl_seconds)

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._k(key))
        if raw is None:
            return None
        data: dict[str, Any] = json.loads(raw)
        return data

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._k(key))

    async def incr(self, key: str, ttl_seconds: int) -> int:
        full = self._k(key)
        count = int(await self._redis.incr(full))
        if count == 1:
            await self._redis.expire(full, ttl_seconds)
        return count
