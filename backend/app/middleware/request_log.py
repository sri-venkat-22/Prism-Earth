"""Request-log middleware — the Neon audit trail (SRS §22.3, §15.19).

Persists one :class:`app.models.registry.RequestLog` row per request to the two
data-serving endpoints (``POST /api/v1/ask`` and ``POST /api/v1/fetch``),
including error responses (422/429/503/504), so the audit trail reflects what
was actually served. HTTP surface only — MCP tool calls invoke the pipelines
in-process and are not logged here.

The handlers stash per-request facts the middleware cannot see (coordinates,
field count, cache hit) on ``request.state.audit``; a request that failed
before its handler ran simply logs without them.

Failure policy: **fail-open**, like the caches (SRS §23.5) — the writer runs
fire-and-forget on its own session, a write failure is a warning, and serving
never waits on or depends on the audit write. The writer lives on
``app.state.request_log_writer`` (the ``ephemeral_store`` pattern) so tests can
swap in a recorder or ``None``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import get_sessionmaker
from app.core.logging import get_logger
from app.models.registry import RequestLog

logger = get_logger(__name__)

_AUDITED_PATHS = frozenset({"/api/v1/ask", "/api/v1/fetch"})
_WRITE_TIMEOUT_S = 5.0
#: Cap concurrent audit writes so a burst can never occupy more than a couple of
#: the serving engine's shared connections. The serving path holds one pooled
#: connection per in-flight request (up to 90s for /ask); an unbounded audit
#: fan-out sharing that pool could starve request handlers on connection-limited
#: managed Postgres (Neon). Bounded + fail-open, the audit path can never fail a
#: real request.
_MAX_CONCURRENT_WRITES = 2


class RequestLogWriter:
    """Fire-and-forget persister for :class:`RequestLog` rows (fail-open)."""

    def __init__(self) -> None:
        # Hold a strong reference to each in-flight write: asyncio only keeps a
        # weak reference to a task, so an unreferenced fire-and-forget task can
        # be garbage-collected mid-write before it commits.
        self._pending: set[asyncio.Task[None]] = set()
        self._slots = asyncio.Semaphore(_MAX_CONCURRENT_WRITES)

    async def persist(self, **row: Any) -> None:
        """Schedule the write and return immediately (never blocks serving)."""
        task = asyncio.get_running_loop().create_task(self._write(row))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _write(self, row: dict[str, Any]) -> None:
        try:
            # The whole acquire+write is under the timeout, so even a fully
            # saturated pool makes the audit write give up rather than pile up.
            async with asyncio.timeout(_WRITE_TIMEOUT_S):
                async with self._slots:
                    async with get_sessionmaker()() as session:
                        session.add(RequestLog(**row))
                        await session.commit()
        except Exception as exc:  # fail-open: a lost audit row, never a failure
            logger.warning("request_log.write_failed", error=str(exc))


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != "POST" or request.url.path not in _AUDITED_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000.0

        writer = getattr(request.app.state, "request_log_writer", None)
        if writer is None:
            return response

        audit: dict[str, Any] = getattr(request.state, "audit", {})
        await writer.persist(
            correlation_id=getattr(request.state, "correlation_id", ""),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            lat=audit.get("lat"),
            lng=audit.get("lng"),
            field_count=audit.get("field_count"),
            cache_hit=audit.get("cache_hit"),
        )
        return response
