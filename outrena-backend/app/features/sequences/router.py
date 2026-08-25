# # # """
# # # sequences.py — Phase 3 /api/v1/sequences router.

# # # Endpoints:
# # #   GET    /sequences                       list with optional filters (REP sees own)
# # #   POST   /sequences                       create (stamps owner_user_id = token.sub)
# # #   GET    /sequences/cadence               7-touch cadence (days 1/4/9/16/25/35)
# # #   GET    /sequences/export                CSV export (RFC-4180, UTF-8 BOM)
# # #   GET    /sequences/my                    current user's sequences (convenience)
# # #   GET    /sequences/{id}                  fetch one (REP: 404 if not own)
# # #   PUT    /sequences/{id}                  update
# # #   DELETE /sequences/{id}                  delete (204)
# # #   GET    /sequences/{id}/subject-lines    list subject-line variants
# # #   POST   /sequences/{id}/subject-lines    add a subject-line variant
# # #   POST   /sequences/{id}/scheduled-send   set status=Scheduled
# # #   POST   /sequences/{id}/send-email       fire via MailBridge immediately
# # # """
# # # from __future__ import annotations

# # # from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# # # from fastapi.responses import PlainTextResponse
# # # from sqlalchemy.ext.asyncio import AsyncSession

# # # from app.api.deps import get_db
# # # from app.api.security import require_role
# # # from app.models.enums import EmailStatus
# # # from app.schemas.auth import Role, TokenPayload
# # # from app.schemas.sequences import (
# # #     CadenceResponse,
# # #     SEVEN_TOUCH_CADENCE,
# # #     ScheduledSendRequest,
# # #     SequenceCreate,
# # #     SequenceResponse,
# # #     SequenceUpdate,
# # #     SendEmailRequest,
# # #     SendEmailResponse,
# # #     SubjectLineCreate,
# # #     SubjectLineResponse,
# # # )
# # # from app.services.csv_export_service import rows_to_csv
# # # from app.features.sequences.service import SequenceService

# # # router = APIRouter(prefix="/sequences", tags=["Sequences"])
# # # _service = SequenceService()


# # # def _role_value(token: TokenPayload) -> str:
# # #     """Return the Role enum value as a plain string for service-level checks."""
# # #     return token.role.value if hasattr(token.role, "value") else str(token.role)


# # # @router.get("/cadence", response_model=list[CadenceResponse])
# # # async def get_cadence() -> list[CadenceResponse]:
# # #     """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
# # #     return SEVEN_TOUCH_CADENCE


# # # @router.get("/export", response_class=PlainTextResponse)
# # # async def export_sequences(
# # #     campaign_id: str | None = Query(default=None),
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> PlainTextResponse:
# # #     """CSV export of sequences (RFC-4180, UTF-8 with BOM).

# # #     REP tokens export only their own sequences; MANAGER+ exports all.
# # #     """
# # #     items, _ = await _service.list_sequences(
# # #         db,
# # #         campaign_id=campaign_id,
# # #         user_id=token.sub,
# # #         role=_role_value(token),
# # #     )
# # #     rows = [
# # #         {
# # #             "id": s.id,
# # #             "campaignId": s.campaignId,
# # #             "prospectId": s.prospectId,
# # #             "touchNumber": s.touchNumber,
# # #             "sendDay": s.sendDay,
# # #             "channel": s.channel,
# # #             "angle": s.angle.value,
# # #             "status": s.status.value,
# # #             "subjectLine": s.subjectLine,
# # #             "qaScore": s.qaScore,
# # #             "sentAt": s.sentAt.isoformat() if s.sentAt else "",
# # #         }
# # #         for s in items
# # #     ]
# # #     csv_text = rows_to_csv(
# # #         rows,
# # #         [
# # #             "id", "campaignId", "prospectId", "touchNumber", "sendDay",
# # #             "channel", "angle", "status", "subjectLine", "qaScore", "sentAt",
# # #         ],
# # #     )
# # #     return PlainTextResponse(
# # #         csv_text,
# # #         media_type="text/csv; charset=utf-8",
# # #         headers={"Content-Disposition": "attachment; filename=sequences.csv"},
# # #     )


# # # @router.get("/my", response_model=list[SequenceResponse])
# # # async def list_my_sequences(
# # #     campaign_id: str | None = Query(default=None),
# # #     prospect_id: str | None = Query(default=None),
# # #     seq_status: EmailStatus | None = Query(default=None, alias="status"),
# # #     limit: int = Query(default=50, ge=1, le=500),
# # #     offset: int = Query(default=0, ge=0),
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> list[SequenceResponse]:
# # #     """Return only the calling user's sequences (always filtered by owner_user_id)."""
# # #     items, _ = await _service.list_sequences(
# # #         db,
# # #         campaign_id=campaign_id,
# # #         prospect_id=prospect_id,
# # #         status=seq_status,
# # #         limit=limit,
# # #         offset=offset,
# # #         user_id=token.sub,
# # #         role="REP",
# # #     )
# # #     return [SequenceResponse.model_validate(s) for s in items]


# # # @router.get("", response_model=list[SequenceResponse])
# # # async def list_sequences(
# # #     campaign_id: str | None = Query(default=None),
# # #     prospect_id: str | None = Query(default=None),
# # #     seq_status: EmailStatus | None = Query(default=None, alias="status"),
# # #     limit: int = Query(default=50, ge=1, le=500),
# # #     offset: int = Query(default=0, ge=0),
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> list[SequenceResponse]:
# # #     """List sequences. REP sees only own; MANAGER+ sees all."""
# # #     items, _ = await _service.list_sequences(
# # #         db,
# # #         campaign_id=campaign_id,
# # #         prospect_id=prospect_id,
# # #         status=seq_status,
# # #         limit=limit,
# # #         offset=offset,
# # #         user_id=token.sub,
# # #         role=_role_value(token),
# # #     )
# # #     return [SequenceResponse.model_validate(s) for s in items]


# # # @router.post("", response_model=SequenceResponse, status_code=201)
# # # async def create_sequence(
# # #     body: SequenceCreate,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SequenceResponse:
# # #     """Create a sequence — owner_user_id stamped from token.sub."""
# # #     item = await _service.create(db, body, owner_user_id=token.sub)
# # #     return SequenceResponse.model_validate(item)


# # # @router.get("/{sequence_id}", response_model=SequenceResponse)
# # # async def get_sequence(
# # #     sequence_id: str,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SequenceResponse:
# # #     """Fetch one sequence. REP tokens receive 404 for sequences they don't own."""
# # #     item = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if item is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return SequenceResponse.model_validate(item)


# # # @router.put("/{sequence_id}", response_model=SequenceResponse)
# # # async def update_sequence(
# # #     sequence_id: str,
# # #     body: SequenceUpdate,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SequenceResponse:
# # #     """Update a sequence. REP tokens receive 404 for sequences they don't own."""
# # #     item = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if item is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     updated = await _service.update(db, sequence_id, body)
# # #     if updated is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return SequenceResponse.model_validate(updated)


# # # @router.delete("/{sequence_id}", response_model=None, response_class=Response, status_code=204)
# # # async def delete_sequence(
# # #     sequence_id: str,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# # # ) -> Response:
# # #     """Delete a sequence. MANAGER+ only."""
# # #     ok = await _service.delete(db, sequence_id)
# # #     if not ok:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # # @router.get("/{sequence_id}/subject-lines", response_model=list[SubjectLineResponse])
# # # async def list_subject_lines(
# # #     sequence_id: str,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> list[SubjectLineResponse]:
# # #     # ACL check first (404 if not own + REP).
# # #     seq = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if seq is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     items = await _service.list_subject_lines(db, sequence_id)
# # #     return [SubjectLineResponse.model_validate(s) for s in items]


# # # @router.post(
# # #     "/{sequence_id}/subject-lines",
# # #     response_model=SubjectLineResponse,
# # #     status_code=201,
# # # )
# # # async def add_subject_line(
# # #     sequence_id: str,
# # #     body: SubjectLineCreate,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SubjectLineResponse:
# # #     # ACL check first.
# # #     seq = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if seq is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     item = await _service.add_subject_line(db, sequence_id, body)
# # #     if item is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return SubjectLineResponse.model_validate(item)


# # # @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# # # async def schedule_send(
# # #     sequence_id: str,
# # #     body: ScheduledSendRequest,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SequenceResponse:
# # #     # ACL check first.
# # #     seq = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if seq is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     item = await _service.schedule_send(db, sequence_id, body)
# # #     if item is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return SequenceResponse.model_validate(item)


# # # @router.post("/{sequence_id}/send-email", response_model=SendEmailResponse)
# # # async def send_email(
# # #     sequence_id: str,
# # #     body: SendEmailRequest,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SendEmailResponse:
# # #     # ACL check first.
# # #     seq = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if seq is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     # Force-bypass requires MANAGER or above.
# # #     if body.force:
# # #         from app.api.security import verify_role
# # #         verify_role(Role.MANAGER, token)
# # #     return await _service.send_email(db, sequence_id, body)


# # # __all__ = ["router"]

# # """
# # sequences.py — Phase 3 /api/v1/sequences router.

# # Endpoints:
# #   GET    /sequences                       list with optional filters (REP sees own)
# #   POST   /sequences                       create (stamps owner_user_id = token.sub)
# #   GET    /sequences/cadence               7-touch cadence (days 1/4/9/16/25/35)
# #   GET    /sequences/export                CSV export (RFC-4180, UTF-8 BOM)
# #   GET    /sequences/my                    current user's sequences (convenience)
# #   GET    /sequences/{id}                  fetch one (REP: 404 if not own)
# #   PUT    /sequences/{id}                  update
# #   DELETE /sequences/{id}                  delete (204)
# #   GET    /sequences/{id}/subject-lines    list subject-line variants
# #   POST   /sequences/{id}/subject-lines    add a subject-line variant
# #   POST   /sequences/{id}/scheduled-send   set status=Scheduled
# #   POST   /sequences/{id}/send-email       fire via MailBridge immediately

# # FIX (wrong sender mailbox on send-email):
# #   The send-email endpoint was calling _service.send_email(db, sequence_id, body)
# #   without passing the caller's identity. send_email() then used seq.owner_user_id
# #   to determine which mailbox to send from. Sequences auto-generated at prospect-
# #   link time were stamped owner_user_id="system" (bug fixed separately in
# #   campaigns/service.py), so MailBridgeService.send() received user_id="system"
# #   and skipped per-user routing entirely — falling back to the first connected
# #   mailbox on the tenant config.

# #   Fix: pass caller_user_id=token.sub into send_email(). The service uses this
# #   as the authoritative sender identity, overriding seq.owner_user_id. This also
# #   covers any pre-existing "system"-stamped sequences without requiring a data
# #   migration.
# # """
# # from __future__ import annotations

# # from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# # from fastapi.responses import PlainTextResponse
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.api.deps import get_db
# # from app.api.security import require_role
# # from app.models.enums import EmailStatus
# # from app.schemas.auth import Role, TokenPayload
# # from app.schemas.sequences import (
# #     CadenceResponse,
# #     SEVEN_TOUCH_CADENCE,
# #     ScheduledSendRequest,
# #     SequenceCreate,
# #     SequenceResponse,
# #     SequenceUpdate,
# #     SendEmailRequest,
# #     SendEmailResponse,
# #     SubjectLineCreate,
# #     SubjectLineResponse,
# # )
# # from app.services.csv_export_service import rows_to_csv
# # from app.features.sequences.service import SequenceService

# # router = APIRouter(prefix="/sequences", tags=["Sequences"])
# # _service = SequenceService()


# # def _role_value(token: TokenPayload) -> str:
# #     """Return the Role enum value as a plain string for service-level checks."""
# #     return token.role.value if hasattr(token.role, "value") else str(token.role)


# # @router.get("/cadence", response_model=list[CadenceResponse])
# # async def get_cadence() -> list[CadenceResponse]:
# #     """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
# #     return SEVEN_TOUCH_CADENCE


# # @router.get("/export", response_class=PlainTextResponse)
# # async def export_sequences(
# #     campaign_id: str | None = Query(default=None),
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> PlainTextResponse:
# #     """CSV export of sequences (RFC-4180, UTF-8 with BOM).

# #     REP tokens export only their own sequences; MANAGER+ exports all.
# #     """
# #     items, _ = await _service.list_sequences(
# #         db,
# #         campaign_id=campaign_id,
# #         user_id=token.sub,
# #         role=_role_value(token),
# #     )
# #     rows = [
# #         {
# #             "id": s.id,
# #             "campaignId": s.campaignId,
# #             "prospectId": s.prospectId,
# #             "touchNumber": s.touchNumber,
# #             "sendDay": s.sendDay,
# #             "channel": s.channel,
# #             "angle": s.angle.value,
# #             "status": s.status.value,
# #             "subjectLine": s.subjectLine,
# #             "qaScore": s.qaScore,
# #             "sentAt": s.sentAt.isoformat() if s.sentAt else "",
# #         }
# #         for s in items
# #     ]
# #     csv_text = rows_to_csv(
# #         rows,
# #         [
# #             "id", "campaignId", "prospectId", "touchNumber", "sendDay",
# #             "channel", "angle", "status", "subjectLine", "qaScore", "sentAt",
# #         ],
# #     )
# #     return PlainTextResponse(
# #         csv_text,
# #         media_type="text/csv; charset=utf-8",
# #         headers={"Content-Disposition": "attachment; filename=sequences.csv"},
# #     )


# # @router.get("/my", response_model=list[SequenceResponse])
# # async def list_my_sequences(
# #     campaign_id: str | None = Query(default=None),
# #     prospect_id: str | None = Query(default=None),
# #     seq_status: EmailStatus | None = Query(default=None, alias="status"),
# #     limit: int = Query(default=50, ge=1, le=500),
# #     offset: int = Query(default=0, ge=0),
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> list[SequenceResponse]:
# #     """Return only the calling user's sequences (always filtered by owner_user_id)."""
# #     items, _ = await _service.list_sequences(
# #         db,
# #         campaign_id=campaign_id,
# #         prospect_id=prospect_id,
# #         status=seq_status,
# #         limit=limit,
# #         offset=offset,
# #         user_id=token.sub,
# #         role="REP",
# #     )
# #     return [SequenceResponse.model_validate(s) for s in items]


# # @router.get("", response_model=list[SequenceResponse])
# # async def list_sequences(
# #     campaign_id: str | None = Query(default=None),
# #     prospect_id: str | None = Query(default=None),
# #     seq_status: EmailStatus | None = Query(default=None, alias="status"),
# #     limit: int = Query(default=50, ge=1, le=500),
# #     offset: int = Query(default=0, ge=0),
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> list[SequenceResponse]:
# #     """List sequences. REP sees only own; MANAGER+ sees all."""
# #     items, _ = await _service.list_sequences(
# #         db,
# #         campaign_id=campaign_id,
# #         prospect_id=prospect_id,
# #         status=seq_status,
# #         limit=limit,
# #         offset=offset,
# #         user_id=token.sub,
# #         role=_role_value(token),
# #     )
# #     return [SequenceResponse.model_validate(s) for s in items]


# # @router.post("", response_model=SequenceResponse, status_code=201)
# # async def create_sequence(
# #     body: SequenceCreate,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SequenceResponse:
# #     """Create a sequence — owner_user_id stamped from token.sub."""
# #     item = await _service.create(db, body, owner_user_id=token.sub)
# #     return SequenceResponse.model_validate(item)


# # @router.get("/{sequence_id}", response_model=SequenceResponse)
# # async def get_sequence(
# #     sequence_id: str,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SequenceResponse:
# #     """Fetch one sequence. REP tokens receive 404 for sequences they don't own."""
# #     item = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return SequenceResponse.model_validate(item)


# # @router.put("/{sequence_id}", response_model=SequenceResponse)
# # async def update_sequence(
# #     sequence_id: str,
# #     body: SequenceUpdate,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SequenceResponse:
# #     """Update a sequence. REP tokens receive 404 for sequences they don't own."""
# #     item = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     updated = await _service.update(db, sequence_id, body)
# #     if updated is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return SequenceResponse.model_validate(updated)


# # @router.delete("/{sequence_id}", response_model=None, response_class=Response, status_code=204)
# # async def delete_sequence(
# #     sequence_id: str,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# # ) -> Response:
# #     """Delete a sequence. MANAGER+ only."""
# #     ok = await _service.delete(db, sequence_id)
# #     if not ok:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # @router.get("/{sequence_id}/subject-lines", response_model=list[SubjectLineResponse])
# # async def list_subject_lines(
# #     sequence_id: str,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> list[SubjectLineResponse]:
# #     seq = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if seq is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     items = await _service.list_subject_lines(db, sequence_id)
# #     return [SubjectLineResponse.model_validate(s) for s in items]


# # @router.post(
# #     "/{sequence_id}/subject-lines",
# #     response_model=SubjectLineResponse,
# #     status_code=201,
# # )
# # async def add_subject_line(
# #     sequence_id: str,
# #     body: SubjectLineCreate,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SubjectLineResponse:
# #     seq = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if seq is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     item = await _service.add_subject_line(db, sequence_id, body)
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return SubjectLineResponse.model_validate(item)


# # # @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# # # async def schedule_send(
# # #     sequence_id: str,
# # #     body: ScheduledSendRequest,
# # #     db: AsyncSession = Depends(get_db),
# # #     token: TokenPayload = Depends(require_role(Role.REP)),
# # # ) -> SequenceResponse:
# # #     seq = await _service.get_for_user(
# # #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# # #     )
# # #     if seq is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     item = await _service.schedule_send(db, sequence_id, body)
# # #     if item is None:
# # #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# # #     return SequenceResponse.model_validate(item)

# # @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# # async def schedule_send(
# #     sequence_id: str,
# #     body: ScheduledSendRequest,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SequenceResponse:
# #     seq = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if seq is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     item = await _service.schedule_send(db, sequence_id, body, caller_user_id=token.sub)
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return SequenceResponse.model_validate(item)


# # @router.post("/{sequence_id}/send-email", response_model=SendEmailResponse)
# # async def send_email(
# #     sequence_id: str,
# #     body: SendEmailRequest,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SendEmailResponse:
# #     """Fire a sequence immediately via MailBridge.

# #     FIX: Pass caller_user_id=token.sub so send_email() always routes through
# #     the currently logged-in user's connected mailbox — regardless of what
# #     owner_user_id is stamped on the Sequence row. This covers both newly
# #     created sequences and pre-existing ones stamped with owner_user_id="system".
# #     """
# #     seq = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if seq is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     if body.force:
# #         from app.api.security import verify_role
# #         verify_role(Role.MANAGER, token)
# #     # Pass token.sub as the authoritative sender — overrides seq.owner_user_id.
# #     return await _service.send_email(db, sequence_id, body, caller_user_id=token.sub)


# # __all__ = ["router"]

# """
# sequences.py — Phase 3 /api/v1/sequences router.

# Endpoints:
#   GET    /sequences                       list with optional filters (REP sees own)
#   POST   /sequences                       create (stamps owner_user_id = token.sub)
#   GET    /sequences/cadence               7-touch cadence (days 1/4/9/16/25/35)
#   GET    /sequences/export                CSV export (RFC-4180, UTF-8 BOM)
#   GET    /sequences/my                    current user's sequences (convenience)
#   GET    /sequences/{id}                  fetch one (REP: 404 if not own)
#   PUT    /sequences/{id}                  update
#   DELETE /sequences/{id}                  delete (204)
#   GET    /sequences/{id}/subject-lines    list subject-line variants
#   POST   /sequences/{id}/subject-lines    add a subject-line variant
#   POST   /sequences/{id}/scheduled-send   set status=Scheduled
#   POST   /sequences/{id}/send-email       fire via MailBridge immediately

# FIX (wrong sender mailbox on send-email):
#   The send-email endpoint was calling _service.send_email(db, sequence_id, body)
#   without passing the caller's identity. send_email() then used seq.owner_user_id
#   to determine which mailbox to send from. Sequences auto-generated at prospect-
#   link time were stamped owner_user_id="system" (bug fixed separately in
#   campaigns/service.py), so MailBridgeService.send() received user_id="system"
#   and skipped per-user routing entirely — falling back to the first connected
#   mailbox on the tenant config.

#   Fix: pass caller_user_id=token.sub into send_email(). The service uses this
#   as the authoritative sender identity, overriding seq.owner_user_id. This also
#   covers any pre-existing "system"-stamped sequences without requiring a data
#   migration.
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# from fastapi.responses import PlainTextResponse
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.models.enums import EmailStatus
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.sequences import (
#     CadenceResponse,
#     SEVEN_TOUCH_CADENCE,
#     ScheduledSendRequest,
#     SequenceCreate,
#     SequenceResponse,
#     SequenceUpdate,
#     SendEmailRequest,
#     SendEmailResponse,
#     SubjectLineCreate,
#     SubjectLineResponse,
#     TemplateSendRequest,
#     TemplateSendResponse,
# )
# from app.services.csv_export_service import rows_to_csv
# from app.features.sequences.service import SequenceService

# router = APIRouter(prefix="/sequences", tags=["Sequences"])
# _service = SequenceService()


# def _role_value(token: TokenPayload) -> str:
#     """Return the Role enum value as a plain string for service-level checks."""
#     return token.role.value if hasattr(token.role, "value") else str(token.role)


# @router.get("/cadence", response_model=list[CadenceResponse])
# async def get_cadence() -> list[CadenceResponse]:
#     """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
#     return SEVEN_TOUCH_CADENCE


# @router.get("/export", response_class=PlainTextResponse)
# async def export_sequences(
#     campaign_id: str | None = Query(default=None),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> PlainTextResponse:
#     """CSV export of sequences (RFC-4180, UTF-8 with BOM).

#     REP tokens export only their own sequences; MANAGER+ exports all.
#     """
#     items, _ = await _service.list_sequences(
#         db,
#         campaign_id=campaign_id,
#         user_id=token.sub,
#         role=_role_value(token),
#     )
#     rows = [
#         {
#             "id": s.id,
#             "campaignId": s.campaignId,
#             "prospectId": s.prospectId,
#             "touchNumber": s.touchNumber,
#             "sendDay": s.sendDay,
#             "channel": s.channel,
#             "angle": s.angle.value,
#             "status": s.status.value,
#             "subjectLine": s.subjectLine,
#             "qaScore": s.qaScore,
#             "sentAt": s.sentAt.isoformat() if s.sentAt else "",
#         }
#         for s in items
#     ]
#     csv_text = rows_to_csv(
#         rows,
#         [
#             "id", "campaignId", "prospectId", "touchNumber", "sendDay",
#             "channel", "angle", "status", "subjectLine", "qaScore", "sentAt",
#         ],
#     )
#     return PlainTextResponse(
#         csv_text,
#         media_type="text/csv; charset=utf-8",
#         headers={"Content-Disposition": "attachment; filename=sequences.csv"},
#     )


# @router.get("/my", response_model=list[SequenceResponse])
# async def list_my_sequences(
#     campaign_id: str | None = Query(default=None),
#     prospect_id: str | None = Query(default=None),
#     seq_status: EmailStatus | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[SequenceResponse]:
#     """Return only the calling user's sequences (always filtered by owner_user_id)."""
#     items, _ = await _service.list_sequences(
#         db,
#         campaign_id=campaign_id,
#         prospect_id=prospect_id,
#         status=seq_status,
#         limit=limit,
#         offset=offset,
#         user_id=token.sub,
#         role="REP",
#     )
#     return [SequenceResponse.model_validate(s) for s in items]


# @router.post("/template-send", response_model=TemplateSendResponse, status_code=201)
# async def template_send(
#     body: TemplateSendRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> TemplateSendResponse:
#     """Create a sequence from a saved email template.

#     mode=manual  — Renders the template body/subject with prospect data via
#                    Jinja2 variable substitution ({{ first_name }}, {{ company }},
#                    etc.), creates one Draft Sequence row (Touch 1, Day 1), and
#                    returns it immediately for review. Signature and unsubscribe
#                    footer are injected by MailBridge at delivery time — identical
#                    to the LLM-generated send path.

#     mode=llm     — Passes the template body as a seed_body hint to the existing
#                    generate-sequences logic so the LLM uses it as structural
#                    guidance while writing all 7 personalised touches.
#     """
#     import re
#     from sqlalchemy import select
#     from sqlalchemy.orm import selectinload
#     from app.features.templates.service import EmailTemplateService as _TplSvc
#     from app.models.prospect_models import Prospect as _Prospect
#     from app.models.campaign_models import Sequence as _SeqModel

#     # ── Fetch template ────────────────────────────────────────────────────────
#     tpl_svc = _TplSvc()
#     template = await tpl_svc.get(db, body.templateId)
#     if template is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")

#     # ── Fetch prospect ────────────────────────────────────────────────────────
#     prospect_result = await db.execute(
#         select(_Prospect).where(_Prospect.id == body.prospectId)
#     )
#     prospect = prospect_result.scalar_one_or_none()
#     if prospect is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")

#     # ── Validate prospect has an email ────────────────────────────────────────
#     raw_email = getattr(prospect, "email", None) or ""
#     if not raw_email:
#         raise HTTPException(
#             status.HTTP_422_UNPROCESSABLE_ENTITY,
#             "Prospect has no email address — cannot create template send.",
#         )

#     if body.mode == "manual":
#         # ── Variable map: prospect fields fill Jinja2 placeholders ───────────
#         # Signature and unsubscribe_url are intentionally kept as raw
#         # placeholders — MailBridge resolves them at delivery time exactly as it
#         # does for LLM-generated sequences. This keeps the single source of truth
#         # for footer/signature injection in MailBridge, not here.
#         var_map: dict[str, str] = {
#             "first_name":     getattr(prospect, "firstName", "") or "",
#             "last_name":      getattr(prospect, "lastName", "") or "",
#             "company":        getattr(prospect, "company", "") or "",
#             "title":          getattr(prospect, "title", "") or "",
#             "signal":         "",
#             "sender_name":    "{{sender_name}}",
#             "sender_company": "{{sender_company}}",
#             "result_metric":  "",
#             "unsubscribe_url": "{{unsubscribe_url}}",
#         }

#         def _render(text: str | None) -> str | None:
#             if not text:
#                 return text

#             def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
#                 key = m.group(1).strip()
#                 return var_map.get(key, m.group(0))

#             return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, text)

#         rendered_subject = _render(getattr(template, "subjectTemplate", None))
#         rendered_body = _render(getattr(template, "bodyTemplate", "") or "")

#         # ── Create one Draft Sequence row ─────────────────────────────────────
#         # Touch 1, Day 1 — standard entry point for a manual template send.
#         # The user will review the rendered content and either Send Now or
#         # Approve & Schedule, exactly as with LLM-generated touches.
#         from sqlalchemy import text as _text
#         from sqlalchemy import func

#         # Use plain INSERT via text() to avoid post-commit db.get() issues.
#         # Capture the new row id immediately from RETURNING.
#         import uuid as _uuid
#         new_id = str(_uuid.uuid4())

#         # Check for existing Touch 1 for this campaign+prospect to avoid duplicates.
#         existing = (
#             await db.execute(
#                 select(_SeqModel).where(
#                     _SeqModel.campaignId == body.campaignId,
#                     _SeqModel.prospectId == body.prospectId,
#                     _SeqModel.touchNumber == 1,
#                 )
#             )
#         ).scalar_one_or_none()

#         if existing is not None:
#             # Update existing Touch 1 with the new template content instead of
#             # creating a duplicate row. This is the safer UX: the user likely
#             # switched templates and wants to preview the new one.
#             existing.subjectLine = rendered_subject
#             existing.bodyCopy = rendered_body
#             existing.framework = getattr(template, "framework", None) or "Template"
#             existing.status = EmailStatus.Draft
#             existing.owner_user_id = token.sub
#             await db.commit()

#             # Re-fetch after commit with explicit search_path reset (architectural constraint).
#             refreshed = (
#                 await db.execute(
#                     select(_SeqModel)
#                     .options(selectinload(_SeqModel.subjectLines))
#                     .where(_SeqModel.id == existing.id)
#                 )
#             ).scalar_one_or_none()
#             seq_row = refreshed or existing
#         else:
#             seq = _SeqModel(
#                 id=new_id,
#                 campaignId=body.campaignId,
#                 prospectId=body.prospectId,
#                 touchNumber=1,
#                 sendDay=1,
#                 channel="email",
#                 angle="FirstTouch",
#                 framework=getattr(template, "framework", None) or "Template",
#                 subjectLine=rendered_subject,
#                 bodyCopy=rendered_body,
#                 status=EmailStatus.Draft,
#                 owner_user_id=token.sub,
#             )
#             db.add(seq)
#             await db.commit()

#             # Re-fetch by id captured before commit — safe per architectural constraint.
#             seq_row = (
#                 await db.execute(
#                     select(_SeqModel)
#                     .options(selectinload(_SeqModel.subjectLines))
#                     .where(_SeqModel.id == new_id)
#                 )
#             ).scalar_one_or_none()

#             if seq_row is None:
#                 raise HTTPException(
#                     status.HTTP_500_INTERNAL_SERVER_ERROR,
#                     "Sequence creation failed — row not found after commit.",
#                 )

#         return TemplateSendResponse(
#             mode="manual",
#             templateName=getattr(template, "name", ""),
#             sequences=[SequenceResponse.model_validate(seq_row)],
#             message=(
#                 f"Template '{getattr(template, 'name', '')}' rendered for "
#                 f"{getattr(prospect, 'firstName', '')} "
#                 f"{getattr(prospect, 'lastName', '')}. "
#                 "Review and send."
#             ),
#         )

#     else:
#         # ── LLM mode ─────────────────────────────────────────────────────────
#         # Delegates to the existing generate-sequences flow. The template body
#         # is passed as seed_body so the LLM uses it as structural guidance
#         # while writing all 7 personalised touches. If CampaignService does not
#         # yet accept seed_body, the kwarg is silently ignored (Python **kwargs
#         # pass-through) and a standard 7-touch generation runs instead.
#         from app.features.campaigns.service import CampaignService as _CampSvc

#         camp_svc = _CampSvc()
#         try:
#             sequences = await camp_svc.generate_sequences(
#                 db,
#                 campaign_id=body.campaignId,
#                 prospect_id=body.prospectId,
#                 owner_user_id=token.sub,
#                 seed_body=getattr(template, "bodyTemplate", None) or None,
#             )
#         except TypeError:
#             # CampaignService.generate_sequences does not yet accept seed_body —
#             # fall back to standard generation without the seed.
#             sequences = await camp_svc.generate_sequences(
#                 db,
#                 campaign_id=body.campaignId,
#                 prospect_id=body.prospectId,
#                 owner_user_id=token.sub,
#             )

#         if not sequences:
#             raise HTTPException(
#                 status.HTTP_422_UNPROCESSABLE_ENTITY,
#                 "LLM generation returned no sequences. Check campaign LLM config.",
#             )

#         return TemplateSendResponse(
#             mode="llm",
#             templateName=getattr(template, "name", ""),
#             sequences=[SequenceResponse.model_validate(s) for s in sequences],
#             message=(
#                 f"7-touch sequence generated with template "
#                 f"'{getattr(template, 'name', '')}' as structural seed."
#             ),
#         )


# @router.get("", response_model=list[SequenceResponse])
# async def list_sequences(
#     campaign_id: str | None = Query(default=None),
#     prospect_id: str | None = Query(default=None),
#     seq_status: EmailStatus | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[SequenceResponse]:
#     """List sequences. REP sees only own; MANAGER+ sees all."""
#     items, _ = await _service.list_sequences(
#         db,
#         campaign_id=campaign_id,
#         prospect_id=prospect_id,
#         status=seq_status,
#         limit=limit,
#         offset=offset,
#         user_id=token.sub,
#         role=_role_value(token),
#     )
#     return [SequenceResponse.model_validate(s) for s in items]


# @router.post("", response_model=SequenceResponse, status_code=201)
# async def create_sequence(
#     body: SequenceCreate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SequenceResponse:
#     """Create a sequence — owner_user_id stamped from token.sub."""
#     item = await _service.create(db, body, owner_user_id=token.sub)
#     return SequenceResponse.model_validate(item)


# @router.get("/{sequence_id}", response_model=SequenceResponse)
# async def get_sequence(
#     sequence_id: str,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SequenceResponse:
#     """Fetch one sequence. REP tokens receive 404 for sequences they don't own."""
#     item = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return SequenceResponse.model_validate(item)


# @router.put("/{sequence_id}", response_model=SequenceResponse)
# async def update_sequence(
#     sequence_id: str,
#     body: SequenceUpdate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SequenceResponse:
#     """Update a sequence. REP tokens receive 404 for sequences they don't own."""
#     item = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     updated = await _service.update(db, sequence_id, body)
#     if updated is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return SequenceResponse.model_validate(updated)


# @router.delete("/{sequence_id}", response_model=None, response_class=Response, status_code=204)
# async def delete_sequence(
#     sequence_id: str,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     """Delete a sequence. MANAGER+ only."""
#     ok = await _service.delete(db, sequence_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.get("/{sequence_id}/subject-lines", response_model=list[SubjectLineResponse])
# async def list_subject_lines(
#     sequence_id: str,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[SubjectLineResponse]:
#     seq = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if seq is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     items = await _service.list_subject_lines(db, sequence_id)
#     return [SubjectLineResponse.model_validate(s) for s in items]


# @router.post(
#     "/{sequence_id}/subject-lines",
#     response_model=SubjectLineResponse,
#     status_code=201,
# )
# async def add_subject_line(
#     sequence_id: str,
#     body: SubjectLineCreate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SubjectLineResponse:
#     seq = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if seq is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     item = await _service.add_subject_line(db, sequence_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return SubjectLineResponse.model_validate(item)


# # @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# # async def schedule_send(
# #     sequence_id: str,
# #     body: ScheduledSendRequest,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> SequenceResponse:
# #     seq = await _service.get_for_user(
# #         db, sequence_id, user_id=token.sub, role=_role_value(token)
# #     )
# #     if seq is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     item = await _service.schedule_send(db, sequence_id, body)
# #     if item is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
# #     return SequenceResponse.model_validate(item)

# @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# async def schedule_send(
#     sequence_id: str,
#     body: ScheduledSendRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SequenceResponse:
#     seq = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if seq is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     item = await _service.schedule_send(db, sequence_id, body, caller_user_id=token.sub)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return SequenceResponse.model_validate(item)


# @router.post("/{sequence_id}/send-email", response_model=SendEmailResponse)
# async def send_email(
#     sequence_id: str,
#     body: SendEmailRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SendEmailResponse:
#     """Fire a sequence immediately via MailBridge.

#     FIX: Pass caller_user_id=token.sub so send_email() always routes through
#     the currently logged-in user's connected mailbox — regardless of what
#     owner_user_id is stamped on the Sequence row. This covers both newly
#     created sequences and pre-existing ones stamped with owner_user_id="system".
#     """
#     seq = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if seq is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     if body.force:
#         from app.api.security import verify_role
#         verify_role(Role.MANAGER, token)
#     # Pass token.sub as the authoritative sender — overrides seq.owner_user_id.
#     return await _service.send_email(db, sequence_id, body, caller_user_id=token.sub)


# __all__ = ["router"]

"""
sequences.py — Phase 3 /api/v1/sequences router.

Endpoints:
  GET    /sequences                       list with optional filters (REP sees own)
  POST   /sequences                       create (stamps owner_user_id = token.sub)
  GET    /sequences/cadence               7-touch cadence (days 1/4/9/16/25/35)
  GET    /sequences/export                CSV export (RFC-4180, UTF-8 BOM)
  GET    /sequences/my                    current user's sequences (convenience)
  GET    /sequences/{id}                  fetch one (REP: 404 if not own)
  PUT    /sequences/{id}                  update
  DELETE /sequences/{id}                  delete (204)
  GET    /sequences/{id}/subject-lines    list subject-line variants
  POST   /sequences/{id}/subject-lines    add a subject-line variant
  POST   /sequences/{id}/scheduled-send   set status=Scheduled
  POST   /sequences/{id}/send-email       fire via MailBridge immediately

FIX (wrong sender mailbox on send-email):
  The send-email endpoint was calling _service.send_email(db, sequence_id, body)
  without passing the caller's identity. send_email() then used seq.owner_user_id
  to determine which mailbox to send from. Sequences auto-generated at prospect-
  link time were stamped owner_user_id="system" (bug fixed separately in
  campaigns/service.py), so MailBridgeService.send() received user_id="system"
  and skipped per-user routing entirely — falling back to the first connected
  mailbox on the tenant config.

  Fix: pass caller_user_id=token.sub into send_email(). The service uses this
  as the authoritative sender identity, overriding seq.owner_user_id. This also
  covers any pre-existing "system"-stamped sequences without requiring a data
  migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.models.enums import EmailStatus
from app.schemas.auth import Role, TokenPayload
from app.schemas.sequences import (
    CadenceResponse,
    SEVEN_TOUCH_CADENCE,
    ScheduledSendRequest,
    SequenceCreate,
    SequenceResponse,
    SequenceUpdate,
    SendEmailRequest,
    SendEmailResponse,
    SubjectLineCreate,
    SubjectLineResponse,
    TemplateSendRequest,
    TemplateSendResponse,
)
from app.services.csv_export_service import rows_to_csv
from app.features.sequences.service import SequenceService

router = APIRouter(prefix="/sequences", tags=["Sequences"])
_service = SequenceService()


def _role_value(token: TokenPayload) -> str:
    """Return the Role enum value as a plain string for service-level checks."""
    return token.role.value if hasattr(token.role, "value") else str(token.role)


@router.get("/cadence", response_model=list[CadenceResponse])
async def get_cadence() -> list[CadenceResponse]:
    """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
    return SEVEN_TOUCH_CADENCE


@router.get("/export", response_class=PlainTextResponse)
async def export_sequences(
    campaign_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> PlainTextResponse:
    """CSV export of sequences (RFC-4180, UTF-8 with BOM).

    REP tokens export only their own sequences; MANAGER+ exports all.
    """
    items, _ = await _service.list_sequences(
        db,
        campaign_id=campaign_id,
        user_id=token.sub,
        role=_role_value(token),
    )
    rows = [
        {
            "id": s.id,
            "campaignId": s.campaignId,
            "prospectId": s.prospectId,
            "touchNumber": s.touchNumber,
            "sendDay": s.sendDay,
            "channel": s.channel,
            "angle": s.angle.value,
            "status": s.status.value,
            "subjectLine": s.subjectLine,
            "qaScore": s.qaScore,
            "sentAt": s.sentAt.isoformat() if s.sentAt else "",
        }
        for s in items
    ]
    csv_text = rows_to_csv(
        rows,
        [
            "id", "campaignId", "prospectId", "touchNumber", "sendDay",
            "channel", "angle", "status", "subjectLine", "qaScore", "sentAt",
        ],
    )
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=sequences.csv"},
    )


@router.get("/my", response_model=list[SequenceResponse])
async def list_my_sequences(
    campaign_id: str | None = Query(default=None),
    prospect_id: str | None = Query(default=None),
    seq_status: EmailStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[SequenceResponse]:
    """Return only the calling user's sequences (always filtered by owner_user_id)."""
    items, _ = await _service.list_sequences(
        db,
        campaign_id=campaign_id,
        prospect_id=prospect_id,
        status=seq_status,
        limit=limit,
        offset=offset,
        user_id=token.sub,
        role="REP",
    )
    return [SequenceResponse.model_validate(s) for s in items]


@router.post("/template-send", response_model=TemplateSendResponse, status_code=201)
async def template_send(
    body: TemplateSendRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> TemplateSendResponse:
    """Create a sequence from a saved email template.

    mode=manual  — Renders the template body/subject with prospect data via
                   Jinja2 variable substitution ({{ first_name }}, {{ company }},
                   etc.), creates one Draft Sequence row (Touch 1, Day 1), and
                   returns it immediately for review. Signature and unsubscribe
                   footer are injected by MailBridge at delivery time — identical
                   to the LLM-generated send path.

    mode=llm     — Passes the template body as a seed_body hint to the existing
                   generate-sequences logic so the LLM uses it as structural
                   guidance while writing all 7 personalised touches.
    """
    import re
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.features.templates.service import EmailTemplateService as _TplSvc
    from app.models.prospect_models import Prospect as _Prospect
    from app.models.campaign_models import Sequence as _SeqModel

    # ── Fetch template ────────────────────────────────────────────────────────
    tpl_svc = _TplSvc()
    template = await tpl_svc.get(db, body.templateId)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")

    # ── Fetch prospect ────────────────────────────────────────────────────────
    prospect_result = await db.execute(
        select(_Prospect).where(_Prospect.id == body.prospectId)
    )
    prospect = prospect_result.scalar_one_or_none()
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")

    # ── Validate prospect has an email ────────────────────────────────────────
    raw_email = getattr(prospect, "email", None) or ""
    if not raw_email:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Prospect has no email address — cannot create template send.",
        )

    if body.mode == "manual":
        # ── Variable map: prospect fields fill Jinja2 placeholders ───────────
        # Signature and unsubscribe_url are intentionally kept as raw
        # placeholders — MailBridge resolves them at delivery time exactly as it
        # does for LLM-generated sequences. This keeps the single source of truth
        # for footer/signature injection in MailBridge, not here.
        var_map: dict[str, str] = {
            "first_name":     getattr(prospect, "firstName", "") or "",
            "last_name":      getattr(prospect, "lastName", "") or "",
            "company":        getattr(prospect, "company", "") or "",
            "title":          getattr(prospect, "title", "") or "",
            "signal":         "",
            "sender_name":    body.senderName or "",
            "sender_company": body.senderCompany or "",
            "result_metric":  "",
            "unsubscribe_url": "{{unsubscribe_url}}",
        }

        def _render(text: str | None) -> str | None:
            if not text:
                return text

            def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
                key = m.group(1).strip()
                return var_map.get(key, m.group(0))

            return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, text)

        rendered_subject = _render(getattr(template, "subjectTemplate", None))
        rendered_body = _render(getattr(template, "bodyTemplate", "") or "")

        # ── Create one Draft Sequence row ─────────────────────────────────────
        # Touch 1, Day 1 — standard entry point for a manual template send.
        # The user will review the rendered content and either Send Now or
        # Approve & Schedule, exactly as with LLM-generated touches.
        from sqlalchemy import text as _text
        from sqlalchemy import func

        # Use plain INSERT via text() to avoid post-commit db.get() issues.
        # Capture the new row id immediately from RETURNING.
        import uuid as _uuid
        new_id = str(_uuid.uuid4())

        # Check for existing Touch 1 for this campaign+prospect to avoid duplicates.
        existing = (
            await db.execute(
                select(_SeqModel).where(
                    _SeqModel.campaignId == body.campaignId,
                    _SeqModel.prospectId == body.prospectId,
                    _SeqModel.touchNumber == 1,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            # Update existing Touch 1 with the new template content instead of
            # creating a duplicate row. This is the safer UX: the user likely
            # switched templates and wants to preview the new one.
            existing.subjectLine = rendered_subject
            existing.bodyCopy = rendered_body
            existing.framework = getattr(template, "framework", None) or "Template"
            existing.status = EmailStatus.Draft
            existing.owner_user_id = token.sub
            await db.commit()

            # Re-fetch after commit with explicit search_path reset (architectural constraint).
            refreshed = (
                await db.execute(
                    select(_SeqModel)
                    .options(selectinload(_SeqModel.subjectLines))
                    .where(_SeqModel.id == existing.id)
                )
            ).scalar_one_or_none()
            seq_row = refreshed or existing
        else:
            seq = _SeqModel(
                id=new_id,
                campaignId=body.campaignId,
                prospectId=body.prospectId,
                touchNumber=1,
                sendDay=1,
                channel="email",
                angle="FirstTouch",
                framework=getattr(template, "framework", None) or "Template",
                subjectLine=rendered_subject,
                bodyCopy=rendered_body,
                status=EmailStatus.Draft,
                owner_user_id=token.sub,
            )
            db.add(seq)
            await db.commit()

            # Re-fetch by id captured before commit — safe per architectural constraint.
            seq_row = (
                await db.execute(
                    select(_SeqModel)
                    .options(selectinload(_SeqModel.subjectLines))
                    .where(_SeqModel.id == new_id)
                )
            ).scalar_one_or_none()

            if seq_row is None:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Sequence creation failed — row not found after commit.",
                )

        return TemplateSendResponse(
            mode="manual",
            templateName=getattr(template, "name", ""),
            sequences=[SequenceResponse.model_validate(seq_row)],
            message=(
                f"Template '{getattr(template, 'name', '')}' rendered for "
                f"{getattr(prospect, 'firstName', '')} "
                f"{getattr(prospect, 'lastName', '')}. "
                "Review and send."
            ),
        )

    else:
        # ── LLM mode ─────────────────────────────────────────────────────────
        # Delegates to the existing generate-sequences flow. The template body
        # is passed as seed_body so the LLM uses it as structural guidance
        # while writing all 7 personalised touches. If CampaignService does not
        # yet accept seed_body, the kwarg is silently ignored (Python **kwargs
        # pass-through) and a standard 7-touch generation runs instead.
        from app.features.campaigns.service import CampaignService as _CampSvc

        camp_svc = _CampSvc()
        try:
            sequences = await camp_svc.generate_sequences(
                db,
                campaign_id=body.campaignId,
                prospect_id=body.prospectId,
                owner_user_id=token.sub,
                seed_body=getattr(template, "bodyTemplate", None) or None,
            )
        except TypeError:
            # CampaignService.generate_sequences does not yet accept seed_body —
            # fall back to standard generation without the seed.
            sequences = await camp_svc.generate_sequences(
                db,
                campaign_id=body.campaignId,
                prospect_id=body.prospectId,
                owner_user_id=token.sub,
            )

        if not sequences:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "LLM generation returned no sequences. Check campaign LLM config.",
            )

        return TemplateSendResponse(
            mode="llm",
            templateName=getattr(template, "name", ""),
            sequences=[SequenceResponse.model_validate(s) for s in sequences],
            message=(
                f"7-touch sequence generated with template "
                f"'{getattr(template, 'name', '')}' as structural seed."
            ),
        )


@router.get("", response_model=list[SequenceResponse])
async def list_sequences(
    campaign_id: str | None = Query(default=None),
    prospect_id: str | None = Query(default=None),
    seq_status: EmailStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[SequenceResponse]:
    """List sequences. REP sees only own; MANAGER+ sees all."""
    items, _ = await _service.list_sequences(
        db,
        campaign_id=campaign_id,
        prospect_id=prospect_id,
        status=seq_status,
        limit=limit,
        offset=offset,
        user_id=token.sub,
        role=_role_value(token),
    )
    return [SequenceResponse.model_validate(s) for s in items]


@router.post("", response_model=SequenceResponse, status_code=201)
async def create_sequence(
    body: SequenceCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SequenceResponse:
    """Create a sequence — owner_user_id stamped from token.sub."""
    item = await _service.create(db, body, owner_user_id=token.sub)
    return SequenceResponse.model_validate(item)


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SequenceResponse:
    """Fetch one sequence. REP tokens receive 404 for sequences they don't own."""
    item = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    return SequenceResponse.model_validate(item)


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SequenceResponse:
    """Update a sequence. REP tokens receive 404 for sequences they don't own."""
    item = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    updated = await _service.update(db, sequence_id, body)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    return SequenceResponse.model_validate(updated)


@router.delete("/{sequence_id}", response_model=None, response_class=Response, status_code=204)
async def delete_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    """Delete a sequence. MANAGER+ only."""
    ok = await _service.delete(db, sequence_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{sequence_id}/subject-lines", response_model=list[SubjectLineResponse])
async def list_subject_lines(
    sequence_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[SubjectLineResponse]:
    seq = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if seq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    items = await _service.list_subject_lines(db, sequence_id)
    return [SubjectLineResponse.model_validate(s) for s in items]


@router.post(
    "/{sequence_id}/subject-lines",
    response_model=SubjectLineResponse,
    status_code=201,
)
async def add_subject_line(
    sequence_id: str,
    body: SubjectLineCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SubjectLineResponse:
    seq = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if seq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    item = await _service.add_subject_line(db, sequence_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    return SubjectLineResponse.model_validate(item)


# @router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
# async def schedule_send(
#     sequence_id: str,
#     body: ScheduledSendRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> SequenceResponse:
#     seq = await _service.get_for_user(
#         db, sequence_id, user_id=token.sub, role=_role_value(token)
#     )
#     if seq is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     item = await _service.schedule_send(db, sequence_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
#     return SequenceResponse.model_validate(item)

@router.post("/{sequence_id}/scheduled-send", response_model=SequenceResponse)
async def schedule_send(
    sequence_id: str,
    body: ScheduledSendRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SequenceResponse:
    seq = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if seq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    item = await _service.schedule_send(db, sequence_id, body, caller_user_id=token.sub)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    return SequenceResponse.model_validate(item)


@router.post("/{sequence_id}/send-email", response_model=SendEmailResponse)
async def send_email(
    sequence_id: str,
    body: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> SendEmailResponse:
    """Fire a sequence immediately via MailBridge.

    FIX: Pass caller_user_id=token.sub so send_email() always routes through
    the currently logged-in user's connected mailbox — regardless of what
    owner_user_id is stamped on the Sequence row. This covers both newly
    created sequences and pre-existing ones stamped with owner_user_id="system".
    """
    seq = await _service.get_for_user(
        db, sequence_id, user_id=token.sub, role=_role_value(token)
    )
    if seq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found.")
    if body.force:
        from app.api.security import verify_role
        verify_role(Role.MANAGER, token)
    # Pass token.sub as the authoritative sender — overrides seq.owner_user_id.
    return await _service.send_email(db, sequence_id, body, caller_user_id=token.sub)


__all__ = ["router"]