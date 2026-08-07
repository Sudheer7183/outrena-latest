"""
test_jwks_cache.py — JWKS is fetched once from Keycloak, cached in Redis,
and reused on subsequent requests.

Reference model §5, migration doc §7.4 + §D.2.
"""
from __future__ import annotations

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.mark.usefixtures("test_engine")
async def test_jwks_cache_hit_skips_keycloak_fetch(
    db_public,
    monkeypatch,
) -> None:
    """
    After the first JWKS fetch, subsequent verify_token() calls reuse the
    Redis cache and do NOT hit Keycloak.
    """
    from app.core.cache import get_json, platform_key, set_json
    from app.services.keycloak_admin_service import (
        _JWKS_CACHE_KEY,
        KeycloakAdminService,
        get_keycloak_admin_service,
    )

    # Use the real Redis (test fixture) but control the JWKS payload.
    fake_jwks = {
        "keys": [
            {
                "kid": "test-kid-1",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "fake-modulus",
                "e": "AQAB",
            }
        ]
    }
    await set_json(_JWKS_CACHE_KEY, fake_jwks, ttl_seconds=3600)

    # Build a service whose http_client is never called.
    svc = get_keycloak_admin_service()

    fetch_count = 0
    original_get = svc._http_client.get

    async def _counting_get(url, **kwargs):  # noqa: ARG001
        nonlocal fetch_count
        fetch_count += 1
        return await original_get(url, **kwargs)

    monkeypatch.setattr(svc._http_client, "get", _counting_get)

    # Call _get_jwks — should return the cached payload without hitting HTTP.
    jwks = await svc._get_jwks()
    assert jwks == fake_jwks
    assert fetch_count == 0, "JWKS cache miss — HTTP fetch occurred despite cached entry"


@pytest.mark.usefixtures("test_engine")
async def test_redis_namespace_platform_key(db_public) -> None:
    """Platform-level keys have no tenant prefix — verify the contract."""
    from app.core.cache import platform_key, tenant_key

    pk = platform_key("jwks", "keycloak")
    tk = tenant_key("tenant_acme", "jwks", "keycloak")

    assert pk == "jwks:keycloak"
    assert tk == "tenant_acme:jwks:keycloak"
    assert pk != tk
