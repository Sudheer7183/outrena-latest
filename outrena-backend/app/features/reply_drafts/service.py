# """
# reply_draft_service.py — Reply-draft CRUD + categorize + auto-pilot eligibility.

# Auto-pilot eligibility rule (Phase 3 deliverable):
#     positive category + confidence >= 0.8 + status == 'approved'
# """
# from __future__ import annotations

# import json
# from typing import Any

# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.campaign_models import ReplyDraft, Sequence
# from app.models.prospect_models import Prospect
# from app.schemas.reply_drafts import (
#     AutoPilotEligibleResponse,
#     ReplyCategorizeResponse,
#     ReplyDraftCreate,
#     ReplyDraftUpdate,
# )
# from app.services.llm_service import get_llm_service
# from app.features.mailbridge.service import MailBridgeService

# logger = structlog.get_logger(__name__)

# # Categories considered "positive" for auto-pilot eligibility.
# POSITIVE_CATEGORIES: frozenset[str] = frozenset(
#     {"interested", "meeting_request", "demo_request", "positive_reply"}
# )

# # Auto-pilot thresholds (Phase 3 deliverable).
# AUTOPILOT_MIN_CONFIDENCE: float = 0.8
# AUTOPILOT_REQUIRED_STATUS: str = "approved"


# class ReplyDraftService:
#     """CRUD + LLM categorization + auto-pilot eligibility for reply drafts."""

#     def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
#         self._mailbridge = mailbridge or MailBridgeService()

#     async def list_drafts(
#         self,
#         db: AsyncSession,
#         *,
#         prospect_id: str | None = None,
#         status: str | None = None,
#         limit: int = 50,
#         offset: int = 0,
#     ) -> list[ReplyDraft]:
#         stmt = select(ReplyDraft).offset(offset).limit(limit)
#         if prospect_id:
#             stmt = stmt.where(ReplyDraft.prospectId == prospect_id)
#         if status:
#             stmt = stmt.where(ReplyDraft.status == status)
#         result = await db.execute(stmt)
#         return list(result.scalars().all())

#     async def get(self, db: AsyncSession, draft_id: str) -> ReplyDraft | None:
#         result = await db.execute(
#             select(ReplyDraft).where(ReplyDraft.id == draft_id)
#         )
#         return result.scalar_one_or_none()

#     async def create(
#         self, db: AsyncSession, body: ReplyDraftCreate
#     ) -> ReplyDraft:
#         draft = ReplyDraft(
#             sequenceId=body.sequenceId,
#             prospectId=body.prospectId,
#             originalReply=body.originalReply,
#             category=body.category,
#             status="pending",
#         )
#         db.add(draft)
#         await db.commit()
#         draft = await db.get(ReplyDraft, draft.id)
#         return draft

#     async def update(
#         self, db: AsyncSession, draft_id: str, body: ReplyDraftUpdate
#     ) -> ReplyDraft | None:
#         draft = await self.get(db, draft_id)
#         if draft is None:
#             return None
#         data = body.model_dump(exclude_unset=True)
#         for key, value in data.items():
#             setattr(draft, key, value)
#         await db.commit()
#         draft = await db.get(ReplyDraft, draft.id)
#         return draft

#     async def delete(self, db: AsyncSession, draft_id: str) -> bool:
#         draft = await self.get(db, draft_id)
#         if draft is None:
#             return False
#         await db.delete(draft)
#         await db.commit()
#         return True

#     async def categorize(
#         self, db: AsyncSession, draft_id: str, original_reply: str
#     ) -> ReplyCategorizeResponse | None:
#         """LLM-categorize a reply (positive/negative/OOO/etc.)."""
#         draft = await self.get(db, draft_id)
#         if draft is None:
#             return None
#         llm = get_llm_service()
#         prompt = (
#             "Categorize the following prospect reply into exactly one of: "
#             "interested, meeting_request, demo_request, positive_reply, "
#             "negative_reply, not_interested, ooo, unsubscribe, other. "
#             "Also provide a one-sentence summary and a suggested next action.\n\n"
#             f"Reply: {original_reply[:1000]}\n\n"
#             'Respond as JSON: {"category":"...","summary":"...","suggestedAction":"...","confidence":0.0}'
#         )
#         data = await llm.generate_json(prompt=prompt, system="You are a sales assistant.")
#         category = str(data.get("category", "other"))
#         summary = str(data.get("summary", ""))
#         suggested_action = str(data.get("suggestedAction", ""))
#         confidence = float(data.get("confidence", 0.5))
#         draft.category = category
#         draft.summary = summary
#         draft.suggestedAction = suggested_action
#         draft.confidence = confidence
#         # Auto-mark eligibility if all conditions met
#         draft.autoPilotEligible = self._is_autopilot_eligible(category, confidence, draft.status)
#         await db.commit()
#         return ReplyCategorizeResponse(
#             category=category,
#             summary=summary,
#             suggestedAction=suggested_action,
#             confidence=confidence,
#         )

#     async def auto_reply(
#         self, db: AsyncSession, draft_id: str, dry_run: bool = False
#     ) -> dict[str, Any]:
#         """Fire a reply draft via MailBridge. Returns status dict.

#         Wiring audit (Task 2-e): previously this method passed ``to=""`` to
#         ``MailBridgeService.send`` with a comment saying "caller resolves
#         prospect.email" — but no caller actually did so. The result was an
#         empty-envelope send that the MailBridge stub accepted (returning
#         ``stub-…`` messageId) but real SMTP relays reject. This now resolves
#         the recipient email from the linked Prospect (with PII decryption,
#         mirroring ``SequenceService.send_email``) so the auto-reply actually
#         reaches the prospect who replied.
#         """
#         draft = await self.get(db, draft_id)
#         if draft is None:
#             return {"ok": False, "message": "Reply draft not found"}
#         if not draft.draftBody:
#             return {"ok": False, "message": "Reply draft has no body"}
#         if dry_run:
#             return {"ok": True, "message": "Dry-run: would send", "draftId": draft.id}

#         # Resolve the recipient's email from the linked Prospect row.
#         # PII is encrypted at rest — decrypt via PiiService before sending.
#         to_email = ""
#         prospect_id = getattr(draft, "prospectId", None)
#         if prospect_id:
#             prospect_result = await db.execute(
#                 select(Prospect).where(Prospect.id == prospect_id)
#             )
#             prospect = prospect_result.scalar_one_or_none()
#             if prospect is not None:
#                 raw_email = getattr(prospect, "email", None) or ""
#                 if raw_email and not getattr(prospect, "anonymized", False):
#                     try:
#                         from app.services.pii_service import PiiService

#                         to_email = PiiService().decrypt_field(raw_email) or ""
#                     except Exception as exc:  # noqa: BLE001 — best-effort
#                         logger.warning(
#                             "reply_draft.auto_reply.email_decrypt_failed",
#                             prospect_id=prospect_id,
#                             error=str(exc),
#                         )
#                         to_email = raw_email
#                 elif raw_email:
#                     to_email = raw_email

#         if not to_email:
#             return {
#                 "ok": False,
#                 "message": "Prospect email is missing — cannot send auto-reply.",
#             }

#         # Determine the owner of the underlying sequence so the per-user
#         # MailBridge config + quota are honoured (mirrors SequenceService).
#         owner_user_id: str | None = None
#         try:
#             seq_result = await db.execute(
#                 select(Sequence).where(Sequence.id == draft.sequenceId)
#             )
#             seq = seq_result.scalar_one_or_none()
#             if seq is not None:
#                 owner_user_id = getattr(seq, "owner_user_id", None)
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "reply_draft.auto_reply.sequence_lookup_failed",
#                 sequence_id=draft.sequenceId,
#                 error=str(exc),
#             )

#         result = await self._mailbridge.send(
#             db=db,
#             to=to_email,
#             subject="Re: your reply",
#             body=draft.draftBody or "",
#             sequence_id=draft.sequenceId,
#             user_id=owner_user_id,
#         )
#         if result.accepted:
#             draft.status = "sent"
#             draft.sentAt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
#             await db.commit()
#             return {"ok": True, "message": "Sent", "messageId": result.messageId}
#         return {"ok": False, "message": "Send failed"}

#     async def list_autopilot_eligible(
#         self, db: AsyncSession
#     ) -> AutoPilotEligibleResponse:
#         """
#         Return all reply drafts eligible for auto-pilot send.

#         Eligibility rule (Phase 3 deliverable):
#             positive category + confidence >= 0.8 + status == 'approved'
#         """
#         result = await db.execute(select(ReplyDraft))
#         all_drafts = list(result.scalars().all())
#         eligible = [
#             d for d in all_drafts
#             if d.autoPilotEligible
#             and d.category in POSITIVE_CATEGORIES
#             and (d.confidence or 0.0) >= AUTOPILOT_MIN_CONFIDENCE
#             and d.status == AUTOPILOT_REQUIRED_STATUS
#         ]
#         return AutoPilotEligibleResponse(eligible=eligible, count=len(eligible))

#     @staticmethod
#     def _is_autopilot_eligible(category: str, confidence: float, status: str) -> bool:
#         """Check the auto-pilot eligibility rule."""
#         return (
#             category in POSITIVE_CATEGORIES
#             and confidence >= AUTOPILOT_MIN_CONFIDENCE
#             and status == AUTOPILOT_REQUIRED_STATUS
#         )

"""
reply_draft_service.py — Reply-draft CRUD + categorize + auto-pilot eligibility.

FIX: Removed all post-commit db.get(ReplyDraft, draft.id) calls in create()
and update(). After db.commit() on a schema-per-tenant asyncpg session, the
connection is re-pooled and loses search_path — the subsequent db.get() raises
`relation "ReplyDraft" does not exist`. Both methods now return the in-memory
ORM object directly (safe because eager_defaults=True on Base populates
server-generated columns via RETURNING at INSERT time).

Auto-pilot eligibility rule (Phase 3 deliverable):
    positive category + confidence >= 0.8 + status == 'approved'
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import ReplyDraft, Sequence
from app.models.prospect_models import Prospect
from app.schemas.reply_drafts import (
    AutoPilotEligibleResponse,
    ReplyCategorizeResponse,
    ReplyDraftCreate,
    ReplyDraftUpdate,
)
from app.services.llm_service import get_llm_service
from app.features.mailbridge.service import MailBridgeService

logger = structlog.get_logger(__name__)

POSITIVE_CATEGORIES: frozenset[str] = frozenset(
    {"interested", "meeting_request", "demo_request", "positive_reply"}
)
AUTOPILOT_MIN_CONFIDENCE: float = 0.8
AUTOPILOT_REQUIRED_STATUS: str = "approved"


class ReplyDraftService:
    """CRUD + LLM categorization + auto-pilot eligibility for reply drafts."""

    def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
        self._mailbridge = mailbridge or MailBridgeService()

    async def list_drafts(
        self,
        db: AsyncSession,
        *,
        prospect_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReplyDraft]:
        stmt = select(ReplyDraft).offset(offset).limit(limit)
        if prospect_id:
            stmt = stmt.where(ReplyDraft.prospectId == prospect_id)
        if status:
            stmt = stmt.where(ReplyDraft.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, draft_id: str) -> ReplyDraft | None:
        result = await db.execute(
            select(ReplyDraft).where(ReplyDraft.id == draft_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: ReplyDraftCreate
    ) -> ReplyDraft:
        """Create a reply draft.

        FIX: Removed post-commit db.get(ReplyDraft, draft.id).
        eager_defaults=True on Base populates id/createdAt/updatedAt via
        RETURNING at INSERT time — no second SELECT needed, and no
        search_path loss from re-fetching after commit.
        """
        draft = ReplyDraft(
            sequenceId=body.sequenceId,
            prospectId=body.prospectId,
            originalReply=body.originalReply,
            category=body.category,
            status="pending",
        )
        db.add(draft)
        await db.commit()
        # Do NOT call db.get() — connection loses search_path after commit.
        # The in-memory draft object has all fields via RETURNING.
        return draft

    async def update(
        self, db: AsyncSession, draft_id: str, body: ReplyDraftUpdate
    ) -> ReplyDraft | None:
        """Update a reply draft.

        FIX: Removed post-commit db.get(ReplyDraft, draft.id).
        Mutations are applied in-memory before commit and remain valid
        on the in-memory object after commit.
        """
        draft = await self.get(db, draft_id)
        if draft is None:
            return None
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(draft, key, value)
        await db.commit()
        # Do NOT call db.get() — return the in-memory object.
        return draft

    async def delete(self, db: AsyncSession, draft_id: str) -> bool:
        draft = await self.get(db, draft_id)
        if draft is None:
            return False
        await db.delete(draft)
        await db.commit()
        return True

    async def categorize(
        self, db: AsyncSession, draft_id: str, original_reply: str
    ) -> ReplyCategorizeResponse | None:
        """LLM-categorize a reply (positive/negative/OOO/etc.)."""
        draft = await self.get(db, draft_id)
        if draft is None:
            return None
        llm = get_llm_service()
        prompt = (
            "Categorize the following prospect reply into exactly one of: "
            "interested, meeting_request, demo_request, positive_reply, "
            "negative_reply, not_interested, ooo, unsubscribe, other. "
            "Also provide a one-sentence summary and a suggested next action.\n\n"
            f"Reply: {original_reply[:1000]}\n\n"
            'Respond as JSON: {"category":"...","summary":"...","suggestedAction":"...","confidence":0.0}'
        )
        data = await llm.generate_json(prompt=prompt, system="You are a sales assistant.")
        category = str(data.get("category", "other"))
        summary = str(data.get("summary", ""))
        suggested_action = str(data.get("suggestedAction", ""))
        confidence = float(data.get("confidence", 0.5))
        draft.category = category
        draft.summary = summary
        draft.suggestedAction = suggested_action
        draft.confidence = confidence
        draft.autoPilotEligible = self._is_autopilot_eligible(category, confidence, draft.status)
        await db.commit()
        return ReplyCategorizeResponse(
            category=category,
            summary=summary,
            suggestedAction=suggested_action,
            confidence=confidence,
        )

    async def auto_reply(
        self, db: AsyncSession, draft_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Fire a reply draft via MailBridge."""
        draft = await self.get(db, draft_id)
        if draft is None:
            return {"ok": False, "message": "Reply draft not found"}
        if not draft.draftBody:
            return {"ok": False, "message": "Reply draft has no body"}
        if dry_run:
            return {"ok": True, "message": "Dry-run: would send", "draftId": draft.id}

        to_email = ""
        prospect_id = getattr(draft, "prospectId", None)
        if prospect_id:
            prospect_result = await db.execute(
                select(Prospect).where(Prospect.id == prospect_id)
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
                            "reply_draft.auto_reply.email_decrypt_failed",
                            prospect_id=prospect_id,
                            error=str(exc),
                        )
                        to_email = raw_email
                elif raw_email:
                    to_email = raw_email

        if not to_email:
            return {
                "ok": False,
                "message": "Prospect email is missing — cannot send auto-reply.",
            }

        owner_user_id: str | None = None
        try:
            seq_result = await db.execute(
                select(Sequence).where(Sequence.id == draft.sequenceId)
            )
            seq = seq_result.scalar_one_or_none()
            if seq is not None:
                owner_user_id = getattr(seq, "owner_user_id", None)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reply_draft.auto_reply.sequence_lookup_failed",
                sequence_id=draft.sequenceId,
                error=str(exc),
            )

        result = await self._mailbridge.send(
            db=db,
            to=to_email,
            subject="Re: your reply",
            body=draft.draftBody or "",
            sequence_id=draft.sequenceId,
            user_id=owner_user_id,
        )
        if result.accepted:
            draft.status = "sent"
            draft.sentAt = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            )
            await db.commit()
            return {"ok": True, "message": "Sent", "messageId": result.messageId}
        return {"ok": False, "message": "Send failed"}

    async def list_autopilot_eligible(
        self, db: AsyncSession
    ) -> AutoPilotEligibleResponse:
        """Return all reply drafts eligible for auto-pilot send."""
        result = await db.execute(select(ReplyDraft))
        all_drafts = list(result.scalars().all())
        eligible = [
            d for d in all_drafts
            if d.autoPilotEligible
            and d.category in POSITIVE_CATEGORIES
            and (d.confidence or 0.0) >= AUTOPILOT_MIN_CONFIDENCE
            and d.status == AUTOPILOT_REQUIRED_STATUS
        ]
        return AutoPilotEligibleResponse(eligible=eligible, count=len(eligible))

    @staticmethod
    def _is_autopilot_eligible(category: str, confidence: float, status: str) -> bool:
        return (
            category in POSITIVE_CATEGORIES
            and confidence >= AUTOPILOT_MIN_CONFIDENCE
            and status == AUTOPILOT_REQUIRED_STATUS
        )