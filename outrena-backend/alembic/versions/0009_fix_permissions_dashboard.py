"""Fix permissions catalog: add missing dashboard.read permission.

Revision ID: 0009
Revises: 0008
Create Date: 2025-01-09 00:00:00

AUDIT-BE-1 / MEDIUM 9 (re-verification): The 0003_saas_platform.py migration
seeded a 37-entry ``public.permissions`` catalog (prospects/icp/campaigns/
sequences/email_studio/deals/meeting_prep/analytics/ab_testing/optimization/
integrations/llm_config/domain_settings/linkedin/users/roles/billing/support/
audit/help — counted 37 entries). However the ``_SYSTEM_ROLE_PERMS`` dict in
0003 (and the lib/nav-config gate downstream) references a 38th permission
key, ``dashboard.read``, that was never inserted into ``public.permissions``.

This broke the TENANT_ADMIN / MANAGER / REP role cards:
  - GET /api/v1/roles/permissions returned 37 entries but the role-permission
    join query selected 38 → the missing key was silently dropped from role
    detail responses.
  - SUPER_ADMIN/TENANT_ADMIN role-management UX showed a "phantom" permission
    assigned to roles but absent from the catalog.

This migration is IDEMPOTENT: it ON CONFLICT DO NOTHING inserts the missing
``dashboard.read`` row (category="optimize"), bringing the catalog to 38
entries as originally specced.

Branches on schema: PUBLIC-only (the permissions catalog lives in public).
Tenant-schema migrations are no-ops.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Permission to add ───────────────────────────────────────────────────────
# (key, display_name, description, category)
_NEW_PERMISSIONS: list[tuple[str, str, str, str]] = [
    (
        "dashboard.read",
        "Read Dashboard",
        "View the top-level dashboard (KPI cards, recent activity, charts).",
        "optimize",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Guard: only run on the public schema (tenant schemas have no
    # permissions table).
    schema = _current_schema()
    if schema != "public":
        return

    # Insert missing permissions idempotently.
    for key, disp, desc, cat in _NEW_PERMISSIONS:
        bind.execute(
            text(
                "INSERT INTO public.permissions "
                "(key, display_name, description, category) "
                "VALUES (:k, :d, :desc, :c) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"k": key, "d": disp, "desc": desc, "c": cat},
        )


def downgrade() -> None:
    """Remove the dashboard.read permission row.

    Idempotent — safe to run on schemas where the row doesn't exist.
    """
    schema = _current_schema()
    if schema != "public":
        return
    op.execute(
        text("DELETE FROM public.permissions WHERE key = 'dashboard.read'")
    )


def _current_schema() -> str:
    """Best-effort detection of the active schema for this migration step.

    Mirrors the convention used by 0007/0008 (which read
    ``context.get_context().version_table_schema``).
    """
    try:
        from alembic import context

        ctx = context.get_context()
        if ctx is None:
            return "public"
        return getattr(ctx, "version_table_schema", None) or "public"
    except Exception:  # noqa: BLE001 — never fail a downgrade/upgrade on context lookup
        return "public"


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
