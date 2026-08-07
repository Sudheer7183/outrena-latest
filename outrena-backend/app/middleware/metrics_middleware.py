"""
metrics_middleware.py — Prometheus HTTP metrics middleware.

ASGI middleware that wraps every request and records:

  - ``outrena_http_requests_total``     (Counter, labels: method, endpoint, status)
  - ``outrena_http_request_duration_seconds`` (Histogram, labels: method, endpoint)
  - ``outrena_http_requests_active``    (Gauge — inc on start, dec on end)

Cardinality control — CRITICAL for Prometheus memory:

  The ``endpoint`` label uses the FASTAPI ROUTE PATTERN (e.g.
  ``/api/v1/campaigns/{id}``), NOT the raw URL (which would be
  ``/api/v1/campaigns/c123`` and explode cardinality). When the route
  can't be resolved (404, /metrics, /health, middleware-exempt paths),
  we fall back to the literal path with all UUID-like / numeric segments
  replaced by ``:param``.

Registered in app/main.py between RequestContextMiddleware and
AuditMiddleware so tenant + request_id are already bound to structlog
context when this middleware records the latency.
"""
from __future__ import annotations

import re
import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from app.core.metrics import (
    ACTIVE_REQUESTS,
    REQUEST_COUNT,
    REQUEST_LATENCY,
)

logger = structlog.get_logger(__name__)

# Paths we don't meter (would just be noise — health probes, Prometheus
# self-scrape, OpenAPI). They still go through the rest of the middleware
# chain; we just don't emit metric samples for them.
_EXEMPT_PATHS: frozenset[str] = frozenset({
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/",
})

# Cardinality cap — if route resolution fails AND the heuristic produces
# more than 64 distinct endpoints in a window, we collapse the rest into
# ``_other``. The cap is defensive; in practice the FastAPI route table
# resolves >99% of paths.
_MAX_ENDPOINT_LABELS = 256
_seen_endpoints: set[str] = set()

# Patterns used to collapse raw URLs into route-like strings when the
# FastAPI route can't be resolved.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_CUID_RE = re.compile(r"\bc[0-9a-z]{16,}\b")
_NUMERIC_RE = re.compile(r"/\d+(?=/|$)")
_LONG_ID_RE = re.compile(r"/[A-Za-z0-9_-]{20,}(?=/|$)")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record Prometheus HTTP metrics for every non-exempt request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        # Skip exempt paths entirely — no metric sample, no active gauge.
        if path in _EXEMPT_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        endpoint = _resolve_endpoint(request) or _collapse_path(path)
        method = request.method

        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # The exception will propagate after we record the metric.
            status_code = 500
            raise
        finally:
            elapsed = time.perf_counter() - start
            ACTIVE_REQUESTS.dec()
            try:
                # Cardinality cap
                if endpoint not in _seen_endpoints:
                    if len(_seen_endpoints) >= _MAX_ENDPOINT_LABELS:
                        endpoint = "_other"
                    else:
                        _seen_endpoints.add(endpoint)
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    status=str(status_code),
                ).inc()
            except Exception as exc:  # noqa: BLE001 — metrics must never break a request
                logger.warning(
                    "metrics_middleware.record_failed",
                    path=path,
                    method=method,
                    error=str(exc),
                )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _resolve_endpoint(request: Request) -> str | None:
    """Return the FastAPI route pattern for the request, or None.

    Walks the app's router to find the matching route. The route's
    ``.path`` is the pattern (e.g. ``/api/v1/campaigns/{campaign_id}``),
    which has bounded cardinality. Returns None when no route matches
    (404) or when the resolved route has no path-format string.
    """
    try:
        scope = request.scope
        route = scope.get("route")
        if route is not None and getattr(route, "path_format", None):
            return route.path_format  # type: ignore[no-any-return]
        # Fall back to iterating the app's router
        app = scope.get("app")
        if app is None:
            return None
        for r in app.routes:  # type: ignore[union-attr]
            try:
                match = r.matches(scope)
            except Exception:  # noqa: BLE001
                continue
            if match and match[0] == Match.FULL:
                return getattr(r, "path_format", None) or getattr(r, "path", None)
    except Exception:  # noqa: BLE001
        return None
    return None


def _collapse_path(path: str) -> str:
    """Replace UUIDs / CUIDs / numeric IDs in a raw URL with ``:param``.

    Used when the FastAPI route can't be resolved (e.g., 404). Bounds
    cardinality by collapsing per-ID paths into one label.
    """
    out = _UUID_RE.sub("/:id", path)
    out = _CUID_RE.sub("/:cuid", out)
    out = _NUMERIC_RE.sub("/:id", out)
    out = _LONG_ID_RE.sub("/:id", out)
    return out or path


__all__ = ["MetricsMiddleware"]
