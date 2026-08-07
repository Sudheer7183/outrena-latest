"""
test_platform_routes.py — HTTP-level tests for the /platform/* router.

Uses FastAPI's TestClient (via ASGITransport) with a real Postgres + a mock
Keycloak. Verifies the Phase 2 exit criteria from migration doc §7.6.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def platform_client(test_engine, mock_keycloak):
    """ASGI client with the live FastAPI app, pointed at the test DB."""
    # Set environment so the app uses the test DB.
    import os
    os.environ["DATABASE_URL"] = str(test_engine.url)

    # Force settings cache to refresh.
    from app.core.config import get_settings
    get_settings.cache_clear()

    # Patch the engine in app.core.database to point at the test DB.
    import app.core.cache as cachemod
    import app.core.database as dbmod
    import app.middleware.tenant_middleware as tmm
    original_engine = dbmod.engine
    dbmod.engine = test_engine
    tmm.engine = test_engine

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore.
    dbmod.engine = original_engine
    tmm.engine = original_engine
    get_settings.cache_clear()


def _super_admin_headers(mint_jwt, auth_headers) -> dict[str, str]:
    return auth_headers(
        mint_jwt(
            sub="super-admin-id",
            email="superadmin@outrena.com",
            role="SUPER_ADMIN",
            tenant_slug=None,
        )
    )


@pytest.mark.usefixtures("test_engine")
async def test_list_tenants_empty(
    platform_client,
    mint_jwt,
    auth_headers,
    db_public,
) -> None:
    """GET /platform/tenants returns an empty list when no tenants exist."""
    # Clean slate
    await db_public.execute(text("DELETE FROM public.tenant_config"))
    await db_public.execute(text("DELETE FROM public.tenants"))
    await db_public.commit()

    headers = _super_admin_headers(mint_jwt, auth_headers)
    resp = await platform_client.get("/platform/tenants", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.usefixtures("test_engine")
async def test_slug_availability(
    platform_client,
    mint_jwt,
    auth_headers,
    db_public,
) -> None:
    """GET /platform/tenants/slug-availability returns availability + URL."""
    headers = _super_admin_headers(mint_jwt, auth_headers)

    # Clean — 'free-co' should be available.
    await db_public.execute(text("DELETE FROM public.tenant_config"))
    await db_public.execute(text("DELETE FROM public.tenants"))
    await db_public.commit()

    resp = await platform_client.get(
        "/platform/tenants/slug-availability",
        params={"slug": "free-co"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "free-co"
    assert body["available"] is True
    assert body["url"] == "http://free-co.localhost"


@pytest.mark.usefixtures("test_engine")
async def test_slug_availability_rejects_reserved(
    platform_client,
    mint_jwt,
    auth_headers,
) -> None:
    """Reserved slugs (www, api, admin) are not available."""
    headers = _super_admin_headers(mint_jwt, auth_headers)
    for slug in ["www", "api", "admin"]:
        resp = await platform_client.get(
            "/platform/tenants/slug-availability",
            params={"slug": slug},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False


@pytest.mark.usefixtures("test_engine")
async def test_slug_availability_rejects_invalid(
    platform_client,
    mint_jwt,
    auth_headers,
) -> None:
    """Invalid slugs (too short, uppercase, etc.) are not available."""
    headers = _super_admin_headers(mint_jwt, auth_headers)
    for slug in ["ab", "Acme", "acme_corp"]:
        resp = await platform_client.get(
            "/platform/tenants/slug-availability",
            params={"slug": slug},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False


@pytest.mark.usefixtures("test_engine")
async def test_platform_routes_require_super_admin(
    platform_client,
    mint_jwt,
    auth_headers,
) -> None:
    """Non-SUPER_ADMIN tokens are rejected with 403."""
    rep_token = mint_jwt(
        sub="rep-id",
        email="rep@acme.com",
        role="REP",
        tenant_slug="acme",
    )
    resp = await platform_client.get(
        "/platform/tenants",
        headers=auth_headers(rep_token),
    )
    assert resp.status_code == 403


@pytest.mark.usefixtures("test_engine")
async def test_platform_routes_require_auth(platform_client) -> None:
    """No Bearer token → 401."""
    resp = await platform_client.get("/platform/tenants")
    assert resp.status_code == 401


@pytest.mark.usefixtures("test_engine")
async def test_suspend_and_reactivate_tenant(
    platform_client,
    mint_jwt,
    auth_headers,
    db_public,
) -> None:
    """POST /platform/tenants/{id}/suspend and /reactivate toggle status."""
    # Insert a tenant directly.
    await db_public.execute(
        text(
            "INSERT INTO public.tenants (slug, schema_name, name, status) "
            "VALUES ('susco', 'tenant_susco', 'Sus Co', 'ACTIVE')"
        )
    )
    await db_public.commit()
    result = await db_public.execute(
        text("SELECT tenant_id FROM public.tenants WHERE slug = 'susco'")
    )
    tenant_id = result.scalar()

    headers = _super_admin_headers(mint_jwt, auth_headers)

    # Suspend
    resp = await platform_client.post(
        f"/platform/tenants/{tenant_id}/suspend", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUSPENDED"

    # Reactivate
    resp = await platform_client.post(
        f"/platform/tenants/{tenant_id}/reactivate", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"
