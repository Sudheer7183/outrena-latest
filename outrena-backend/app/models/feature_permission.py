"""
feature_permission.py — Nav-feature → required-permission map (public, read-only).

Each OUTRENA frontend nav feature (lib/nav-config.tsx) is mapped to the
minimum permission a user must hold to see/enter that feature. The frontend
calls GET /api/v1/feature-permissions and hides features the caller cannot
access; the backend additionally enforces the same map via
``require_feature(feature_key)``.

Example rows:
  autopilot           → campaigns.write
  email_studio        → campaigns.write
  billing             → billing.manage
  user_management     → users.manage
  help_getting_started→ (no permission — visible to all authenticated users)
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column


class FeaturePermission(Base):
    """Map a frontend nav feature_key to a required permission key."""

    __tablename__ = "feature_permissions"
    __table_args__ = ({"schema": "public"},)

    feature_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    required_permission: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("public.permissions.key", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["FeaturePermission"]
