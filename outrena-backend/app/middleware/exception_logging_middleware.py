"""
exception_logging_middleware.py — captures unhandled exceptions for PostHog + structured log.

This is the LAST line of defense: if a request raises an exception that isn't caught
by a route-level handler, this middleware:
  1. Captures the exception to PostHog (capture_exception) with full context
  2. Logs it via structlog (error level) with request_id, tenant, user, path, method
  3. Re-raises so FastAPI's default 500 handler responds

It does NOT swallow exceptions — it observes + re-raises. This ensures the client
still gets a proper error response while PostHog gets the signal for self-driving.

Placement (see app/main.py):
  Registered LAST via add_middleware() so it is OUTERMOST at runtime (Starlette
  runs middleware in reverse registration order). This lets it observe exceptions
  raised anywhere in the chain — including RequestContextMiddleware and the
  route handler.

Contextvar note:
  Because this middleware is OUTERMOST, RequestContextMiddleware (inner to it)
  has already run its ``finally`` block and unbound ``request_id``/``tenant_slug``/
  ``user_id`` from structlog contextvars by the time we catch the exception. So
  we extract these values DIRECTLY from the request (x-request-id header +
  unverified JWT claims) instead of relying on contextvars. The contextvar path
  is still tried first as a defensive fallback — if this middleware is ever
  repositioned inner to RequestContextMiddleware, the contextvar path takes over
  automatically.

Shared capture helper:
  ``capture_unhandled_exception(request, exc)`` is exported so the global
  ``@app.exception_handler(Exception)`` in app/main.py can reuse the SAME
  capture logic (PostHog + structured log) for handler-raised exceptions.
  The middleware handles middleware-raised exceptions; the exception handler
  handles route-raised exceptions. Together they provide defense-in-depth
  coverage with no double-capture (the handler returns a response so the
  middleware never sees the exception).
"""
from __future__ import annotations

import re
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from app.core.config import get_settings
from app.core.posthog_client import posthog

logger = structlog.get_logger(__name__)

# Service identifier sent as a PostHog property so the PostHog project can
# filter events by source (backend vs worker vs frontend).
_SERVICE_NAME = "outrena-backend"

# Patterns used to collapse raw URLs into route-like strings when the FastAPI
# route can't be resolved (e.g., exceptions raised before routing completes).
# Mirrors the cardinality-control logic in metrics_middleware.py — duplicated
# here to keep this middleware self-contained (no cross-middleware imports).
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_CUID_RE = re.compile(r"\bc[0-9a-z]{16,}\b")
_NUMERIC_RE = re.compile(r"/\d+(?=/|$)")
_LONG_ID_RE = re.compile(r"/[A-Za-z0-9_-]{20,}(?=/|$)")


class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    """Observe + re-raise unhandled exceptions. Captures to PostHog + structured log."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 — catch-all observer
            # IMPORTANT: re-raise after capturing. This middleware NEVER swallows.
            await capture_unhandled_exception(request, exc)
            raise


# ── Shared capture helper ───────────────────────────────────────────────────
# Used by both ExceptionLoggingMiddleware (above) and the global
# @app.exception_handler(Exception) in app/main.py. Keeps the PostHog property
# schema + structured log fields consistent across both capture paths.


async def capture_unhandled_exception(request: Request, exc: BaseException) -> None:
    """Capture an exception to PostHog + structured log. Never raises.

    This is the SINGLE source of truth for how unhandled exceptions are
    reported. Called from:
      - ExceptionLoggingMiddleware.dispatch  (for middleware-raised exceptions)
      - @app.exception_handler(Exception)    (for route-raised exceptions)

    Defense-in-depth: if one capture path fails to fire, the other still
    captures the exception. No double-capture — the exception handler returns
    a response (so the middleware never sees the exception), and the middleware
    only fires for exceptions that bypass the handler (raised in middleware
    itself).
    """
    try:
        settings = get_settings()
        request_id, tenant_slug, user_id = _extract_context(request)
        http_path = _resolve_path(request)
        distinct_id = _distinct_id(user_id, tenant_slug)

        properties: dict[str, Any] = {
            "tenant_slug": tenant_slug,
            "request_id": request_id,
            "http_method": request.method,
            "http_path": http_path,  # route pattern, not raw URL — cardinality
            "http_status": 500,
            "environment": settings.ENVIRONMENT,
            "service": _SERVICE_NAME,
        }

        # PostHog capture — fire-and-forget (SDK is async/batched internally;
        # posthog.capture_exception wraps every call in try/except so it
        # cannot raise).
        posthog.capture_exception(
            exc,
            distinct_id=distinct_id,
            properties=properties,
        )

        # Structured log — error level. The structlog `merge_contextvars`
        # processor will also pick up any contextvars bound at this point
        # (likely empty — see module docstring).
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            tenant_slug=tenant_slug,
            user_id=user_id,
            http_method=request.method,
            http_path=http_path,
            http_status=500,
            environment=settings.ENVIRONMENT,
            service=_SERVICE_NAME,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except Exception as capture_exc:  # noqa: BLE001 — capture must never raise
        # If the capture itself fails (e.g., logger misconfiguration), log
        # to stdlib as a last resort. We MUST NOT mask the original
        # exception — it will still propagate via the `raise` in dispatch()
        # or via the exception handler's JSON response.
        import logging as _stdlib_logging

        _stdlib_logging.getLogger(__name__).warning(
            "exception_logging.capture_failed: %s (original: %s)",
            capture_exc,
            exc,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _extract_context(request: Request) -> tuple[str | None, str | None, str | None]:
    """Resolve (request_id, tenant_slug, user_id) for the current request.

    Tries structlog contextvars first (works if this middleware is inner
    to RequestContextMiddleware at runtime). Falls back to direct request
    extraction (x-request-id header + unverified JWT claims) — this is the
    primary path because ExceptionLoggingMiddleware is OUTERMOST and the
    inner RequestContextMiddleware has already unbound its contextvars by
    the time we catch the exception.
    """
    # 1. Try contextvars (defensive — works if middleware is repositioned).
    ctx = structlog.contextvars.get_contextvars()
    request_id: str | None = ctx.get("request_id")
    tenant_slug: str | None = ctx.get("tenant_slug")
    user_id: str | None = ctx.get("user_id")

    # 2. Fall back to request headers / JWT for any missing value.
    if not request_id:
        request_id = request.headers.get("x-request-id")
    if not tenant_slug or not user_id:
        jwt_tenant, jwt_user = _extract_jwt_claims(request)
        if not tenant_slug:
            tenant_slug = jwt_tenant
        if not user_id:
            user_id = jwt_user
    return request_id, tenant_slug, user_id


def _distinct_id(user_id: str | None, tenant_slug: str | None) -> str:
    """PostHog distinct ID: user_id > tenant:anonymous > anonymous."""
    if user_id:
        return user_id
    if tenant_slug:
        return f"{tenant_slug}:anonymous"
    return "anonymous"


def _resolve_path(request: Request) -> str:
    """Return the FastAPI route pattern (e.g. /api/v1/campaigns/{id}).

    Falls back to a collapsed raw URL (UUIDs/CUIDs/numerics → :id) when
    route resolution fails — same cardinality-control approach as
    MetricsMiddleware. Bounds the cardinality of the PostHog ``http_path``
    property so the PostHog project doesn't explode with per-ID events.
    """
    try:
        scope = request.scope
        route = scope.get("route")
        if route is not None and getattr(route, "path_format", None):
            return route.path_format  # type: ignore[no-any-return]
        app = scope.get("app")
        if app is not None:
            for r in app.routes:  # type: ignore[union-attr]
                try:
                    match = r.matches(scope)
                except Exception:  # noqa: BLE001
                    continue
                if match and match[0] == Match.FULL:
                    pattern = getattr(r, "path_format", None) or getattr(r, "path", None)
                    if pattern:
                        return pattern  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        pass
    # Last resort: collapse the raw URL.
    path = request.url.path
    out = _UUID_RE.sub("/:id", path)
    out = _CUID_RE.sub("/:cuid", out)
    out = _NUMERIC_RE.sub("/:id", out)
    out = _LONG_ID_RE.sub("/:id", out)
    return out or path


def _extract_jwt_claims(request: Request) -> tuple[str | None, str | None]:
    """Extract tenant_slug + user_id from the JWT (unverified — telemetry only).

    Mirrors the pattern in RequestContextMiddleware. We do NOT verify the
    signature here because this is telemetry-only context for PostHog; trust
    is established separately by verify_tenant() + get_current_user().
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    try:
        from jose import jwt as _jwt

        claims = _jwt.get_unverified_claims(auth[7:])
        raw_slug = claims.get("tenant_slug")
        raw_sub = claims.get("sub")
        tenant_slug = str(raw_slug) if isinstance(raw_slug, str) and raw_slug else None
        user_id = str(raw_sub) if isinstance(raw_sub, str) and raw_sub else None
        return tenant_slug, user_id
    except Exception:  # noqa: BLE001 — telemetry-only; never break on bad JWT
        return None, None


__all__ = ["ExceptionLoggingMiddleware", "capture_unhandled_exception"]
