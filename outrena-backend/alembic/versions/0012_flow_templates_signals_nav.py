"""
0012_flow_templates_signals_nav.py — Alpha gap fixes.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-26 00:00:00

Changes:
  1. Seed 5 pre-built ProspectingFlow template rows into every tenant schema
     (FR-E10-012 / G-10).
  2. No schema changes — pure data migration.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Template definitions (inserted into every tenant schema's ProspectingFlow)
# ---------------------------------------------------------------------------

_FLOW_TEMPLATES = [
    {
        "id": "tpl-apollo-hunter-basic",
        "name": "Apollo → Hunter (Basic Email Discovery)",
        "description": "Source prospects from Apollo by title/industry, then validate emails via Hunter.io. Best for targeted outbound to known ICPs.",
        "templateTag": "email-discovery",
        "sourceSteps": '[{"provider":"apollo","filters":{"title_keywords":["VP","Director","Head of"],"employee_count_range":"50-500"}}]',
        "enrichmentSteps": '[{"provider":"hunter","action":"email_verify"}]',
        "qualityGates": '{"min_email_confidence":0.7,"exclude_catch_all":true}',
    },
    {
        "id": "tpl-clay-clearbit-enrichment",
        "name": "Clay → Clearbit (Full Firmographic Enrichment)",
        "description": "Source from Clay with intent signals, then enrich company firmographics via Clearbit. Best for ABM campaigns.",
        "templateTag": "firmographic-enrichment",
        "sourceSteps": '[{"provider":"clay","filters":{"intent_signal":"funding","days_back":30}}]',
        "enrichmentSteps": '[{"provider":"clearbit","action":"company_enrich"},{"provider":"hunter","action":"email_find"}]',
        "qualityGates": '{"min_icp_score":60,"require_email":true}',
    },
    {
        "id": "tpl-zoominfo-linkedin-verified",
        "name": "ZoomInfo → LinkedIn Verified",
        "description": "High-quality prospects from ZoomInfo, cross-verified with LinkedIn presence. Best for enterprise deals.",
        "templateTag": "enterprise-verified",
        "sourceSteps": '[{"provider":"zoominfo","filters":{"company_revenue_min":10000000,"department":"engineering"}}]',
        "enrichmentSteps": '[{"provider":"linkedin","action":"profile_verify"}]',
        "qualityGates": '{"require_linkedin":true,"min_seniority":"Director"}',
    },
    {
        "id": "tpl-hiring-signal-trigger",
        "name": "Hiring Signal → Job-Change Triggered",
        "description": "Detect companies hiring for roles matching your ICP, then surface the hiring manager as a prospect. Timed to catch budget approval moments.",
        "templateTag": "signal-triggered",
        "sourceSteps": '[{"provider":"apollo","filters":{"hiring_keyword":"sales","job_posted_days":14}}]',
        "enrichmentSteps": '[{"provider":"hunter","action":"email_find"},{"provider":"clearbit","action":"company_enrich"}]',
        "qualityGates": '{"min_company_size":50,"exclude_existing_prospects":true}',
    },
    {
        "id": "tpl-snovio-kaspr-smb",
        "name": "Snovio → Kaspr (SMB Direct Dial)",
        "description": "Source SMB decision-makers from Snovio, then add direct-dial numbers via Kaspr for multi-channel outreach.",
        "templateTag": "smb-direct-dial",
        "sourceSteps": '[{"provider":"snovio","filters":{"company_size":"1-200","country":"US"}}]',
        "enrichmentSteps": '[{"provider":"kaspr","action":"phone_enrich"}]',
        "qualityGates": '{"require_phone":false,"min_email_confidence":0.6}',
    },
]


def upgrade() -> None:
    """Insert flow templates into every tenant schema."""
    conn = op.get_bind()

    # Discover all ACTIVE tenant schemas
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM public.tenants "
            "WHERE deleted_at IS NULL ORDER BY tenant_id"
        )
    )
    schemas = [row[0] for row in result.fetchall()]

    now = sa.text("NOW()")

    for schema in schemas:
        for tpl in _FLOW_TEMPLATES:
            # Idempotent: skip if already present
            existing = conn.execute(
                sa.text(
                    f'SELECT id FROM "{schema}"."ProspectingFlow" WHERE id = :id'
                ),
                {"id": tpl["id"]},
            ).fetchone()
            if existing:
                continue
            conn.execute(
                sa.text(
                    f'INSERT INTO "{schema}"."ProspectingFlow" '
                    '(id, name, description, "isDefault", "isActive", "isTemplate", '
                    '"templateTag", "sourceSteps", "enrichmentSteps", "qualityGates", '
                    '"createdAt", "updatedAt") VALUES '
                    '(:id, :name, :desc, false, true, true, :tag, :src, :enr, :gates, NOW(), NOW())'
                ),
                {
                    "id": tpl["id"],
                    "name": tpl["name"],
                    "desc": tpl["description"],
                    "tag": tpl["templateTag"],
                    "src": tpl["sourceSteps"],
                    "enr": tpl["enrichmentSteps"],
                    "gates": tpl["qualityGates"],
                },
            )


def downgrade() -> None:
    """Remove seeded flow templates from all tenant schemas."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT schema_name FROM public.tenants WHERE deleted_at IS NULL")
    )
    schemas = [row[0] for row in result.fetchall()]
    template_ids = [t["id"] for t in _FLOW_TEMPLATES]
    for schema in schemas:
        conn.execute(
            sa.text(
                f'DELETE FROM "{schema}"."ProspectingFlow" WHERE id = ANY(:ids) AND "isTemplate" = true'
            ),
            {"ids": template_ids},
        )
