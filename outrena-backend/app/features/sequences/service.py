# # """
# # sequence_service.py — Sequence CRUD + send-email + scheduled-send + 7-touch cadence.
# # """
# # from __future__ import annotations

# # from datetime import datetime, timezone
# # from typing import Any

# # import structlog
# # from sqlalchemy import select
# # from sqlalchemy.orm import selectinload
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.models.campaign_models import Campaign, Sequence, SubjectLine
# # from app.models.enums import EmailStatus
# # from app.models.prospect_models import Prospect
# # from app.schemas.sequences import (
# #     SEVEN_TOUCH_CADENCE,
# #     ScheduledSendRequest,
# #     SequenceCreate,
# #     SequenceUpdate,
# #     SendEmailRequest,
# #     SendEmailResponse,
# #     SubjectLineCreate,
# # )
# # from app.features.mailbridge.service import MailBridgeService

# # logger = structlog.get_logger(__name__)



# # class SequenceService:
# #     """CRUD + send + cadence operations for Sequence rows."""

# #     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
# #         self._mailbridge = mailbridge or MailBridgeService()

# #     async def list_sequences(
# #         self,
# #         db: AsyncSession,
# #         *,
# #         campaign_id: str | None = None,
# #         prospect_id: str | None = None,
# #         status: EmailStatus | None = None,
# #         limit: int = 50,
# #         offset: int = 0,
# #         user_id: str | None = None,
# #         role: str | None = None,
# #     ) -> tuple[list[Sequence], int]:
# #         """List sequences, optionally filtered by owner_user_id.

# #         Per-user scoping (mirrors CampaignService.list_campaigns):
# #           * role == "REP" → filter by owner_user_id == user_id.
# #           * MANAGER+ or role is None → no owner filter.
# #         """
# #         stmt = select(Sequence).options(selectinload(Sequence.subjectLines)).offset(offset).limit(limit)
# #         if campaign_id:
# #             stmt = stmt.where(Sequence.campaignId == campaign_id)
# #         if prospect_id:
# #             stmt = stmt.where(Sequence.prospectId == prospect_id)
# #         if status:
# #             stmt = stmt.where(Sequence.status == status)
# #         if user_id is not None and role is not None and role.upper() == "REP":
# #             stmt = stmt.where(Sequence.owner_user_id == user_id)
# #         result = await db.execute(stmt)
# #         items = list(result.scalars().all())
# #         # total count (best-effort — Phase 4 may add a count query)
# #         return items, len(items)

# #     async def get(self, db: AsyncSession, sequence_id: str) -> Sequence | None:
# #         result = await db.execute(
# #             select(Sequence).options(selectinload(Sequence.subjectLines)).where(Sequence.id == sequence_id)
# #         )
# #         return result.scalar_one_or_none()

# #     async def get_for_user(
# #         self,
# #         db: AsyncSession,
# #         sequence_id: str,
# #         *,
# #         user_id: str,
# #         role: str,
# #     ) -> Sequence | None:
# #         """Fetch a sequence, enforcing per-user ACL for REP role."""
# #         item = await self.get(db, sequence_id)
# #         if item is None:
# #             return None
# #         if role.upper() == "REP" and item.owner_user_id != user_id:
# #             return None
# #         return item

# #     async def create(
# #         self,
# #         db: AsyncSession,
# #         body: SequenceCreate,
# #         *,
# #         owner_user_id: str | None = None,
# #     ) -> Sequence:
# #         """Create a sequence — owner_user_id stamped from token.sub by router.

# #         If owner_user_id is not provided, the sequence is stamped with the
# #         backfill default 'system' (existing behaviour preserved).
# #         """
# #         seq = Sequence(
# #             campaignId=body.campaignId,
# #             prospectId=body.prospectId,
# #             touchNumber=body.touchNumber,
# #             sendDay=body.sendDay,
# #             channel=body.channel,
# #             angle=body.angle,
# #             framework=body.framework,
# #             subjectLine=body.subjectLine,
# #             bodyCopy=body.bodyCopy,
# #             status=EmailStatus.Draft,
# #             owner_user_id=owner_user_id or "system",
# #         )
# #         db.add(seq)
# #         await db.commit()
# #         seq = await db.get(Sequence, seq.id)
# #         return seq

# #     async def update(
# #         self, db: AsyncSession, sequence_id: str, body: SequenceUpdate
# #     ) -> Sequence | None:
# #         seq = await self.get(db, sequence_id)
# #         if seq is None:
# #             return None
# #         data = body.model_dump(exclude_unset=True)
# #         for key, value in data.items():
# #             setattr(seq, key, value)
# #         await db.commit()
# #         seq = await db.get(Sequence, seq.id)
# #         return seq

# #     async def delete(self, db: AsyncSession, sequence_id: str) -> bool:
# #         seq = await self.get(db, sequence_id)
# #         if seq is None:
# #             return False
# #         await db.delete(seq)
# #         await db.commit()
# #         return True

# #     async def add_subject_line(
# #         self, db: AsyncSession, sequence_id: str, body: SubjectLineCreate
# #     ) -> SubjectLine | None:
# #         seq = await self.get(db, sequence_id)
# #         if seq is None:
# #             return None
# #         sl = SubjectLine(
# #             sequenceId=sequence_id,
# #             variant=body.variant,
# #             isSelected=body.isSelected,
# #         )
# #         db.add(sl)
# #         await db.commit()
# #         sl = await db.get(SubjectLine, sl.id)
# #         return sl

# #     async def list_subject_lines(
# #         self, db: AsyncSession, sequence_id: str
# #     ) -> list[SubjectLine]:
# #         result = await db.execute(
# #             select(SubjectLine).where(SubjectLine.sequenceId == sequence_id)
# #         )
# #         return list(result.scalars().all())

# #     async def schedule_send(
# #         self, db: AsyncSession, sequence_id: str, body: ScheduledSendRequest
# #     ) -> Sequence | None:
# #         """Set status=Scheduled. Phase 5 scheduler will pick it up."""
# #         seq = await self.get(db, sequence_id)
# #         if seq is None:
# #             return None
# #         if seq.status not in (EmailStatus.Draft, EmailStatus.QaPassed):
# #             # Can only schedule drafts or QA-passed sequences
# #             pass
# #         seq.status = EmailStatus.Scheduled
# #         await db.commit()
# #         seq = await db.get(Sequence, seq.id)
# #         return seq

# #     async def send_email(
# #         self, db: AsyncSession, sequence_id: str, body: SendEmailRequest
# #     ) -> SendEmailResponse:
# #         """Fire a sequence immediately via MailBridge (Phase 3 stub-friendly)."""
# #         seq = await self.get(db, sequence_id)
# #         if seq is None:
# #             return SendEmailResponse(
# #                 id=sequence_id,
# #                 status=EmailStatus.Failed,
# #                 mailBridgeMessageId=None,
# #                 sentAt=None,
# #                 message="Sequence not found",
# #             )
# #         # QA gate: only QaPassed/Scheduled can be sent unless force=True
# #         if not body.force and seq.status not in (
# #             EmailStatus.QaPassed,
# #             EmailStatus.Scheduled,
# #         ):
# #             return SendEmailResponse(
# #                 id=sequence_id,
# #                 status=seq.status,
# #                 mailBridgeMessageId=None,
# #                 sentAt=None,
# #                 message=(
# #                     f"Cannot send sequence in status '{seq.status.value}'. "
# #                     "Pass force=true to bypass."
# #                 ),
# #             )
# #         # Lookup the campaign's MailBridgeConfig
# #         campaign_result = await db.execute(
# #             select(Campaign).where(Campaign.id == seq.campaignId)
# #         )
# #         campaign = campaign_result.scalar_one_or_none()

# #         # FIX-BE-1 / HIGH 5 (re-verification): resolve the prospect's email
# #         # from the linked Prospect row. Previously this passed to="" which
# #         # produced empty-envelope sends (MailBridge stub-accepts, but real
# #         # SMTP relays reject null-recipient messages). PII is encrypted at
# #         # rest — the ProspectService._pii.decrypt_field helper is used to
# #         # recover the cleartext email. Best-effort: if Prospect is missing
# #         # or email is empty, surface a deterministic Failed response so the
# #         # caller sees an actionable error instead of a silent success.
# #         to_email = ""
# #         prospect_result = await db.execute(
# #             select(Prospect).where(Prospect.id == seq.prospectId)
# #         )
# #         prospect = prospect_result.scalar_one_or_none()
# #         if prospect is not None:
# #             raw_email = getattr(prospect, "email", None) or ""
# #             if raw_email and not getattr(prospect, "anonymized", False):
# #                 # Decrypt at rest via the shared PII service. We import
# #                 # lazily to avoid a circular import at module load time.
# #                 try:
# #                     from app.services.pii_service import PiiService

# #                     to_email = PiiService().decrypt_field(raw_email) or ""
# #                 except Exception as exc:  # noqa: BLE001 — best-effort
# #                     logger.warning(
# #                         "sequence.send_email.email_decrypt_failed",
# #                         prospect_id=getattr(prospect, "id", None),
# #                         error=str(exc),
# #                     )
# #                     to_email = raw_email  # fall back to stored value
# #             elif raw_email:
# #                 to_email = raw_email
# #         if not to_email:
# #             return SendEmailResponse(
# #                 id=sequence_id,
# #                 status=EmailStatus.Failed,
# #                 mailBridgeMessageId=None,
# #                 sentAt=None,
# #                 message="Prospect email is missing — cannot send sequence.",
# #             )

# #         result = await self._mailbridge.send(
# #             db=db,
# #             to=to_email,
# #             subject=seq.subjectLine or "",
# #             body=seq.bodyCopy or "",
# #             sequence_id=sequence_id,
# #             config_id=campaign.domainId if campaign else None,
# #             user_id=getattr(seq, "owner_user_id", None),
# #         )
# #         seq.status = (
# #             EmailStatus.Sent if result.accepted else EmailStatus.Failed
# #         )
# #         seq.sentAt = datetime.now(timezone.utc) if result.accepted else None
# #         seq.mailBridgeMessageId = result.messageId
# #         await db.commit()
# #         seq = await db.get(Sequence, seq.id)
# #         return SendEmailResponse(
# #             id=sequence_id,
# #             status=seq.status,
# #             mailBridgeMessageId=seq.mailBridgeMessageId,
# #             sentAt=seq.sentAt,
# #             message="Sent" if result.accepted else "Send failed",
# #         )

# #     @staticmethod
# #     def get_cadence() -> list[Any]:
# #         """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
# #         return SEVEN_TOUCH_CADENCE

# #     async def auto_generate_for_campaign(
# #         self,
# #         db: AsyncSession,
# #         campaign_id: str,
# #         *,
# #         prospect_id: str | None = None,
# #         owner_user_id: str | None = None,
# #     ) -> list[Sequence]:
# #         """Auto-generate the 7 Sequence rows for a campaign's 7-touch cadence.

# #         FIX-BE-1 / MEDIUM 10 (re-verification): get_cadence() returned the
# #         7-touch cadence but nothing auto-generated the Sequence rows when a
# #         campaign was created, leaving the Sequence tab empty until the user
# #         manually created all 7 rows. This helper:

# #           1. Reads SEVEN_TOUCH_CADENCE (7 entries: touchNumber, sendDay,
# #              angle, defaultFramework).
# #           2. Idempotency: skips touches that already exist for
# #              (campaignId, prospectId, touchNumber) — safe to re-run after
# #              a partial failure or when prospect_id is added later.
# #           3. Inserts one Sequence per cadence entry with status=Draft and
# #              owner_user_id stamped from the caller.

# #         Returns the list of newly-created Sequence rows (existing ones are
# #         excluded). Called by CampaignService.link_prospect on prospect-link
# #         (prospect_id is the linked Prospect's id — the Sequence model
# #         requires prospectId NOT NULL + FK to Prospect, so we can't
# #         auto-generate at campaign-create time before any prospect is linked).
# #         """
# #         from app.models.campaign_models import Sequence as _Seq

# #         if not prospect_id:
# #             # Without a prospect_id the FK constraint on Sequence.prospectId
# #             # would reject the insert — skip silently (callers should pass
# #             # the prospect_id being linked).
# #             return []

# #         created: list[Sequence] = []
# #         for touch in SEVEN_TOUCH_CADENCE:
# #             # Idempotency: skip if a row already exists for this combo.
# #             existing = (
# #                 await db.execute(
# #                     select(_Seq).where(
# #                         _Seq.campaignId == campaign_id,
# #                         _Seq.prospectId == prospect_id,
# #                         _Seq.touchNumber == touch.touchNumber,
# #                     )
# #                 )
# #             ).scalar_one_or_none()
# #             if existing is not None:
# #                 continue
# #             seq = Sequence(
# #                 campaignId=campaign_id,
# #                 prospectId=prospect_id,
# #                 touchNumber=touch.touchNumber,
# #                 sendDay=touch.sendDay,
# #                 channel="email",
# #                 angle=touch.angle,
# #                 framework=touch.defaultFramework,
# #                 status=EmailStatus.Draft,
# #                 owner_user_id=owner_user_id or "system",
# #             )
# #             db.add(seq)
# #             created.append(seq)
# #         if created:
# #             await db.commit()
# #             for s in created:
# #                 s = await db.get(Sequence, s.id)
# #         return created

# """
# sequence_service.py — Sequence CRUD + send-email + scheduled-send + 7-touch cadence.

# FIX (search_path crash): Removed all post-commit db.get() / db.refresh() calls.
# After db.commit() on a schema-per-tenant asyncpg session, the connection is
# re-pooled and loses search_path. All methods now read from the in-memory ORM
# object after commit. eager_defaults=True on Base ensures server-generated
# columns (id, createdAt, updatedAt) are populated via RETURNING at INSERT time.

# FIX (wrong sender mailbox): send_email() now accepts caller_user_id which the
# router passes as token.sub. This is used as the user_id for MailBridge routing
# instead of seq.owner_user_id — which was frequently "system" on auto-generated
# sequences, causing all sends to go through the first connected mailbox.
# """
# from __future__ import annotations

# from datetime import datetime, timezone
# from typing import Any

# import structlog
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.campaign_models import Campaign, Sequence, SubjectLine
# from app.models.enums import EmailStatus
# from app.models.prospect_models import Prospect
# from app.schemas.sequences import (
#     SEVEN_TOUCH_CADENCE,
#     ScheduledSendRequest,
#     SequenceCreate,
#     SequenceUpdate,
#     SendEmailRequest,
#     SendEmailResponse,
#     SubjectLineCreate,
# )
# from app.features.mailbridge.service import MailBridgeService

# logger = structlog.get_logger(__name__)


# class SequenceService:
#     """CRUD + send + cadence operations for Sequence rows."""

#     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
#         self._mailbridge = mailbridge or MailBridgeService()

#     async def list_sequences(
#         self,
#         db: AsyncSession,
#         *,
#         campaign_id: str | None = None,
#         prospect_id: str | None = None,
#         status: EmailStatus | None = None,
#         limit: int = 50,
#         offset: int = 0,
#         user_id: str | None = None,
#         role: str | None = None,
#     ) -> tuple[list[Sequence], int]:
#         """List sequences, optionally filtered by owner_user_id."""
#         stmt = (
#             select(Sequence)
#             .options(selectinload(Sequence.subjectLines))
#             .offset(offset)
#             .limit(limit)
#         )
#         if campaign_id:
#             stmt = stmt.where(Sequence.campaignId == campaign_id)
#         if prospect_id:
#             stmt = stmt.where(Sequence.prospectId == prospect_id)
#         if status:
#             stmt = stmt.where(Sequence.status == status)
#         if user_id is not None and role is not None and role.upper() == "REP":
#             stmt = stmt.where(Sequence.owner_user_id == user_id)
#         result = await db.execute(stmt)
#         items = list(result.scalars().all())
#         return items, len(items)

#     async def get(self, db: AsyncSession, sequence_id: str) -> Sequence | None:
#         result = await db.execute(
#             select(Sequence)
#             .options(selectinload(Sequence.subjectLines))
#             .where(Sequence.id == sequence_id)
#         )
#         return result.scalar_one_or_none()

#     async def get_for_user(
#         self,
#         db: AsyncSession,
#         sequence_id: str,
#         *,
#         user_id: str,
#         role: str,
#     ) -> Sequence | None:
#         """Fetch a sequence, enforcing per-user ACL for REP role."""
#         item = await self.get(db, sequence_id)
#         if item is None:
#             return None
#         if role.upper() == "REP" and item.owner_user_id != user_id:
#             return None
#         return item

#     async def create(
#         self,
#         db: AsyncSession,
#         body: SequenceCreate,
#         *,
#         owner_user_id: str | None = None,
#     ) -> Sequence:
#         seq = Sequence(
#             campaignId=body.campaignId,
#             prospectId=body.prospectId,
#             touchNumber=body.touchNumber,
#             sendDay=body.sendDay,
#             channel=body.channel,
#             angle=body.angle,
#             framework=body.framework,
#             subjectLine=body.subjectLine,
#             bodyCopy=body.bodyCopy,
#             status=EmailStatus.Draft,
#             owner_user_id=owner_user_id or "system",
#         )
#         db.add(seq)
#         await db.commit()
#         return seq

#     async def update(
#         self, db: AsyncSession, sequence_id: str, body: SequenceUpdate
#     ) -> Sequence | None:
#         seq = await self.get(db, sequence_id)
#         if seq is None:
#             return None
#         data = body.model_dump(exclude_unset=True)
#         for key, value in data.items():
#             setattr(seq, key, value)
#         await db.commit()
#         return seq

#     async def delete(self, db: AsyncSession, sequence_id: str) -> bool:
#         seq = await self.get(db, sequence_id)
#         if seq is None:
#             return False
#         await db.delete(seq)
#         await db.commit()
#         return True

#     async def add_subject_line(
#         self, db: AsyncSession, sequence_id: str, body: SubjectLineCreate
#     ) -> SubjectLine | None:
#         seq = await self.get(db, sequence_id)
#         if seq is None:
#             return None
#         sl = SubjectLine(
#             sequenceId=sequence_id,
#             variant=body.variant,
#             isSelected=body.isSelected,
#         )
#         db.add(sl)
#         await db.commit()
#         return sl

#     async def list_subject_lines(
#         self, db: AsyncSession, sequence_id: str
#     ) -> list[SubjectLine]:
#         result = await db.execute(
#             select(SubjectLine).where(SubjectLine.sequenceId == sequence_id)
#         )
#         return list(result.scalars().all())

#     async def schedule_send(
#         self, db: AsyncSession, sequence_id: str, body: ScheduledSendRequest
#     ) -> Sequence | None:
#         seq = await self.get(db, sequence_id)
#         if seq is None:
#             return None
#         seq.status = EmailStatus.Scheduled
#         await db.commit()
#         return seq

#     async def send_email(
#         self,
#         db: AsyncSession,
#         sequence_id: str,
#         body: SendEmailRequest,
#         *,
#         caller_user_id: str | None = None,
#     ) -> SendEmailResponse:
#         """Fire a sequence immediately via MailBridge.

#         caller_user_id: token.sub from the router — the Keycloak UUID of the
#           user clicking Send Now. Used as MailBridge external_user_id so the
#           email routes through that user's connected mailbox (Gmail/Outlook).
#           Takes priority over seq.owner_user_id, which is often "system" on
#           auto-generated sequences.
#         """
#         seq = await self.get(db, sequence_id)
#         if seq is None:
#             return SendEmailResponse(
#                 id=sequence_id,
#                 status=EmailStatus.Failed,
#                 mailBridgeMessageId=None,
#                 sentAt=None,
#                 message="Sequence not found",
#             )

#         if not body.force and seq.status not in (
#             EmailStatus.QaPassed,
#             EmailStatus.Scheduled,
#         ):
#             return SendEmailResponse(
#                 id=sequence_id,
#                 status=seq.status,
#                 mailBridgeMessageId=None,
#                 sentAt=None,
#                 message=(
#                     f"Cannot send sequence in status '{seq.status.value}'. "
#                     "Pass force=true to bypass."
#                 ),
#             )

#         campaign_result = await db.execute(
#             select(Campaign).where(Campaign.id == seq.campaignId)
#         )
#         campaign = campaign_result.scalar_one_or_none()

#         to_email = ""
#         prospect_result = await db.execute(
#             select(Prospect).where(Prospect.id == seq.prospectId)
#         )
#         prospect = prospect_result.scalar_one_or_none()
#         if prospect is not None:
#             raw_email = getattr(prospect, "email", None) or ""
#             if raw_email and not getattr(prospect, "anonymized", False):
#                 try:
#                     from app.services.pii_service import PiiService
#                     to_email = PiiService().decrypt_field(raw_email) or ""
#                 except Exception as exc:  # noqa: BLE001
#                     logger.warning(
#                         "sequence.send_email.email_decrypt_failed",
#                         prospect_id=getattr(prospect, "id", None),
#                         error=str(exc),
#                     )
#                     to_email = raw_email
#             elif raw_email:
#                 to_email = raw_email

#         if not to_email:
#             return SendEmailResponse(
#                 id=sequence_id,
#                 status=EmailStatus.Failed,
#                 mailBridgeMessageId=None,
#                 sentAt=None,
#                 message="Prospect email is missing — cannot send sequence.",
#             )

#         # FIX: use caller_user_id (token.sub) as the authoritative sender.
#         # Fall back to seq.owner_user_id only if it is a real user UUID
#         # (not "system"). Never pass "system" to MailBridge — it skips
#         # per-user routing and sends from the tenant's default mailbox.
#         seq_owner = getattr(seq, "owner_user_id", None)
#         effective_user_id = (
#             caller_user_id
#             or (seq_owner if seq_owner and seq_owner != "system" else None)
#         )

#         # send() never commits on this db session — all side effects use
#         # isolated AsyncSessionLocal() sessions internally.
#         result = await self._mailbridge.send(
#             db=db,
#             to=to_email,
#             subject=seq.subjectLine or "",
#             body=seq.bodyCopy or "",
#             sequence_id=sequence_id,
#             config_id=campaign.domainId if campaign else None,
#             user_id=effective_user_id,
#         )

#         # Capture values before commit — no post-commit db.get() needed.
#         new_status = EmailStatus.Sent if result.accepted else EmailStatus.Failed
#         new_sent_at = datetime.now(timezone.utc) if result.accepted else None
#         new_message_id = result.messageId

#         seq.status = new_status
#         seq.sentAt = new_sent_at
#         seq.mailBridgeMessageId = new_message_id
#         await db.commit()

#         return SendEmailResponse(
#             id=sequence_id,
#             status=new_status,
#             mailBridgeMessageId=new_message_id,
#             sentAt=new_sent_at,
#             message="Sent" if result.accepted else "Send failed",
#         )

#     @staticmethod
#     def get_cadence() -> list[Any]:
#         """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
#         return SEVEN_TOUCH_CADENCE

#     async def auto_generate_for_campaign(
#         self,
#         db: AsyncSession,
#         campaign_id: str,
#         *,
#         prospect_id: str | None = None,
#         owner_user_id: str | None = None,
#     ) -> list[Sequence]:
#         """Auto-generate the 7 Sequence rows for a campaign's 7-touch cadence."""
#         from app.models.campaign_models import Sequence as _Seq

#         if not prospect_id:
#             return []

#         created: list[Sequence] = []
#         for touch in SEVEN_TOUCH_CADENCE:
#             existing = (
#                 await db.execute(
#                     select(_Seq).where(
#                         _Seq.campaignId == campaign_id,
#                         _Seq.prospectId == prospect_id,
#                         _Seq.touchNumber == touch.touchNumber,
#                     )
#                 )
#             ).scalar_one_or_none()
#             if existing is not None:
#                 continue
#             seq = Sequence(
#                 campaignId=campaign_id,
#                 prospectId=prospect_id,
#                 touchNumber=touch.touchNumber,
#                 sendDay=touch.sendDay,
#                 channel="email",
#                 angle=touch.angle,
#                 framework=touch.defaultFramework,
#                 status=EmailStatus.Draft,
#                 owner_user_id=owner_user_id or "system",
#             )
#             db.add(seq)
#             created.append(seq)

#         if created:
#             await db.commit()

#         return created

"""
sequence_service.py — Sequence CRUD + send-email + scheduled-send + 7-touch cadence.

FIX (search_path crash): Removed all post-commit db.get() / db.refresh() calls.
After db.commit() on a schema-per-tenant asyncpg session, the connection is
re-pooled and loses search_path. All methods now read from the in-memory ORM
object after commit. eager_defaults=True on Base ensures server-generated
columns (id, createdAt, updatedAt) are populated via RETURNING at INSERT time.

FIX (wrong sender mailbox): send_email() now accepts caller_user_id which the
router passes as token.sub. This is used as the user_id for MailBridge routing
instead of seq.owner_user_id — which was frequently "system" on auto-generated
sequences, causing all sends to go through the first connected mailbox.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status as http_status
from sqlalchemy import select, text
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
        """List sequences, optionally filtered by owner_user_id."""
        stmt = (
            select(Sequence)
            .options(selectinload(Sequence.subjectLines))
            .offset(offset)
            .limit(limit)
        )
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
        return items, len(items)

    async def get(self, db: AsyncSession, sequence_id: str) -> Sequence | None:
        result = await db.execute(
            select(Sequence)
            .options(selectinload(Sequence.subjectLines))
            .where(Sequence.id == sequence_id)
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
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        seq.status = EmailStatus.Scheduled
        await db.commit()
        return seq

    async def send_email(
        self,
        db: AsyncSession,
        sequence_id: str,
        body: SendEmailRequest,
        *,
        caller_user_id: str | None = None,
    ) -> SendEmailResponse:
        """Fire a sequence immediately via MailBridge.

        caller_user_id: token.sub from the router — the Keycloak UUID of the
          user clicking Send Now. Used as MailBridge external_user_id so the
          email routes through that user's connected mailbox (Gmail/Outlook).
          Takes priority over seq.owner_user_id, which is often "system" on
          auto-generated sequences.
        """
        seq = await self.get(db, sequence_id)
        if seq is None:
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Sequence not found",
            )

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

        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == seq.campaignId)
        )
        campaign = campaign_result.scalar_one_or_none()

        to_email = ""
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == seq.prospectId)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is not None:
            raw_email = getattr(prospect, "email", None) or ""
            if raw_email and not getattr(prospect, "anonymized", False):
                try:
                    from app.services.pii_service import PiiService
                    to_email = PiiService().decrypt_field(raw_email) or ""
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "sequence.send_email.email_decrypt_failed",
                        prospect_id=getattr(prospect, "id", None),
                        error=str(exc),
                    )
                    to_email = raw_email
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

        # FIX: use caller_user_id (token.sub) as the authoritative sender.
        # Fall back to seq.owner_user_id only if it is a real user UUID
        # (not "system"). Never pass "system" to MailBridge — it skips
        # per-user routing and sends from the tenant's default mailbox.
        # seq_owner = getattr(seq, "owner_user_id", None)
        # effective_user_id = (
        #     caller_user_id
        #     or (seq_owner if seq_owner and seq_owner != "system" else None)
        # )

        # # send() never commits on this db session — all side effects use
        # # isolated AsyncSessionLocal() sessions internally.
        # result = await self._mailbridge.send(
        #     db=db,
        #     to=to_email,
        #     subject=seq.subjectLine or "",
        #     body=seq.bodyCopy or "",
        #     sequence_id=sequence_id,
        #     config_id=campaign.domainId if campaign else None,
        #     user_id=effective_user_id,
        # )

        seq_owner = getattr(seq, "owner_user_id", None)
        effective_user_id = (
            caller_user_id
            or (seq_owner if seq_owner and seq_owner != "system" else None)
        )

        # ── Domain warming gate (mirrors scheduler/_send_via_mailbridge) ──
        # Resolve the MailBridgeConfig for this user, then check the Domain
        # it points to — same three checks the scheduler runs on every tick.
        # body.force=true (MANAGER only) bypasses all three gates so admins
        # can override for testing or urgent manual sends.
        if not body.force:
            from app.features.mailbridge.service import MailBridgeService
            from app.models.config_models import Domain as _Domain, MailBridgeConfig as _MBConfig

            mb_config = await MailBridgeService._resolve_config(
                db, None, user_id=effective_user_id
            )
            if mb_config is not None and getattr(mb_config, "domainId", None):
                dom_result = await db.execute(
                    select(_Domain).where(_Domain.id == mb_config.domainId)
                )
                dom = dom_result.scalar_one_or_none()

                # Gate 1 — DNS verification
                if dom is not None and dom.lastChecked is not None:
                    failing = [
                        name for name, ok in (
                            ("SPF", dom.spfStatus),
                            ("DKIM", dom.dkimStatus),
                            ("DMARC", dom.dmarcStatus),
                        ) if not ok
                    ]
                    if failing:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"DNS verification failing for domain "
                                f"'{dom.domainName}': {', '.join(failing)}. "
                                "Fix the DNS records and re-verify in "
                                "Setup → Domains before sending."
                            ),
                        )

                # Gate 2 — warming week
                if dom is not None:
                    week = int(getattr(dom, "warmingWeek", 0) or 0)
                    if 1 <= week < 2:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"Domain '{dom.domainName}' has only completed "
                                f"{week} week(s) of warm-up. Click 'Auto-warm' "
                                "on Setup → Domains to advance to Week 2 before "
                                "sending."
                            ),
                        )

                # Gate 3 — daily cap
                if dom is not None:
                    _WARMUP_RAMP: dict[int, int] = {
                        1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500
                    }
                    week = int(getattr(dom, "warmingWeek", 0) or 0)
                    base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
                    effective_cap = min(base, _WARMUP_RAMP[week]) if 1 <= week <= 7 else base
                    sent_today = (
                        await db.execute(
                            text(
                                'SELECT COUNT(*) FROM "Sequence" s '
                                'JOIN "Campaign" c ON c.id = s."campaignId" '
                                'WHERE c."domainId" = :dom_id '
                                "  AND s.\"sentAt\" >= date_trunc('day', now())"
                            ),
                            {"dom_id": dom.id},
                        )
                    ).scalar() or 0
                    if int(sent_today) >= effective_cap:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"Daily warm-up cap reached for domain "
                                f"'{dom.domainName}' "
                                f"({sent_today}/{effective_cap} emails, "
                                f"Week {dom.warmingWeek}). "
                                "Remaining sends will go out tomorrow."
                            ),
                        )

        # send() never commits on this db session — all side effects use
        # isolated AsyncSessionLocal() sessions internally.
        result = await self._mailbridge.send(
            db=db,
            to=to_email,
            subject=seq.subjectLine or "",
            body=seq.bodyCopy or "",
            sequence_id=sequence_id,
            config_id=None,  # FIX: campaign.domainId is a Domain PK, not a MailBridgeConfig PK.
            user_id=effective_user_id,
        )

        # Capture values before commit — no post-commit db.get() needed.
        new_status = EmailStatus.Sent if result.accepted else EmailStatus.Failed
        new_sent_at = datetime.now(timezone.utc) if result.accepted else None
        new_message_id = result.messageId

        seq.status = new_status
        seq.sentAt = new_sent_at
        seq.mailBridgeMessageId = new_message_id
        # FIX: stamp owner_user_id with the mailbox that actually sent the email.
        # effective_user_id is the Keycloak UUID MailBridge used for routing —
        # this is the same UUID registered as external_user_id in MailBridge's
        # users table. The reply poller uses owner_user_id to call
        # GET /auth/connect/replies, so it must match the mailbox that received
        # the reply, not the user who clicked Send Now.
        if result.accepted and effective_user_id:
            seq.owner_user_id = effective_user_id
        await db.commit()

        return SendEmailResponse(
            id=sequence_id,
            status=new_status,
            mailBridgeMessageId=new_message_id,
            sentAt=new_sent_at,
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
        """Auto-generate the 7 Sequence rows for a campaign's 7-touch cadence."""
        from app.models.campaign_models import Sequence as _Seq

        if not prospect_id:
            return []

        created: list[Sequence] = []
        for touch in SEVEN_TOUCH_CADENCE:
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

        return created