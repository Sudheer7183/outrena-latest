"""
data_subject_request.py — Public-schema GDPR DSR registry.

A DataSubjectRequest (DSR) is the system-of-record entry for any data
subject exercising one of the six GDPR rights:
  - access         (Article 15) — subject wants a copy of their data
  - portability    (Article 20) — machine-readable export for transfer
  - rectification  (Article 16) — correct inaccurate data
  - erasure        (Article 17) — right to be forgotten
  - restriction    (Article 18) — freeze processing
  - objection      (Article 21) — stop processing for specific purposes

DSRs live in the PUBLIC schema (not tenant-scoped) because:
  1. The data subject submitting the request is NOT a platform user —
     they cannot be authenticated through the normal tenant JWT flow.
  2. A DSR may target one or more tenants (cross-tenant lookup by email).
  3. The platform operator (DPO / SUPER_ADMIN) needs a unified view of
     all open DSRs across tenants for SLA tracking.

The public submission endpoint (POST /gdpr/dsr) creates rows here without
authentication; tenant admins process them via authenticated endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.database import Base
from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


# ── Enumerations (VARCHAR + service-layer validation — no PG enum) ───────────

DSR_TYPES: tuple[str, ...] = (
    "access",
    "portability",
    "rectification",
    "erasure",
    "restriction",
    "objection",
)

DSR_STATUSES: tuple[str, ...] = (
    "pending",
    "in_progress",
    "completed",
    "rejected",
)


class DataSubjectRequest(Base):
    """GDPR data-subject-request registry (public schema)."""

    __tablename__ = "data_subject_requests"
    __table_args__ = (
        Index("ix_dsr_email", "email"),
        Index("ix_dsr_tenant_slug", "tenant_slug"),
        Index("ix_dsr_status", "status"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_slug: Mapped[str] = mapped_column(String(63), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.cast("{}", JSONB),
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Signed URL to the exported data bundle (time-limited — typically 24h).
    # Only populated for access / portability requests.
    export_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "DataSubjectRequest",
    "DSR_TYPES",
    "DSR_STATUSES",
]
