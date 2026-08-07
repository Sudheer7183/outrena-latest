"""
audit_log.py — ORM model for the EXISTING ``public.platform_audit_log`` table.

The table itself was created by alembic migration 0001_initial_public.py
(columns: id, actor_sub, actor_email, tenant_slug, action, target,
metadata, created_at). This module only provides an ORM model so services
and middleware can INSERT and SELECT via SQLAlchemy instead of raw text()
SQL. **The model intentionally matches the existing schema exactly — no
new columns are added here.**

Differences from the migration 0001 column set, mapped to ORM attributes:
  id             → id
  actor_sub      → actor_user_id       (renamed for clarity; column stays actor_sub)
  actor_email    → actor_email         (kept as-is)
  tenant_slug    → tenant_slug         (kept)
  action         → action
  target         → split into target_type + target_id (column stays `target`)
  metadata       → metadata_           (Python reserved name; column stays `metadata`)
  created_at     → created_at

For inserts we coalesce target_type/target_id back into the single `target`
column as ``"{type}:{id}"`` via a helper in audit_service. This keeps the
schema stable while giving the ORM a richer shape.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.database import Base
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class AuditLog(Base):
    """ORM projection of the existing public.platform_audit_log table.

    Maps the legacy single-column ``target`` to two ORM-only attributes
    (target_type, target_id) via property accessors; the underlying column
    is still ``target``. ``metadata`` is exposed as ``metadata_`` because
    ``metadata`` is reserved by SQLAlchemy Declarative.
    """

    __tablename__ = "platform_audit_log"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column("actor_sub", String(128), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tenant_slug: Mapped[str | None] = mapped_column(String(63), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column("target", String(255), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.cast("{}", JSONB),
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["AuditLog"]
