"""
meetings_router.py — /api/v1/meetings CRUD endpoints.

Meeting model lives in app/models/prospect_models.Meeting.  The existing
meeting-prep router (router.py in this package) handles brief generation.
This router handles the calendar entry itself.

Endpoints:
  GET    /meetings            list all meetings (optional: status, prospectId filters)
  POST   /meetings            create a meeting (201)
  GET    /meetings/{id}       fetch one
  PATCH  /meetings/{id}       partial update
  DELETE /meetings/{id}       delete (204)

Role gate: Role.REP
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.models.prospect_models import Meeting
from app.schemas.auth import Role, TokenPayload

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/meetings", tags=["Meetings"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class MeetingInput(BaseModel):
    title: str
    scheduledAt: datetime
    durationMin: int = 30
    meetingUrl: str | None = None
    status: str = "scheduled"
    prospectId: str | None = None
    meetingPrepId: str | None = None
    notes: str | None = None


class MeetingPatch(BaseModel):
    title: str | None = None
    scheduledAt: datetime | None = None
    durationMin: int | None = None
    meetingUrl: str | None = None
    status: str | None = None
    prospectId: str | None = None
    meetingPrepId: str | None = None
    notes: str | None = None


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    scheduledAt: datetime
    durationMin: int
    meetingUrl: str | None
    status: str
    prospectId: str | None
    meetingPrepId: str | None
    notes: str | None
    createdAt: datetime
    updatedAt: datetime


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MeetingResponse])
async def list_meetings(
    status: str | None = Query(None),
    prospect_id: str | None = Query(None, alias="prospectId"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[MeetingResponse]:
    stmt = select(Meeting).order_by(Meeting.scheduledAt.desc()).offset(offset).limit(limit)
    if status:
        stmt = stmt.where(Meeting.status == status)
    if prospect_id:
        stmt = stmt.where(Meeting.prospectId == prospect_id)
    result = await db.execute(stmt)
    meetings = list(result.scalars().all())
    return [MeetingResponse.model_validate(m) for m in meetings]


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    body: MeetingInput,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingResponse:
    meeting = Meeting(**body.model_dump(exclude_none=False))
    db.add(meeting)
    await db.commit()
    meeting = await db.get(Meeting, meeting.id)
    logger.info("meeting.created", meeting_id=meeting.id, title=meeting.title)
    return MeetingResponse.model_validate(meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingResponse:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return MeetingResponse.model_validate(meeting)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    body: MeetingPatch,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MeetingResponse:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(meeting, field, value)
    await db.commit()
    meeting = await db.get(Meeting, meeting.id)
    return MeetingResponse.model_validate(meeting)


@router.get(
    "/{meeting_id}/ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}, "description": "iCalendar file"}},
)
async def get_meeting_ics(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
):
    """
    Return a downloadable .ics calendar invite for a meeting (FR-E8-008).

    The invite is always in UTC. Attendees get an ORGANIZER line from the
    server — no Keycloak call needed. Compatible with Outlook, Google
    Calendar, and Apple Calendar.
    """
    from fastapi.responses import Response as _Response
    from datetime import timezone as _tz
    import textwrap as _textwrap

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Convert to UTC
    start = meeting.scheduledAt.astimezone(_tz.utc)
    from datetime import timedelta as _td
    end = start + _td(minutes=meeting.durationMin)

    def _dt(dt) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    location_line = f"\r\nLOCATION:{meeting.meetingUrl}" if meeting.meetingUrl else ""
    _notes = (meeting.notes or "").replace("\n", "\\n")
    description_line = f"\r\nDESCRIPTION:{_notes}"

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//OUTRENA//Meeting//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{meeting_id}@outrena\r\n"
        f"DTSTART:{_dt(start)}\r\n"
        f"DTEND:{_dt(end)}\r\n"
        f"SUMMARY:{meeting.title}"
        f"{location_line}"
        f"{description_line}\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return _Response(
        content=ics,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="meeting-{meeting_id}.ics"',
        },
    )


@router.post("/{meeting_id}/send-invite", status_code=200)
async def send_meeting_invite(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """
    FR-056: email the .ics calendar invite to the meeting's attendee via
    MailBridge. The attendee is the linked prospect's email; the sender is
    the calling user's MailBridge identity. The .ics content is embedded in
    the message body (text/calendar inline is relay-dependent; the body
    carries the invite content so any client can import it).
    """
    from datetime import timedelta as _td
    from datetime import timezone as _tz

    from app.features.mailbridge.service import MailBridgeService
    from app.models.prospect_models import Prospect as _Prospect

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.prospectId:
        raise HTTPException(
            status_code=422, detail="Meeting has no linked prospect to invite."
        )
    prospect = (
        await db.execute(select(_Prospect).where(_Prospect.id == meeting.prospectId))
    ).scalar_one_or_none()
    if prospect is None or not prospect.email:
        raise HTTPException(
            status_code=422, detail="Linked prospect has no email address."
        )

    start = meeting.scheduledAt.astimezone(_tz.utc)
    end = start + _td(minutes=meeting.durationMin)

    def _dt(dt) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "PRODID:-//OUTRENA//Meeting//EN\r\nMETHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{meeting_id}@outrena\r\n"
        f"DTSTART:{_dt(start)}\r\nDTEND:{_dt(end)}\r\n"
        f"SUMMARY:{meeting.title}\r\n"
        f"ATTENDEE;RSVP=TRUE:mailto:{prospect.email}\r\n"
        "STATUS:CONFIRMED\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    body = (
        f"You're invited: {meeting.title}\n"
        f"When: {start.strftime('%Y-%m-%d %H:%M UTC')} "
        f"({meeting.durationMin} min)\n"
        + (f"Where: {meeting.meetingUrl}\n" if meeting.meetingUrl else "")
        + "\n--- Calendar invite (save as .ics and open) ---\n\n"
        + ics
    )
    mb = MailBridgeService()
    resp = await mb.send(
        db=db,
        to=prospect.email,
        subject=f"Invitation: {meeting.title}",
        body=body,
        user_id=token.sub,
    )
    return {
        "sent": bool(resp.accepted),
        "messageId": resp.messageId,
        "to": prospect.email,
    }


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> Response:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await db.delete(meeting)
    await db.commit()
    logger.info("meeting.deleted", meeting_id=meeting_id)
    return Response(status_code=204)