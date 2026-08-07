"""
support_ticket.py — Tenant-scoped support tickets + threaded messages.

A tenant user creates a SupportTicket (BUG / QUESTION / FEATURE_REQUEST /
BILLING / ACCOUNT) with a priority and initial description. Subsequent
messages form a thread. The original creator and any tenant admin can
post messages; platform operators (SUPER_ADMIN) post via the platform
admin route (not implemented in this layer — they would post through the
Keycloak Admin API or a future /platform/admin/tickets endpoint).

Both tables live in the tenant schema (search_path-resolved).
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class SupportTicket(Base):
    """A tenant support ticket."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # BUG | QUESTION | FEATURE_REQUEST | BILLING | ACCOUNT
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="QUESTION")
    # LOW | MEDIUM | HIGH | URGENT
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    # OPEN | IN_PROGRESS | RESOLVED | CLOSED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    created_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SupportMessage(Base):
    """A single message in a support ticket thread."""

    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    author_role: Mapped[str] = mapped_column(String(40), nullable=False, default="REP")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal_note: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["SupportTicket", "SupportMessage"]
