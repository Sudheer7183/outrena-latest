"""SaaS commercialization + compliance layer (Phase 7).

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-03 00:00:00

This migration branches on schema (same pattern as 0002):

  PUBLIC schema  → creates the platform-wide tables:
      plans, subscriptions, tenant_signup_requests, permissions,
      feature_permissions, help_sections, help_articles,
      help_section_roles, contact_messages
      + ALTERs public.platform_audit_log to add the new columns
        (actor_role, target_id, request_id, ip_address)
      + seeds the plans, permissions, feature_permissions, and
        help_sections/articles/roles catalogs.

  tenant_{slug} schema → creates the tenant-scoped tables that hold
      per-tenant data:
      roles, role_permissions, support_tickets, support_messages
      + seeds the 4 system roles (REP/MANAGER/TENANT_ADMIN) and
        their default permission keys into role_permissions.

  Both branches are import-safe: no app imports that require a DB.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0002_initial_tenant.py conventions) ─────────────────────


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


# ── Seed data ───────────────────────────────────────────────────────────────

_PLANS = [
    # (name, display_name, description, monthly_cents, yearly_cents, seat_limit, feature_flags, sort_order)
    (
        "free",
        "Free",
        "For individuals exploring OUTRENA. Limited but functional.",
        0, 0, 3, {"autopilot": False, "ab_testing": False}, 0,
    ),
    (
        "starter",
        "Starter",
        "For small teams getting started with structured outbound.",
        4900, 49000, 10, {"autopilot": False, "ab_testing": True}, 1,
    ),
    (
        "growth",
        "Growth",
        "For scaling revenue teams that need full automation + analytics.",
        19900, 199000, 50, {"autopilot": True, "ab_testing": True}, 2,
    ),
    (
        "scale",
        "Scale",
        "For larger orgs with multi-pod teams and SLA needs.",
        49900, 499000, 200, {"autopilot": True, "ab_testing": True, "sso": True}, 3,
    ),
]


_PERMISSIONS = [
    # (key, display_name, description, category)
    # ── prospecting ──
    ("prospects.read", "Read Prospects", "View prospect records.", "prospecting"),
    ("prospects.write", "Create/Edit Prospects", "Create or edit prospect records.", "prospecting"),
    ("prospects.delete", "Delete Prospects", "Delete prospect records.", "prospecting"),
    ("prospects.import", "Import Prospects", "Bulk import prospects via CSV.", "prospecting"),
    ("prospects.export", "Export Prospects", "Bulk export prospects via CSV.", "prospecting"),
    ("icp.read", "Read ICPs", "View Ideal Customer Profiles.", "prospecting"),
    ("icp.write", "Create/Edit ICPs", "Create or edit ICPs.", "prospecting"),
    # ── outreach ──
    ("campaigns.read", "Read Campaigns", "View campaigns.", "outreach"),
    ("campaigns.write", "Create/Edit Campaigns", "Create or edit campaigns.", "outreach"),
    ("campaigns.publish", "Publish Campaigns", "Activate a campaign for sending.", "outreach"),
    ("campaigns.delete", "Delete Campaigns", "Delete campaigns.", "outreach"),
    ("sequences.read", "Read Sequences", "View sequences.", "outreach"),
    ("sequences.write", "Create/Edit Sequences", "Create or edit sequences.", "outreach"),
    ("sequences.delete", "Delete Sequences", "Delete sequences.", "outreach"),
    ("email_studio.write", "Use Email Studio", "Generate and edit emails in Email Studio.", "outreach"),
    # ── pipeline ──
    ("deals.read", "Read Deals", "View deals.", "pipeline"),
    ("deals.write", "Create/Edit Deals", "Create or edit deals.", "pipeline"),
    ("deals.delete", "Delete Deals", "Delete deals.", "pipeline"),
    ("meeting_prep.read", "Read Meeting Prep", "View meeting prep briefs.", "pipeline"),
    # ── optimize ──
    ("dashboard.read", "Read Dashboard", "View the top-level dashboard (KPI cards, recent activity, charts).", "optimize"),
    ("analytics.read", "Read Analytics", "View analytics dashboards.", "optimize"),
    ("analytics.export", "Export Analytics", "Export analytics reports.", "optimize"),
    ("ab_testing.read", "Read A/B Tests", "View A/B test results.", "optimize"),
    ("ab_testing.write", "Create/Edit A/B Tests", "Create or edit A/B tests.", "optimize"),
    ("ab_testing.delete", "Delete A/B Tests", "Delete A/B tests.", "optimize"),
    ("optimization.read", "Read Optimization Rules", "View optimization rules.", "optimize"),
    ("optimization.write", "Manage Optimization Rules", "Create or edit optimization rules.", "optimize"),
    # ── setup ──
    ("integrations.manage", "Manage Integrations", "Configure third-party integrations.", "setup"),
    ("llm_config.manage", "Manage LLM Config", "Configure LLM provider settings.", "setup"),
    ("domain_settings.manage", "Manage Domain Settings", "Configure sending domains.", "setup"),
    ("linkedin.manage", "Manage LinkedIn", "Configure LinkedIn integration.", "setup"),
    # ── admin ──
    ("users.manage", "Manage Users", "Invite, edit, deactivate tenant users.", "admin"),
    ("roles.manage", "Manage Roles", "Create / edit / delete custom roles.", "admin"),
    ("billing.manage", "Manage Billing", "View invoices, change plan, update payment.", "admin"),
    ("support.read", "Read Support Tickets", "View own / all support tickets.", "admin"),
    ("support.manage", "Manage Support Tickets", "Close / reassign support tickets.", "admin"),
    ("audit.read", "Read Audit Log", "View tenant audit log.", "admin"),
    ("help.read", "Read Help", "View help-guide content.", "admin"),
]


# NOTE: the _PERMISSIONS catalog now has 38 entries (dashboard.read was
# added back as MEDIUM 9 fix — see migration 0009 for the prod back-fill).
_FEATURE_PERMISSIONS = [
    # (feature_key, required_permission, description)
    # Mirrors lib/nav-config.tsx features.
    ("dashboard", None, "Top-level dashboard."),
    ("autopilot", "campaigns.write", "Autopilot pipeline generation."),
    ("prospects", "prospects.read", "Prospect list + enrich."),
    ("prospect_source", "prospects.read", "Prospect source directory."),
    ("campaigns", "campaigns.read", "Multi-channel campaign workspace."),
    ("sequences", "sequences.read", "Sequence builder + scheduler."),
    ("email_studio", "email_studio.write", "AI email drafting studio."),
    ("ab_testing", "ab_testing.read", "Subject line + body A/B testing."),
    ("optimization_rules", "optimization.read", "Optimization rules engine."),
    ("analytics", "analytics.read", "Cross-campaign analytics."),
    ("icp", "icp.read", "Ideal Customer Profile editor."),
    ("competitors", "prospects.read", "Competitor tracking."),
    ("content_ideas", "campaigns.read", "AI content-idea generator."),
    ("collaterals", "campaigns.read", "Sales collateral library."),
    ("deals", "deals.read", "Pipeline deal board."),
    ("meeting_prep", "meeting_prep.read", "Meeting prep briefs."),
    ("signals", "prospects.read", "Intent signals + alerts."),
    ("job_change_monitor", "prospects.read", "Job-change alerts."),
    ("domain_enrich", "domain_settings.manage", "Domain DNS + deliverability."),
    ("domains", "domain_settings.manage", "Sending domain management."),
    ("exclusion_rules", "prospects.read", "Exclusion list rules."),
    ("integrations", "integrations.manage", "Third-party integrations."),
    ("linkedin", "linkedin.manage", "LinkedIn inbox + engagement."),
    ("llm_config", "llm_config.manage", "LLM provider config."),
    ("mailbridge", "domain_settings.manage", "MailBridge webhook settings."),
    ("prompt_management", "llm_config.manage", "LLM prompt template management."),
    ("scheduler", "sequences.read", "Sequence scheduler status."),
    ("system_params", "llm_config.manage", "System parameter overrides."),
    ("templates", "campaigns.read", "Reusable sequence templates."),
    ("weekly_digest", "analytics.read", "Weekly digest config."),
    ("user_management", "users.manage", "Tenant user management."),
    ("billing", "billing.manage", "Subscription + invoices."),
    ("support", "support.read", "In-app support tickets."),
    ("help_getting_started", None, "Help-guide getting started section."),
]


_HELP_SECTIONS = [
    # (slug, title, description, sort_order, min_role or None)
    ("getting-started", "Getting Started", "Your first 30 minutes with OUTRENA.", 0, None),
    ("navigation", "Navigation", "Finding your way around the workspace.", 1, None),
    ("roles-permissions", "Roles & Permissions", "Understanding the 4-role hierarchy and custom roles.", 2, "MANAGER"),
    ("platform-admin", "Platform Admin", "Super-admin operations across all tenants.", 3, "SUPER_ADMIN"),
    ("faq", "FAQ", "Frequently asked questions.", 4, None),
]


_HELP_ARTICLES = [
    # (section_slug, slug, title, body, sort_order)
    (
        "getting-started", "welcome",
        "Welcome to OUTRENA",
        "OUTRENA is the AI-Powered Outreach Operating System. This guide walks you through the first 30 minutes.",
        0,
    ),
    (
        "getting-started", "first-campaign",
        "Create Your First Campaign",
        "A campaign is the unit of work in OUTRENA. Follow these steps to create your first one.",
        1,
    ),
    (
        "navigation", "workspace",
        "Workspace Layout",
        "The left nav groups features by stage: prospecting, outreach, pipeline, optimize, setup.",
        0,
    ),
    (
        "roles-permissions", "role-hierarchy",
        "The 4-Role Hierarchy",
        "REP → MANAGER → TENANT_ADMIN → SUPER_ADMIN. Higher roles inherit lower-role permissions.",
        0,
    ),
    (
        "platform-admin", "tenant-signup",
        "Tenant Signup Approval",
        "Approve or reject self-serve signup requests from /platform/admin/signups.",
        0,
    ),
    (
        "faq", "billing-changes",
        "How do I change my plan?",
        "TENANT_ADMIN users can change plans from the Billing page. Changes take effect immediately.",
        0,
    ),
]


_SYSTEM_ROLE_PERMS = {
    "REP": [
        "prospects.read", "prospects.write", "prospects.import",
        "campaigns.read", "campaigns.write",
        "sequences.read", "sequences.write",
        "email_studio.write",
        "analytics.read", "dashboard.read",
        "deals.read", "meeting_prep.read",
        "support.read", "help.read",
        "icp.read",
    ],
    "MANAGER": [
        "prospects.read", "prospects.write", "prospects.import", "prospects.export",
        "campaigns.read", "campaigns.write", "campaigns.publish",
        "sequences.read", "sequences.write",
        "email_studio.write",
        "analytics.read", "analytics.export",
        "ab_testing.read", "ab_testing.write",
        "optimization.read", "optimization.write",
        "deals.read", "deals.write", "meeting_prep.read",
        "dashboard.read",
        "support.read", "help.read",
        "icp.read",
    ],
    "TENANT_ADMIN": [
        "prospects.read", "prospects.write", "prospects.delete", "prospects.import", "prospects.export",
        "campaigns.read", "campaigns.write", "campaigns.publish", "campaigns.delete",
        "sequences.read", "sequences.write", "sequences.delete",
        "email_studio.write",
        "analytics.read", "analytics.export",
        "ab_testing.read", "ab_testing.write", "ab_testing.delete",
        "optimization.read", "optimization.write",
        "deals.read", "deals.write", "deals.delete", "meeting_prep.read",
        "dashboard.read",
        "users.manage", "roles.manage", "billing.manage",
        "integrations.manage", "llm_config.manage",
        "domain_settings.manage", "linkedin.manage",
        "support.read", "support.manage", "help.read", "audit.read",
        "icp.read", "icp.write",
    ],
}


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

    # ── plans ───────────────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "plans"):
        op.create_table(
            "plans",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("price_monthly_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("price_yearly_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "feature_flags",
                sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "is_active", sa.Boolean(),
                nullable=False, server_default=sa.text("true"),
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_plans_name"),
            schema="public",
        )

    # ── subscriptions ───────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="TRIALING"),
            sa.Column("external_id", sa.String(length=120), nullable=True),
            sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "cancel_at_period_end", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column("seats_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", name="uq_subscriptions_tenant_id"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["public.tenants.tenant_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["plan_id"], ["public.plans.id"], ondelete="RESTRICT"
            ),
            schema="public",
        )
        op.create_index(
            "ix_subscriptions_status", "subscriptions", ["status"], schema="public"
        )

    # ── tenant_signup_requests ──────────────────────────────────────────────
    if not _table_exists(bind, "public", "tenant_signup_requests"):
        op.create_table(
            "tenant_signup_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("subdomain", sa.String(length=63), nullable=False),
            sa.Column("owner_email", sa.String(length=255), nullable=False),
            sa.Column("owner_first_name", sa.String(length=120), nullable=False),
            sa.Column("owner_last_name", sa.String(length=120), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column(
                "status", sa.String(length=20),
                nullable=False, server_default="PENDING_APPROVAL",
            ),
            sa.Column("rejection_reason", sa.String(length=500), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_by", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["plan_id"], ["public.plans.id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["public.tenants.tenant_id"], ondelete="SET NULL"
            ),
            schema="public",
        )
        op.create_index(
            "ix_tenant_signup_requests_status",
            "tenant_signup_requests", ["status"], schema="public",
        )
        op.create_index(
            "ix_tenant_signup_requests_subdomain",
            "tenant_signup_requests", ["subdomain"], schema="public",
        )

    # ── permissions ─────────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "permissions"):
        op.create_table(
            "permissions",
            sa.Column("key", sa.String(length=80), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("key"),
            schema="public",
        )

    # ── feature_permissions ─────────────────────────────────────────────────
    if not _table_exists(bind, "public", "feature_permissions"):
        op.create_table(
            "feature_permissions",
            sa.Column("feature_key", sa.String(length=80), nullable=False),
            sa.Column("required_permission", sa.String(length=80), nullable=True),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("feature_key"),
            sa.ForeignKeyConstraint(
                ["required_permission"], ["public.permissions.key"], ondelete="RESTRICT"
            ),
            schema="public",
        )

    # ── help_sections ───────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "help_sections"):
        op.create_table(
            "help_sections",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_help_sections_slug"),
            schema="public",
        )

    # ── help_articles ───────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "help_articles"):
        op.create_table(
            "help_articles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("section_id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["section_id"], ["public.help_sections.id"], ondelete="CASCADE"
            ),
            schema="public",
        )

    # ── help_section_roles ──────────────────────────────────────────────────
    if not _table_exists(bind, "public", "help_section_roles"):
        op.create_table(
            "help_section_roles",
            sa.Column("section_id", sa.Integer(), nullable=False),
            sa.Column("min_role", sa.String(length=40), nullable=False),
            sa.PrimaryKeyConstraint("section_id", "min_role"),
            sa.ForeignKeyConstraint(
                ["section_id"], ["public.help_sections.id"], ondelete="CASCADE"
            ),
            schema="public",
        )

    # ── contact_messages ────────────────────────────────────────────────────
    if not _table_exists(bind, "public", "contact_messages"):
        op.create_table(
            "contact_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "handled", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )

    # ── ALTER platform_audit_log: add new columns (additive) ────────────────
    if not _column_exists(bind, "public", "platform_audit_log", "actor_role"):
        op.execute(
            "ALTER TABLE public.platform_audit_log "
            "ADD COLUMN actor_role VARCHAR(40)"
        )
    if not _column_exists(bind, "public", "platform_audit_log", "target_id"):
        op.execute(
            "ALTER TABLE public.platform_audit_log "
            "ADD COLUMN target_id VARCHAR(128)"
        )
    if not _column_exists(bind, "public", "platform_audit_log", "request_id"):
        op.execute(
            "ALTER TABLE public.platform_audit_log "
            "ADD COLUMN request_id VARCHAR(64)"
        )
    if not _column_exists(bind, "public", "platform_audit_log", "ip_address"):
        op.execute(
            "ALTER TABLE public.platform_audit_log "
            "ADD COLUMN ip_address VARCHAR(64)"
        )

    # ── Seed catalog data (idempotent — uses ON CONFLICT DO NOTHING) ────────
    _seed_plans(bind)
    _seed_permissions(bind)
    _seed_feature_permissions(bind)
    _seed_help_content(bind)


def _seed_plans(bind) -> None:
    for name, disp, desc, mo, yr, seats, flags, sort in _PLANS:
        bind.execute(
            text(
                "INSERT INTO public.plans "
                "(name, display_name, description, price_monthly_cents, "
                " price_yearly_cents, seat_limit, feature_flags, is_active, sort_order) "
                "VALUES (:name, :disp, :desc, :mo, :yr, :seats, "
                "        CAST(:flags AS jsonb), true, :sort) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {
                "name": name, "disp": disp, "desc": desc,
                "mo": mo, "yr": yr, "seats": seats,
                "flags": _json_dumps(flags), "sort": sort,
            },
        )


def _seed_permissions(bind) -> None:
    for key, disp, desc, cat in _PERMISSIONS:
        bind.execute(
            text(
                "INSERT INTO public.permissions "
                "(key, display_name, description, category) "
                "VALUES (:k, :d, :desc, :c) ON CONFLICT (key) DO NOTHING"
            ),
            {"k": key, "d": disp, "desc": desc, "c": cat},
        )


def _seed_feature_permissions(bind) -> None:
    for fkey, perm, desc in _FEATURE_PERMISSIONS:
        bind.execute(
            text(
                "INSERT INTO public.feature_permissions "
                "(feature_key, required_permission, description) "
                "VALUES (:fk, :perm, :desc) "
                "ON CONFLICT (feature_key) DO UPDATE SET "
                "  required_permission = EXCLUDED.required_permission, "
                "  description = EXCLUDED.description"
            ),
            {"fk": fkey, "perm": perm, "desc": desc},
        )


def _seed_help_content(bind) -> None:
    # Help sections + role gates + articles.
    section_id_map: dict[str, int] = {}
    for slug, title, desc, sort, min_role in _HELP_SECTIONS:
        # Upsert section.
        bind.execute(
            text(
                "INSERT INTO public.help_sections "
                "(slug, title, description, sort_order) "
                "VALUES (:slug, :title, :desc, :sort) "
                "ON CONFLICT (slug) DO UPDATE SET "
                "  title = EXCLUDED.title, "
                "  description = EXCLUDED.description, "
                "  sort_order = EXCLUDED.sort_order"
            ),
            {"slug": slug, "title": title, "desc": desc, "sort": sort},
        )
        row = bind.execute(
            text("SELECT id FROM public.help_sections WHERE slug = :slug"),
            {"slug": slug},
        ).fetchone()
        if row is None:
            continue
        sid = row.id
        section_id_map[slug] = sid
        if min_role is not None:
            bind.execute(
                text(
                    "INSERT INTO public.help_section_roles "
                    "(section_id, min_role) VALUES (:sid, :role) "
                    "ON CONFLICT (section_id, min_role) DO NOTHING"
                ),
                {"sid": sid, "role": min_role},
            )
    for sec_slug, art_slug, title, body, sort in _HELP_ARTICLES:
        sid = section_id_map.get(sec_slug)
        if sid is None:
            continue
        # Upsert article by (section_id, slug).
        existing = bind.execute(
            text(
                "SELECT id FROM public.help_articles "
                "WHERE section_id = :sid AND slug = :slug"
            ),
            {"sid": sid, "slug": art_slug},
        ).fetchone()
        if existing is None:
            bind.execute(
                text(
                    "INSERT INTO public.help_articles "
                    "(section_id, slug, title, body, sort_order) "
                    "VALUES (:sid, :slug, :title, :body, :sort)"
                ),
                {
                    "sid": sid, "slug": art_slug, "title": title,
                    "body": body, "sort": sort,
                },
            )
        else:
            bind.execute(
                text(
                    "UPDATE public.help_articles SET title = :title, "
                    "body = :body, sort_order = :sort WHERE id = :id"
                ),
                {"title": title, "body": body, "sort": sort, "id": existing.id},
            )


# ── TENANT schema upgrade ────────────────────────────────────────────────────


def _upgrade_tenant(schema: str) -> None:
    bind = op.get_bind()

    # ── roles ───────────────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "roles"):
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column(
                "is_system", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name=f"uq_{schema}_roles_name"),
        )

    # ── role_permissions ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_key", sa.String(length=80), nullable=False),
            sa.PrimaryKeyConstraint("role_id", "permission_key"),
            sa.ForeignKeyConstraint(
                ["role_id"], [f"{schema}.roles.id"], ondelete="CASCADE"
            ),
        )

    # ── support_tickets ─────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "support_tickets"):
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False, server_default="QUESTION"),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
            sa.Column("created_by_user_id", sa.String(length=128), nullable=False),
            sa.Column("assigned_to", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            f"ix_{schema}_support_tickets_status",
            "support_tickets", ["status"],
        )

    # ── support_messages ────────────────────────────────────────────────────
    if not _table_exists(bind, schema, "support_messages"):
        op.create_table(
            "support_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.String(length=128), nullable=False),
            sa.Column("author_role", sa.String(length=40), nullable=False, server_default="REP"),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "is_internal_note", sa.Boolean(),
                nullable=False, server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["ticket_id"], [f"{schema}.support_tickets.id"], ondelete="CASCADE"
            ),
        )

    # ── Seed the 4 system roles + their default permissions ────────────────
    _seed_system_roles(bind, schema)


def _seed_system_roles(bind, schema: str) -> None:
    role_id_map: dict[str, int] = {}
    for role_name in ("REP", "MANAGER", "TENANT_ADMIN"):
        # Insert if missing.
        bind.execute(
            text(
                f'INSERT INTO "{schema}".roles (name, description, is_system) '
                f"VALUES (:name, :desc, true) "
                f"ON CONFLICT (name) DO NOTHING"
            ),
            {"name": role_name, "desc": f"System role: {role_name}"},
        )
        row = bind.execute(
            text(f'SELECT id FROM "{schema}".roles WHERE name = :name'),
            {"name": role_name},
        ).fetchone()
        if row is not None:
            role_id_map[role_name] = row.id

    for role_name, perms in _SYSTEM_ROLE_PERMS.items():
        rid = role_id_map.get(role_name)
        if rid is None:
            continue
        for perm in perms:
            bind.execute(
                text(
                    f'INSERT INTO "{schema}".role_permissions '
                    f"(role_id, permission_key) VALUES (:rid, :perm) "
                    f"ON CONFLICT (role_id, permission_key) DO NOTHING"
                ),
                {"rid": rid, "perm": perm},
            )


# ── Downgrade ────────────────────────────────────────────────────────────────


def _downgrade_public() -> None:
    bind = op.get_bind()
    # Drop tables in reverse dependency order. We do NOT undo the
    # platform_audit_log column additions (additive only — leaving them
    # is harmless and rolling them back would lose audit data).
    for tbl in (
        "contact_messages",
        "help_section_roles",
        "help_articles",
        "help_sections",
        "feature_permissions",
        "permissions",
        "tenant_signup_requests",
        "subscriptions",
        "plans",
    ):
        if _table_exists(bind, "public", tbl):
            op.drop_table(tbl, schema="public")


def _downgrade_tenant(schema: str) -> None:
    bind = op.get_bind()
    for tbl in ("support_messages", "support_tickets", "role_permissions", "roles"):
        if _table_exists(bind, schema, tbl):
            op.drop_table(tbl)


# ── Utilities ────────────────────────────────────────────────────────────────


def _json_dumps(value) -> str:  # type: ignore[no-untyped-def]
    import json
    return json.dumps(value, default=str)


__all__ = ["upgrade", "downgrade"]
