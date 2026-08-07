"""Seed the dev 'acme' tenant row (local Docker Compose dev bypass only).

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-02

Without a real row in public.tenants, the SKIP_JWT_VERIFICATION dev-bypass
flow (app/middleware/tenant_middleware.py) had to synthesize a fake tenant
pointing at the "public" schema — but migration 0002+ explicitly skips the
"public" schema (tenant-scoped tables only exist in tenant_{slug} schemas),
so tables like SystemParameter and Domain were never actually created,
causing UndefinedTableError on every request.

This migration inserts a real 'acme' tenant row with schema_name=
'tenant_acme' and status='ACTIVE'. env.py's Mode B loop (run_migrations_online)
queries public.tenants for ACTIVE/PROVISIONING rows after this migration
completes and will automatically create + populate the tenant_acme schema
on the very next `alembic upgrade head` invocation (which happens on every
backend container start per docker-compose.yml).

Only runs against the public schema; no-op for any tenant schema pass.
Idempotent — ON CONFLICT DO NOTHING on the unique slug constraint.
"""
from __future__ import annotations

from typing import Union

from alembic import context, op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels = None
depends_on = None


def _s() -> str:
    """Return the active schema for this migration step (mirrors 0001/0002+)."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return ctx.version_table_schema or "public"


def upgrade() -> None:
    if _s() != "public":
        return  # tenant registry rows only ever live in public.tenants

    op.execute(
        text(
            "INSERT INTO public.tenants (slug, schema_name, name, tenant_type, status) "
            "VALUES ('acme', 'tenant_acme', 'Acme Inc. (Dev)', 'STANDARD', 'ACTIVE') "
            "ON CONFLICT ON CONSTRAINT uq_tenants_slug DO NOTHING"
        )
    )


def downgrade() -> None:
    if _s() != "public":
        return
    op.execute(text("DELETE FROM public.tenants WHERE slug = 'acme'"))