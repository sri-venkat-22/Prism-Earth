"""Async Redis client management (SRS §23).

Provides a lazily-initialized shared client and a non-raising ``ping`` used by
the readiness probe. No caching logic is implemented in Phase 0.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: aioredis.Redis | None = None


def init_redis(settings: Settings | None = None) -> aioredis.Redis:
    """Create the global Redis client (idempotent)."""
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("redis.client.initialized")
    return _client


def get_redis() -> aioredis.Redis:
    return _client or init_redis()


async def ping_redis() -> bool:
    """Return ``True`` if Redis responds to PING (readiness check, SRS §13.16)."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception as exc:  # report, never raise (health/readiness checks)
        logger.warning("redis.ping.failed", error=str(exc))
        return False


async def close_redis() -> None:
    """Close the Redis client on application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("redis.client.closed")
