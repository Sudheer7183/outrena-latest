# """
# security.py — Zero-trust guards: JWT decode, role, and tenant checks.

# Reference model Section 3.3. Every protected endpoint applies, in order:
#   1. get_current_user()   — signature-verified claims (JWKS, RS256)
#   2. verify_role()        — role hierarchy check
#   3. verify_tenant()      — JWT tenant_slug must match the resolved tenant

# OUTRENA has no second-level partition (no workspace scope), so the
# verify_workspace_scope guard from the reference is omitted.
# """
# from __future__ import annotations

# import structlog
# from fastapi import Depends, HTTPException, Request, status
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# from jose import JWTError, jwt

# from app.core.config import get_settings
# from app.schemas.auth import ROLE_HIERARCHY, Role, TokenPayload

# logger = structlog.get_logger(__name__)

# _bearer_scheme = HTTPBearer(auto_error=False)

# _KNOWN_REALM_ROLES: frozenset[str] = frozenset(
#     role.value.lower() for role in Role
# )


# # ---------------------------------------------------------------------------
# # 1 — JWT decoding / validation
# # ---------------------------------------------------------------------------


# async def get_current_user(
#     request: Request,
#     credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
# ) -> TokenPayload:
#     """
#     FastAPI dependency: decode the Bearer JWT and return validated claims.

#     Production: JWKS fetched from the identity provider (Redis-cached,
#     TTL 3600s), RS256 signature verified before any claim is trusted.
#     Dev (SKIP_JWT_VERIFICATION=true): decodes without verification.
#     """
#     settings = get_settings()

#     if credentials is None:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authentication credentials are missing.",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     if settings.SKIP_JWT_VERIFICATION:
#         # Dev bypass: the frontend sends the literal string "dev-token" which
#         # is not a valid JWT. Return a synthetic TENANT_ADMIN payload so all
#         # role gates pass without a real Keycloak instance.
#         if credentials.credentials == "dev-token":
#             # SUPER_ADMIN so all role gates (including /llm-configs and
#             # platform-level endpoints) pass in local development without
#             # a real Keycloak instance. tenant_slug=None is the canonical
#             # marker for a platform-level token per Role.SUPER_ADMIN semantics.
#             payload = {
#                 "sub": "dev-user",
#                 "email": "admin@outrena.dev",
#                 "role": "SUPER_ADMIN",
#                 "tenant_slug": "acme",
#             }
#         else:
#             try:
#                 payload = jwt.get_unverified_claims(credentials.credentials)
#             except JWTError as exc:
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Malformed token.",
#                 ) from exc
#     else:
#         from app.services.keycloak_admin_service import get_keycloak_admin_service

#         payload = await get_keycloak_admin_service().verify_token(
#             credentials.credentials
#         )

#     return _payload_to_token(payload)


# def _payload_to_token(payload: dict[str, object]) -> TokenPayload:
#     """Map raw claims to TokenPayload; 401 on missing/invalid claims."""
#     try:
#         raw_role = payload.get("role")
#         if not raw_role:
#             # Fallback: Keycloak-native realm_access.roles array
#             realm_access = payload.get("realm_access") or {}
#             roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
#             matched = [r for r in roles if isinstance(r, str) and r.lower() in _KNOWN_REALM_ROLES]
#             raw_role = matched[0] if matched else None
#         if not isinstance(raw_role, str):
#             raise KeyError("role")
#         tenant_slug = payload.get("tenant_slug")
#         return TokenPayload(
#             sub=str(payload["sub"]),
#             email=str(payload.get("email", "")),
#             role=Role(raw_role.upper()),
#             tenant_slug=tenant_slug if isinstance(tenant_slug, str) else None,
#         )
#     except (KeyError, ValueError) as exc:
#         logger.warning("security.token_payload.invalid", error=str(exc))
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token contains invalid or missing claims.",
#         ) from exc


# # ---------------------------------------------------------------------------
# # 2 — Role hierarchy
# # ---------------------------------------------------------------------------


# def verify_role(required_role: Role, token: TokenPayload) -> None:
#     """Raise HTTP 403 if the token role is below the required minimum."""
#     if ROLE_HIERARCHY[token.role] < ROLE_HIERARCHY[required_role]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=f"Role '{token.role.value}' lacks permission "
#             f"(requires '{required_role.value}' or higher).",
#         )


# # ---------------------------------------------------------------------------
# # 3 — Tenant claim vs resolved tenant
# # ---------------------------------------------------------------------------


# def verify_tenant(request: Request, token: TokenPayload) -> None:
#     """
#     Raise HTTP 403 if the JWT tenant_slug does not match the tenant the
#     middleware resolved for this request. SUPER_ADMIN (tenant_slug=None)
#     is exempt.
#     """
#     if token.role is Role.SUPER_ADMIN:
#         return
#     tenant = getattr(request.state, "tenant", None)
#     if tenant is None or token.tenant_slug != tenant.slug:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Token tenant does not match the requested tenant.",
#         )


# # ---------------------------------------------------------------------------
# # Convenience dependency factories
# # ---------------------------------------------------------------------------


# def require_role(required_role: Role):
#     """
#     Return a FastAPI dependency that enforces both authentication and role.

#     Usage:
#         @router.get("/", dependencies=[Depends(require_role(Role.MANAGER))])
#         async def list_items(...): ...
#     """
#     async def _dependency(
#         request: Request,
#         token: TokenPayload = Depends(get_current_user),
#     ) -> TokenPayload:
#         verify_role(required_role, token)
#         verify_tenant(request, token)
#         return token

#     return _dependency


# # ---------------------------------------------------------------------------
# # 4 — Fine-grained permission + feature-key gates (data-driven RBAC)
# # ---------------------------------------------------------------------------


# async def _resolve_permissions(
#     request: Request, token: TokenPayload
# ) -> set[str]:
#     """Resolve the caller's permission-key set via RbacService.

#     SUPER_ADMIN short-circuits to a wildcard that grants every key.
#     Otherwise the tenant's roles table is consulted on a fresh session
#     locked to the tenant schema. Falls back to the static
#     SYSTEM_ROLE_PERMISSIONS map if no tenant context is available.
#     """
#     if token.role is Role.SUPER_ADMIN:
#         return {"*"}  # wildcard — short-circuits has_permission checks

#     from sqlalchemy import text as _text
#     from app.core.database import AsyncSessionLocal
#     from app.services.rbac_service import RbacService, SYSTEM_ROLE_PERMISSIONS

#     tenant = getattr(request.state, "tenant", None)
#     if tenant is None or not getattr(tenant, "schema_name", None):
#         return set(SYSTEM_ROLE_PERMISSIONS.get(token.role, []))
#     async with AsyncSessionLocal() as session:
#         await session.execute(
#             _text(f'SET search_path TO "{tenant.schema_name}", public')
#         )
#         return await RbacService().get_user_permissions(session, token.role, token.sub)


# def require_permission(permission_key: str):
#     """
#     Return a FastAPI dependency that enforces the given permission key.

#     Usage:
#         @router.post("/", dependencies=[Depends(require_permission("campaigns.write"))])
#         async def create_campaign(...): ...

#     Resolution:
#       1. Authenticate (get_current_user) + verify_tenant.
#       2. Resolve the caller's permission set via RbacService.
#       3. 403 if ``permission_key`` is not in the set.

#     SUPER_ADMIN tokens short-circuit to a wildcard that grants every key.
#     """
#     async def _dependency(
#         request: Request,
#         token: TokenPayload = Depends(get_current_user),
#     ) -> TokenPayload:
#         verify_tenant(request, token)
#         perms = await _resolve_permissions(request, token)
#         if "*" in perms or permission_key in perms:
#             return token
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=f"Missing permission '{permission_key}'.",
#         )

#     return _dependency


# def require_feature(feature_key: str):
#     """
#     Return a FastAPI dependency that enforces the permission mapped to a
#     frontend nav feature_key. The map lives in public.feature_permissions
#     (managed by SUPER_ADMIN via PUT /api/v1/feature-permissions/{key}).

#     Usage:
#         @router.get("/", dependencies=[Depends(require_feature("autopilot"))])
#         async def autopilot_home(...): ...

#     A feature_key with no required_permission (NULL) is treated as open
#     to every authenticated user (the help_getting_started feature).
#     """
#     async def _dependency(
#         request: Request,
#         token: TokenPayload = Depends(get_current_user),
#     ) -> TokenPayload:
#         verify_tenant(request, token)
#         # Look up the required permission for this feature_key on a fresh
#         # session locked to the tenant schema.
#         from sqlalchemy import select as _select
#         from sqlalchemy import text as _text
#         from app.core.database import AsyncSessionLocal
#         from app.models.feature_permission import FeaturePermission

#         required: str | None = None
#         tenant = getattr(request.state, "tenant", None)
#         if tenant is not None and getattr(tenant, "schema_name", None):
#             async with AsyncSessionLocal() as session:
#                 await session.execute(
#                     _text(f'SET search_path TO "{tenant.schema_name}", public')
#                 )
#                 row = (
#                     await session.execute(
#                         _select(FeaturePermission).where(
#                             FeaturePermission.feature_key == feature_key
#                         )
#                     )
#                 ).scalar_one_or_none()
#                 required = row.required_permission if row is not None else None

#         if not required:
#             return token  # open feature

#         perms = await _resolve_permissions(request, token)
#         if "*" in perms or required in perms:
#             return token
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=f"Missing permission '{required}' required by feature '{feature_key}'.",
#         )

#     return _dependency

"""
security.py — Zero-trust guards: JWT decode, role, and tenant checks.

Reference model Section 3.3. Every protected endpoint applies, in order:
  1. get_current_user()   — signature-verified claims (JWKS, RS256)
  2. verify_role()        — role hierarchy check
  3. verify_tenant()      — JWT tenant_slug must match the resolved tenant

OUTRENA has no second-level partition (no workspace scope), so the
verify_workspace_scope guard from the reference is omitted.
"""
from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.schemas.auth import ROLE_HIERARCHY, Role, TokenPayload

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_KNOWN_REALM_ROLES: frozenset[str] = frozenset(
    role.value.lower() for role in Role
)


# ---------------------------------------------------------------------------
# 1 — JWT decoding / validation
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    FastAPI dependency: decode the Bearer JWT and return validated claims.

    Production: JWKS fetched from the identity provider (Redis-cached,
    TTL 3600s), RS256 signature verified before any claim is trusted.
    Dev (SKIP_JWT_VERIFICATION=true): decodes without verification.
    """
    settings = get_settings()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.SKIP_JWT_VERIFICATION:
        # Dev bypass: the frontend sends the literal string "dev-token" which
        # is not a valid JWT. Return a synthetic TENANT_ADMIN payload so all
        # role gates pass without a real Keycloak instance.
        if credentials.credentials == "dev-token":
            # SUPER_ADMIN so all role gates (including /llm-configs and
            # platform-level endpoints) pass in local development without
            # a real Keycloak instance. tenant_slug=None is the canonical
            # marker for a platform-level token per Role.SUPER_ADMIN semantics.
            payload = {
                "sub": "dev-user",
                "email": "admin@outrena.dev",
                "role": "SUPER_ADMIN",
                "tenant_slug": "acme",
            }
        else:
            try:
                payload = jwt.get_unverified_claims(credentials.credentials)
            except JWTError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Malformed token.",
                ) from exc
    else:
        from app.services.keycloak_admin_service import get_keycloak_admin_service

        payload = await get_keycloak_admin_service().verify_token(
            credentials.credentials
        )

    return _payload_to_token(payload)


def _payload_to_token(payload: dict[str, object]) -> TokenPayload:
    """Map raw claims to TokenPayload; 401 on missing/invalid claims.

    Role resolution order:
    1. 'role' claim (flat string) — set by oidc-usermodel-attribute-mapper
       on the frontend client. Value is already uppercase (TENANT_ADMIN etc.)
    2. realm_access.roles array — Keycloak's native role format (lowercase).
       Matched against _KNOWN_REALM_ROLES and uppercased.
    3. Single realmRole from 'roles' top-level claim (some Keycloak versions).
    """
    try:
        raw_role = payload.get("role")

        # Tier 1: flat string claim (our custom mapper)
        if raw_role and isinstance(raw_role, str):
            pass  # use as-is
        else:
            # Tier 2: realm_access.roles array (Keycloak native)
            raw_role = None
            realm_access = payload.get("realm_access") or {}
            roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
            # Filter out Keycloak built-in roles (offline_access, uma_authorization)
            matched = [
                r for r in roles
                if isinstance(r, str) and r.lower() in _KNOWN_REALM_ROLES
            ]
            if matched:
                raw_role = matched[0]

        # Tier 3: top-level 'roles' array (some Keycloak mapper configs)
        if not raw_role:
            top_roles = payload.get("roles") or []
            if isinstance(top_roles, list):
                matched = [
                    r for r in top_roles
                    if isinstance(r, str) and r.lower() in _KNOWN_REALM_ROLES
                ]
                if matched:
                    raw_role = matched[0]

        if not raw_role or not isinstance(raw_role, str):
            logger.warning(
                "security.token_payload.no_role_claim",
                available_keys=list(payload.keys()),
                realm_access=payload.get("realm_access"),
            )
            raise KeyError("role")
        tenant_slug = payload.get("tenant_slug")
        return TokenPayload(
            sub=str(payload["sub"]),
            email=str(payload.get("email", "")),
            role=Role(raw_role.upper()),
            tenant_slug=tenant_slug if isinstance(tenant_slug, str) else None,
        )
    except (KeyError, ValueError) as exc:
        logger.warning("security.token_payload.invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains invalid or missing claims.",
        ) from exc


# ---------------------------------------------------------------------------
# 2 — Role hierarchy
# ---------------------------------------------------------------------------


def verify_role(required_role: Role, token: TokenPayload) -> None:
    """Raise HTTP 403 if the token role is below the required minimum."""
    if ROLE_HIERARCHY[token.role] < ROLE_HIERARCHY[required_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{token.role.value}' lacks permission "
            f"(requires '{required_role.value}' or higher).",
        )


# ---------------------------------------------------------------------------
# 3 — Tenant claim vs resolved tenant
# ---------------------------------------------------------------------------


def verify_tenant(request: Request, token: TokenPayload) -> None:
    """
    Raise HTTP 403 if the JWT tenant_slug does not match the tenant the
    middleware resolved for this request. SUPER_ADMIN (tenant_slug=None)
    is exempt.
    """
    if token.role is Role.SUPER_ADMIN:
        return
    tenant = getattr(request.state, "tenant", None)
    if tenant is None or token.tenant_slug != tenant.slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token tenant does not match the requested tenant.",
        )


# ---------------------------------------------------------------------------
# Convenience dependency factories
# ---------------------------------------------------------------------------


def require_role(required_role: Role):
    """
    Return a FastAPI dependency that enforces both authentication and role.

    Usage:
        @router.get("/", dependencies=[Depends(require_role(Role.MANAGER))])
        async def list_items(...): ...
    """
    async def _dependency(
        request: Request,
        token: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        verify_role(required_role, token)
        verify_tenant(request, token)
        return token

    return _dependency


# ---------------------------------------------------------------------------
# 4 — Fine-grained permission + feature-key gates (data-driven RBAC)
# ---------------------------------------------------------------------------


async def _resolve_permissions(
    request: Request, token: TokenPayload
) -> set[str]:
    """Resolve the caller's permission-key set via RbacService.

    SUPER_ADMIN short-circuits to a wildcard that grants every key.
    Otherwise the tenant's roles table is consulted on a fresh session
    locked to the tenant schema. Falls back to the static
    SYSTEM_ROLE_PERMISSIONS map if no tenant context is available.
    """
    if token.role is Role.SUPER_ADMIN:
        return {"*"}  # wildcard — short-circuits has_permission checks

    from sqlalchemy import text as _text
    from app.core.database import AsyncSessionLocal
    from app.services.rbac_service import RbacService, SYSTEM_ROLE_PERMISSIONS

    tenant = getattr(request.state, "tenant", None)
    if tenant is None or not getattr(tenant, "schema_name", None):
        return set(SYSTEM_ROLE_PERMISSIONS.get(token.role, []))
    async with AsyncSessionLocal() as session:
        await session.execute(
            _text(f'SET search_path TO "{tenant.schema_name}", public')
        )
        return await RbacService().get_user_permissions(session, token.role, token.sub)


def require_permission(permission_key: str):
    """
    Return a FastAPI dependency that enforces the given permission key.

    Usage:
        @router.post("/", dependencies=[Depends(require_permission("campaigns.write"))])
        async def create_campaign(...): ...

    Resolution:
      1. Authenticate (get_current_user) + verify_tenant.
      2. Resolve the caller's permission set via RbacService.
      3. 403 if ``permission_key`` is not in the set.

    SUPER_ADMIN tokens short-circuit to a wildcard that grants every key.
    """
    async def _dependency(
        request: Request,
        token: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        verify_tenant(request, token)
        perms = await _resolve_permissions(request, token)
        if "*" in perms or permission_key in perms:
            return token
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission '{permission_key}'.",
        )

    return _dependency


def require_feature(feature_key: str):
    """
    Return a FastAPI dependency that enforces the permission mapped to a
    frontend nav feature_key. The map lives in public.feature_permissions
    (managed by SUPER_ADMIN via PUT /api/v1/feature-permissions/{key}).

    Usage:
        @router.get("/", dependencies=[Depends(require_feature("autopilot"))])
        async def autopilot_home(...): ...

    A feature_key with no required_permission (NULL) is treated as open
    to every authenticated user (the help_getting_started feature).
    """
    async def _dependency(
        request: Request,
        token: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        verify_tenant(request, token)
        # Look up the required permission for this feature_key on a fresh
        # session locked to the tenant schema.
        from sqlalchemy import select as _select
        from sqlalchemy import text as _text
        from app.core.database import AsyncSessionLocal
        from app.models.feature_permission import FeaturePermission

        required: str | None = None
        tenant = getattr(request.state, "tenant", None)
        if tenant is not None and getattr(tenant, "schema_name", None):
            async with AsyncSessionLocal() as session:
                await session.execute(
                    _text(f'SET search_path TO "{tenant.schema_name}", public')
                )
                row = (
                    await session.execute(
                        _select(FeaturePermission).where(
                            FeaturePermission.feature_key == feature_key
                        )
                    )
                ).scalar_one_or_none()
                required = row.required_permission if row is not None else None

        if not required:
            return token  # open feature

        perms = await _resolve_permissions(request, token)
        if "*" in perms or required in perms:
            return token
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission '{required}' required by feature '{feature_key}'.",
        )

    return _dependency