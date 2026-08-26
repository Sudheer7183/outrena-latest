

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

# # from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
# #     TemplateSendRequest,
# #     TemplateSendResponse,
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


# # @router.post("/template-send", response_model=TemplateSendResponse, status_code=201)
# # async def template_send(
# #     request: Request,
# #     body: TemplateSendRequest,
# #     db: AsyncSession = Depends(get_db),
# #     token: TokenPayload = Depends(require_role(Role.REP)),
# # ) -> TemplateSendResponse:
# #     """Create sequences from a saved email template for ALL prospects under an ICP profile.

# #     mode=manual  — Renders the template body/subject for every prospect linked to
# #                    body.icpProfileId. For each prospect: substitutes Jinja2 variables
# #                    ({{ first_name }}, {{ company }}, etc.), upserts one Draft Sequence
# #                    row (Touch 1, Day 1), and returns the full list for bulk review.
# #                    No LLM call is made. Signature and unsubscribe footer are injected
# #                    by MailBridge at delivery time.

# #     mode=llm     — Generates 7 personalised LLM touches per prospect under the ICP,
# #                    using the template body as a structural seed/constraint.

# #     Prospects without an email address are skipped and reported in the message.
# #     """
# #     import re
# #     import uuid as _uuid
# #     from sqlalchemy import select
# #     from sqlalchemy.orm import selectinload
# #     from app.features.templates.service import EmailTemplateService as _TplSvc
# #     from app.models.prospect_models import Prospect as _Prospect, IcpProfile as _IcpProfile
# #     from app.models.campaign_models import Sequence as _SeqModel

# #     # ── Fetch template ────────────────────────────────────────────────────────
# #     tpl_svc = _TplSvc()
# #     template = await tpl_svc.get(db, body.templateId)
# #     if template is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")

# #     # ── Verify ICP exists ─────────────────────────────────────────────────────
# #     icp_row = (
# #         await db.execute(select(_IcpProfile).where(_IcpProfile.id == body.icpProfileId))
# #     ).scalar_one_or_none()
# #     if icp_row is None:
# #         raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")

# #     # ── Fetch all ACTIVE (non-deleted, non-anonymized) prospects under this ICP ─
# #     # Soft-deleted prospects have deleted_at set and PII replaced with "[anonymized]".
# #     # They must be excluded: rendering their data produces "[anonymized]" in emails.
# #     prospect_rows = (
# #         await db.execute(
# #             select(_Prospect).where(
# #                 _Prospect.icpProfileId == body.icpProfileId,
# #                 _Prospect.deleted_at.is_(None),
# #                 _Prospect.anonymized.is_(False),
# #             )
# #         )
# #     ).scalars().all()

# #     if not prospect_rows:
# #         raise HTTPException(
# #             status.HTTP_422_UNPROCESSABLE_ENTITY,
# #             f"No active prospects are linked to ICP '{getattr(icp_row, 'name', body.icpProfileId)}'. "
# #             "Deleted prospects are excluded. Go to Prospects and link active prospects to this ICP.",
# #         )

# #     template_name = getattr(template, "name", "")
# #     icp_name = getattr(icp_row, "name", body.icpProfileId)

# #     if body.mode == "manual":
# #         # ── Shared render helper ─────────────────────────────────────────────
# #         def _build_var_map(prospect: "_Prospect") -> dict[str, str]:
# #             return {
# #                 "first_name":     getattr(prospect, "firstName", "") or "",
# #                 "last_name":      getattr(prospect, "lastName", "") or "",
# #                 "company":        getattr(prospect, "company", "") or "",
# #                 "title":          getattr(prospect, "title", "") or "",
# #                 "signal":         "",
# #                 "sender_name":    body.senderName or "",
# #                 "sender_company": body.senderCompany or "",
# #                 "result_metric":  "",
# #                 "unsubscribe_url": "{{unsubscribe_url}}",
# #             }

# #         def _render(text: str | None, var_map: dict[str, str]) -> str | None:
# #             if not text:
# #                 return text
# #             def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
# #                 return var_map.get(m.group(1).strip(), m.group(0))
# #             return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, text)

# #         rendered_rows: list[SequenceResponse] = []
# #         prospect_map: dict[str, str] = {}   # seq.id → "First Last · Company"
# #         skipped: list[str] = []

# #         for prospect in prospect_rows:
# #             raw_email = getattr(prospect, "email", None) or ""
# #             if not raw_email or raw_email == "[anonymized]":
# #                 name = f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
# #                 skipped.append(name or prospect.id)
# #                 continue

# #             var_map = _build_var_map(prospect)
# #             rendered_subject = _render(getattr(template, "subjectTemplate", None), var_map)
# #             rendered_body    = _render(getattr(template, "bodyTemplate", "") or "", var_map)

# #             new_id = str(_uuid.uuid4())

# #             # Upsert: update existing Touch 1 if it exists, else create new row.
# #             existing = (
# #                 await db.execute(
# #                     select(_SeqModel).where(
# #                         _SeqModel.campaignId == body.campaignId,
# #                         _SeqModel.prospectId == prospect.id,
# #                         _SeqModel.touchNumber == 1,
# #                     )
# #                 )
# #             ).scalar_one_or_none()

# #             if existing is not None:
# #                 existing.subjectLine = rendered_subject
# #                 existing.bodyCopy    = rendered_body
# #                 existing.framework   = getattr(template, "framework", None) or "Template"
# #                 existing.status      = EmailStatus.Draft
# #                 existing.owner_user_id = token.sub
# #                 saved_id = existing.id          # capture id before commit strips context
# #                 await db.commit()

# #                 # Re-apply search_path after commit — asyncpg returns the connection
# #                 # to the pool on commit and strips search_path. Re-set it exactly as
# #                 # get_db does on initial checkout.
# #                 _tenant = getattr(request.state, "tenant", None)
# #                 _schema = _tenant.schema_name if _tenant else "public"
# #                 from sqlalchemy import text as _sql_text
# #                 await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
# #                 seq_row = (
# #                     await db.execute(
# #                         select(_SeqModel)
# #                         .options(selectinload(_SeqModel.subjectLines))
# #                         .where(_SeqModel.id == saved_id)
# #                     )
# #                 ).scalar_one_or_none()

# #                 if seq_row is None:
# #                     skipped.append(
# #                         f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
# #                         or prospect.id
# #                     )
# #                     continue
# #             else:
# #                 seq = _SeqModel(
# #                     id=new_id,
# #                     campaignId=body.campaignId,
# #                     prospectId=prospect.id,
# #                     touchNumber=1,
# #                     sendDay=1,
# #                     channel="email",
# #                     angle="FirstTouch",
# #                     framework=getattr(template, "framework", None) or "Template",
# #                     subjectLine=rendered_subject,
# #                     bodyCopy=rendered_body,
# #                     status=EmailStatus.Draft,
# #                     owner_user_id=token.sub,
# #                 )
# #                 db.add(seq)
# #                 await db.commit()

# #                 # Re-apply search_path after commit (same pattern as get_db on checkout).
# #                 _tenant = getattr(request.state, "tenant", None)
# #                 _schema = _tenant.schema_name if _tenant else "public"
# #                 from sqlalchemy import text as _sql_text
# #                 await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
# #                 seq_row = (
# #                     await db.execute(
# #                         select(_SeqModel)
# #                         .options(selectinload(_SeqModel.subjectLines))
# #                         .where(_SeqModel.id == new_id)
# #                     )
# #                 ).scalar_one_or_none()
# #                 if seq_row is None:
# #                     skipped.append(
# #                         f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
# #                         or prospect.id
# #                     )
# #                     continue

# #             rendered_rows.append(SequenceResponse.model_validate(seq_row))
# #             # Build display name: "First Last · Company" for the frontend card header
# #             first  = getattr(prospect, "firstName", "") or ""
# #             last   = getattr(prospect, "lastName", "") or ""
# #             co     = getattr(prospect, "company", "") or ""
# #             label  = f"{first} {last}".strip()
# #             if co:
# #                 label = f"{label} · {co}" if label else co
# #             prospect_map[seq_row.id] = label or f"Prospect {len(rendered_rows)}"

# #         skip_note = f" {len(skipped)} skipped (no email): {', '.join(skipped)}." if skipped else ""
# #         return TemplateSendResponse(
# #             mode="manual",
# #             templateName=template_name,
# #             sequences=rendered_rows,
# #             prospectMap=prospect_map,
# #             message=(
# #                 f"Template '{template_name}' rendered for {len(rendered_rows)} prospect(s) "
# #                 f"under ICP '{icp_name}'.{skip_note} Review all and Approve & Schedule."
# #             ),
# #         )

# #     else:
# #         # ── LLM mode: generate 7 touches per prospect ─────────────────────────
# #         from app.features.campaigns.service import CampaignService as _CampSvc

# #         camp_svc = _CampSvc()
# #         all_sequences: list[SequenceResponse] = []
# #         skipped_llm: list[str] = []

# #         for prospect in prospect_rows:
# #             raw_email = getattr(prospect, "email", None) or ""
# #             if not raw_email:
# #                 skipped_llm.append(
# #                     f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
# #                     or prospect.id
# #                 )
# #                 continue
# #             try:
# #                 seqs = await camp_svc.generate_sequences(
# #                     db,
# #                     campaign_id=body.campaignId,
# #                     prospect_id=prospect.id,
# #                     owner_user_id=token.sub,
# #                     seed_body=getattr(template, "bodyTemplate", None) or None,
# #                 )
# #             except TypeError:
# #                 seqs = await camp_svc.generate_sequences(
# #                     db,
# #                     campaign_id=body.campaignId,
# #                     prospect_id=prospect.id,
# #                     owner_user_id=token.sub,
# #                 )
# #             except Exception:
# #                 skipped_llm.append(
# #                     f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
# #                     or prospect.id
# #                 )
# #                 continue
# #             all_sequences.extend([SequenceResponse.model_validate(s) for s in (seqs or [])])

# #         if not all_sequences:
# #             raise HTTPException(
# #                 status.HTTP_422_UNPROCESSABLE_ENTITY,
# #                 "LLM generation returned no sequences for any prospect. Check campaign LLM config.",
# #             )

# #         skip_note = f" {len(skipped_llm)} skipped: {', '.join(skipped_llm)}." if skipped_llm else ""
# #         return TemplateSendResponse(
# #             mode="llm",
# #             templateName=template_name,
# #             sequences=all_sequences,
# #             message=(
# #                 f"Sequences generated with template '{template_name}' as seed for "
# #                 f"{len(prospect_rows) - len(skipped_llm)} prospect(s) under ICP '{icp_name}'.{skip_note}"
# #             ),
# #         )


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

# from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
#     request: Request,
#     body: TemplateSendRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> TemplateSendResponse:
#     """Create sequences from a saved email template for ALL prospects under an ICP profile.

#     mode=manual  — Renders the template body/subject for every prospect linked to
#                    body.icpProfileId. For each prospect: substitutes Jinja2 variables
#                    ({{ first_name }}, {{ company }}, etc.), upserts one Draft Sequence
#                    row (Touch 1, Day 1), and returns the full list for bulk review.
#                    No LLM call is made. Signature and unsubscribe footer are injected
#                    by MailBridge at delivery time.

#     mode=llm     — Generates 7 personalised LLM touches per prospect under the ICP,
#                    using the template body as a structural seed/constraint.

#     Prospects without an email address are skipped and reported in the message.
#     """
#     import re
#     import uuid as _uuid
#     from sqlalchemy import select
#     from sqlalchemy.orm import selectinload
#     from app.features.templates.service import EmailTemplateService as _TplSvc
#     from app.models.prospect_models import Prospect as _Prospect, IcpProfile as _IcpProfile
#     from app.models.campaign_models import Sequence as _SeqModel

#     # ── Fetch template ────────────────────────────────────────────────────────
#     tpl_svc = _TplSvc()
#     template = await tpl_svc.get(db, body.templateId)
#     if template is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")

#     # ── Verify ICP exists ─────────────────────────────────────────────────────
#     icp_row = (
#         await db.execute(select(_IcpProfile).where(_IcpProfile.id == body.icpProfileId))
#     ).scalar_one_or_none()
#     if icp_row is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")

#     # ── Fetch all ACTIVE (non-deleted, non-anonymized) prospects under this ICP ─
#     # Soft-deleted prospects have deleted_at set and PII replaced with "[anonymized]".
#     # They must be excluded: rendering their data produces "[anonymized]" in emails.
#     prospect_rows = (
#         await db.execute(
#             select(_Prospect).where(
#                 _Prospect.icpProfileId == body.icpProfileId,
#                 _Prospect.deleted_at.is_(None),
#                 _Prospect.anonymized.is_(False),
#             )
#         )
#     ).scalars().all()

#     if not prospect_rows:
#         raise HTTPException(
#             status.HTTP_422_UNPROCESSABLE_ENTITY,
#             f"No active prospects are linked to ICP '{getattr(icp_row, 'name', body.icpProfileId)}'. "
#             "Deleted prospects are excluded. Go to Prospects and link active prospects to this ICP.",
#         )

#     template_name = getattr(template, "name", "")
#     icp_name = getattr(icp_row, "name", body.icpProfileId)

#     if body.mode == "manual":
#         # ── Shared render helper ─────────────────────────────────────────────
#         def _build_var_map(prospect: "_Prospect") -> dict[str, str]:
#             return {
#                 "first_name":     getattr(prospect, "firstName", "") or "",
#                 "last_name":      getattr(prospect, "lastName", "") or "",
#                 "company":        getattr(prospect, "company", "") or "",
#                 "title":          getattr(prospect, "title", "") or "",
#                 "signal":         "",
#                 "sender_name":    body.senderName or "",
#                 "sender_company": body.senderCompany or "",
#                 "result_metric":  "",
#                 "unsubscribe_url": "{{unsubscribe_url}}",
#             }

#         def _render(text: str | None, var_map: dict[str, str]) -> str | None:
#             if not text:
#                 return text
#             def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
#                 return var_map.get(m.group(1).strip(), m.group(0))
#             return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, text)

#         def _append_footer(body_text: str | None, prospect: "_Prospect") -> str:
#             """Append signature + CAN-SPAM footer if the template body doesn't
#             already contain an unsubscribe reference or a signature block.
#             MailBridge also injects these at send time for LLM sequences, but
#             for manual template renders we do it here so the preview is accurate.
#             """
#             text = body_text or ""
#             sig   = (body.emailSignature or "").strip()
#             addr  = (body.physicalAddress or "").strip()

#             # Only append if the template doesn't already have a footer/signature
#             has_sig   = sig   and sig   in text
#             has_unsub = "unsubscribe" in text.lower()

#             footer_parts: list[str] = []
#             if sig and not has_sig:
#                 footer_parts.append(sig)
#             if addr and not has_unsub:
#                 footer_parts.append(f"---\nTo unsubscribe: {{{{unsubscribe_url}}}}\n{addr}")
#             elif not has_unsub and addr:
#                 footer_parts.append(f"---\nTo unsubscribe: {{{{unsubscribe_url}}}}\n{addr}")

#             if footer_parts:
#                 return text.rstrip() + "\n\n" + "\n\n".join(footer_parts)
#             return text

#         rendered_rows: list[SequenceResponse] = []
#         prospect_map: dict[str, str] = {}   # seq.id → "First Last · Company"
#         skipped: list[str] = []

#         for prospect in prospect_rows:
#             raw_email = getattr(prospect, "email", None) or ""
#             if not raw_email or raw_email == "[anonymized]":
#                 name = f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
#                 skipped.append(name or prospect.id)
#                 continue

#             var_map = _build_var_map(prospect)
#             rendered_subject = _render(getattr(template, "subjectTemplate", None), var_map)
#             rendered_body    = _append_footer(
#                 _render(getattr(template, "bodyTemplate", "") or "", var_map),
#                 prospect,
#             )

#             new_id = str(_uuid.uuid4())

#             # Upsert: update existing Touch 1 if it exists, else create new row.
#             existing = (
#                 await db.execute(
#                     select(_SeqModel).where(
#                         _SeqModel.campaignId == body.campaignId,
#                         _SeqModel.prospectId == prospect.id,
#                         _SeqModel.touchNumber == 1,
#                     )
#                 )
#             ).scalar_one_or_none()

#             if existing is not None:
#                 existing.subjectLine = rendered_subject
#                 existing.bodyCopy    = rendered_body
#                 existing.framework   = getattr(template, "framework", None) or "Template"
#                 existing.status      = EmailStatus.Draft
#                 existing.owner_user_id = token.sub
#                 saved_id = existing.id          # capture id before commit strips context
#                 await db.commit()

#                 # Re-apply search_path after commit — asyncpg returns the connection
#                 # to the pool on commit and strips search_path. Re-set it exactly as
#                 # get_db does on initial checkout.
#                 _tenant = getattr(request.state, "tenant", None)
#                 _schema = _tenant.schema_name if _tenant else "public"
#                 from sqlalchemy import text as _sql_text
#                 await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
#                 seq_row = (
#                     await db.execute(
#                         select(_SeqModel)
#                         .options(selectinload(_SeqModel.subjectLines))
#                         .where(_SeqModel.id == saved_id)
#                     )
#                 ).scalar_one_or_none()

#                 if seq_row is None:
#                     skipped.append(
#                         f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
#                         or prospect.id
#                     )
#                     continue
#             else:
#                 seq = _SeqModel(
#                     id=new_id,
#                     campaignId=body.campaignId,
#                     prospectId=prospect.id,
#                     touchNumber=1,
#                     sendDay=1,
#                     channel="email",
#                     angle="FirstTouch",
#                     framework=getattr(template, "framework", None) or "Template",
#                     subjectLine=rendered_subject,
#                     bodyCopy=rendered_body,
#                     status=EmailStatus.Draft,
#                     owner_user_id=token.sub,
#                 )
#                 db.add(seq)
#                 await db.commit()

#                 # Re-apply search_path after commit (same pattern as get_db on checkout).
#                 _tenant = getattr(request.state, "tenant", None)
#                 _schema = _tenant.schema_name if _tenant else "public"
#                 from sqlalchemy import text as _sql_text
#                 await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
#                 seq_row = (
#                     await db.execute(
#                         select(_SeqModel)
#                         .options(selectinload(_SeqModel.subjectLines))
#                         .where(_SeqModel.id == new_id)
#                     )
#                 ).scalar_one_or_none()
#                 if seq_row is None:
#                     skipped.append(
#                         f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
#                         or prospect.id
#                     )
#                     continue

#             rendered_rows.append(SequenceResponse.model_validate(seq_row))
#             # Build display name: "First Last · Company" for the frontend card header
#             first  = getattr(prospect, "firstName", "") or ""
#             last   = getattr(prospect, "lastName", "") or ""
#             co     = getattr(prospect, "company", "") or ""
#             label  = f"{first} {last}".strip()
#             if co:
#                 label = f"{label} · {co}" if label else co
#             prospect_map[seq_row.id] = label or f"Prospect {len(rendered_rows)}"

#         skip_note = f" {len(skipped)} skipped (no email): {', '.join(skipped)}." if skipped else ""
#         return TemplateSendResponse(
#             mode="manual",
#             templateName=template_name,
#             sequences=rendered_rows,
#             prospectMap=prospect_map,
#             message=(
#                 f"Template '{template_name}' rendered for {len(rendered_rows)} prospect(s) "
#                 f"under ICP '{icp_name}'.{skip_note} Review all and Approve & Schedule."
#             ),
#         )

#     else:
#         # ── LLM mode: generate 7 touches per prospect ─────────────────────────
#         from app.features.campaigns.service import CampaignService as _CampSvc

#         camp_svc = _CampSvc()
#         all_sequences: list[SequenceResponse] = []
#         skipped_llm: list[str] = []

#         for prospect in prospect_rows:
#             raw_email = getattr(prospect, "email", None) or ""
#             if not raw_email:
#                 skipped_llm.append(
#                     f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
#                     or prospect.id
#                 )
#                 continue
#             try:
#                 seqs = await camp_svc.generate_sequences(
#                     db,
#                     campaign_id=body.campaignId,
#                     prospect_id=prospect.id,
#                     owner_user_id=token.sub,
#                     seed_body=getattr(template, "bodyTemplate", None) or None,
#                 )
#             except TypeError:
#                 seqs = await camp_svc.generate_sequences(
#                     db,
#                     campaign_id=body.campaignId,
#                     prospect_id=prospect.id,
#                     owner_user_id=token.sub,
#                 )
#             except Exception:
#                 skipped_llm.append(
#                     f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
#                     or prospect.id
#                 )
#                 continue
#             all_sequences.extend([SequenceResponse.model_validate(s) for s in (seqs or [])])

#         if not all_sequences:
#             raise HTTPException(
#                 status.HTTP_422_UNPROCESSABLE_ENTITY,
#                 "LLM generation returned no sequences for any prospect. Check campaign LLM config.",
#             )

#         skip_note = f" {len(skipped_llm)} skipped: {', '.join(skipped_llm)}." if skipped_llm else ""
#         return TemplateSendResponse(
#             mode="llm",
#             templateName=template_name,
#             sequences=all_sequences,
#             message=(
#                 f"Sequences generated with template '{template_name}' as seed for "
#                 f"{len(prospect_rows) - len(skipped_llm)} prospect(s) under ICP '{icp_name}'.{skip_note}"
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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
    request: Request,
    body: TemplateSendRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> TemplateSendResponse:
    """Create sequences from a saved email template for ALL prospects under an ICP profile.

    mode=manual  — Renders the template body/subject for every prospect linked to
                   body.icpProfileId. For each prospect: substitutes Jinja2 variables
                   ({{ first_name }}, {{ company }}, etc.), upserts one Draft Sequence
                   row (Touch 1, Day 1), and returns the full list for bulk review.
                   No LLM call is made. Signature and unsubscribe footer are injected
                   by MailBridge at delivery time.

    mode=llm     — Generates 7 personalised LLM touches per prospect under the ICP,
                   using the template body as a structural seed/constraint.

    Prospects without an email address are skipped and reported in the message.
    """
    import re
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.features.templates.service import EmailTemplateService as _TplSvc
    from app.models.prospect_models import Prospect as _Prospect, IcpProfile as _IcpProfile
    from app.models.campaign_models import Sequence as _SeqModel

    # ── Fetch template ────────────────────────────────────────────────────────
    tpl_svc = _TplSvc()
    template = await tpl_svc.get(db, body.templateId)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")

    # ── Verify ICP exists ─────────────────────────────────────────────────────
    icp_row = (
        await db.execute(select(_IcpProfile).where(_IcpProfile.id == body.icpProfileId))
    ).scalar_one_or_none()
    if icp_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found.")

    # ── Fetch all ACTIVE (non-deleted, non-anonymized) prospects under this ICP ─
    # Soft-deleted prospects have deleted_at set and PII replaced with "[anonymized]".
    # They must be excluded: rendering their data produces "[anonymized]" in emails.
    prospect_rows = (
        await db.execute(
            select(_Prospect).where(
                _Prospect.icpProfileId == body.icpProfileId,
                _Prospect.deleted_at.is_(None),
                _Prospect.anonymized.is_(False),
            )
        )
    ).scalars().all()

    if not prospect_rows:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No active prospects are linked to ICP '{getattr(icp_row, 'name', body.icpProfileId)}'. "
            "Deleted prospects are excluded. Go to Prospects and link active prospects to this ICP.",
        )

    template_name = getattr(template, "name", "")
    icp_name = getattr(icp_row, "name", body.icpProfileId)

    if body.mode == "manual":
        # ── Shared render helper ─────────────────────────────────────────────
        def _build_var_map(prospect: "_Prospect") -> dict[str, str]:
            return {
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

        def _render(text: str | None, var_map: dict[str, str]) -> str | None:
            if not text:
                return text
            def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
                return var_map.get(m.group(1).strip(), m.group(0))
            return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, text)

        def _append_footer(body_text: str | None, prospect: "_Prospect") -> str:  # noqa: ARG001
            """Append signature + CAN-SPAM footer to the rendered body.

            Rules:
            - Signature is appended if profile has one AND it's not already in the body.
            - Unsubscribe footer is appended if the body doesn't already contain
              the literal placeholder {{unsubscribe_url}} (checked after variable
              substitution — the placeholder remains because it's resolved by MailBridge
              at send time, not here).
            - Physical address is included in the footer when available.
            """
            text = body_text or ""
            sig  = (body.emailSignature or "").strip()
            addr = (body.physicalAddress or "").strip()

            footer_parts: list[str] = []

            # Append signature if present and not already in the body
            if sig and sig not in text:
                footer_parts.append(sig)

            # Always append the unsubscribe block unless the body already has
            # the {{unsubscribe_url}} placeholder (meaning the template author
            # included it explicitly). Check for the placeholder, NOT the word
            # "unsubscribe" — the word may appear naturally in the body copy.
            has_unsub_placeholder = "{{unsubscribe_url}}" in text or "{{ unsubscribe_url }}" in text
            if not has_unsub_placeholder:
                unsub_line = "To unsubscribe: {{unsubscribe_url}}"
                if addr:
                    footer_parts.append(f"---\n{unsub_line}\n{addr}")
                else:
                    footer_parts.append(f"---\n{unsub_line}")

            if footer_parts:
                return text.rstrip() + "\n\n" + "\n\n".join(footer_parts)
            return text

        rendered_rows: list[SequenceResponse] = []
        prospect_map: dict[str, str] = {}   # seq.id → "First Last · Company"
        skipped: list[str] = []

        for prospect in prospect_rows:
            raw_email = getattr(prospect, "email", None) or ""
            if not raw_email or raw_email == "[anonymized]":
                name = f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
                skipped.append(name or prospect.id)
                continue

            var_map = _build_var_map(prospect)
            rendered_subject = _render(getattr(template, "subjectTemplate", None), var_map)
            rendered_body    = _append_footer(
                _render(getattr(template, "bodyTemplate", "") or "", var_map),
                prospect,
            )

            new_id = str(_uuid.uuid4())

            # Upsert: update existing Touch 1 if it exists, else create new row.
            existing = (
                await db.execute(
                    select(_SeqModel).where(
                        _SeqModel.campaignId == body.campaignId,
                        _SeqModel.prospectId == prospect.id,
                        _SeqModel.touchNumber == 1,
                    )
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.subjectLine = rendered_subject
                existing.bodyCopy    = rendered_body
                existing.framework   = getattr(template, "framework", None) or "Template"
                existing.status      = EmailStatus.Draft
                existing.owner_user_id = token.sub
                saved_id = existing.id          # capture id before commit strips context
                await db.commit()

                # Re-apply search_path after commit — asyncpg returns the connection
                # to the pool on commit and strips search_path. Re-set it exactly as
                # get_db does on initial checkout.
                _tenant = getattr(request.state, "tenant", None)
                _schema = _tenant.schema_name if _tenant else "public"
                from sqlalchemy import text as _sql_text
                await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
                seq_row = (
                    await db.execute(
                        select(_SeqModel)
                        .options(selectinload(_SeqModel.subjectLines))
                        .where(_SeqModel.id == saved_id)
                    )
                ).scalar_one_or_none()

                if seq_row is None:
                    skipped.append(
                        f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
                        or prospect.id
                    )
                    continue
            else:
                seq = _SeqModel(
                    id=new_id,
                    campaignId=body.campaignId,
                    prospectId=prospect.id,
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

                # Re-apply search_path after commit (same pattern as get_db on checkout).
                _tenant = getattr(request.state, "tenant", None)
                _schema = _tenant.schema_name if _tenant else "public"
                from sqlalchemy import text as _sql_text
                await db.execute(_sql_text(f'SET search_path TO "{_schema}", public'))
                seq_row = (
                    await db.execute(
                        select(_SeqModel)
                        .options(selectinload(_SeqModel.subjectLines))
                        .where(_SeqModel.id == new_id)
                    )
                ).scalar_one_or_none()
                if seq_row is None:
                    skipped.append(
                        f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
                        or prospect.id
                    )
                    continue

            rendered_rows.append(SequenceResponse.model_validate(seq_row))
            # Build display name: "First Last · Company" for the frontend card header
            first  = getattr(prospect, "firstName", "") or ""
            last   = getattr(prospect, "lastName", "") or ""
            co     = getattr(prospect, "company", "") or ""
            label  = f"{first} {last}".strip()
            if co:
                label = f"{label} · {co}" if label else co
            prospect_map[seq_row.id] = label or f"Prospect {len(rendered_rows)}"

        skip_note = f" {len(skipped)} skipped (no email): {', '.join(skipped)}." if skipped else ""
        return TemplateSendResponse(
            mode="manual",
            templateName=template_name,
            sequences=rendered_rows,
            prospectMap=prospect_map,
            message=(
                f"Template '{template_name}' rendered for {len(rendered_rows)} prospect(s) "
                f"under ICP '{icp_name}'.{skip_note} Review all and Approve & Schedule."
            ),
        )

    else:
        # ── LLM mode: generate 7 touches per prospect ─────────────────────────
        from app.features.campaigns.service import CampaignService as _CampSvc

        camp_svc = _CampSvc()
        all_sequences: list[SequenceResponse] = []
        skipped_llm: list[str] = []

        for prospect in prospect_rows:
            raw_email = getattr(prospect, "email", None) or ""
            if not raw_email:
                skipped_llm.append(
                    f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
                    or prospect.id
                )
                continue
            try:
                seqs = await camp_svc.generate_sequences(
                    db,
                    campaign_id=body.campaignId,
                    prospect_id=prospect.id,
                    owner_user_id=token.sub,
                    seed_body=getattr(template, "bodyTemplate", None) or None,
                )
            except TypeError:
                seqs = await camp_svc.generate_sequences(
                    db,
                    campaign_id=body.campaignId,
                    prospect_id=prospect.id,
                    owner_user_id=token.sub,
                )
            except Exception:
                skipped_llm.append(
                    f"{getattr(prospect, 'firstName', '')} {getattr(prospect, 'lastName', '')}".strip()
                    or prospect.id
                )
                continue
            all_sequences.extend([SequenceResponse.model_validate(s) for s in (seqs or [])])

        if not all_sequences:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "LLM generation returned no sequences for any prospect. Check campaign LLM config.",
            )

        skip_note = f" {len(skipped_llm)} skipped: {', '.join(skipped_llm)}." if skipped_llm else ""
        return TemplateSendResponse(
            mode="llm",
            templateName=template_name,
            sequences=all_sequences,
            message=(
                f"Sequences generated with template '{template_name}' as seed for "
                f"{len(prospect_rows) - len(skipped_llm)} prospect(s) under ICP '{icp_name}'.{skip_note}"
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