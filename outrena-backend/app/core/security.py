"""
app/core/security.py — Phase 2: re-exports from app/api/security.py.

Phase 1 shipped a minimal stub here (SKIP_JWT_VERIFICATION only). Phase 2
delivers the full zero-trust guard set in app/api/security.py:
  - get_current_user   — JWKS-verified JWT decode (or dev bypass)
  - verify_role        — role-hierarchy check
  - verify_tenant      — JWT tenant_slug vs resolved tenant
  - require_role       — convenience dependency factory

This module re-exports them so existing imports like
`from app.core.security import require_role` continue to work.
New code should import from app.api.security directly.
"""
from __future__ import annotations

# Re-export the full Phase 2 implementation.
from app.api.security import (  # noqa: F401 — re-exported for compatibility
    get_current_user,
    require_role,
    verify_role,
    verify_tenant,
)
from app.schemas.auth import Role, TokenPayload  # noqa: F401

__all__ = [
    "Role",
    "TokenPayload",
    "get_current_user",
    "require_role",
    "verify_role",
    "verify_tenant",
]
