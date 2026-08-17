"""
sequence_service.py — Sequence CRUD + send-email + scheduled-send + 7-touch cadence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Campaign, Sequence, SubjectLine
from app.models.enums import EmailStatus
from app.models.prospect_models import Prospect
from app.schemas.sequences import (
    SEVEN_TOUCH_CADENCE,
    ScheduledSendRequest,
    SequenceCreate,
    SequenceUpdate,
    SendEmailRequest,
    SendEmailResponse,
    SubjectLineCreate,
)
from app.features.mailbridge.service import MailBridgeService

logger = structlog.get_logger(__name__)



class SequenceService:
    """CRUD + send + cadence operations for Sequence rows."""

    def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
        self._mailbridge = mailbridge or MailBridgeService()

    async def list_sequences(
        self,
        db: AsyncSession,
        *,
        campaign_id: str | None = None,
        prospect_id: str | None = None,
        status: EmailStatus | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        role: str | None = None,
    ) -> tuple[list[Sequence], int]:
        """List sequences, optionally filtered by owner_user_id.

        Per-user scoping (mirrors CampaignService.list_campaigns):
          * role == "REP" → filter by owner_user_id == user_id.
          * MANAGER+ or role is None → no owner filter.
        """
        stmt = select(Sequence).options(selectinload(Sequence.subjectLines)).offset(offset).limit(limit)
        if campaign_id:
            stmt = stmt.where(Sequence.campaignId == campaign_id)
        if prospect_id:
            stmt = stmt.where(Sequence.prospectId == prospect_id)
        if status:
            stmt = stmt.where(Sequence.status == status)
        if user_id is not None and role is not None and role.upper() == "REP":
            stmt = stmt.where(Sequence.owner_user_id == user_id)
        result = await db.execute(stmt)
        items = list(result.scalars().all())
        # total count (best-effort — Phase 4 may add a count query)
        return items, len(items)

    async def get(self, db: AsyncSession, sequence_id: str) -> Sequence | None:
        result = await db.execute(
            select(Sequence).options(selectinload(Sequence.subjectLines)).where(Sequence.id == sequence_id)
        )
        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        db: AsyncSession,
        sequence_id: str,
        *,
        user_id: str,
        role: str,
    ) -> Sequence | None:
        """Fetch a sequence, enforcing per-user ACL for REP role."""
        item = await self.get(db, sequence_id)
        if item is None:
            return None
        if role.upper() == "REP" and item.owner_user_id != user_id:
            return None
        return item

    async def create(
        self,
        db: AsyncSession,
        body: SequenceCreate,
        *,
        owner_user_id: str | None = None,
    ) -> Sequence:
        """Create a sequence — owner_user_id stamped from token.sub by router.

        If owner_user_id is not provided, the sequence is stamped with the
        backfill default 'system' (existing behaviour preserved).
        """
        seq = Sequence(
            campaignId=body.campaignId,
            prospectId=body.prospectId,
            touchNumber=body.touchNumber,
            sendDay=body.sendDay,
            channel=body.channel,
            angle=body.angle,
            framework=body.framework,
            subjectLine=body.subjectLine,
            bodyCopy=body.bodyCopy,
            status=EmailStatus.Draft,
            owner_user_id=owner_user_id or "system",
        )
        db.add(seq)
        await db.commit()
        seq = await db.get(Sequence, seq.id)
        return seq

    async def update(
        self, db: AsyncSession, sequence_id: str, body: SequenceUpdate
    ) -> Sequence | None:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(seq, key, value)
        await db.commit()
        seq = await db.get(Sequence, seq.id)
        return seq

    async def delete(self, db: AsyncSession, sequence_id: str) -> bool:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return False
        await db.delete(seq)
        await db.commit()
        return True

    async def add_subject_line(
        self, db: AsyncSession, sequence_id: str, body: SubjectLineCreate
    ) -> SubjectLine | None:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        sl = SubjectLine(
            sequenceId=sequence_id,
            variant=body.variant,
            isSelected=body.isSelected,
        )
        db.add(sl)
        await db.commit()
        sl = await db.get(SubjectLine, sl.id)
        return sl

    async def list_subject_lines(
        self, db: AsyncSession, sequence_id: str
    ) -> list[SubjectLine]:
        result = await db.execute(
            select(SubjectLine).where(SubjectLine.sequenceId == sequence_id)
        )
        return list(result.scalars().all())

    async def schedule_send(
        self, db: AsyncSession, sequence_id: str, body: ScheduledSendRequest
    ) -> Sequence | None:
        """Set status=Scheduled. Phase 5 scheduler will pick it up."""
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        if seq.status not in (EmailStatus.Draft, EmailStatus.QaPassed):
            # Can only schedule drafts or QA-passed sequences
            pass
        seq.status = EmailStatus.Scheduled
        await db.commit()
        seq = await db.get(Sequence, seq.id)
        return seq

    async def send_email(
        self, db: AsyncSession, sequence_id: str, body: SendEmailRequest
    ) -> SendEmailResponse:
        """Fire a sequence immediately via MailBridge (Phase 3 stub-friendly)."""
        seq = await self.get(db, sequence_id)
        if seq is None:
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Sequence not found",
            )
        # QA gate: only QaPassed/Scheduled can be sent unless force=True
        if not body.force and seq.status not in (
            EmailStatus.QaPassed,
            EmailStatus.Scheduled,
        ):
            return SendEmailResponse(
                id=sequence_id,
                status=seq.status,
                mailBridgeMessageId=None,
                sentAt=None,
                message=(
                    f"Cannot send sequence in status '{seq.status.value}'. "
                    "Pass force=true to bypass."
                ),
            )
        # Lookup the campaign's MailBridgeConfig
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == seq.campaignId)
        )
        campaign = campaign_result.scalar_one_or_none()

        # FIX-BE-1 / HIGH 5 (re-verification): resolve the prospect's email
        # from the linked Prospect row. Previously this passed to="" which
        # produced empty-envelope sends (MailBridge stub-accepts, but real
        # SMTP relays reject null-recipient messages). PII is encrypted at
        # rest — the ProspectService._pii.decrypt_field helper is used to
        # recover the cleartext email. Best-effort: if Prospect is missing
        # or email is empty, surface a deterministic Failed response so the
        # caller sees an actionable error instead of a silent success.
        to_email = ""
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == seq.prospectId)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is not None:
            raw_email = getattr(prospect, "email", None) or ""
            if raw_email and not getattr(prospect, "anonymized", False):
                # Decrypt at rest via the shared PII service. We import
                # lazily to avoid a circular import at module load time.
                try:
                    from app.services.pii_service import PiiService

                    to_email = PiiService().decrypt_field(raw_email) or ""
                except Exception as exc:  # noqa: BLE001 — best-effort
                    logger.warning(
                        "sequence.send_email.email_decrypt_failed",
                        prospect_id=getattr(prospect, "id", None),
                        error=str(exc),
                    )
                    to_email = raw_email  # fall back to stored value
            elif raw_email:
                to_email = raw_email
        if not to_email:
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Prospect email is missing — cannot send sequence.",
            )

        result = await self._mailbridge.send(
            db=db,
            to=to_email,
            subject=seq.subjectLine or "",
            body=seq.bodyCopy or "",
            sequence_id=sequence_id,
            config_id=campaign.domainId if campaign else None,
            user_id=getattr(seq, "owner_user_id", None),
        )
        seq.status = (
            EmailStatus.Sent if result.accepted else EmailStatus.Failed
        )
        seq.sentAt = datetime.now(timezone.utc) if result.accepted else None
        seq.mailBridgeMessageId = result.messageId
        await db.commit()
        seq = await db.get(Sequence, seq.id)
        return SendEmailResponse(
            id=sequence_id,
            status=seq.status,
            mailBridgeMessageId=seq.mailBridgeMessageId,
            sentAt=seq.sentAt,
            message="Sent" if result.accepted else "Send failed",
        )

    @staticmethod
    def get_cadence() -> list[Any]:
        """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
        return SEVEN_TOUCH_CADENCE

    async def auto_generate_for_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
        *,
        prospect_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[Sequence]:
        """Auto-generate the 7 Sequence rows for a campaign's 7-touch cadence.

        FIX-BE-1 / MEDIUM 10 (re-verification): get_cadence() returned the
        7-touch cadence but nothing auto-generated the Sequence rows when a
        campaign was created, leaving the Sequence tab empty until the user
        manually created all 7 rows. This helper:

          1. Reads SEVEN_TOUCH_CADENCE (7 entries: touchNumber, sendDay,
             angle, defaultFramework).
          2. Idempotency: skips touches that already exist for
             (campaignId, prospectId, touchNumber) — safe to re-run after
             a partial failure or when prospect_id is added later.
          3. Inserts one Sequence per cadence entry with status=Draft and
             owner_user_id stamped from the caller.

        Returns the list of newly-created Sequence rows (existing ones are
        excluded). Called by CampaignService.link_prospect on prospect-link
        (prospect_id is the linked Prospect's id — the Sequence model
        requires prospectId NOT NULL + FK to Prospect, so we can't
        auto-generate at campaign-create time before any prospect is linked).
        """
        from app.models.campaign_models import Sequence as _Seq

        if not prospect_id:
            # Without a prospect_id the FK constraint on Sequence.prospectId
            # would reject the insert — skip silently (callers should pass
            # the prospect_id being linked).
            return []

        created: list[Sequence] = []
        for touch in SEVEN_TOUCH_CADENCE:
            # Idempotency: skip if a row already exists for this combo.
            existing = (
                await db.execute(
                    select(_Seq).where(
                        _Seq.campaignId == campaign_id,
                        _Seq.prospectId == prospect_id,
                        _Seq.touchNumber == touch.touchNumber,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            seq = Sequence(
                campaignId=campaign_id,
                prospectId=prospect_id,
                touchNumber=touch.touchNumber,
                sendDay=touch.sendDay,
                channel="email",
                angle=touch.angle,
                framework=touch.defaultFramework,
                status=EmailStatus.Draft,
                owner_user_id=owner_user_id or "system",
            )
            db.add(seq)
            created.append(seq)
        if created:
            await db.commit()
            for s in created:
                s = await db.get(Sequence, s.id)
        return created