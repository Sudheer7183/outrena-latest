"""
app/main.py — FastAPI application factory.

Phase 1: skeleton + /health endpoint.
Phase 2: activate /platform/* router (tenant registry CRUD + provisioning).
Phase 3: activate /api/v1/* router (22 feature modules, 73 endpoints).
Phase 4: frontend (no backend change).
Phase 5: scheduler tick loop (APScheduler lifespan wiring).
Phase 6: cloud deployment (no further main.py change).
Phase 7: SaaS platform (billing, RBAC, audit).
Phase 8 (SAAS2-OBS-BE): Prometheus /metrics endpoint +
       MetricsMiddleware + per-user cost tracking (UsageService).
Phase 9 (this task — PH-BE): PostHog exception tracking +
       ExceptionLoggingMiddleware + global exception handlers.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.posthog_client import posthog
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.exception_logging_middleware import ExceptionLoggingMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware
from app.middleware.tenant_middleware import TenantMiddleware

logger = structlog.get_logger(__name__)


# ── Lightweight middleware to ensure structlog is bound per request ──────────
class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds request_id + tenant + user_id to structlog contextvars.

    request_id  — from x-request-id header or a fresh UUID.
    tenant_slug — from the JWT ``tenant_slug`` claim (unverified — telemetry
                  only; trust is still established by verify_tenant()).
                  Falls back to None when no JWT is present (e.g., /health).
    user_id     — from the JWT ``sub`` claim (unverified — telemetry only).

    The tenant + user_id bindings are consumed by the LLM instrumentation
    in app/services/llm_service.py so per-tenant + per-user Prometheus
    metrics + UsageEvents can be recorded without changing the call_llm
    signature. They are unbound at request end so a stale binding never
    leaks across requests.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        import uuid

        from structlog import contextvars

        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        # Extract tenant_slug + user_id from the JWT (unverified — telemetry only).
        tenant_slug: str | None = None
        user_id: str | None = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                from jose import jwt as _jwt

                claims = _jwt.get_unverified_claims(auth[7:])
                raw_slug = claims.get("tenant_slug")
                if isinstance(raw_slug, str) and raw_slug:
                    tenant_slug = raw_slug
                raw_sub = claims.get("sub")
                if isinstance(raw_sub, str) and raw_sub:
                    user_id = raw_sub
            except Exception:  # noqa: BLE001 — telemetry binding must never break the request
                pass

        contextvars.bind_contextvars(
            request_id=request_id,
            tenant_slug=tenant_slug,
            user_id=user_id,
        )
        try:
            response = await call_next(request)
        finally:
            contextvars.unbind_contextvars("request_id", "tenant_slug", "user_id")
        response.headers["x-request-id"] = request_id
        return response


def create_app() -> FastAPI:
    """Application factory — single entry point for uvicorn and tests."""
    configure_logging()
    settings = get_settings()

    # BUG-04 FIX: Fail fast if ENCRYPTION_KEY is absent — prevents mid-request 500s.
    if not settings.ENCRYPTION_KEY:
        import sys
        sys.stderr.write(
            "\n[OUTRENA] FATAL: ENCRYPTION_KEY is not set.\n"
            "Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "Then set it in your .env file as ENCRYPTION_KEY=<value>\n\n"
        )
        # Do NOT raise in dev (SKIP_JWT_VERIFICATION) so the app still boots without encryption.
        # In production, fail hard.
        if settings.is_production:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set — refusing to start in production."
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        """Phase 5 lifespan — start/stop the APScheduler AsyncIOScheduler.

        Per migration §9.1 + audit-A3 finding #8. The scheduler only starts
        when settings.SCHEDULER_ENABLED is True (the worker deployment
        sets SCHEDULER_ENABLED=false so only the backend container ticks).

        Phase 9 (PH-BE): also flushes + shuts down the PostHog client on
        exit so the consumer thread doesn't drop queued exception events.
        """
        if settings.SCHEDULER_ENABLED:
            from app.features.scheduler.service import get_scheduler

            scheduler = get_scheduler()
            try:
                scheduler.start()
                app.state.scheduler = scheduler
            except Exception:  # noqa: BLE001 — startup must not crash
                # Scheduler already running or unavailable — log + continue.
                # The app can still serve HTTP requests without the tick loop.
                pass
        try:
            yield
        finally:
            # PostHog: flush + shutdown FIRST so queued exception events
            # are delivered before the process exits. posthog.shutdown()
            # is wrapped in try/except internally (never raises).
            posthog.shutdown()
            if settings.SCHEDULER_ENABLED and getattr(app.state, "scheduler", None) is not None:
                try:
                    app.state.scheduler.shutdown(wait=False)
                except Exception:  # noqa: BLE001
                    pass

    application = FastAPI(
        title="OUTRENA API",
        version="1.0.0",
        description="AI-Powered Outreach Operating System — multitenant (Phase 2)",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS FIRST (Starlette runs middleware in reverse registration order —
    # CORS must wrap tenant resolution so cross-origin preflights succeed).
    base_domain_pattern = settings.BASE_DOMAIN.replace(".", r"\.")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=rf"https?://([a-z0-9-]+\.)*{base_domain_pattern}",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(MetricsMiddleware)
    application.add_middleware(AuditMiddleware)
    application.add_middleware(TenantMiddleware)
    # ExceptionLoggingMiddleware LAST (→ OUTERMOST at runtime) so it wraps
    # every other middleware + the route handler. It observes + re-raises —
    # never swallows. Captures to PostHog + structured log on the way out.
    # See app/middleware/exception_logging_middleware.py for the full design.
    application.add_middleware(ExceptionLoggingMiddleware)

    # ── Phase 2: Platform router (SUPER_ADMIN tenant registry CRUD + provisioning).
    # ISSUE-3 FIX: mounted at /api/platform so the nginx /api/ proxy forwards it
    # correctly. /api/platform is added to EXEMPT_PREFIXES in tenant_middleware.py.
    # The old /platform prefix still works via the nginx /platform/ proxy location
    # for backward compatibility — but all new frontend calls use /api/platform.
    from app.api.routes.platform import router as platform_router

    application.include_router(platform_router, prefix="/api")

    # ── Phase 3: feature routers under /api/v1/* (22 modules, 73 endpoints).
    # Auto-mounted via _wire_module_routers in app.api.v1 — adding a new module
    # router only requires editing app/api/v1/__init__.py.
    from app.api.v1 import api_router

    application.include_router(api_router, prefix="/api/v1")

    # ── Phase 9 (PH-BE): Global exception handlers ────────────────────────────
    # These provide structured JSON responses (instead of FastAPI's default
    # plain-text 500 / 422). PostHog capture is handled by
    # ExceptionLoggingMiddleware (OUTERMOST) which captures + re-raises for
    # ALL exceptions (route-raised AND middleware-raised) — see
    # app/middleware/exception_logging_middleware.py.
    #
    # Why the handler doesn't also capture: FastAPI routes the
    # @app.exception_handler(Exception) handler to ServerErrorMiddleware
    # (the OUTERMOST built-in middleware), which is OUTER to user middleware.
    # So a route-raised exception propagates THROUGH ExceptionLoggingMiddleware
    # (which captures + re-raises) BEFORE reaching this handler. Capturing
    # here too would double-capture. The handler's only job is to return a
    # structured JSON 500 response.

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(  # noqa: RUF029 — FastAPI signature
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all exception handler — returns structured JSON 500.

        FastAPI routes this handler to ServerErrorMiddleware (OUTERMOST),
        which catches exceptions that escape ExceptionLoggingMiddleware's
        re-raise. PostHog capture + structured logging already happened in
        ExceptionLoggingMiddleware (which is INNER to ServerErrorMiddleware
        but OUTER to the rest of the user middleware stack) — see
        app/middleware/exception_logging_middleware.py for the full design.

        The response body deliberately omits the exception type/message to
        avoid leaking internal details to clients. The ``request_id`` is
        echoed so the client can correlate with backend logs.
        """
        request_id = request.headers.get("x-request-id")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
            },
            headers={"x-request-id": request_id} if request_id else None,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # noqa: RUF029 — FastAPI signature
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Structured JSON 422 for request validation failures.

        Overrides FastAPI's default ``{"detail": [...]}`` 422 with a richer
        schema that includes ``request_id`` + an ``error`` slug so the frontend
        can branch on ``error == "validation_error"`` without parsing detail
        strings. Validation errors are NOT sent to PostHog (they're client
        errors, not server errors — logging them would just be noise).
        """
        request_id = request.headers.get("x-request-id")
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request validation failed.",
                "request_id": request_id,
                "details": exc.errors(),
            },
            headers={"x-request-id": request_id} if request_id else None,
        )

    @application.get("/health", include_in_schema=False, tags=["meta"])
    async def health_check(request: Request) -> JSONResponse:
        """
        Liveness/readiness probe.

        Phase 1 contract: returns 200 + {status:"ok"} always, with per-service
        substatus. A failing sub-service does NOT fail the probe — that's a
        separate readiness concern (Phase 2 adds /ready).
        """
        tenant = getattr(request.state, "tenant", None)
        checks = await asyncio.gather(
            _check_db(), _check_redis(), _check_keycloak(settings), return_exceptions=True
        )
        db_status, redis_status, kc_status = checks
        return JSONResponse(
            {
                "status": "ok",
                "tenant": tenant.slug if tenant else None,
                "checks": {
                    "db": _status_payload(db_status),
                    "redis": _status_payload(redis_status),
                    "keycloak": _status_payload(kc_status),
                },
            }
        )

    @application.get(
        "/metrics",
        include_in_schema=False,
        tags=["meta"],
        summary="Prometheus metrics",
    )
    async def metrics() -> PlainTextResponse:
        """Prometheus scrape endpoint.

        Returns the default prometheus_client registry in the text exposition
        format (Content-Type: text/plain; version=0.0.4). NOT auth-protected
        — Prometheus scrapes without credentials. Network-level ACLs (security
        groups / VPC) restrict access in production.
        """
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            body = generate_latest()
            return PlainTextResponse(content=body, media_type=CONTENT_TYPE_LATEST)
        except Exception as exc:  # noqa: BLE001 — /metrics must never crash
            return PlainTextResponse(
                content=f"# metrics collection failed: {exc}\n",
                media_type="text/plain",
                status_code=500,
            )

    @application.get("/", include_in_schema=False, tags=["meta"])
    async def root() -> JSONResponse:
        return JSONResponse(
            {"name": "OUTRENA API", "version": "1.0.0", "phase": 2, "docs": "/docs"}
        )

    return application


def _status_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, Exception):
        return {"status": "down", "error": str(result)}
    if isinstance(result, dict):
        return result
    return {"status": "unknown"}


async def _check_db() -> dict[str, Any]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "up"}


async def _check_redis() -> dict[str, Any]:
    client = get_redis()
    pong = await client.ping()
    return {"status": "up" if pong else "down"}


async def _check_keycloak(settings: Any) -> dict[str, Any]:
    url = f"{settings.keycloak_realm_url}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return {"status": "up", "realm": settings.KEYCLOAK_REALM}
        return {"status": "down", "http_status": resp.status_code}
    except Exception as exc:  # noqa: BLE001 — health probe must never raise
        return {"status": "down", "error": str(exc)}


app: FastAPI = create_app()
