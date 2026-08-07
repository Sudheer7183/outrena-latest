"""
user_email.py — Per-user email sending infrastructure (tenant-scoped).

Two tables (both live in the tenant_{slug}.* schema):

  UserSenderIdentity
      A user's sender email — either platform-assigned (managed by OUTRENA
      on a tenant sending domain) or corporate (the user's own @company.com
      address, verified via SPF/DKIM). Each identity carries its own
      daily_send_quota. One identity per user can be marked is_default=True.

  UserEmailQuota
      A per-user, per-day counter for outbound email activity. Tracks
      emails_sent / emails_bounced / complaints for the current 24h window.
      is_throttled + throttled_until are flipped when the spam-complaint
      or bounce-rate threshold is exceeded (managed by
      UserEmailQuotaService.check_can_send / record_complaint).

      UNIQUE(user_id, date) enforces one quota row per user per UTC day.
      window_start + last_reset_at are tracked separately to support
      rolling-window resets.

The Keycloak user UUID (token.sub, a String) is the canonical user key —
there is no app-level User table, mirroring the support_tickets pattern
(app/models/support_ticket.py:35).
"""
from __future__ import annotations

from datetime import date, datetime

from app.models.base import Base, TimestampMixin
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


# ── UserSenderIdentity ─────────────────────────────────────────────────────


class UserSenderIdentity(Base, TimestampMixin):
    """A user's outbound email sender identity.

    email_type:
      * "platform_assigned" — OUTRENA-managed mailbox on a tenant sending
        domain (e.g. user1@tenant-mail.com). Verified at provisioning time.
      * "corporate"          — the user's own @company.com address. Requires
        SPF/DKIM verification before is_verified=True is set.
    """

    __tablename__ = "user_sender_identities"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "email", name="uq_user_sender_identities_user_email"
        ),
        Index(
            "ix_user_sender_identities_user_id_is_default",
            "user_id",
            "is_default",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Keycloak user UUID (token.sub) — String(128) per support_tickets pattern.
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="platform_assigned"
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    daily_send_quota: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )


# ── UserEmailQuota ─────────────────────────────────────────────────────────


class UserEmailQuota(Base, TimestampMixin):
    """Per-user, per-day outbound email activity counters + throttle state.

    UNIQUE(user_id, date) — one quota row per user per UTC day. The
    UserEmailQuotaService resets / rolls a new row at midnight UTC or
    24h after window_start, whichever comes first.
    """

    __tablename__ = "user_email_quotas"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_email_quotas_user_date"),
        Index("ix_user_email_quotas_user_id_date", "user_id", "date"),
        Index("ix_user_email_quotas_is_throttled", "is_throttled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Keycloak user UUID (token.sub) — String(128) per support_tickets pattern.
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    emails_sent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    emails_bounced: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    complaints: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_throttled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    throttled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["UserSenderIdentity", "UserEmailQuota"]
