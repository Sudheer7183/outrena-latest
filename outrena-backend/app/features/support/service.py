"""
support_service.py — Tenant-scoped support ticket + message management.

Endpoints in app/api/v1/support.py call into this service. REP can
create tickets and post messages on their own tickets; TENANT_ADMIN can
list/close all tenant tickets. Messages are stored in the tenant schema
(via the search_path-locked session).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_ticket import SupportMessage, SupportTicket


class SupportService:
    """Tenant-scoped ticket + message lifecycle."""

    async def list_tickets(
        self,
        db: AsyncSession,
        user_id: str,
        role: str,
    ) -> list[dict[str, Any]]:
        """List tickets visible to the caller.

        REP sees only their own tickets; MANAGER / TENANT_ADMIN see all.
        """
        stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
        if role == "REP":
            stmt = stmt.where(SupportTicket.created_by_user_id == user_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [self._ticket_dict(r) for r in rows]

    async def create_ticket(
        self,
        db: AsyncSession,
        *,
        subject: str,
        category: str,
        priority: str,
        description: str,
        created_by_user_id: str,
        author_role: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ticket = SupportTicket(
            subject=subject,
            category=category,
            priority=priority,
            status="OPEN",
            created_by_user_id=created_by_user_id,
        )
        db.add(ticket)
        await db.flush()
        # First message is the description body.
        msg = SupportMessage(
            ticket_id=ticket.id,
            author_user_id=created_by_user_id,
            author_role=author_role,
            body=description,
            is_internal_note=False,
        )
        db.add(msg)
        # FR-101: auto-attach contextual diagnostics as an internal note so
        # support agents see the environment without asking the user.
        if diagnostics:
            import json as _json

            diag_msg = SupportMessage(
                ticket_id=ticket.id,
                author_user_id="system",
                author_role="SYSTEM",
                body=(
                    "Contextual diagnostics (auto-attached):\n"
                    + _json.dumps(diagnostics, indent=2, default=str)
                ),
                is_internal_note=True,
            )
            db.add(diag_msg)
        await db.commit()
        ticket = await db.get(SupportTicket, ticket.id)
        return self._ticket_dict(ticket)

    async def get_ticket_with_messages(
        self,
        db: AsyncSession,
        ticket_id: int,
        user_id: str,
        role: str,
    ) -> dict[str, Any]:
        ticket = await self._fetch_ticket(db, ticket_id, user_id, role)
        msgs = (
            await db.execute(
                select(SupportMessage)
                .where(SupportMessage.ticket_id == ticket_id)
                .order_by(SupportMessage.created_at)
            )
        ).scalars().all()
        result = self._ticket_dict(ticket)
        result["messages"] = [
            {
                "id": m.id,
                "author_user_id": m.author_user_id,
                "author_role": m.author_role,
                "body": m.body,
                "is_internal_note": m.is_internal_note,
                "created_at": m.created_at,
            }
            for m in msgs
        ]
        return result

    async def add_message(
        self,
        db: AsyncSession,
        ticket_id: int,
        body: str,
        author_user_id: str,
        author_role: str,
        is_internal_note: bool = False,
        user_id_for_acl: str | None = None,
        role_for_acl: str | None = None,
    ) -> dict[str, Any]:
        # ACL: only the original creator or MANAGER+ may post messages.
        await self._fetch_ticket(
            db,
            ticket_id,
            user_id_for_acl or author_user_id,
            role_for_acl or author_role,
        )
        msg = SupportMessage(
            ticket_id=ticket_id,
            author_user_id=author_user_id,
            author_role=author_role,
            body=body,
            is_internal_note=is_internal_note,
        )
        db.add(msg)
        # Bump ticket updated_at + flip to IN_PROGRESS if OPEN.
        ticket = (
            await db.execute(
                select(SupportTicket).where(SupportTicket.id == ticket_id)
            )
        ).scalar_one_or_none()
        if ticket is not None:
            ticket.updated_at = datetime.now(timezone.utc)
            if ticket.status == "OPEN":
                ticket.status = "IN_PROGRESS"
        await db.commit()
        msg = await db.get(SupportMessage, msg.id)
        return {
            "id": msg.id,
            "ticket_id": msg.ticket_id,
            "author_user_id": msg.author_user_id,
            "author_role": msg.author_role,
            "body": msg.body,
            "is_internal_note": msg.is_internal_note,
            "created_at": msg.created_at,
        }

    async def close_ticket(
        self,
        db: AsyncSession,
        ticket_id: int,
        user_id: str,
        role: str,
    ) -> None:
        ticket = await self._fetch_ticket(db, ticket_id, user_id, role)
        if role not in ("MANAGER", "TENANT_ADMIN", "SUPER_ADMIN"):
            # REP can only close their own tickets.
            if ticket.created_by_user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the ticket creator or a manager may close it.",
                )
        ticket.status = "CLOSED"
        ticket.resolved_at = datetime.now(timezone.utc)
        await db.commit()

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    async def _fetch_ticket(
        db: AsyncSession, ticket_id: int, user_id: str, role: str
    ) -> SupportTicket:
        ticket = (
            await db.execute(
                select(SupportTicket).where(SupportTicket.id == ticket_id)
            )
        ).scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found."
            )
        if role == "REP" and ticket.created_by_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="REP users can only access their own tickets.",
            )
        return ticket

    @staticmethod
    def _ticket_dict(t: SupportTicket) -> dict[str, Any]:
        return {
            "id": t.id,
            "subject": t.subject,
            "category": t.category,
            "priority": t.priority,
            "status": t.status,
            "created_by_user_id": t.created_by_user_id,
            "assigned_to": t.assigned_to,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "resolved_at": t.resolved_at,
        }


__all__ = ["SupportService"]
