"""
posthog_client.py — PostHog client singleton for exception tracking + product analytics.

PostHog is self-hosted (see docker-compose.posthog.yml + runbooks/15). The client
is lazy-initialized on first use. If POSTHOG_KEY is empty, all calls no-op (dev-safe).

Usage:
    from app.core.posthog_client import posthog
    posthog.capture_exception(exc, distinct_id=user_id, properties={...})
    posthog.capture(distinct_id, event, properties={...})
    posthog.identify(distinct_id, properties={...})

Design notes (mirrors the LLM usage instrumentation in app/services/llm_service.py):
  * Every public method is wrapped in try/except — PostHog must NEVER break
    the app. A failed capture() is logged at warning level and swallowed.
  * The underlying posthog.Posthog SDK is batched + async (consumer thread),
    so capture() calls return immediately without blocking the request.
  * tenant_slug + request_id + user_id are pulled from structlog contextvars
    (bound by RequestContextMiddleware in app/main.py) so exception events
    carry the same request context as the structured logs.
  * On FastAPI lifespan shutdown, call posthog.shutdown() to flush + close
    the consumer thread cleanly (see app/main.py).
"""
from __future__ import annotations

import threading
import traceback
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level singleton state — built lazily by get_posthog().
_posthog_instance: "PosthogClient | NullPosthog | None" = None
_posthog_lock = threading.Lock()


class NullPosthog:
    """Dev-safe no-op PostHog client.

    Returned by get_posthog() when POSTHOG_KEY is empty (or when the SDK
    fails to initialize). All methods are silent no-ops so the app runs
    fine in dev/CI without a PostHog instance. Mirrors the public
    PosthogClient interface so callers can treat both uniformly.
    """

    __slots__ = ()  # no state — pure no-op

    def capture_exception(
        self,
        exc: BaseException,
        distinct_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        # Deliberately silent — see class docstring.
        pass

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        pass

    def identify(
        self,
        distinct_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        pass

    def flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class PosthogClient:
    """Real PostHog client wrapper.

    Wraps the posthog.Posthog SDK. Every public method is wrapped in
    try/except — PostHog must NEVER break the app (same defensive pattern
    as the LLM usage instrumentation in app/services/llm_service.py).

    The SDK is batched + async (consumer thread), so capture() calls
    return immediately. Network failures are retried with backoff inside
    the SDK; if all retries fail the event is dropped (logged at warning).
    """

    def __init__(self) -> None:
        # Local import: don't crash module import if the posthog lib is
        # missing (e.g., a dev env that hasn't pip-installed yet). The
        # _build_client() factory catches ImportError and falls back to
        # NullPosthog.
        from posthog import Posthog as _Posthog

        settings = get_settings()
        self._client = _Posthog(
            api_key=settings.POSTHOG_KEY,
            host=settings.POSTHOG_HOST,
            flush_at=settings.POSTHOG_FLUSH_AT,
            flush_interval=settings.POSTHOG_FLUSH_INTERVAL,
            personal_api_key=settings.POSTHOG_PERSONAL_API_KEY or None,
            # Async batching — capture() returns immediately, never blocks
            # the request thread. The consumer thread flushes in the
            # background (flush_at events OR flush_interval seconds).
            sync_mode=False,
            # Don't auto-capture — we capture explicitly via middleware +
            # capture_exception. Avoids duplicate events + SDK-side noise.
            enable_exception_autocapture=False,
        )

    def capture_exception(
        self,
        exc: BaseException,
        distinct_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Capture an exception to PostHog as a ``$exception`` event.

        Pulls ``tenant_slug`` + ``request_id`` + ``user_id`` from structlog
        contextvars (bound by RequestContextMiddleware in app/main.py) and
        formats the exception into the ``$exception_*`` properties the
        PostHog error-tracking UI recognizes.

        Args:
            exc: The exception instance. ``exc.__traceback__`` is used to
                build the stacktrace; pass ``sys.exc_info()[1]`` from an
                ``except`` block to preserve the live traceback.
            distinct_id: PostHog distinct ID (usually the user_id). When
                None, falls back to ``user_id`` from contextvars, then
                ``"anonymous"``.
            properties: Extra event properties. Merged over contextvar-
                derived defaults (caller wins on key collision EXCEPT for
                the ``$exception_*`` keys which are always overwritten).
        """
        try:
            ctx = structlog.contextvars.get_contextvars()
            props: dict[str, Any] = dict(properties or {})
            # Enrich with request context (bound by RequestContextMiddleware).
            # setdefault so caller-provided values win.
            if ctx.get("tenant_slug"):
                props.setdefault("tenant_slug", ctx["tenant_slug"])
            if ctx.get("request_id"):
                props.setdefault("request_id", ctx["request_id"])
            # Extract exception metadata — PostHog error-tracking format.
            # These are always overwritten (not setdefault) so a stale
            # caller-provided $exception_type can never mask the real one.
            props["$exception_type"] = type(exc).__name__
            props["$exception_message"] = str(exc)
            props["$exception_stacktrace"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
            # Distinct ID: explicit > user_id (from JWT contextvar) > anonymous.
            distinct = distinct_id or ctx.get("user_id") or "anonymous"
            self._client.capture(distinct, "$exception", properties=props)
        except Exception as exc_self:  # noqa: BLE001 — PostHog must never break the app
            logger.warning(
                "posthog.capture_exception_failed",
                error=str(exc_self),
                original_error=type(exc).__name__,
            )

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Capture a custom event. Fire-and-forget; never raises."""
        try:
            self._client.capture(distinct_id, event, properties=properties or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("posthog.capture_failed", event=event, error=str(exc))

    def identify(
        self,
        distinct_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Identify a user with properties. Fire-and-forget; never raises."""
        try:
            self._client.identify(distinct_id, properties=properties or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("posthog.identify_failed", error=str(exc))

    def flush(self) -> None:
        """Flush the in-memory event queue to PostHog. Never raises."""
        try:
            self._client.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("posthog.flush_failed", error=str(exc))

    def shutdown(self) -> None:
        """Flush + shut down the consumer thread. Call on FastAPI lifespan exit."""
        try:
            # flush() first to push queued events, then shutdown() to join
            # the consumer thread. shutdown() itself flushes, but calling
            # flush() first makes the intent explicit + handles the case
            # where shutdown() is overridden by a subclass.
            self._client.flush()
            self._client.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.warning("posthog.shutdown_failed", error=str(exc))


def _build_client() -> "PosthogClient | NullPosthog":
    """Construct the appropriate client based on settings.

    - POSTHOG_KEY empty  -> NullPosthog (dev-safe no-op)
    - POSTHOG_KEY set    -> PosthogClient (real SDK)
    - Construction error -> NullPosthog (never crash the app)

    Never raises — any failure (missing posthog lib, bad host, etc.) is
    caught and a NullPosthog is returned so the app keeps running.
    """
    settings = get_settings()
    if not settings.POSTHOG_KEY:
        logger.info("posthog.disabled", reason="POSTHOG_KEY empty")
        return NullPosthog()
    try:
        return PosthogClient()
    except Exception as exc:  # noqa: BLE001 — fall back to NullPosthog on init failure
        logger.warning(
            "posthog.init_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            fallback="NullPosthog",
        )
        return NullPosthog()


def get_posthog() -> "PosthogClient | NullPosthog":
    """Lazy, thread-safe accessor for the PostHog singleton.

    Returns NullPosthog when POSTHOG_KEY is empty (dev-safe) or when the
    SDK fails to initialize. Never raises.

    Thread-safe via double-checked locking — the first caller to hit the
    None branch acquires the lock and builds the client; subsequent
    callers see the populated instance without contending.
    """
    global _posthog_instance
    if _posthog_instance is None:
        with _posthog_lock:
            if _posthog_instance is None:  # double-checked locking
                _posthog_instance = _build_client()
    return _posthog_instance


# Module-level singleton — built lazily on first call to get_posthog().
# `from app.core.posthog_client import posthog` gives callers a ready-to-use
# NullPosthog (dev/CI) or PosthogClient (production) instance. All public
# methods are safe to call without guarding — NullPosthog no-ops, and
# PosthogClient wraps every call in try/except.
posthog: "PosthogClient | NullPosthog" = get_posthog()


__all__ = ["posthog", "get_posthog", "PosthogClient", "NullPosthog"]
