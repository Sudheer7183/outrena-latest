"""
audit_middleware.py — Auto-logs all mutations + PII reads to public.platform_audit_log.

ASGI middleware that wraps every request. For mutating HTTP methods
(POST/PUT/PATCH/DELETE) it captures:
  - actor (sub, email, role from JWT if present; None for unauth mutations
    like /public/contact or /payments/webhook)
  - tenant_slug (from request.state.tenant if resolved; None otherwise)
  - action (e.g. "POST /api/v1/campaigns")
  - target_type + target_id (best-effort parse from path params)
  - request_id (from x-request-id header — set by RequestContextMiddleware)
  - ip_address (from request.client.host or x-forwarded-for)

For GET requests to PII-bearing paths (Article 30 — records of processing
activities), it captures the same fields with ``action="GET /api/v1/prospects"
``
so the audit log records who READ PII, not just who mutated it. PII-bearing
paths are matched against ``_PII_READ_PATH_PREFIXES`` below.

The write is FIRE-AND-FORGET: it runs after the response is generated
and any DB error is swallowed and logged so a failed audit-log write
NEVER breaks the request it is logging.

Registered in app/main.py between RequestContextMiddleware and
TenantMiddleware.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

_MUTATING_METHODS: frozenset[str] = frozenset(
    {"POST", "PUT", "PATCH", "DELETE"}
)

# Paths we never audit-log (they ARE the audit log read endpoints, or are
# pure health/doc endpoints that would just generate noise).
_EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/audit-logs",
    "/platform/admin/audit-logs",
)

# GET requests to these path prefixes are PII reads — logged with
# action="GET <path>" so the audit trail records who accessed PII (GDPR
# Article 30 — records of processing activities). The match is a prefix
# match, so /api/v1/prospects matches GET /api/v1/prospects AND
# GET /api/v1/prospects/{id} AND GET /api/v1/prospects/export.
_PII_READ_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/prospects",
    "/api/v1/users",           # user_management — PII (names, emails)
    "/api/v1/gdpr/export",     # DSR data export — full PII bundle
    "/api/v1/gdpr/consent",    # consent status by email
    "/api/v1/support/tickets",  # support tickets contain user PII in messages
)


class AuditMiddleware(BaseHTTPMiddleware):
    """Auto-log mutations + PII reads to public.platform_audit_log."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate the response FIRST so the audit log captures only
        # successful (2xx) mutations. Failures are logged too but tagged.
        try:
            response = await call_next(request)
        except Exception:
            # The exception will propagate; we still log the attempt below
            # but cannot know the status code. Re-raise after logging.
            await self._safe_log(request, status_code=500)
            raise

        if self._is_exempt(request.url.path):
            return response

        if request.method in _MUTATING_METHODS:
            await self._safe_log(request, status_code=response.status_code)
        elif request.method == "GET" and self._is_pii_read(request.url.path):
            # GDPR Article 30 — log every PII read so we have a complete
            # record of who accessed personal data (not just who mutated it).
            # Governed by AUDIT_LOG_PII_READS env flag (default true).
            settings = get_settings()
            if getattr(settings, "AUDIT_LOG_PII_READS", True):
                await self._safe_log(request, status_code=response.status_code)

        return response

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _is_exempt(path: str) -> bool:
        return any(path.startswith(p) for p in _EXEMPT_PATH_PREFIXES)

    @staticmethod
    def _is_pii_read(path: str) -> bool:
        """True iff the path is a PII-bearing read endpoint (Article 30)."""
        return any(path.startswith(p) for p in _PII_READ_PATH_PREFIXES)

    async def _safe_log(self, request: Request, *, status_code: int) -> None:
        """Fire-and-forget audit-log write. Never raises."""
        try:
            actor_sub: str | None = None
            actor_email: str | None = None
            actor_role: str | None = None
            # Try to decode the JWT (no signature verification — we just
            # want the actor identity, which is already trusted by the
            # downstream guards). If verification is required, the guards
            # will reject the request anyway.
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                try:
                    from jose import jwt as _jwt
                    claims = _jwt.get_unverified_claims(auth[7:])
                    actor_sub = str(claims.get("sub") or "") or None
                    actor_email = str(claims.get("email") or "") or None
                    actor_role = str(claims.get("role") or "") or None
                except Exception:  # noqa: BLE001
                    pass

            tenant = getattr(request.state, "tenant", None)
            tenant_slug = getattr(tenant, "slug", None) if tenant else None

            target_type, target_id = self._parse_target(request.url.path)
            request_id = request.headers.get("x-request-id")
            ip_address = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or (request.client.host if request.client else None)
            )

            action = f"{request.method} {request.url.path}"
            meta: dict[str, Any] = {
                "status_code": status_code,
                "query": str(request.url.query) if request.url.query else None,
            }

            async with AsyncSessionLocal() as session:
                await AuditService().log(
                    session,
                    actor_user_id=actor_sub,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    tenant_slug=tenant_slug,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    metadata=meta,
                    request_id=request_id,
                    ip_address=ip_address,
                )
        except Exception as exc:  # noqa: BLE001 — audit-log must never break a request
            logger.warning(
                "audit.middleware.log_failed",
                path=request.url.path,
                method=request.method,
                error=str(exc),
            )

    @staticmethod
    def _parse_target(path: str) -> tuple[str | None, str | None]:
        """Best-effort parse of path into (target_type, target_id).

        Heuristic: the second-to-last segment that looks like a collection
        name (alphabetic) is the target_type, and the last segment (if
        numeric or cuid-like) is the target_id.

        Examples:
          /api/v1/campaigns                  → ("campaigns", None)
          /api/v1/campaigns/c123             → ("campaigns", "c123")
          /api/v1/campaigns/c123/sequences   → ("sequences", None)
          /api/v1/campaigns/c123/publish     → ("campaigns", "c123")
          /platform/admin/signups/42/approve → ("signups", "42")
          /api/v1/public/contact             → ("contact", None)
        """
        parts = [p for p in path.split("/") if p]
        if not parts:
            return None, None
        # Walk from the right; the first thing that looks like an ID is the
        # target_id; the next alphabetic segment to its left is the type.
        target_id: str | None = None
        target_type: str | None = None
        for seg in reversed(parts):
            if target_id is None and _looks_like_id(seg):
                target_id = seg
                continue
            if target_id is not None and not _looks_like_id(seg):
                target_type = seg
                break
        if target_type is None and target_id is None:
            # No ID found — use the last alphabetic segment as the type.
            for seg in reversed(parts):
                if seg.isalpha():
                    target_type = seg
                    break
        return target_type, target_id


def _looks_like_id(seg: str) -> bool:
    """Heuristic: numeric, cuid-like (starts with 'c' + alnum), or UUID-ish."""
    if seg.isdigit():
        return True
    if len(seg) >= 8 and seg[0] == "c" and seg[1:].isalnum():
        return True
    if "-" in seg and len(seg) >= 32:
        return True  # UUID
    return False


__all__ = ["AuditMiddleware"]
