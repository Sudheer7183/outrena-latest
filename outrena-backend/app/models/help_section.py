"""
help_section.py — Public-schema help-guide content with role-gated visibility.

Three tables:
  HelpSection       top-level group (Getting Started, Navigation, ...)
  HelpArticle       leaf node inside a section
  HelpSectionRole   minimum-role visibility gate per section

HelpSectionRole.min_role is compared against the JWT role using the
``ROLE_HIERARCHY`` ladder: a section with min_role="MANAGER" is visible to
MANAGER, TENANT_ADMIN, and SUPER_ADMIN, but NOT to REP. Sections without
any HelpSectionRole row are visible to all authenticated users (open help).
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class HelpSection(Base):
    """Top-level help-guide section."""

    __tablename__ = "help_sections"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HelpArticle(Base):
    """An article inside a help section."""

    __tablename__ = "help_articles"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.help_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HelpSectionRole(Base):
    """Minimum-role visibility gate for a section.

    A row here means: callers whose role is BELOW ``min_role`` (per the
    ROLE_HIERARCHY ladder) cannot see this section. Sections without any
    row are open to all authenticated users.
    """

    __tablename__ = "help_section_roles"
    __table_args__ = ({"schema": "public"},)

    section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.help_sections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    min_role: Mapped[str] = mapped_column(String(40), primary_key=True)


__all__ = ["HelpSection", "HelpArticle", "HelpSectionRole"]
