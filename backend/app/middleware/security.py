"""Security-headers middleware (SRS §13.20 gateway, §29).

Adds conservative, broadly-safe response headers to every response. HSTS is
emitted only in production (it is meaningful over HTTPS and harmful to set on a
plain-HTTP dev server).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in _BASE_HEADERS.items():
            response.headers.setdefault(header, value)
        if self._hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
