"""
help_service.py — Public-schema help-guide content with role-gated visibility.

Sections without a HelpSectionRole row are open to all authenticated users.
Sections WITH a row require the caller's role to be at or above
``min_role`` on the ROLE_HIERARCHY ladder.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.help_section import HelpArticle, HelpSection, HelpSectionRole
from app.schemas.auth import ROLE_HIERARCHY, Role


class HelpService:
    """Help-guide content with role-gated visibility."""

    async def list_sections_for_role(
        self, db: AsyncSession, role: Role
    ) -> list[dict[str, Any]]:
        """Return all sections visible to ``role``."""
        rows = (
            await db.execute(
                select(HelpSection).order_by(HelpSection.sort_order)
            )
        ).scalars().all()
        out: list[dict[str, Any]] = []
        caller_level = ROLE_HIERARCHY[role]
        for s in rows:
            gate_rows = (
                await db.execute(
                    select(HelpSectionRole).where(
                        HelpSectionRole.section_id == s.id
                    )
                )
            ).scalars().all()
            if not gate_rows:
                out.append(self._section_dict(s))
                continue
            # Visible iff caller level >= any gate's min_role level.
            ok = False
            for g in gate_rows:
                try:
                    required = Role(g.min_role)
                except ValueError:
                    continue
                if caller_level >= ROLE_HIERARCHY[required]:
                    ok = True
                    break
            if ok:
                out.append(self._section_dict(s))
        return out

    async def get_section(
        self, db: AsyncSession, slug: str, role: Role
    ) -> dict[str, Any]:
        from fastapi import HTTPException, status
        section = (
            await db.execute(
                select(HelpSection).where(HelpSection.slug == slug)
            )
        ).scalar_one_or_none()
        if section is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Section not found."
            )
        # Enforce role gate.
        gates = (
            await db.execute(
                select(HelpSectionRole).where(
                    HelpSectionRole.section_id == section.id
                )
            )
        ).scalars().all()
        if gates:
            caller_level = ROLE_HIERARCHY[role]
            ok = False
            for g in gates:
                try:
                    required = Role(g.min_role)
                except ValueError:
                    continue
                if caller_level >= ROLE_HIERARCHY[required]:
                    ok = True
                    break
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your role cannot view this help section.",
                )
        articles = (
            await db.execute(
                select(HelpArticle)
                .where(HelpArticle.section_id == section.id)
                .order_by(HelpArticle.sort_order)
            )
        ).scalars().all()
        result = self._section_dict(section)
        result["articles"] = [
            {
                "id": a.id,
                "slug": a.slug,
                "title": a.title,
                "body": a.body,
                "sort_order": a.sort_order,
            }
            for a in articles
        ]
        return result

    async def search_articles(
        self, db: AsyncSession, query: str, role: Role
    ) -> list[dict[str, Any]]:
        """ILIKE search across article title + body, filtered by role visibility.

        Returns one dict per matching article with both ``section_slug``
        and ``section_title`` so the frontend can render the section
        badge without an extra lookup round-trip (AUDIT-HELP-1 / G-3).
        """
        pattern = f"%{query.lower()}%"
        rows = (
            await db.execute(
                select(
                    HelpArticle,
                    HelpSection.slug.label("section_slug"),
                    HelpSection.title.label("section_title"),
                )
                .join(HelpSection, HelpSection.id == HelpArticle.section_id)
                .where(
                    or_(
                        HelpArticle.title.ilike(pattern),
                        HelpArticle.body.ilike(pattern),
                    )
                )
                .order_by(HelpArticle.sort_order)
            )
        ).fetchall()
        # Restrict results to sections the caller can see.
        visible_slugs = {
            s["slug"] for s in await self.list_sections_for_role(db, role)
        }
        return [
            {
                "id": row.HelpArticle.id,
                "slug": row.HelpArticle.slug,
                "title": row.HelpArticle.title,
                "body_excerpt": (row.HelpArticle.body or "")[:280],
                "section_slug": row.section_slug,
                "section_title": row.section_title,
            }
            for row in rows
            if row.section_slug in visible_slugs
        ]

    @staticmethod
    def _section_dict(s: HelpSection) -> dict[str, Any]:
        return {
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "description": s.description,
            "sort_order": s.sort_order,
            "created_at": s.created_at,
        }

    async def _section_visible(
        self, db: AsyncSession, section_id: int, role: Role
    ) -> bool:
        gates = (
            await db.execute(
                select(HelpSectionRole).where(
                    HelpSectionRole.section_id == section_id
                )
            )
        ).scalars().all()
        if not gates:
            return True
        caller_level = ROLE_HIERARCHY[role]
        for g in gates:
            try:
                required = Role(g.min_role)
            except ValueError:
                continue
            if caller_level >= ROLE_HIERARCHY[required]:
                return True
        return False


__all__ = ["HelpService"]
