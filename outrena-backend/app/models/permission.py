"""
permission.py — Permission catalog (public schema, read-only).

A flat, platform-wide catalog of every fine-grained permission in OUTRENA.
Permissions are addressed by string key (e.g. "prospects.read") from the
RBAC layer (rbac_service.has_permission) and from FeaturePermission
mappings (which gate nav features on permissions).

Seeded by alembic migration 0003_saas_platform with ~30 keys spanning the
six categories: prospecting, outreach, pipeline, optimize, setup, admin.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Permission(Base):
    """Read-only permission catalog row (public schema, PK is the string key)."""

    __tablename__ = "permissions"
    __table_args__ = ({"schema": "public"},)

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # prospecting | outreach | pipeline | optimize | setup | admin
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Permission"]
