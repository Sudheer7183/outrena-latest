"""
contact_message.py — Public-schema contact-form submissions.

Created by the public landing page (POST /api/v1/public/contact). Platform
operators triage these from the admin UI; ``handled`` flips to true once
they reply out-of-band.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class ContactMessage(Base):
    """Inbound contact-form submission from the public landing page."""

    __tablename__ = "contact_messages"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    handled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["ContactMessage"]
