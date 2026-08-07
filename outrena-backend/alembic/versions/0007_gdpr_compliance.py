"""GDPR compliance layer (SAAS2-GDPR-BE).

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-07 00:00:00

This migration branches on schema (same pattern as 0002/0003):

  PUBLIC schema → creates:
      public.data_subject_requests (DSR registry — Article 15-22)
      public.retention_policies (key-value: policy_name, days, action, ...)
      + seeds the retention_policies table with the 5 default policies
        (prospects_inactive / consent_logs / email_events / audit_logs /
        support_tickets_resolved).

  tenant_{slug} schema → creates:
      consents (Consent — Article 7)
      consent_logs (ConsentLog — append-only audit trail)
      + ALTERs "Prospect" to add 4 GDPR columns:
          consent_status   VARCHAR(32) NOT NULL DEFAULT 'pending'
          lawful_basis     VARCHAR(32) NOT NULL DEFAULT 'legitimate_interest'
          deleted_at       TIMESTAMP NULL  (soft-delete / right-to-erasure)
          anonymized       BOOLEAN NOT NULL DEFAULT false
      + CREATE INDEX on "Prospect"(deleted_at), "Prospect"(consent_status),
        consents(email), consents(prospect_id)

  Data migration note:
      Existing Prospect rows (created before GDPR compliance was wired) get
      consent_status='pending' — they have NOT explicitly consented under
      GDPR. Operators MUST obtain fresh consent from existing prospects OR
      rely on the lawful_basis='legitimate_interest' default (Article 6(1)(f))
      for B2B outreach. The lawful_basis default of 'legitimate_interest'
      applies to all existing rows; operators who switch a prospect's basis
      to 'consent' must obtain explicit consent before any further processing.

  Both branches are import-safe: no app imports that require a DB.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0002/0003 conventions) ──────────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return getattr(ctx, "version_table_schema", None) or "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


def _column_exists(bind, schema: str, table: str, column: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(bind, schema: str, table: str, index: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table "
            "AND indexname = :index"
        ),
        {"schema": schema, "table": table, "index": index},
    )
    return result.fetchone() is not None


# ── Retention policy defaults (mirrors RetentionService.RETENTION_POLICIES) ─

_RETENTION_POLICIES = [
    # (policy_name, days, action, description)
    (
        "prospects_inactive",
        730,
        "anonymize",
        "Prospects with no activity in the last 2 years are anonymised.",
    ),
    (
        "consent_logs",
        1095,
        "delete",
        "Consent log entries older than 3 years are hard-deleted.",
    ),
    (
        "email_events",
        365,
        "delete",
        "Per-recipient email engagement events older than 1 year are deleted.",
    ),
    (
        "audit_logs",
        2555,
        "delete",
        "Platform audit log rows older than 7 years are hard-deleted (SOC2).",
    ),
    (
        "support_tickets_resolved",
        365,
        "anonymize",
        "Resolved support tickets older than 1 year are anonymised.",
    ),
]


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    if schema == "public":
        _upgrade_public()
    else:
        _upgrade_tenant(schema)


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        _downgrade_public()
    else:
        _downgrade_tenant(schema)


# ── PUBLIC schema upgrade ────────────────────────────────────────────────────


def _upgrade_public() -> None:
    bind = op.get_bind()

    # ── public.data_subject_requests ────────────────────────────────────────
    if not _table_exists(bind, "public", "data_subject_requests"):
        op.create_table(
            "data_subject_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("request_type", sa.String(length=32), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("tenant_slug", sa.String(length=63), nullable=False),
            sa.Column(
                "details",
                sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "status", sa.String(length=32),
                nullable=False, server_default="pending",
            ),
            sa.Column("assigned_to", sa.String(length=128), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completion_notes", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("export_url", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )
        op.create_index(
            "ix_dsr_email", "data_subject_requests", ["email"], schema="public"
        )
        op.create_index(
            "ix_dsr_tenant_slug", "data_subject_requests", ["tenant_slug"],
            schema="public",
        )
        op.create_index(
            "ix_dsr_status", "data_subject_requests", ["status"], schema="public"
        )

    # ── public.retention_policies ───────────────────────────────────────────
    if not _table_exists(bind, "public", "retention_policies"):
        op.create_table(
            "retention_policies",
            sa.Column("policy_name", sa.String(length=80), nullable=False),
            sa.Column("days", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("policy_name"),
            schema="public",
        )

    # ── Seed retention policies (idempotent) ────────────────────────────────
    _seed_retention_policies(bind)


def _seed_retention_policies(bind) -> None:
    for name, days, action, desc in _RETENTION_POLICIES:
        bind.execute(
            text(
                "INSERT INTO public.retention_policies "
                "(policy_name, days, action, description) "
                "VALUES (:name, :days, :action, :desc) "
                "ON CONFLICT (policy_name) DO UPDATE SET "
                "  days = EXCLUDED.days, "
                "  action = EXCLUDED.action, "
                "  description = EXCLUDED.description, "
                "  updated_at = now()"
            ),
            {"name": name, "days": days, "action": action, "desc": desc},
        )


# ── TENANT schema upgrade ────────────────────────────────────────────────────


def _upgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # ── ALTER Prospect: add 4 GDPR columns (additive, idempotent) ──────────
    if not _column_exists(bind, schema, "Prospect", "consent_status"):
        bind.execute(
            text(
                f'ALTER TABLE "{schema}"."Prospect" '
                f"ADD COLUMN consent_status VARCHAR(32) NOT NULL "
                f"DEFAULT 'pending'"
            )
        )
    if not _column_exists(bind, schema, "Prospect", "lawful_basis"):
        bind.execute(
            text(
                f'ALTER TABLE "{schema}"."Prospect" '
                f"ADD COLUMN lawful_basis VARCHAR(32) NOT NULL "
                f"DEFAULT 'legitimate_interest'"
            )
        )
    if not _column_exists(bind, schema, "Prospect", "deleted_at"):
        bind.execute(
            text(
                f'ALTER TABLE "{schema}"."Prospect" '
                f"ADD COLUMN deleted_at TIMESTAMP NULL"
            )
        )
    if not _column_exists(bind, schema, "Prospect", "anonymized"):
        bind.execute(
            text(
                f'ALTER TABLE "{schema}"."Prospect" '
                f"ADD COLUMN anonymized BOOLEAN NOT NULL "
                f"DEFAULT false"
            )
        )

    # ── Indexes on Prospect (idempotent) ────────────────────────────────────
    if not _index_exists(bind, schema, "Prospect", "ix_Prospect_deleted_at"):
        op.create_index(
            "ix_Prospect_deleted_at", "Prospect", ["deleted_at"], schema=schema
        )
    if not _index_exists(bind, schema, "Prospect", "ix_Prospect_consent_status"):
        op.create_index(
            "ix_Prospect_consent_status", "Prospect", ["consent_status"],
            schema=schema,
        )

    # ── consents ────────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "consents"):
        op.create_table(
            "consents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "prospect_id", sa.String(length=64),
                sa.ForeignKey("Prospect.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("lawful_basis", sa.String(length=32), nullable=False),
            sa.Column(
                "consent_status", sa.String(length=32),
                nullable=False, server_default="pending",
            ),
            sa.Column("consent_text", sa.Text(), nullable=False),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_consents_email", "consents", ["email"], schema=schema
        )
        op.create_index(
            "ix_consents_prospect_id", "consents", ["prospect_id"], schema=schema
        )

    # ── consent_logs ────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "consent_logs"):
        op.create_table(
            "consent_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "consent_id", sa.Integer(),
                sa.ForeignKey("consents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column(
                "details",
                sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_consent_logs_consent_id", "consent_logs", ["consent_id"],
            schema=schema,
        )


# ── Downgrade ────────────────────────────────────────────────────────────────


def _downgrade_public() -> None:
    bind = op.get_bind()
    for tbl in ("retention_policies", "data_subject_requests"):
        if _table_exists(bind, "public", tbl):
            op.drop_table(tbl, schema="public")


def _downgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # Drop consent tables.
    for tbl in ("consent_logs", "consents"):
        if _table_exists(bind, schema, tbl):
            op.drop_table(tbl, schema=schema)

    # Drop Prospect indexes (idempotent).
    for idx in ("ix_Prospect_consent_status", "ix_Prospect_deleted_at"):
        if _index_exists(bind, schema, "Prospect", idx):
            op.drop_index(idx, table_name="Prospect", schema=schema)

    # Drop Prospect GDPR columns (additive — leaving them is harmless; the
    # downgrade removes them for a true rollback).
    for col in ("anonymized", "deleted_at", "lawful_basis", "consent_status"):
        if _column_exists(bind, schema, "Prospect", col):
            bind.execute(
                text(f'ALTER TABLE "{schema}"."Prospect" DROP COLUMN {col}')
            )


__all__ = ["upgrade", "downgrade"]