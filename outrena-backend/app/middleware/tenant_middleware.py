# # """
# # tenant_middleware.py — Resolves the tenant for every request.

# # Resolution order (reference model Section 3.1):
# #   1. Subdomain from the Host header (authoritative).
# #   2. X-Tenant-Slug header — accepted on localhost only (dev fallback).
# #   3. JWT Bearer 'tenant_slug' claim — fallback for deployments where
# #      per-tenant subdomains are not yet wired. The claim is read WITHOUT
# #      signature verification here; this middleware only IDENTIFIES the
# #      tenant. Trust is established later by get_current_user() +
# #      verify_tenant(), which verify the signature and cross-check the
# #      claim against the resolved tenant.

# # Registered AFTER CORSMiddleware in main.py (Starlette runs middleware in
# # reverse registration order, so CORS wraps tenant resolution).
# # """
# # from __future__ import annotations

# # import structlog
# # from fastapi import Request, Response
# # from fastapi.responses import JSONResponse
# # from jose import JWTError, jwt
# # from sqlalchemy import text
# # from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# # from app.core.config import get_settings
# # from app.core.database import engine
# # from app.schemas.tenant import TenantResolved

# # logger = structlog.get_logger(__name__)

# # # Paths served without a tenant context.
# # EXEMPT_PREFIXES: tuple[str, ...] = (
# #     "/health",
# #     "/docs",
# #     "/redoc",
# #     "/openapi.json",
# #     "/platform",      # SUPER_ADMIN registry routes — legacy path (nginx /platform/ proxy)
# #   "/api/platform",  # ISSUE-3 FIX: new canonical path (nginx /api/ proxy)
# #     "/api/v1/public",  # Public landing-page data + contact form
# #     "/api/v1/tenant-signup",  # Self-serve signup request (no auth, no tenant)
# #     "/api/v1/payments/webhook",  # Stripe webhook — HMAC-verified, no tenant
# #     # GDPR — public DSR submission + status check (data subjects may not be
# #     # platform users). Authenticated GDPR endpoints (/gdpr/dsrs, /gdpr/consent,
# #     # /gdpr/retention-status, /gdpr/export) require a tenant context and are
# #     # NOT exempt. Platform-level SUPER_ADMIN GDPR routes (/gdpr/platform/*)
# #     # are also exempt (they query the public schema only).
# #     "/api/v1/gdpr/dsr",  # singular — POST /dsr + GET /dsr/{id}/status
# #     "/api/v1/gdpr/platform",  # SUPER_ADMIN cross-tenant endpoints
# #     # Retention policy CRUD + manual enforcement — SUPER_ADMIN only, public
# #     # schema. Mounted at /api/v1/retention (see app/api/v1/retention.py).
# #     "/api/v1/retention",
# #     # One-click unsubscribe — public, token-verified. tenant_slug is embedded
# #     # in the query string / request body rather than the subdomain.
# #     "/api/v1/public/unsubscribe",
# # )


# # class TenantMiddleware(BaseHTTPMiddleware):
# #     """Extracts the tenant and attaches it to request.state.tenant."""

# #     async def dispatch(
# #         self, request: Request, call_next: RequestResponseEndpoint
# #     ) -> Response:
# #         if self._is_exempt(request.url.path):
# #             return await call_next(request)

# #         slug = self._extract_slug(request)
# #         if not slug:
# #             return JSONResponse({"detail": "Tenant not identified"}, status_code=400)

# #         tenant = await self._resolve_tenant(slug)
# #         if tenant is None:
# #             return JSONResponse(
# #                 {"detail": f"Unknown tenant: {slug}"}, status_code=404
# #             )
# #         if not tenant.is_active:
# #             return JSONResponse({"detail": "Tenant inactive"}, status_code=403)

# #         request.state.tenant = tenant
# #         return await call_next(request)

# #     # ── Identification ──────────────────────────────────────────────────────

# #     @staticmethod
# #     def _is_exempt(path: str) -> bool:
# #         return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)

# #     def _extract_slug(self, request: Request) -> str | None:
# #         settings = get_settings()
# #         host = (request.headers.get("host") or "").split(":")[0].lower()

# #         # 1 — Subdomain of BASE_DOMAIN (authoritative)
# #         base = settings.BASE_DOMAIN.lower()
# #         if host.endswith(f".{base}"):
# #             candidate = host.removesuffix(f".{base}")
# #             if candidate and "." not in candidate:
# #                 return candidate

# #         # 2 — Dev header, localhost only
# #         if host in ("localhost", "127.0.0.1"):
# #             header_slug = request.headers.get("x-tenant-slug")
# #             if header_slug:
# #                 return header_slug.lower()

# #         # 3 — JWT claim fallback (identification only — NOT trust)
# #         return self._slug_from_bearer(request)

# #     @staticmethod
# #     def _slug_from_bearer(request: Request) -> str | None:
# #         auth = request.headers.get("authorization", "")
# #         if not auth.lower().startswith("bearer "):
# #             return None
# #         token = auth[7:]
# #         # Dev bypass: the frontend sends the literal string "dev-token"
# #         # which is not a valid JWT. Return the dev tenant slug directly.
# #         if token == "dev-token":
# #             return "acme"
# #         try:
# #             claims = jwt.get_unverified_claims(token)
# #         except JWTError:
# #             return None
# #         slug = claims.get("tenant_slug")
# #         return slug.lower() if isinstance(slug, str) and slug else None

# #     # ── Resolution ──────────────────────────────────────────────────────────

# #     @staticmethod
# #     async def _resolve_tenant(slug: str) -> TenantResolved | None:
# #         """Look the slug up in public.tenants on a fresh connection.

# #         Dev fallback: if SKIP_JWT_VERIFICATION is enabled and no DB row
# #         exists for the slug (or the table can't be queried yet — asyncpg's
# #         per-connection statement-plan cache occasionally serves a stale
# #         "table does not exist" plan reused across pooled connections),
# #         return a synthetic TenantResolved so the dev bypass flow works.
# #         """
# #         row = None
# #         try:
# #             async with engine.connect() as conn:
# #                 result = await conn.execute(
# #                     text(
# #                         "SELECT tenant_id, slug, schema_name, status "
# #                         "FROM public.tenants "
# #                         "WHERE slug = :slug AND deleted_at IS NULL"
# #                     ),
# #                     {"slug": slug},
# #                 )
# #                 row = result.fetchone()
# #         except Exception as exc:
# #             if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
# #                 raise
# #             row = None
# #         if row is not None:
# #             return TenantResolved(
# #                 tenant_id=row.tenant_id,
# #                 slug=row.slug,
# #                 schema_name=row.schema_name,
# #                 status=row.status,
# #             )
# #         # Dev bypass: no tenant provisioned yet — synthesize one so the
# #         # dev token flow works end-to-end without a real tenant row.
# #         # tenant_id must be an int to satisfy TenantResolved's type.
# #         settings = get_settings()
# #         if settings.SKIP_JWT_VERIFICATION:
# #             return TenantResolved(
# #                 tenant_id=0,
# #                 slug=slug,
# #                 schema_name="public",
# #                 status="ACTIVE",
# #             )
# #         return None

# """
# tenant_middleware.py — Resolves the tenant for every request.

# Resolution order (reference model Section 3.1):
#   1. Subdomain from the Host header (authoritative).
#   2. X-Tenant-Slug header — accepted on localhost only (dev fallback).
#   3. JWT Bearer 'tenant_slug' claim — fallback for deployments where
#      per-tenant subdomains are not yet wired. The claim is read WITHOUT
#      signature verification here; this middleware only IDENTIFIES the
#      tenant. Trust is established later by get_current_user() +
#      verify_tenant(), which verify the signature and cross-check the
#      claim against the resolved tenant.

# Registered AFTER CORSMiddleware in main.py (Starlette runs middleware in
# reverse registration order, so CORS wraps tenant resolution).
# """
# from __future__ import annotations

# import structlog
# from fastapi import Request, Response
# from fastapi.responses import JSONResponse
# from jose import JWTError, jwt
# from sqlalchemy import text
# from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# from app.core.config import get_settings
# from app.core.database import engine
# from app.schemas.tenant import TenantResolved

# logger = structlog.get_logger(__name__)

# # Paths served without a tenant context.
# EXEMPT_PREFIXES: tuple[str, ...] = (
#     "/health",
#     "/metrics",  # Prometheus scrape — no tenant context needed
#     "/docs",
#     "/redoc",
#     "/openapi.json",
#     "/platform",      # SUPER_ADMIN registry routes — legacy path (nginx /platform/ proxy)
#     "/api/platform",  # ISSUE-3 FIX: new canonical path (nginx /api/ proxy)
#     "/api/v1/public",  # Public landing-page data + contact form
#     "/api/v1/tenant-signup",  # Self-serve signup request (no auth, no tenant)
#     "/api/v1/payments/webhook",  # Stripe webhook — HMAC-verified, no tenant
#     # GDPR — public DSR submission + status check (data subjects may not be
#     # platform users). Authenticated GDPR endpoints (/gdpr/dsrs, /gdpr/consent,
#     # /gdpr/retention-status, /gdpr/export) require a tenant context and are
#     # NOT exempt. Platform-level SUPER_ADMIN GDPR routes (/gdpr/platform/*)
#     # are also exempt (they query the public schema only).
#     "/api/v1/gdpr/dsr",  # singular — POST /dsr + GET /dsr/{id}/status
#     "/api/v1/gdpr/platform",  # SUPER_ADMIN cross-tenant endpoints
#     # Retention policy CRUD + manual enforcement — SUPER_ADMIN only, public
#     # schema. Mounted at /api/v1/retention (see app/api/v1/retention.py).
#     "/api/v1/retention",
#     # One-click unsubscribe — public, token-verified. tenant_slug is embedded
#     # in the query string / request body rather than the subdomain.
#     "/api/v1/public/unsubscribe",
# )


# class TenantMiddleware(BaseHTTPMiddleware):
#     """Extracts the tenant and attaches it to request.state.tenant."""

#     async def dispatch(
#         self, request: Request, call_next: RequestResponseEndpoint
#     ) -> Response:
#         if self._is_exempt(request.url.path):
#             return await call_next(request)

#         slug = self._extract_slug(request)
#         if not slug:
#             return JSONResponse({"detail": "Tenant not identified"}, status_code=400)

#         tenant = await self._resolve_tenant(slug)
#         if tenant is None:
#             return JSONResponse(
#                 {"detail": f"Unknown tenant: {slug}"}, status_code=404
#             )
#         if not tenant.is_active:
#             return JSONResponse({"detail": "Tenant inactive"}, status_code=403)

#         request.state.tenant = tenant
#         return await call_next(request)

#     # ── Identification ──────────────────────────────────────────────────────

#     @staticmethod
#     def _is_exempt(path: str) -> bool:
#         return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)

#     def _extract_slug(self, request: Request) -> str | None:
#         settings = get_settings()
#         host = (request.headers.get("host") or "").split(":")[0].lower()

#         # 1 — Subdomain of BASE_DOMAIN (authoritative)
#         base = settings.BASE_DOMAIN.lower()
#         if host.endswith(f".{base}"):
#             candidate = host.removesuffix(f".{base}")
#             if candidate and "." not in candidate:
#                 return candidate

#         # 2 — Dev header, localhost only
#         if host in ("localhost", "127.0.0.1"):
#             header_slug = request.headers.get("x-tenant-slug")
#             if header_slug:
#                 return header_slug.lower()

#         # 3 — JWT claim fallback (identification only — NOT trust)
#         return self._slug_from_bearer(request)

#     @staticmethod
#     def _slug_from_bearer(request: Request) -> str | None:
#         auth = request.headers.get("authorization", "")
#         if not auth.lower().startswith("bearer "):
#             return None
#         token = auth[7:]
#         # Dev bypass: the frontend sends the literal string "dev-token"
#         # which is not a valid JWT. Return the dev tenant slug directly.
#         if token == "dev-token":
#             return "acme"
#         try:
#             claims = jwt.get_unverified_claims(token)
#         except JWTError:
#             return None
#         slug = claims.get("tenant_slug")
#         return slug.lower() if isinstance(slug, str) and slug else None

#     # ── Resolution ──────────────────────────────────────────────────────────

#     @staticmethod
#     async def _resolve_tenant(slug: str) -> TenantResolved | None:
#         """Look the slug up in public.tenants on a fresh connection.

#         Dev fallback: if SKIP_JWT_VERIFICATION is enabled and no DB row
#         exists for the slug (or the table can't be queried yet — asyncpg's
#         per-connection statement-plan cache occasionally serves a stale
#         "table does not exist" plan reused across pooled connections),
#         return a synthetic TenantResolved so the dev bypass flow works.
#         """
#         row = None
#         try:
#             async with engine.connect() as conn:
#                 result = await conn.execute(
#                     text(
#                         "SELECT tenant_id, slug, schema_name, status "
#                         "FROM public.tenants "
#                         "WHERE slug = :slug AND deleted_at IS NULL"
#                     ),
#                     {"slug": slug},
#                 )
#                 row = result.fetchone()
#         except Exception as exc:
#             if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
#                 raise
#             row = None
#         if row is not None:
#             return TenantResolved(
#                 tenant_id=row.tenant_id,
#                 slug=row.slug,
#                 schema_name=row.schema_name,
#                 status=row.status,
#             )
#         # Dev bypass: no tenant provisioned yet — synthesize one so the
#         # dev token flow works end-to-end without a real tenant row.
#         # tenant_id must be an int to satisfy TenantResolved's type.
#         settings = get_settings()
#         if settings.SKIP_JWT_VERIFICATION:
#             return TenantResolved(
#                 tenant_id=0,
#                 slug=slug,
#                 schema_name="public",
#                 status="ACTIVE",
#             )
#         return None
# """
# tenant_middleware.py — Resolves the tenant for every request.

# Resolution order (reference model Section 3.1):
#   1. Subdomain from the Host header (authoritative).
#   2. X-Tenant-Slug header — accepted on localhost only (dev fallback).
#   3. JWT Bearer 'tenant_slug' claim — fallback for deployments where
#      per-tenant subdomains are not yet wired. The claim is read WITHOUT
#      signature verification here; this middleware only IDENTIFIES the
#      tenant. Trust is established later by get_current_user() +
#      verify_tenant(), which verify the signature and cross-check the
#      claim against the resolved tenant.

# Registered AFTER CORSMiddleware in main.py (Starlette runs middleware in
# reverse registration order, so CORS wraps tenant resolution).
# """
# from __future__ import annotations

# import structlog
# from fastapi import Request, Response
# from fastapi.responses import JSONResponse
# from jose import JWTError, jwt
# from sqlalchemy import text
# from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# from app.core.config import get_settings
# from app.core.database import engine
# from app.schemas.tenant import TenantResolved

# logger = structlog.get_logger(__name__)

# # Paths served without a tenant context.
# EXEMPT_PREFIXES: tuple[str, ...] = (
#     "/health",
#     "/docs",
#     "/redoc",
#     "/openapi.json",
#     "/platform",      # SUPER_ADMIN registry routes — legacy path (nginx /platform/ proxy)
#   "/api/platform",  # ISSUE-3 FIX: new canonical path (nginx /api/ proxy)
#     "/api/v1/public",  # Public landing-page data + contact form
#     "/api/v1/tenant-signup",  # Self-serve signup request (no auth, no tenant)
#     "/api/v1/payments/webhook",  # Stripe webhook — HMAC-verified, no tenant
#     # GDPR — public DSR submission + status check (data subjects may not be
#     # platform users). Authenticated GDPR endpoints (/gdpr/dsrs, /gdpr/consent,
#     # /gdpr/retention-status, /gdpr/export) require a tenant context and are
#     # NOT exempt. Platform-level SUPER_ADMIN GDPR routes (/gdpr/platform/*)
#     # are also exempt (they query the public schema only).
#     "/api/v1/gdpr/dsr",  # singular — POST /dsr + GET /dsr/{id}/status
#     "/api/v1/gdpr/platform",  # SUPER_ADMIN cross-tenant endpoints
#     # Retention policy CRUD + manual enforcement — SUPER_ADMIN only, public
#     # schema. Mounted at /api/v1/retention (see app/api/v1/retention.py).
#     "/api/v1/retention",
#     # One-click unsubscribe — public, token-verified. tenant_slug is embedded
#     # in the query string / request body rather than the subdomain.
#     "/api/v1/public/unsubscribe",
# )


# class TenantMiddleware(BaseHTTPMiddleware):
#     """Extracts the tenant and attaches it to request.state.tenant."""

#     async def dispatch(
#         self, request: Request, call_next: RequestResponseEndpoint
#     ) -> Response:
#         if self._is_exempt(request.url.path):
#             return await call_next(request)

#         slug = self._extract_slug(request)
#         if not slug:
#             return JSONResponse({"detail": "Tenant not identified"}, status_code=400)

#         tenant = await self._resolve_tenant(slug)
#         if tenant is None:
#             return JSONResponse(
#                 {"detail": f"Unknown tenant: {slug}"}, status_code=404
#             )
#         if not tenant.is_active:
#             return JSONResponse({"detail": "Tenant inactive"}, status_code=403)

#         request.state.tenant = tenant
#         return await call_next(request)

#     # ── Identification ──────────────────────────────────────────────────────

#     @staticmethod
#     def _is_exempt(path: str) -> bool:
#         return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)

#     def _extract_slug(self, request: Request) -> str | None:
#         settings = get_settings()
#         host = (request.headers.get("host") or "").split(":")[0].lower()

#         # 1 — Subdomain of BASE_DOMAIN (authoritative)
#         base = settings.BASE_DOMAIN.lower()
#         if host.endswith(f".{base}"):
#             candidate = host.removesuffix(f".{base}")
#             if candidate and "." not in candidate:
#                 return candidate

#         # 2 — Dev header, localhost only
#         if host in ("localhost", "127.0.0.1"):
#             header_slug = request.headers.get("x-tenant-slug")
#             if header_slug:
#                 return header_slug.lower()

#         # 3 — JWT claim fallback (identification only — NOT trust)
#         return self._slug_from_bearer(request)

#     @staticmethod
#     def _slug_from_bearer(request: Request) -> str | None:
#         auth = request.headers.get("authorization", "")
#         if not auth.lower().startswith("bearer "):
#             return None
#         token = auth[7:]
#         # Dev bypass: the frontend sends the literal string "dev-token"
#         # which is not a valid JWT. Return the dev tenant slug directly.
#         if token == "dev-token":
#             return "acme"
#         try:
#             claims = jwt.get_unverified_claims(token)
#         except JWTError:
#             return None
#         slug = claims.get("tenant_slug")
#         return slug.lower() if isinstance(slug, str) and slug else None

#     # ── Resolution ──────────────────────────────────────────────────────────

#     @staticmethod
#     async def _resolve_tenant(slug: str) -> TenantResolved | None:
#         """Look the slug up in public.tenants on a fresh connection.

#         Dev fallback: if SKIP_JWT_VERIFICATION is enabled and no DB row
#         exists for the slug (or the table can't be queried yet — asyncpg's
#         per-connection statement-plan cache occasionally serves a stale
#         "table does not exist" plan reused across pooled connections),
#         return a synthetic TenantResolved so the dev bypass flow works.
#         """
#         row = None
#         try:
#             async with engine.connect() as conn:
#                 result = await conn.execute(
#                     text(
#                         "SELECT tenant_id, slug, schema_name, status "
#                         "FROM public.tenants "
#                         "WHERE slug = :slug AND deleted_at IS NULL"
#                     ),
#                     {"slug": slug},
#                 )
#                 row = result.fetchone()
#         except Exception as exc:
#             if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
#                 raise
#             row = None
#         if row is not None:
#             return TenantResolved(
#                 tenant_id=row.tenant_id,
#                 slug=row.slug,
#                 schema_name=row.schema_name,
#                 status=row.status,
#             )
#         # Dev bypass: no tenant provisioned yet — synthesize one so the
#         # dev token flow works end-to-end without a real tenant row.
#         # tenant_id must be an int to satisfy TenantResolved's type.
#         settings = get_settings()
#         if settings.SKIP_JWT_VERIFICATION:
#             return TenantResolved(
#                 tenant_id=0,
#                 slug=slug,
#                 schema_name="public",
#                 status="ACTIVE",
#             )
#         return None

"""
tenant_middleware.py — Resolves the tenant for every request.

Resolution order (reference model Section 3.1):
  1. Subdomain from the Host header (authoritative).
  2. X-Tenant-Slug header — accepted on localhost only (dev fallback).
  3. JWT Bearer 'tenant_slug' claim — fallback for deployments where
     per-tenant subdomains are not yet wired. The claim is read WITHOUT
     signature verification here; this middleware only IDENTIFIES the
     tenant. Trust is established later by get_current_user() +
     verify_tenant(), which verify the signature and cross-check the
     claim against the resolved tenant.

Registered AFTER CORSMiddleware in main.py (Starlette runs middleware in
reverse registration order, so CORS wraps tenant resolution).
"""
from __future__ import annotations

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings
from app.core.database import engine
from app.schemas.tenant import TenantResolved

logger = structlog.get_logger(__name__)

# Paths served without a tenant context.
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/metrics",  # Prometheus scrape — no tenant context needed
    "/docs",
    "/redoc",
    "/openapi.json",
    "/platform",      # SUPER_ADMIN registry routes — legacy path (nginx /platform/ proxy)
    "/api/platform",  # ISSUE-3 FIX: new canonical path (nginx /api/ proxy)
    "/api/v1/public",  # Public landing-page data + contact form
    "/api/v1/tenant-signup",  # Self-serve signup request (no auth, no tenant)
    "/api/v1/payments/webhook",  # Stripe webhook — HMAC-verified, no tenant
    # GDPR — public DSR submission + status check (data subjects may not be
    # platform users). Authenticated GDPR endpoints (/gdpr/dsrs, /gdpr/consent,
    # /gdpr/retention-status, /gdpr/export) require a tenant context and are
    # NOT exempt. Platform-level SUPER_ADMIN GDPR routes (/gdpr/platform/*)
    # are also exempt (they query the public schema only).
    "/api/v1/gdpr/dsr",  # singular — POST /dsr + GET /dsr/{id}/status
    "/api/v1/gdpr/platform",  # SUPER_ADMIN cross-tenant endpoints
    # Retention policy CRUD + manual enforcement — SUPER_ADMIN only, public
    # schema. Mounted at /api/v1/retention (see app/api/v1/retention.py).
    "/api/v1/retention",
    # One-click unsubscribe — public, token-verified. tenant_slug is embedded
    # in the query string / request body rather than the subdomain.
    "/api/v1/public/unsubscribe",
    # BatchSend completion webhook from MailBridge. Cannot rely on subdomain
    # resolution: MailBridge is a separate service with no guarantee that
    # every tenant's subdomain is DNS-resolvable/TLS-covered from wherever
    # it runs (wildcard DNS + wildcard cert per tenant is a heavier
    # deployment requirement than this webhook needs). Same pattern as
    # /api/v1/public/unsubscribe above: tenant_slug travels as a query
    # parameter instead, HMAC-verified inside the route itself — see
    # app/features/mailbridge/router.py::batch_complete.
    "/api/v1/mailbridge/batch-complete",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts the tenant and attaches it to request.state.tenant."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        slug = self._extract_slug(request)
        if not slug:
            return JSONResponse({"detail": "Tenant not identified"}, status_code=400)

        tenant = await self._resolve_tenant(slug)
        if tenant is None:
            return JSONResponse(
                {"detail": f"Unknown tenant: {slug}"}, status_code=404
            )
        if not tenant.is_active:
            return JSONResponse({"detail": "Tenant inactive"}, status_code=403)

        request.state.tenant = tenant
        return await call_next(request)

    # ── Identification ──────────────────────────────────────────────────────

    @staticmethod
    def _is_exempt(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)

    def _extract_slug(self, request: Request) -> str | None:
        settings = get_settings()
        host = (request.headers.get("host") or "").split(":")[0].lower()

        # 1 — Subdomain of BASE_DOMAIN (authoritative)
        base = settings.BASE_DOMAIN.lower()
        if host.endswith(f".{base}"):
            candidate = host.removesuffix(f".{base}")
            if candidate and "." not in candidate:
                return candidate

        # 2 — Dev header, localhost only
        if host in ("localhost", "127.0.0.1"):
            header_slug = request.headers.get("x-tenant-slug")
            if header_slug:
                return header_slug.lower()

        # 3 — JWT claim fallback (identification only — NOT trust)
        return self._slug_from_bearer(request)

    @staticmethod
    def _slug_from_bearer(request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth[7:]
        # Dev bypass: the frontend sends the literal string "dev-token"
        # which is not a valid JWT. Return the dev tenant slug directly.
        if token == "dev-token":
            return "acme"
        try:
            claims = jwt.get_unverified_claims(token)
        except JWTError:
            return None
        slug = claims.get("tenant_slug")
        return slug.lower() if isinstance(slug, str) and slug else None

    # ── Resolution ──────────────────────────────────────────────────────────

    @staticmethod
    async def _resolve_tenant(slug: str) -> TenantResolved | None:
        """Look the slug up in public.tenants on a fresh connection.

        Dev fallback: if SKIP_JWT_VERIFICATION is enabled and no DB row
        exists for the slug (or the table can't be queried yet — asyncpg's
        per-connection statement-plan cache occasionally serves a stale
        "table does not exist" plan reused across pooled connections),
        return a synthetic TenantResolved so the dev bypass flow works.
        """
        row = None
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT tenant_id, slug, schema_name, status "
                        "FROM public.tenants "
                        "WHERE slug = :slug AND deleted_at IS NULL"
                    ),
                    {"slug": slug},
                )
                row = result.fetchone()
        except Exception as exc:
            if "UndefinedTableError" not in type(exc).__name__ and "tenants" not in str(exc):
                raise
            row = None
        if row is not None:
            return TenantResolved(
                tenant_id=row.tenant_id,
                slug=row.slug,
                schema_name=row.schema_name,
                status=row.status,
            )
        # Dev bypass: no tenant provisioned yet — synthesize one so the
        # dev token flow works end-to-end without a real tenant row.
        # tenant_id must be an int to satisfy TenantResolved's type.
        settings = get_settings()
        if settings.SKIP_JWT_VERIFICATION:
            return TenantResolved(
                tenant_id=0,
                slug=slug,
                schema_name="public",
                status="ACTIVE",
            )
        return None