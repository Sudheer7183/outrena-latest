"""
consent.py — Tenant-scoped Consent + ConsentLog (GDPR Article 7).

Consent records capture the lawful basis under which a Prospect's PII is
processed, the exact text the data subject agreed to (for audit), and the
provenance (IP + User-Agent). Every grant / withdrawal / renewal is
appended to the immutable ``consent_logs`` table — consent is NEVER
overwritten in place.

Both tables live in the tenant schema (search_path-resolved, like
SupportTicket / Prospect). Public-schema access is not required because
consent is per-tenant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.database import Base
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


# ── Lawful-basis + status constants (GDPR Article 6) ─────────────────────────
# Stored as plain VARCHAR(32) (not a PG enum) so adding a new value does
# not require an enum migration — only a code update. The set of allowed
# values is enforced at the service / API layer.

LAWFUL_BASES: tuple[str, ...] = (
    "consent",
    "legitimate_interest",
    "contract",
    "legal_obligation",
    "vital_interest",
    "public_task",
)

CONSENT_STATUSES: tuple[str, ...] = (
    "granted",
    "withdrawn",
    "pending",
)

CONSENT_LOG_ACTIONS: tuple[str, ...] = (
    "granted",
    "withdrawn",
    "renewed",
)


class Consent(Base):
    """Tenant-scoped consent record for a Prospect's PII processing.

    One row per (prospect_id, lawful_basis) — a prospect may have multiple
    lawful bases active (e.g. ``consent`` for marketing + ``legitimate_interest``
    for prospecting). The ``consent_status`` field reflects the LATEST state:
    ``granted`` if the most recent action was grant/renew, ``withdrawn`` if
    the most recent action was withdrawal.
    """

    __tablename__ = "consents"
    __table_args__ = (
        Index("ix_consents_email", "email"),
        Index("ix_consents_prospect_id", "prospect_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prospect_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("Prospect.id", ondelete="CASCADE"), nullable=False
    )
    # Email is denormalised here so consent lookups by email work even if the
    # prospect row is later anonymised (email → "[anonymized]"). The consent
    # row retains the original email so the data subject can still prove
    # they withdrew consent after the fact.
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    lawful_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ConsentLog(Base):
    """Immutable append-only audit trail for a Consent record.

    One row per state transition (grant / withdraw / renew). Never UPDATEd
    or DELETEd — provides a complete history for GDPR Article 7(1) evidence.
    """

    __tablename__ = "consent_logs"
    __table_args__ = (
        Index("ix_consent_logs_consent_id", "consent_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("consents.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.cast("{}", JSONB),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "Consent",
    "ConsentLog",
    "LAWFUL_BASES",
    "CONSENT_STATUSES",
    "CONSENT_LOG_ACTIONS",
]
