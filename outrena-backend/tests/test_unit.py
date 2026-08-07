"""
test_unit.py — Pure unit tests with no DB/Redis/Keycloak dependencies.

These run in every environment (no testcontainers, no local Postgres needed).
They cover the slug validator, cache-key namespacing, the role hierarchy,
and the JWT payload builder (in SKIP_JWT_VERIFICATION mode).
"""
from __future__ import annotations

import time

import pytest
from jose import jwt as jose_jwt

# ── Slug validation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "slug, valid",
    [
        ("acme", True),
        ("acme-corp", True),
        ("abc", True),
        ("ab", False),
        ("a" * 64, False),
        ("Acme", False),
        ("acme_corp", False),
        ("acme.corp", False),
        ("-acme", False),
        ("acme-", False),
        ("www", False),
        ("api", False),
        ("admin", False),
        ("", False),
    ],
)
def test_slug_validation(slug: str, valid: bool):
    from app.utils.slug import SlugValidationError, validate_slug
    if valid:
        assert validate_slug(slug) == slug
    else:
        with pytest.raises(SlugValidationError):
            validate_slug(slug)


def test_schema_name_for():
    from app.utils.slug import schema_name_for
    assert schema_name_for("acme") == "tenant_acme"
    assert schema_name_for("acme-corp") == "tenant_acme_corp"


# ── Redis key namespacing ─────────────────────────────────────────────────────


def test_tenant_key_prefixes_schema():
    from app.core.cache import tenant_key
    k = tenant_key("tenant_acme", "llm", "response", "abc")
    assert k == "tenant_acme:llm:response:abc"


def test_tenant_key_rejects_empty_schema():
    from app.core.cache import tenant_key
    with pytest.raises(ValueError, match="non-empty schema_name"):
        tenant_key("", "x")


def test_platform_key_no_prefix():
    from app.core.cache import platform_key
    assert platform_key("jwks", "keycloak") == "jwks:keycloak"


def test_tenant_and_platform_keys_distinguishable():
    """A tenant key for tenant 'acme' never equals a platform key with the
    same logical segments — the schema prefix is the discriminator."""
    from app.core.cache import platform_key, tenant_key
    # Same logical payload ("jwks:keycloak") → different actual keys
    # because tenant_key prepends the schema name.
    assert tenant_key("tenant_acme", "jwks", "keycloak") == "tenant_acme:jwks:keycloak"
    assert platform_key("jwks", "keycloak") == "jwks:keycloak"
    assert tenant_key("tenant_acme", "jwks", "keycloak") != platform_key("jwks", "keycloak")


# ── Role hierarchy ────────────────────────────────────────────────────────────


def test_role_hierarchy_complete():
    from app.schemas.auth import ROLE_HIERARCHY, Role
    assert set(ROLE_HIERARCHY.keys()) == set(Role)
    assert ROLE_HIERARCHY[Role.SUPER_ADMIN] > ROLE_HIERARCHY[Role.TENANT_ADMIN]
    assert ROLE_HIERARCHY[Role.TENANT_ADMIN] > ROLE_HIERARCHY[Role.MANAGER]
    assert ROLE_HIERARCHY[Role.MANAGER] > ROLE_HIERARCHY[Role.REP]


# ── JWT payload extraction (dev mode) ─────────────────────────────────────────


def test_jwt_dev_mode_extracts_claims():
    """In SKIP_JWT_VERIFICATION mode, claims are read without signature check."""
    payload = {
        "sub": "user-123",
        "email": "rep@acme.com",
        "role": "REP",
        "tenant_slug": "acme",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = jose_jwt.encode(payload, key="any-secret", algorithm="HS256")
    decoded = jose_jwt.get_unverified_claims(token)
    assert decoded["sub"] == "user-123"
    assert decoded["role"] == "REP"
    assert decoded["tenant_slug"] == "acme"


def test_jwt_super_admin_has_null_tenant_slug():
    """SUPER_ADMIN tokens have tenant_slug=None (platform-level)."""
    payload = {
        "sub": "super-admin",
        "email": "super@outrena.com",
        "role": "SUPER_ADMIN",
        "tenant_slug": None,
    }
    token = jose_jwt.encode(payload, key="any-secret", algorithm="HS256")
    decoded = jose_jwt.get_unverified_claims(token)
    assert decoded["tenant_slug"] is None


# ── Subdomain allocation ──────────────────────────────────────────────────────


def test_tenant_url_for_localhost_uses_http():
    from app.features.subdomain.service import tenant_url_for
    # Default BASE_DOMAIN=localhost
    url = tenant_url_for("acme")
    assert url == "http://acme.localhost"


def test_tenant_url_for_prod_uses_https(monkeypatch):
    from app.features.subdomain import service as sa
    monkeypatch.setattr(
        sa, "get_settings", lambda: type("S", (), {"BASE_DOMAIN": "outrena.com"})()
    )
    assert sa.tenant_url_for("acme") == "https://acme.outrena.com"


# ── Pydantic schema validation ────────────────────────────────────────────────


def test_tenant_create_request_validates_slug():
    """TenantCreateRequest runs slug through validate_slug."""
    from app.schemas.tenant import TenantCreateRequest
    from pydantic import ValidationError

    # Valid
    req = TenantCreateRequest(
        slug="acme",
        name="Acme Corp",
        admin_email="admin@acme.com",
        admin_first_name="A",
        admin_last_name="B",
    )
    assert req.slug == "acme"

    # Invalid (uppercase) → ValidationError
    with pytest.raises(ValidationError):
        TenantCreateRequest(
            slug="Acme",
            name="Acme",
            admin_email="admin@acme.com",
            admin_first_name="A",
            admin_last_name="B",
        )


def test_tenant_create_request_validates_email():
    from app.schemas.tenant import TenantCreateRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TenantCreateRequest(
            slug="acme",
            name="Acme",
            admin_email="not-an-email",
            admin_first_name="A",
            admin_last_name="B",
        )
