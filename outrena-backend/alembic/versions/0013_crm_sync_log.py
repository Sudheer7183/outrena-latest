"""Add CrmSyncLog table for CRM export audit trail (Help Guide §Deals)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-26
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "CrmSyncLog",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("exportedByUserId", sa.String(), nullable=False),
        sa.Column("dealCount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("crmProvider", sa.String(), nullable=True, server_default="manual"),
        sa.Column("stageBreakdown", sa.Text(), nullable=True),
        sa.Column("sourceBreakdown", sa.Text(), nullable=True),
        sa.Column(
            "exportedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("CrmSyncLog")
