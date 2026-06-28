"""Correlation-id middleware (SRS §27, §28.2).

Assigns a correlation id to every request (honoring an inbound ``X-Request-ID``
or ``X-Correlation-ID`` header, otherwise generating one). The id is stored on
``request.state``, bound to the structlog context so it appears in every log
line, and echoed back in the ``X-Correlation-ID`` response header.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


def _new_correlation_id() -> str:
    return f"REQ-{uuid.uuid4().hex[:12].upper()}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = (
            request.headers.get(REQUEST_ID_HEADER)
            or request.headers.get(CORRELATION_HEADER)
            or _new_correlation_id()
        )
        request.state.correlation_id = correlation_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[CORRELATION_HEADER] = correlation_id
        return response
