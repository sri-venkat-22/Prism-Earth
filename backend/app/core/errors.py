"""Centralized error handling (SRS §28).

Defines the application exception hierarchy (categories from SRS §28.1) and the
FastAPI exception handlers that render every failure as the standard error
envelope from SRS §28.2 / §13.17. Handlers never leak stack traces to clients;
unexpected errors are logged with the request correlation id.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.schemas.common import ErrorModel, ErrorResponse
from app.utils.time import utcnow_iso

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Exception hierarchy — categories per SRS §28.1                              #
# --------------------------------------------------------------------------- #
class AppError(Exception):
    """Base application error rendered as the SRS §28.2 envelope."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        # Extra response headers (e.g. ``Retry-After`` / ``WWW-Authenticate``)
        # emitted alongside the error envelope.
        self.headers = headers or {}
        super().__init__(self.message)


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422
    message = "Request validation failed."


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Resource not found."


class AuthenticationError(AppError):
    code = "AUTHENTICATION_ERROR"
    status_code = 401
    message = "Authentication required."


class AuthorizationError(AppError):
    """The caller is authenticated but lacks the required scope (SRS §13.20)."""

    code = "AUTHORIZATION_ERROR"
    status_code = 403
    message = "Insufficient scope for this resource."


class RateLimitError(AppError):
    """A per-token request budget was exceeded (SRS §13.19)."""

    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    message = "Rate limit exceeded."

    def __init__(self, message: str | None = None, *, retry_after: int | None = None) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__(message, headers=headers)


class PayloadTooLargeError(AppError):
    """The request body exceeded the configured size limit (SRS §29.1)."""

    code = "PAYLOAD_TOO_LARGE"
    status_code = 413
    message = "Request body too large."


class DatasetError(AppError):
    code = "DATASET_ERROR"
    status_code = 502
    message = "A dataset request failed."


class ConnectorError(AppError):
    code = "CONNECTOR_ERROR"
    status_code = 502
    message = "A connector failed."


class DeadlineExceededError(AppError):
    """The request exceeded its end-to-end processing deadline (SRS §7.1).

    Raised instead of holding a request open indefinitely when a downstream
    dependency (LLM provider, Earth Engine) stalls past the configured budget.
    """

    code = "DEADLINE_EXCEEDED"
    status_code = 504
    message = "The request could not be completed within the processing deadline."


class InternalError(AppError):
    code = "INTERNAL_ERROR"
    status_code = 500
    message = "An internal server error occurred."


# --------------------------------------------------------------------------- #
# Rendering helpers                                                            #
# --------------------------------------------------------------------------- #
def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "UNKNOWN")


def _render(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    details: str | None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorModel(
            code=code,
            message=message,
            details=details,
            correlation_id=correlation_id,
            timestamp=utcnow_iso(),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(), headers=headers)


# --------------------------------------------------------------------------- #
# Handlers                                                                     #
# --------------------------------------------------------------------------- #
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _render(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        correlation_id=_correlation_id(request),
        details=exc.details,
        headers=exc.headers or None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _render(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        correlation_id=_correlation_id(request),
        details=str(exc.errors()),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _render(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        correlation_id=_correlation_id(request),
        details=None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "request.unhandled_exception",
        correlation_id=_correlation_id(request),
        path=request.url.path,
        error=str(exc),
        exc_info=exc,
    )
    return _render(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An internal server error occurred.",
        correlation_id=_correlation_id(request),
        details=None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app.

    Starlette types ``add_exception_handler`` to accept handlers whose second
    argument is ``Exception``; our handlers narrow it to the specific exception
    they render. That is safe at runtime (Starlette dispatches by type) but
    mypy flags the contravariance, so the narrowed registrations are ignored.
    """
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
