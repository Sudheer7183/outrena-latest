"""
posthog_middleware.py — Compatibility module (Tech Doc §12.2 / §5.10).

The Technical Documentation refers to the backend PostHog exception-capture
middleware by this filename. The actual implementation lives in
``exception_logging_middleware.py`` (it captures every unhandled exception,
forwards it to PostHog with request_id / tenant_slug / user_id tags, then
re-raises). This module re-exports it under the documented name so both
import paths resolve:

    from app.middleware.posthog_middleware import ExceptionLoggingMiddleware
    from app.middleware.exception_logging_middleware import ExceptionLoggingMiddleware
"""
from app.middleware.exception_logging_middleware import (  # noqa: F401
    ExceptionLoggingMiddleware,
)

# Documented alias — some references call it "PostHogMiddleware".
PostHogMiddleware = ExceptionLoggingMiddleware

__all__ = ["ExceptionLoggingMiddleware", "PostHogMiddleware"]
