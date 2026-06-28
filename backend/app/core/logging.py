"""Structured logging configuration (SRS §27).

Uses ``structlog`` layered on top of the stdlib :mod:`logging` module so a single
pipeline renders both application logs (via :func:`get_logger`) and third-party
logs (uvicorn, SQLAlchemy, Alembic). In production logs are emitted as JSON for
ingestion by Loki; in development a human-friendly console renderer is used. The
active correlation id (set by
:class:`app.middleware.correlation.CorrelationIdMiddleware`) is merged into every
log line via ``contextvars``.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging and structlog to share one renderer."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Processors shared by structlog-native records and "foreign" stdlib records
    # (uvicorn/sqlalchemy), so both are enriched identically before rendering.
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # structlog-native loggers run the shared chain, then hand the event dict to
    # the stdlib ProcessorFormatter (configured below) for final rendering.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    # A single handler renders every record — app logs and uvicorn/sqlalchemy
    # alike — so log output is uniform (and JSON-parseable in production).
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Uvicorn installs its own handlers; clear them so its records propagate to
    # the root handler and are rendered through the same pipeline.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").setLevel(max(level, logging.INFO))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
