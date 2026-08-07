"""
test_rbac.py — Role hierarchy + tenant-claim guards.

Reference model §3.3, migration doc §4.7 + §D.2.
"""
from __future__ import annotations

import pytest
from app.api.security import verify_role, verify_tenant
from app.schemas.auth import ROLE_HIERARCHY, Role, TokenPayload
from fastapi import HTTPException
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


def _make_token(role: Role, tenant_slug: str | None = "acme") -> TokenPayload:
    return TokenPayload(
        sub="test-sub",
        email="test@example.com",
        role=role,
        tenant_slug=tenant_slug,
    )


def _make_request(tenant_slug: str | None):
    """A minimal stand-in for a Request with a resolved tenant on state."""
    class _Req:
        class state:
            pass
    req = _Req()
    if tenant_slug is None:
        req.state.tenant = None
    else:
        # Minimal tenant-like object.
        class _T:
            def __init__(self, slug):
                self.slug = slug
        req.state.tenant = _T(tenant_slug)
    return req


# ── Role hierarchy ────────────────────────────────────────────────────────────


def test_role_hierarchy_ordering():
    """SUPER_ADMIN > TENANT_ADMIN > MANAGER > REP."""
    assert ROLE_HIERARCHY[Role.SUPER_ADMIN] > ROLE_HIERARCHY[Role.TENANT_ADMIN]
    assert ROLE_HIERARCHY[Role.TENANT_ADMIN] > ROLE_HIERARCHY[Role.MANAGER]
    assert ROLE_HIERARCHY[Role.MANAGER] > ROLE_HIERARCHY[Role.REP]


@pytest.mark.parametrize(
    "token_role, required_role, ok",
    [
        (Role.REP, Role.REP, True),
        (Role.REP, Role.MANAGER, False),
        (Role.REP, Role.TENANT_ADMIN, False),
        (Role.REP, Role.SUPER_ADMIN, False),
        (Role.MANAGER, Role.REP, True),
        (Role.MANAGER, Role.MANAGER, True),
        (Role.MANAGER, Role.TENANT_ADMIN, False),
        (Role.TENANT_ADMIN, Role.REP, True),
        (Role.TENANT_ADMIN, Role.TENANT_ADMIN, True),
        (Role.TENANT_ADMIN, Role.SUPER_ADMIN, False),
        (Role.SUPER_ADMIN, Role.REP, True),
        (Role.SUPER_ADMIN, Role.SUPER_ADMIN, True),
    ],
)
def test_verify_role_matrix(token_role, required_role, ok):
    token = _make_token(token_role)
    if ok:
        verify_role(required_role, token)
    else:
        with pytest.raises(HTTPException) as exc:
            verify_role(required_role, token)
        assert exc.value.status_code == 403


# ── Tenant claim checks ───────────────────────────────────────────────────────


def test_verify_tenant_matches():
    token = _make_token(Role.REP, tenant_slug="acme")
    req = _make_request("acme")
    verify_tenant(req, token)  # no raise


def test_verify_tenant_mismatch_raises_403():
    token = _make_token(Role.REP, tenant_slug="acme")
    req = _make_request("globex")  # different tenant
    with pytest.raises(HTTPException) as exc:
        verify_tenant(req, token)
    assert exc.value.status_code == 403


def test_verify_tenant_super_admin_exempt():
    """SUPER_ADMIN (tenant_slug=None) can access any tenant's endpoints."""
    token = _make_token(Role.SUPER_ADMIN, tenant_slug=None)
    req = _make_request("acme")
    verify_tenant(req, token)  # no raise — super_admin is exempt


def test_verify_tenant_no_resolved_tenant_raises():
    """If TenantMiddleware didn't resolve a tenant, non-super-admin tokens
    must be rejected."""
    token = _make_token(Role.REP, tenant_slug="acme")
    req = _make_request(None)
    with pytest.raises(HTTPException) as exc:
        verify_tenant(req, token)
    assert exc.value.status_code == 403


# ── Slug validation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "slug, valid",
    [
        ("acme", True),
        ("acme-corp", True),
        ("abc", True),
        ("ab", False),                # too short
        ("a" * 64, False),            # too long
        ("Acme", False),              # uppercase
        ("acme_corp", False),         # underscore not allowed
        ("acme.corp", False),         # dot not allowed
        ("-acme", False),             # leading hyphen
        ("acme-", False),             # trailing hyphen
        ("www", False),               # reserved
        ("api", False),               # reserved
        ("admin", False),             # reserved
        ("", False),                  # empty
    ],
)
def test_slug_validation(slug: str, valid: bool):
    from app.utils.slug import SlugValidationError, validate_slug

    if valid:
        assert validate_slug(slug) == slug
    else:
        with pytest.raises(SlugValidationError):
            validate_slug(slug)


def test_schema_name_for_replaces_hyphens():
    from app.utils.slug import schema_name_for
    assert schema_name_for("acme") == "tenant_acme"
    assert schema_name_for("acme-corp") == "tenant_acme_corp"
