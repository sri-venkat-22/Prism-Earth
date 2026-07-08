"""Cross-cutting endpoint dependencies (SRS §13.19, §29.1).

Gateway-level protections applied to the data endpoints (``/fetch``, ``/ask``):

- a configurable, environment-specific **rate limit** keyed on the client IP
  (SRS §13.19), complementing the per-token budget in
  :func:`app.auth.dependencies.require_auth` and the Nginx edge limit; and
- a **request-body size guard** (SRS §29.1) that rejects oversized payloads
  before they are parsed.

Both run regardless of authentication and render the standard error envelope
(SRS §28.2) on rejection. The rate-limit counter lives in the shared
:class:`app.auth.stores.EphemeralStore`, so the policy holds across API instances
when Redis backs it (SRS §23).
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, Request, Response

from app.auth.dependencies import get_ephemeral_store
from app.auth.ratelimit import enforce_rate_limit
from app.auth.stores import EphemeralStore
from app.core.config import Settings, get_settings
from app.core.errors import PayloadTooLargeError

_WINDOW_SECONDS = 60


def _settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


def _client_key(request: Request, settings: Settings) -> str:
    """Identify the client for rate-limiting, safe against header spoofing.

    Client-supplied ``X-Forwarded-For`` is spoofable — trusting its first hop
    lets an attacker rotate keys and slip the per-IP budget (§13.19). So proxy
    headers are honored only when ``trust_proxy_headers`` is set (i.e. the app
    runs behind a trusted reverse proxy). Then the Nginx-set ``X-Real-IP`` is
    authoritative (Nginx overwrites it with the real peer, §33.1); failing that,
    the *last* ``X-Forwarded-For`` hop (appended by the trusted proxy) is used.
    Without a trusted proxy the direct socket peer is used and forwarded headers
    are ignored entirely, closing the key-rotation bypass.
    """
    if settings.trust_proxy_headers:
        real_ip = request.headers.get("X-Real-IP", "").strip()
        if real_ip:
            return real_ip
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
            if hops:
                return hops[-1]
    return request.client.host if request.client else "unknown"


async def gateway_guard(
    request: Request,
    response: Response,
    ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)],
) -> None:
    """Enforce the body-size limit and the per-IP gateway rate limit.

    Raises :class:`~app.core.errors.PayloadTooLargeError` (413) for oversized
    bodies and :class:`~app.core.errors.RateLimitError` (429, with
    ``Retry-After``) when the budget is exceeded. On success, advertises the
    ``RateLimit-*`` headers so clients can self-throttle.
    """
    settings = _settings(request)

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if size > settings.max_request_body_bytes:
            raise PayloadTooLargeError(
                f"Request body exceeds the {settings.max_request_body_bytes}-byte limit."
            )

    if not settings.rate_limit_enabled:
        return

    limit = settings.rate_limit_per_minute
    key = f"gateway:{_client_key(request, settings)}"
    count = await enforce_rate_limit(ephemeral, key, limit)

    remaining = max(limit - count, 0)
    reset = _WINDOW_SECONDS - int(time.time() % _WINDOW_SECONDS)
    response.headers["RateLimit-Limit"] = str(limit)
    response.headers["RateLimit-Remaining"] = str(remaining)
    response.headers["RateLimit-Reset"] = str(max(reset, 1))
