"""
test_provisioning_rollback.py — Verify the 6-step provisioning flow's
compensating rollback works correctly.

Reference model §4, migration doc §7.5.

If any step fails after the schema is created (Step 2), the rollback must:
  - DROP the schema (CASCADE)
  - Soft-delete the tenant record (set deleted_at = now())
  - Leave no orphan schema behind

This test simulates a failure in Step 5 (Keycloak user creation) by
injecting a MockKeycloakAdminService that raises on create_tenant_admin_user.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


class _FailingKeycloak:
    """Mock that fails Step 5 (create_tenant_admin_user)."""

    def __init__(self) -> None:
        self.add_redirect_called = False

    async def verify_token(self, token: str):  # noqa: ARG002
        raise RuntimeError("not used in this test")

    async def create_tenant_admin_user(self, **kwargs):  # noqa: ARG002
        raise RuntimeError("Simulated Keycloak outage")

    async def add_redirect_uris_to_frontend_client(self, tenant_slug: str) -> None:  # noqa: ARG002
        self.add_redirect_called = True


@pytest.mark.usefixtures("test_engine")
async def test_provisioning_rollback_on_keycloak_failure(
    db_public: AsyncSession,
    monkeypatch,
) -> None:
    """A failed Step 5 drops the schema + soft-deletes the tenant record."""
    failing_kc = _FailingKeycloak()
    from app.services import keycloak_admin_service as kcmod
    monkeypatch.setattr(kcmod, "get_keycloak_admin_service", lambda: failing_kc)

    from app.services.tenant_provisioning_service import TenantProvisioningService

    service = TenantProvisioningService(keycloak=failing_kc)

    # Patch the alembic subprocess step to a no-op (no migrations to run yet;
    # migration 0001 only handles public, and the tenant schema is empty).
    async def _fake_alembic(schema_name):  # noqa: ARG001
        return None
    monkeypatch.setattr(service, "_run_alembic_migration", staticmethod(_fake_alembic))

    # Provisioning should fail.
    from fastapi import HTTPException
    with pytest.raises((HTTPException, RuntimeError)):
        await service.provision_tenant(
            tenant_slug="failco",
            tenant_name="Failco Inc",
            tenant_type="STANDARD",
            admin_email="admin@failco.com",
            admin_first_name="A",
            admin_last_name="B",
            temporary_password=None,
            send_invitation=False,
            db=db_public,
        )

    # Verify schema is GONE (compensating rollback dropped it).
    async with db_public.bind.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = 'tenant_failco'"
            )
        )
        assert result.fetchone() is None, "Orphan schema tenant_failco left behind"

    # Verify tenant record is soft-deleted.
    result = await db_public.execute(
        text("SELECT deleted_at, status FROM public.tenants WHERE slug = 'failco'")
    )
    row = result.fetchone()
    assert row is not None, "Tenant row was hard-deleted (should be soft-deleted)"
    assert row.deleted_at is not None, "Tenant row's deleted_at is NULL"
    assert row.status == "PROVISIONING"


@pytest.mark.usefixtures("test_engine")
async def test_provisioning_happy_path(
    db_public: AsyncSession,
    mock_keycloak,
    monkeypatch,
) -> None:
    """End-to-end provisioning with a successful Keycloak mock."""
    from app.services.tenant_provisioning_service import TenantProvisioningService

    service = TenantProvisioningService(keycloak=mock_keycloak)

    # Stub alembic subprocess (no tenant-schema migrations exist yet).
    async def _fake_alembic(schema_name):  # noqa: ARG001
        return None
    monkeypatch.setattr(service, "_run_alembic_migration", staticmethod(_fake_alembic))

    slug = await service.provision_tenant(
        tenant_slug="happyco",
        tenant_name="Happy Co",
        tenant_type="STANDARD",
        admin_email="admin@happyco.com",
        admin_first_name="Hap",
        admin_last_name="Py",
        temporary_password="TempPass123!",
        send_invitation=False,
        db=db_public,
    )
    assert slug == "happyco"

    # Verify the tenant is ACTIVE in the registry.
    result = await db_public.execute(
        text("SELECT status, deleted_at FROM public.tenants WHERE slug = 'happyco'")
    )
    row = result.fetchone()
    assert row is not None
    assert row.status == "ACTIVE"
    assert row.deleted_at is None

    # Verify the schema exists.
    async with db_public.bind.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = 'tenant_happyco'"
            )
        )
        assert result.fetchone() is not None

    # Verify a tenant_config row was created.
    result = await db_public.execute(
        text("SELECT plan, max_seats, llm_provider_default FROM public.tenant_config tc "
             "JOIN public.tenants t ON tc.tenant_id = t.tenant_id WHERE t.slug = 'happyco'")
    )
    row = result.fetchone()
    assert row is not None
    assert row.plan == "alpha"
    assert row.max_seats == 5
    assert row.llm_provider_default == "zai"

    # Verify Keycloak user was created.
    assert len(mock_keycloak.users) == 1
    user = next(iter(mock_keycloak.users.values()))
    assert user["email"] == "admin@happyco.com"
    assert user["attributes"]["tenant_slug"] == ["happyco"]

    # Verify redirect URIs were registered.
    assert "https://happyco.localhost/*" in mock_keycloak.redirect_uris
