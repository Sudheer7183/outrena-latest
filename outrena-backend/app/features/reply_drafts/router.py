# # """
# # reply_drafts.py — Phase 3 /api/v1/reply-drafts router.

# # Endpoints:
# #   GET    /reply-drafts                       list (filter by prospectId / status)
# #   POST   /reply-drafts                       create
# #   GET    /reply-drafts/auto-pilot            list eligible drafts (auto-pilot rule)
# #   GET    /reply-drafts/{id}                  fetch one
# #   PUT    /reply-drafts/{id}                  update (status, draftBody, confidence)
# #   DELETE /reply-drafts/{id}                  delete
# #   POST   /reply-drafts/{id}/reply-categorize LLM-categorize the reply
# #   POST   /reply-drafts/{id}/auto-reply       fire via MailBridge
# # """
# # from __future__ import annotations

# # from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.api.deps import get_db
# # from app.api.security import require_role
# # from app.schemas.auth import Role
# # from app.schemas.reply_drafts import (
# #     AutoPilotEligibleResponse,
# #     AutoReplyRequest,
# #     AutoReplyResponse,
# #     ReplyCategorizeRequest,
# #     ReplyCategorizeResponse,
# #     ReplyDraftCreate,
# #     ReplyDraftResponse,
# #     ReplyDraftUpdate,
# # )
# # from app.features.reply_drafts.service import ReplyDraftService

# # router = APIRouter(prefix="/reply-drafts", tags=["Reply Drafts"])
# # _service = ReplyDraftService()


# # @router.get("/auto-pilot", response_model=AutoPilotEligibleResponse)
# # async def list_autopilot_eligible(
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.MANAGER)),
# # ) -> AutoPilotEligibleResponse:
# #     """
# #     List all reply drafts eligible for auto-pilot send.

# #     Eligibility rule (Phase 3 deliverable):
# #         positive category + confidence >= 0.8 + status == 'approved'
# #     """
# #     return await _service.list_autopilot_eligible(db)


# # @router.get("", response_model=list[ReplyDraftResponse])
# # async def list_reply_drafts(
# #     prospect_id: str | None = Query(default=None),
# #     draft_status: str | None = Query(default=None, alias="status"),
# #     limit: int = Query(default=50, ge=1, le=500),
# #     offset: int = Query(default=0, ge=0),
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> list[ReplyDraftResponse]:
# #     items = await _service.list_drafts(
# #         db, prospect_id=prospect_id, status=draft_status,
# #         limit=limit, offset=offset,
# #     )
# #     return [ReplyDraftResponse.model_validate(d) for d in items]


# # @router.post("", response_model=ReplyDraftResponse, status_code=201)
# # async def create_reply_draft(
# #     body: ReplyDraftCreate,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> ReplyDraftResponse:
# #     item = await _service.create(db, body)
# #     return ReplyDraftResponse.model_validate(item)


# # @router.get("/{draft_id}", response_model=ReplyDraftResponse)
# # async def get_reply_draft(
# #     draft_id: str,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> ReplyDraftResponse:
# #     item = await _service.get(db, draft_id)
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
# #     return ReplyDraftResponse.model_validate(item)


# # @router.put("/{draft_id}", response_model=ReplyDraftResponse)
# # async def update_reply_draft(
# #     draft_id: str,
# #     body: ReplyDraftUpdate,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> ReplyDraftResponse:
# #     item = await _service.update(db, draft_id, body)
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
# #     return ReplyDraftResponse.model_validate(item)


# # @router.delete("/{draft_id}", response_model=None, response_class=Response, status_code=204)
# # async def delete_reply_draft(
# #     draft_id: str,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.MANAGER)),
# # ) -> Response:
# #     ok = await _service.delete(db, draft_id)
# #     if not ok:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
# #     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # @router.post("/{draft_id}/reply-categorize", response_model=ReplyCategorizeResponse)
# # async def categorize_reply(
# #     draft_id: str,
# #     body: ReplyCategorizeRequest,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.REP)),
# # ) -> ReplyCategorizeResponse:
# #     result = await _service.categorize(db, draft_id, body.originalReply)
# #     if result is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
# #     return result


# # @router.post("/{draft_id}/auto-reply", response_model=AutoReplyResponse)
# # async def auto_reply(
# #     draft_id: str,
# #     body: AutoReplyRequest,
# #     db: AsyncSession = Depends(get_db),
# #     _: object = Depends(require_role(Role.MANAGER)),
# # ) -> AutoReplyResponse:
# #     result = await _service.auto_reply(db, draft_id, body.dryRun)
# #     return AutoReplyResponse(
# #         ok=bool(result.get("ok", False)),
# #         message=str(result.get("message", "")),
# #         draftId=result.get("draftId"),
# #         messageId=result.get("messageId"),
# #     )

# """
# reply_drafts.py — Phase 3 /api/v1/reply-drafts router.

# Endpoints:
#   GET    /reply-drafts                       list (filter by prospectId / status)
#   POST   /reply-drafts                       create
#   GET    /reply-drafts/auto-pilot            list eligible drafts (auto-pilot rule)
#   GET    /reply-drafts/{id}                  fetch one
#   PUT    /reply-drafts/{id}                  update (status, draftBody, confidence)
#   DELETE /reply-drafts/{id}                  delete
#   POST   /reply-drafts/{id}/reply-categorize LLM-categorize the reply
#   POST   /reply-drafts/{id}/auto-reply       fire via MailBridge
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.schemas.auth import Role
# from app.schemas.reply_drafts import (
#     AutoPilotEligibleResponse,
#     AutoReplyRequest,
#     AutoReplyResponse,
#     ReplyCategorizeRequest,
#     ReplyCategorizeResponse,
#     ReplyDraftCreate,
#     ReplyDraftResponse,
#     ReplyDraftUpdate,
# )
# from app.features.reply_drafts.service import ReplyDraftService

# router = APIRouter(prefix="/reply-drafts", tags=["Reply Drafts"])
# _service = ReplyDraftService()


# @router.get("/auto-pilot", response_model=AutoPilotEligibleResponse)
# async def list_autopilot_eligible(
#     db: AsyncSession = Depends(get_db),
#     # FIX: Lowered from MANAGER to REP — REPs use the Reply Inbox autopilot
#     # view to see which replies are eligible for auto-send.
#     _: object = Depends(require_role(Role.REP)),
# ) -> AutoPilotEligibleResponse:
#     """
#     List all reply drafts eligible for auto-pilot send.

#     Eligibility rule (Phase 3 deliverable):
#         positive category + confidence >= 0.8 + status == 'approved'
#     """
#     return await _service.list_autopilot_eligible(db)


# @router.get("", response_model=list[ReplyDraftResponse])
# async def list_reply_drafts(
#     prospect_id: str | None = Query(default=None),
#     draft_status: str | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> list[ReplyDraftResponse]:
#     items = await _service.list_drafts(
#         db, prospect_id=prospect_id, status=draft_status,
#         limit=limit, offset=offset,
#     )
#     return [ReplyDraftResponse.model_validate(d) for d in items]


# @router.post("", response_model=ReplyDraftResponse, status_code=201)
# async def create_reply_draft(
#     body: ReplyDraftCreate,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> ReplyDraftResponse:
#     item = await _service.create(db, body)
#     return ReplyDraftResponse.model_validate(item)


# @router.get("/{draft_id}", response_model=ReplyDraftResponse)
# async def get_reply_draft(
#     draft_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> ReplyDraftResponse:
#     item = await _service.get(db, draft_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
#     return ReplyDraftResponse.model_validate(item)


# @router.put("/{draft_id}", response_model=ReplyDraftResponse)
# async def update_reply_draft(
#     draft_id: str,
#     body: ReplyDraftUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> ReplyDraftResponse:
#     item = await _service.update(db, draft_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
#     return ReplyDraftResponse.model_validate(item)


# @router.delete("/{draft_id}", response_model=None, response_class=Response, status_code=204)
# async def delete_reply_draft(
#     draft_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.delete(db, draft_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post("/{draft_id}/reply-categorize", response_model=ReplyCategorizeResponse)
# async def categorize_reply(
#     draft_id: str,
#     body: ReplyCategorizeRequest,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.REP)),
# ) -> ReplyCategorizeResponse:
#     result = await _service.categorize(db, draft_id, body.originalReply)
#     if result is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
#     return result


# @router.post("/{draft_id}/auto-reply", response_model=AutoReplyResponse)
# async def auto_reply(
#     draft_id: str,
#     body: AutoReplyRequest,
#     db: AsyncSession = Depends(get_db),
#     _: object = Depends(require_role(Role.MANAGER)),
# ) -> AutoReplyResponse:
#     result = await _service.auto_reply(db, draft_id, body.dryRun)
#     return AutoReplyResponse(
#         ok=bool(result.get("ok", False)),
#         message=str(result.get("message", "")),
#         draftId=result.get("draftId"),
#         messageId=result.get("messageId"),
#     )

"""
reply_drafts.py — Phase 3 /api/v1/reply-drafts router.

Endpoints:
  GET    /reply-drafts                       list (filter by prospectId / status)
  POST   /reply-drafts                       create
  GET    /reply-drafts/auto-pilot            list eligible drafts (auto-pilot rule)
  GET    /reply-drafts/{id}                  fetch one
  PUT    /reply-drafts/{id}                  update (status, draftBody, confidence)
  DELETE /reply-drafts/{id}                  delete
  POST   /reply-drafts/{id}/reply-categorize LLM-categorize the reply
  POST   /reply-drafts/{id}/auto-reply       fire via MailBridge
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.models.campaign_models import ReplyDraft, Sequence
from app.models.prospect_models import Prospect
from app.schemas.auth import Role
from app.schemas.reply_drafts import (
    AutoPilotEligibleResponse,
    AutoReplyRequest,
    AutoReplyResponse,
    ReplyCategorizeRequest,
    ReplyCategorizeResponse,
    ReplyDraftCreate,
    ReplyDraftResponse,
    ReplyDraftUpdate,
)
from app.features.reply_drafts.service import ReplyDraftService

router = APIRouter(prefix="/reply-drafts", tags=["Reply Drafts"])
_service = ReplyDraftService()


async def _enrich(db: AsyncSession, draft: ReplyDraft) -> ReplyDraftResponse:
    """Build a ReplyDraftResponse with prospect name + sent email fields joined in.

    Fetches the linked Sequence (for subjectLine / bodyCopy) and Prospect
    (for firstName / lastName / email) in two lightweight point-lookups.
    Falls back gracefully to None for any field that cannot be resolved so
    a missing row never breaks the list endpoint.
    """
    resp = ReplyDraftResponse.model_validate(draft)

    # ── Sequence (sent email content) ────────────────────────────────────────
    try:
        seq_result = await db.execute(
            select(Sequence).where(Sequence.id == draft.sequenceId)
        )
        seq = seq_result.scalar_one_or_none()
        if seq is not None:
            resp.sentEmailSubject = seq.subjectLine or None
            resp.sentEmailBody = seq.bodyCopy or None
    except Exception:  # noqa: BLE001
        pass  # leave sentEmailSubject / sentEmailBody as None

    # ── Prospect (display name + email) ─────────────────────────────────────
    try:
        pro_result = await db.execute(
            select(Prospect).where(Prospect.id == draft.prospectId)
        )
        pro = pro_result.scalar_one_or_none()
        if pro is not None:
            resp.prospectName = f"{pro.firstName} {pro.lastName}".strip() or None
            # Decrypt PII if needed — mirror what ReplyDraftService.auto_reply does.
            raw_email: str = getattr(pro, "email", None) or ""
            if raw_email and not getattr(pro, "anonymized", False):
                try:
                    from app.services.pii_service import PiiService
                    resp.prospectEmail = PiiService().decrypt_field(raw_email) or None
                except Exception:  # noqa: BLE001
                    resp.prospectEmail = raw_email or None
            elif raw_email:
                resp.prospectEmail = raw_email
    except Exception:  # noqa: BLE001
        pass  # leave prospectName / prospectEmail as None

    return resp


@router.get("/auto-pilot", response_model=AutoPilotEligibleResponse)
async def list_autopilot_eligible(
    db: AsyncSession = Depends(get_db),
    # FIX: Lowered from MANAGER to REP — REPs use the Reply Inbox autopilot
    # view to see which replies are eligible for auto-send.
    _: object = Depends(require_role(Role.REP)),
) -> AutoPilotEligibleResponse:
    """
    List all reply drafts eligible for auto-pilot send.

    Eligibility rule (Phase 3 deliverable):
        positive category + confidence >= 0.8 + status == 'approved'
    """
    raw = await _service.list_autopilot_eligible(db)
    enriched = [await _enrich(db, d) for d in raw.eligible]  # type: ignore[attr-defined]
    return AutoPilotEligibleResponse(eligible=enriched, count=raw.count)


@router.get("", response_model=list[ReplyDraftResponse])
async def list_reply_drafts(
    prospect_id: str | None = Query(default=None),
    draft_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[ReplyDraftResponse]:
    items = await _service.list_drafts(
        db, prospect_id=prospect_id, status=draft_status,
        limit=limit, offset=offset,
    )
    # Enrich each draft with prospect name + sent-email content from the Sequence row.
    return [await _enrich(db, d) for d in items]


@router.post("", response_model=ReplyDraftResponse, status_code=201)
async def create_reply_draft(
    body: ReplyDraftCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ReplyDraftResponse:
    item = await _service.create(db, body)
    return await _enrich(db, item)


@router.get("/{draft_id}", response_model=ReplyDraftResponse)
async def get_reply_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ReplyDraftResponse:
    item = await _service.get(db, draft_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
    return await _enrich(db, item)


@router.put("/{draft_id}", response_model=ReplyDraftResponse)
async def update_reply_draft(
    draft_id: str,
    body: ReplyDraftUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ReplyDraftResponse:
    item = await _service.update(db, draft_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
    return await _enrich(db, item)


@router.delete("/{draft_id}", response_model=None, response_class=Response, status_code=204)
async def delete_reply_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, draft_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{draft_id}/reply-categorize", response_model=ReplyCategorizeResponse)
async def categorize_reply(
    draft_id: str,
    body: ReplyCategorizeRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ReplyCategorizeResponse:
    result = await _service.categorize(db, draft_id, body.originalReply)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply draft not found.")
    return result


@router.post("/{draft_id}/auto-reply", response_model=AutoReplyResponse)
async def auto_reply(
    draft_id: str,
    body: AutoReplyRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> AutoReplyResponse:
    result = await _service.auto_reply(db, draft_id, body.dryRun)
    return AutoReplyResponse(
        ok=bool(result.get("ok", False)),
        message=str(result.get("message", "")),
        draftId=result.get("draftId"),
        messageId=result.get("messageId"),
    )
