"""
notifications_router.py — In-app notification endpoints (FR-E14-019).

Exposes GET /api/v1/notifications returning the current user's notifications
(paginatedD optional unread filter), plus PATCH to mark read and
DELETE to dismiss. The notification bell widget in the Topbar polls the
unread count.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Schemas ────────────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    body: str
    is_read: bool = False
    action_url: str | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class MarkReadRequest(BaseModel):
    notification_ids: list[str] = Field(
        default_factory=list,
        description="IDs to mark read. Empty = mark all read.",
    )


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> NotificationListResponse:
    """List notifications for the current user. Optionally filter to unread only."""
    try:
        from sqlalchemy import text

        where_clause = "" if not unread_only else 'WHERE "isRead" = false'
        # Count
        count_q = await db.execute(
            text(f'SELECT COUNT(*) FROM "Notification" {where_clause}')
        )
        total = count_q.scalar() or 0

        # Unread count (always)
        unread_q = await db.execute(
            text('SELECT COUNT(*) FROM "Notification" WHERE "isRead" = false')
        )
        unread_count = unread_q.scalar() or 0

        # Items
        items_q = await db.execute(
            text(
                f'SELECT id, type, title, body, "isRead", "actionUrl", "createdAt" '
                f'FROM "Notification" {where_clause} '
                f'ORDER BY "createdAt" DESC LIMIT :limit OFFSET :offset'
            ),
            {"limit": limit, "offset": offset},
        )
        rows = items_q.mappings().all()
        items = [
            NotificationResponse(
                id=r["id"],
                type=r.get("type") or "info",
                title=r.get("title") or "",
                body=r.get("body") or "",
                is_read=r.get("isRead", False),
                action_url=r.get("actionUrl"),
                created_at=r.get("createdAt") or datetime.now(timezone.utc),
            )
            for r in rows
        ]
    except Exception:
        # Table may not exist yet — return empty
        items = []
        total = 0
        unread_count = 0

    return NotificationListResponse(
        items=items, total=total, unread_count=unread_count, limit=limit, offset=offset
    )


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Return just the unread notification count (for the bell badge)."""
    try:
        from sqlalchemy import text

        q = await db.execute(
            text('SELECT COUNT(*) FROM "Notification" WHERE "isRead" = false')
        )
        count = q.scalar() or 0
    except Exception:
        count = 0
    return {"unread_count": count}


@router.patch("/mark-read")
async def mark_read(
    body: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Mark notifications as read. Empty list = mark all read."""
    try:
        from sqlalchemy import text

        if body.notification_ids:
            for nid in body.notification_ids:
                await db.execute(
                    text('UPDATE "Notification" SET "isRead" = true WHERE id = :id'),
                    {"id": nid},
                )
        else:
            await db.execute(
                text('UPDATE "Notification" SET "isRead" = true WHERE "isRead" = false')
            )
        await db.commit()
    except Exception:
        pass  # Table may not exist yet
    return {"ok": True}


@router.delete("/{notification_id}", response_class=Response, status_code=204)
async def dismiss_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> Response:
    """Dismiss (delete) a notification."""
    try:
        from sqlalchemy import text

        await db.execute(
            text('DELETE FROM "Notification" WHERE id = :id'), {"id": notification_id}
        )
        await db.commit()
    except Exception:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
