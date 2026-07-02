"""Per-token rate limiting (SRS §13.19).

A fixed-window limiter: each token gets ``limit`` requests per rolling
one-minute window. The counter lives in the ephemeral store (in-memory or
Redis), so the same policy holds across API instances when Redis is used.

Exceeding the budget raises :class:`RateLimitError` (HTTP 429) with a
``Retry-After`` header pointing at the next window boundary.
"""

from __future__ import annotations

import time

from app.auth.stores import EphemeralStore
from app.core.errors import RateLimitError

_WINDOW_SECONDS = 60


async def enforce_rate_limit(store: EphemeralStore, token_id: str, limit_per_minute: int) -> int:
    """Count one request against ``token_id``; raise 429 if over ``limit_per_minute``.

    Returns the current count within the window on success.
    """
    if limit_per_minute <= 0:  # 0 / negative disables limiting for this token
        return 0
    now = time.time()
    window = int(now // _WINDOW_SECONDS)
    key = f"ratelimit:{token_id}:{window}"
    count = await store.incr(key, _WINDOW_SECONDS)
    if count > limit_per_minute:
        retry_after = _WINDOW_SECONDS - int(now % _WINDOW_SECONDS)
        raise RateLimitError(
            f"Rate limit of {limit_per_minute} requests/minute exceeded.",
            retry_after=max(retry_after, 1),
        )
    return count
