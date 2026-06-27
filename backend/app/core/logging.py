"""Structured logging configuration (SRS §27).

Uses ``structlog`` over the stdlib logging module. In production, logs are
emitted as JSON for ingestion by Loki; in development a human-friendly console
renderer is used. The active correlation id (set by
:class:`app.middleware.correlation.CorrelationIdMiddleware`) is merged into
every log line via ``contextvars``.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging and structlog processors."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through the same level.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(max(level, logging.INFO))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
