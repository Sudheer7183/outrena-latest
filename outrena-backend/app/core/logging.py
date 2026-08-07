"""
logging.py — Structured logging via structlog.

Configured once at app startup (see app/main.py:create_app). All modules
import `structlog.get_logger(__name__)` and log via the standard levels.

Output: JSON in production, human-readable console output in development.
"""
from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure structlog + stdlib logging once. Idempotent."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Stdlib root logger — bridge for libraries that use stdlib logging.
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(message)s",
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
