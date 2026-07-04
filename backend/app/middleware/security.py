"""Security-headers middleware (SRS §13.20 gateway, §29.3).

Adds conservative, broadly-safe response headers to every response:

- ``X-Content-Type-Options``, ``X-Frame-Options``, ``Referrer-Policy`` — the
  baseline hardening headers.
- ``Content-Security-Policy`` — a strict ``default-src 'none'`` policy for the
  JSON API, relaxed only for the ``/docs`` and ``/redoc`` HTML pages so Swagger
  UI / ReDoc (SRS §13.22) can load their CDN assets and inline init scripts.
- ``Permissions-Policy`` / ``Cross-Origin-Opener-Policy`` — disable unused
  browser capabilities and isolate the browsing context.
- ``Strict-Transport-Security`` — emitted only in production (it is meaningful
  over HTTPS and harmful to set on a plain-HTTP dev server).
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
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# The JSON API renders nothing, so it gets the tightest possible policy.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# Swagger UI / ReDoc are served as HTML that pulls assets from jsDelivr and runs
# an inline bootstrap script, so those pages need a targeted relaxation.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'"
)

_DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in _BASE_HEADERS.items():
            response.headers.setdefault(header, value)

        csp = _DOCS_CSP if request.url.path in _DOCS_PATHS else _API_CSP
        response.headers.setdefault("Content-Security-Policy", csp)

        if self._hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
