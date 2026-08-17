

# """
# campaigns.py — Phase 2 /api/v1/campaigns router.

# Endpoints:
#   GET    /campaigns                                list (REP sees own; MANAGER+ sees all)
#   GET    /campaigns/my                             list current user's campaigns (convenience)
#   GET    /campaigns/team                           MANAGER+ rollup with owner info
#   POST   /campaigns                                create (stamps owner_user_id = token.sub)
#   GET    /campaigns/campaign-prospects             list linked prospects (enriched with prospect data)
#   POST   /campaigns/campaign-prospects             link prospect(s)
#   DELETE /campaigns/campaign-prospects             unlink prospect (204)
#   POST   /campaigns/clone                          clone campaign
#   POST   /campaigns/preflight                      6-check gate
#   POST   /campaigns/framework-recommend            LLM recommends framework
#   POST   /campaigns/gtm-thesis                     LLM generates GTM thesis
#   GET    /campaigns/{campaign_id}                  fetch one (REP: 404 if not own)
#   PUT    /campaigns/{campaign_id}                  update
#   DELETE /campaigns/{campaign_id}                  delete (204)
#   POST   /campaigns/{campaign_id}/generate-sequences  LLM-write 7-touch sequence content

# Role gate: Role.MANAGER for tenant-wide CRUD. The /my endpoint accepts Role.REP
# so individual contributors can manage their own campaigns.
# """
# from __future__ import annotations

# import asyncio
# import json

# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from fastapi.responses import Response
# from pydantic import BaseModel
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.campaigns import (
#     CampaignCreate,
#     CampaignListResponse,
#     CampaignProspectLinkRequest,
#     CampaignResponse,
#     CampaignUpdate,
#     CloneCampaignRequest,
#     FrameworkRecommendRequest,
#     FrameworkRecommendResponse,
#     GtmThesisRequest,
#     GtmThesisResponse,
#     PreflightRequest,
#     PreflightResult,
# )
# from app.features.campaigns.service import CampaignService

# router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
# _service = CampaignService()


# def _role_value(token: TokenPayload) -> str:
#     """Return the Role enum value as a plain string for service-level checks."""
#     return token.role.value if hasattr(token.role, "value") else str(token.role)


# # ── Per-angle word limits (matches frontend WORD_LIMITS exactly) ─────────────

# _ANGLE_WORD_LIMITS: dict[str, int] = {
#     "FirstTouch":      150,
#     "NewEvidence":     120,
#     "DifferentPain":   120,
#     "IndustryInsight": 120,
#     "DirectQuestion":   80,
#     "Breakup":          60,
# }

# _ANGLE_INSTRUCTIONS: dict[str, str] = {
#     "FirstTouch":
#         "Opening cold email. Reference a specific trigger event or buying signal. "
#         "Establish relevance immediately — no generic intros.",
#     "NewEvidence":
#         "Follow-up introducing new data, a case study, or a relevant metric the prospect cares about. "
#         "Build on the first touch.",
#     "DifferentPain":
#         "Address a different pain point than touch 1. Show breadth of understanding of their challenges.",
#     "IndustryInsight":
#         "Lead with a relevant industry trend or insight. "
#         "Position the sender as a knowledgeable peer, not a vendor.",
#     "DirectQuestion":
#         "Short, direct question that demands a reply. "
#         "Example: 'Is pipeline velocity still a priority for Q3?' Max 80 words.",
#     "Breakup":
#         "Final breakup email. Polite, brief, no hard sell. Acknowledge it may not be the right time. "
#         "Leave the door open.",
# }


# # ── LLM content generation helper ────────────────────────────────────────────

# async def _generate_touch_content(
#     db: AsyncSession,
#     seq,
#     *,
#     prospect,
#     campaign,
#     icp,
#     framework_override: str | None,
# ) -> tuple[str, str, int]:
#     """
#     Call the tenant's configured LLM to write one email touch.

#     Returns (subject_line, body_copy, qa_score).
#     Returns ("", "", 0) on any failure — caller keeps the skeleton row as Draft.
#     """
#     from app.services.llm_service import call_llm, get_default_llm_config, LlmGatewayError
#     import structlog as _sl

#     llm_config = await get_default_llm_config(db)
#     if llm_config is None:
#         _sl.get_logger(__name__).warning(
#             "generate_sequences.no_llm_config",
#             sequence_id=getattr(seq, "id", None),
#         )
#         return "", "", 0

#     angle = seq.angle.value if hasattr(seq.angle, "value") else str(seq.angle)
#     framework = framework_override or seq.framework or "AIDA"
#     word_limit = _ANGLE_WORD_LIMITS.get(angle, 120)
#     angle_instruction = _ANGLE_INSTRUCTIONS.get(angle, "Write a compelling cold outreach email.")

#     # Prospect context
#     p_name      = f"{prospect.firstName} {prospect.lastName}".strip()
#     p_title     = prospect.title or "professional"
#     p_company   = prospect.company or "their company"
#     p_seniority = (
#         prospect.seniority.value
#         if hasattr(prospect.seniority, "value")
#         else str(prospect.seniority)
#     )

#     # Buying signals — stored as JSON list on the Prospect model
#     signals_raw = prospect.signals or []
#     if isinstance(signals_raw, str):
#         try:
#             signals_raw = json.loads(signals_raw)
#         except Exception:
#             signals_raw = []
#     signal_text = ""
#     if signals_raw:
#         first = signals_raw[0]
#         signal_text = (
#             f"Buying signal: {first}"
#             if isinstance(first, str)
#             else f"Buying signal: {first.get('signal') or str(first)}"
#         )

#     # Sender / ICP context
#     sender_role    = (getattr(icp, "senderRole",    None) if icp else None) or getattr(campaign, "senderRole",    None) or "Account Executive"
#     sender_company = (getattr(icp, "senderCompany", None) if icp else None) or getattr(campaign, "senderCompany", None) or "our company"
#     sender_offer   = (getattr(icp, "senderOffer",   None) if icp else None) or ""
#     proof_metric   = (getattr(icp, "proofMetric",   None) if icp else None) or ""
#     persona_desc   = (getattr(icp, "persona",       None) if icp else None) or ""

#     system_msg = (
#         "You are an expert B2B cold email copywriter. "
#         "Respond ONLY with a valid JSON object — no markdown fences, no preamble, no explanation."
#     )

#     user_msg = f"""Write touch #{seq.touchNumber} of a 7-touch cold email sequence.

# PROSPECT
#   Name: {p_name}
#   Title: {p_title}
#   Company: {p_company}
#   Seniority: {p_seniority}
#   {signal_text}

# SENDER
#   Role: {sender_role}
#   Company: {sender_company}
#   Offer: {sender_offer}
#   Proof metric: {proof_metric}

# ICP PERSONA: {persona_desc}

# TOUCH INSTRUCTIONS
#   Angle: {angle} — {angle_instruction}
#   Framework: {framework}
#   Word limit: {word_limit} words for the body (STRICT — do not exceed)
#   Send day: {seq.sendDay}

# Return JSON with exactly these four keys:
# {{
#   "subject": "subject line under 60 characters, no ALL CAPS",
#   "body": "email body — {word_limit} words max, plain text, merge fields like {{{{first_name}}}} are allowed",
#   "qa_score": integer 0-100,
#   "personalisation_confidence": float 0.0-1.0
# }}"""

#     messages = [
#         {"role": "system", "content": system_msg},
#         {"role": "user",   "content": user_msg},
#     ]

#     try:
#         response = await asyncio.wait_for(
#             call_llm(llm_config, messages),
#             timeout=45.0,
#         )
#         raw = response.content if hasattr(response, "content") else str(response)
#         raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
#         data = json.loads(raw)
#         subject   = str(data.get("subject", "")).strip()
#         body_copy = str(data.get("body", "")).strip()
#         qa_score  = int(data.get("qa_score", 70))
#         return subject, body_copy, qa_score
#     except asyncio.TimeoutError:
#         _sl.get_logger(__name__).warning(
#             "generate_sequences.llm_timeout",
#             sequence_id=getattr(seq, "id", None),
#             touch=seq.touchNumber,
#         )
#         return "", "", 0
#     except Exception as exc:  # noqa: BLE001
#         _sl.get_logger(__name__).warning(
#             "generate_sequences.llm_failed",
#             sequence_id=getattr(seq, "id", None),
#             touch=seq.touchNumber,
#             angle=angle,
#             error=str(exc),
#         )
#         return "", "", 0


# # ── Request body for generate-sequences ──────────────────────────────────────

# class _GenerateSequencesBody(BaseModel):
#     """Optional JSON body for POST /{campaign_id}/generate-sequences.

#     prospectId — when supplied, generate only for this specific prospect.
#     framework  — override the sequence framework (optional).
#     All extra fields sent by the frontend are silently ignored.
#     """
#     model_config = {"extra": "ignore"}
#     prospectId: str | None = None
#     framework: str | None = None


# # ── Static routes (declared BEFORE /{campaign_id} per Pitfall #7) ───────────


# @router.get("/my", response_model=CampaignListResponse)
# async def list_my_campaigns(
#     campaign_status: str | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> CampaignListResponse:
#     """Return only the calling user's campaigns (always filtered by owner_user_id)."""
#     items, total = await _service.list_campaigns(
#         db,
#         status=campaign_status,
#         limit=limit,
#         offset=offset,
#         user_id=token.sub,
#         role="REP",
#     )
#     return CampaignListResponse(
#         items=[CampaignResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.get("/team", response_model=CampaignListResponse)
# async def list_team_campaigns(
#     campaign_status: str | None = Query(default=None, alias="status"),
#     owner_user_id: str | None = Query(default=None),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> CampaignListResponse:
#     """Return all tenant campaigns with owner info (MANAGER+ only)."""
#     items, total = await _service.list_campaigns(
#         db,
#         status=campaign_status,
#         limit=limit,
#         offset=offset,
#         user_id=None,
#         role=_role_value(token),
#     )
#     if owner_user_id:
#         items = [i for i in items if i.owner_user_id == owner_user_id]
#         total = len(items)
#     return CampaignListResponse(
#         items=[CampaignResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.get("/campaign-prospects")
# async def list_campaign_prospects(
#     campaign_id: str = Query(...),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[dict]:
#     """Return all CampaignProspect rows for a campaign, enriched with prospect data."""
#     from sqlalchemy import select as _select
#     from app.models.campaign_models import CampaignProspect
#     from app.models.prospect_models import Prospect

#     result = await db.execute(
#         _select(CampaignProspect).where(CampaignProspect.campaignId == campaign_id)
#     )
#     links = result.scalars().all()
#     rows = []
#     for link in links:
#         p = (await db.execute(
#             _select(Prospect).where(Prospect.id == link.prospectId)
#         )).scalar_one_or_none()
#         rows.append({
#             "id": link.id,
#             "campaignId": link.campaignId,
#             "prospectId": link.prospectId,
#             "status": link.status,
#             "createdAt": link.createdAt.isoformat() if link.createdAt else None,
#             "prospect": {
#                 "id": p.id,
#                 "firstName": p.firstName,
#                 "lastName": p.lastName,
#                 "email": p.email,
#                 "title": p.title,
#                 "company": p.company,
#                 "seniority": p.seniority,
#             } if p else None,
#         })
#     return rows


# @router.post("/campaign-prospects", status_code=201)
# async def link_prospect(
#     body: dict,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> dict:
#     """Link one or more prospects to a campaign.

#     Accepts two body shapes:
#       { campaignId, prospectId }           — singular (original form)
#       { campaignId, prospectIds: [...] }   — plural array (sent by Sequence Builder)

#     FIX: The Sequence Builder sends { prospectIds: [id], action: 'add' } but the
#     old endpoint expected singular prospectId only. Pydantic silently dropped the
#     array, so the link was never created and generate-sequences found zero linked
#     prospects — producing empty sequences for manually-created prospects.
#     """
#     from app.features.sequences.service import SequenceService

#     campaign_id: str = body.get("campaignId", "")
#     if not campaign_id:
#         raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "campaignId is required.")

#     raw_ids: list[str] = list(body.get("prospectIds") or [])
#     singular = body.get("prospectId")
#     if singular and singular not in raw_ids:
#         raw_ids.insert(0, singular)
#     if not raw_ids:
#         raise HTTPException(
#             status.HTTP_422_UNPROCESSABLE_ENTITY,
#             "prospectId or prospectIds is required.",
#         )

#     seq_service = SequenceService()
#     for pid in raw_ids:
#         link_body = CampaignProspectLinkRequest(campaignId=campaign_id, prospectId=pid)
#         await _service.link_prospect(db, link_body)
#         try:
#             await seq_service.auto_generate_for_campaign(
#                 db,
#                 campaign_id=campaign_id,
#                 prospect_id=pid,
#                 owner_user_id=token.sub,
#             )
#         except Exception as exc:  # noqa: BLE001
#             import structlog as _sl
#             _sl.get_logger(__name__).warning(
#                 "link_prospect.sequence_gen_failed",
#                 campaign_id=campaign_id,
#                 prospect_id=pid,
#                 error=str(exc),
#             )

#     return {"added": len(raw_ids), "prospectIds": raw_ids, "campaignId": campaign_id}


# @router.delete(
#     "/campaign-prospects", response_model=None, response_class=Response, status_code=204
# )
# async def unlink_prospect(
#     body: CampaignProspectLinkRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.unlink_prospect(db, body)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign-prospect link not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post("/clone", response_model=CampaignResponse, status_code=201)
# async def clone_campaign(
#     body: CloneCampaignRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> CampaignResponse:
#     """Clone a campaign — the clone's owner_user_id is the caller's token.sub."""
#     item = await _service.clone(db, body, owner_user_id=token.sub)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Source campaign not found.")
#     return CampaignResponse.model_validate(item)


# @router.post("/preflight", response_model=PreflightResult)
# async def preflight(
#     body: PreflightRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> PreflightResult:
#     """6-check activation gate (sender, domain, ICP, LLM, MailBridge, prospects)."""
#     return await _service.preflight(db, body)


# @router.post("/framework-recommend", response_model=FrameworkRecommendResponse)
# async def framework_recommend(
#     body: FrameworkRecommendRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FrameworkRecommendResponse:
#     """Ask the LLM to recommend a sales email framework for the campaign."""
#     result = await _service.framework_recommend(db, body)
#     if result is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return result


# @router.post("/gtm-thesis", response_model=GtmThesisResponse)
# async def gtm_thesis(
#     body: GtmThesisRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> GtmThesisResponse:
#     """Ask the LLM to generate a GTM thesis for the campaign."""
#     result = await _service.gtm_thesis(db, body)
#     if result is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return result


# # ── Main CRUD endpoints ───────────────────────────────────────────────────────


# @router.get("", response_model=CampaignListResponse)
# async def list_campaigns(
#     campaign_status: str | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     # REP+ can list campaigns — the service layer filters by owner_user_id for
#     # REPs (they only see their own) and returns all for MANAGER+.
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> CampaignListResponse:
#     items, total = await _service.list_campaigns(
#         db,
#         status=campaign_status,
#         limit=limit,
#         offset=offset,
#         user_id=token.sub,
#         role=_role_value(token),
#     )
#     return CampaignListResponse(
#         items=[CampaignResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post("", response_model=CampaignResponse, status_code=201)
# async def create_campaign(
#     body: CampaignCreate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> CampaignResponse:
#     """Create a campaign — owner_user_id is stamped from token.sub."""
#     item = await _service.create(db, body, owner_user_id=token.sub)
#     return CampaignResponse.model_validate(item)


# @router.get("/{campaign_id}", response_model=CampaignResponse)
# async def get_campaign(
#     campaign_id: str,
#     db: AsyncSession = Depends(get_db),
#     # REP+ can fetch a campaign — service enforces ownership (REPs only see their own).
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> CampaignResponse:
#     item = await _service.get_for_user(
#         db, campaign_id, user_id=token.sub, role=_role_value(token)
#     )
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return CampaignResponse.model_validate(item)


# @router.put("/{campaign_id}", response_model=CampaignResponse)
# async def update_campaign(
#     campaign_id: str,
#     body: CampaignUpdate,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> CampaignResponse:
#     item = await _service.get_for_user(
#         db, campaign_id, user_id=token.sub, role=_role_value(token)
#     )
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     updated = await _service.update(db, campaign_id, body)
#     if updated is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return CampaignResponse.model_validate(updated)


# @router.delete("/{campaign_id}", response_model=None, response_class=Response, status_code=204)
# async def delete_campaign(
#     campaign_id: str,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     item = await _service.get_for_user(
#         db, campaign_id, user_id=token.sub, role=_role_value(token)
#     )
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     ok = await _service.delete(db, campaign_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post("/{campaign_id}/generate-sequences", status_code=202)
# async def generate_sequences(
#     campaign_id: str,
#     body: _GenerateSequencesBody = _GenerateSequencesBody(),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> dict:
#     """
#     Generate LLM-written 7-touch cadence Sequence rows for a campaign's prospects.

#     FIXED (3 bugs corrected in this version):

#     1. Accepts optional { prospectId } body — generates only for that one prospect.
#        When omitted, generates for ALL linked prospects (original bulk behaviour).

#     2. Self-heals missing CampaignProspect link — if prospectId is supplied but
#        not yet linked (because the campaign-prospects call sent the wrong payload
#        shape and was silently rejected), the link is created here before generation.

#     3. LLM content generation — after skeleton rows are created (idempotent), each
#        touch with null bodyCopy is sent to the tenant's configured LLM. The prompt
#        includes prospect name/title/company/seniority/signals, sender/ICP context,
#        touch angle with specific instructions, framework, and strict word limit.
#        Touches are generated sequentially with a 5-second gap to respect rate limits.
#     """
#     from sqlalchemy import select as _select
#     from app.models.campaign_models import CampaignProspect, Sequence as _Seq
#     from app.models.prospect_models import Prospect as _Prospect, IcpProfile as _IcpProfile
#     from app.features.sequences.service import SequenceService

#     campaign = await _service.get_for_user(
#         db, campaign_id, user_id=token.sub, role=_role_value(token)
#     )
#     if campaign is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")

#     requested_prospect_id: str | None = body.prospectId or None

#     # ── Self-heal: link the prospect if not already linked ───────────────────
#     if requested_prospect_id:
#         existing_link = (await db.execute(
#             _select(CampaignProspect).where(
#                 CampaignProspect.campaignId == campaign_id,
#                 CampaignProspect.prospectId == requested_prospect_id,
#             )
#         )).scalar_one_or_none()
#         if existing_link is None:
#             await _service.link_prospect(
#                 db,
#                 CampaignProspectLinkRequest(
#                     campaignId=campaign_id,
#                     prospectId=requested_prospect_id,
#                 ),
#             )

#     # ── Determine which prospects to generate for ────────────────────────────
#     all_linked = [
#         row[0] for row in (await db.execute(
#             _select(CampaignProspect.prospectId).where(
#                 CampaignProspect.campaignId == campaign_id
#             )
#         )).all()
#     ]
#     prospect_ids = [requested_prospect_id] if requested_prospect_id else all_linked
#     if not prospect_ids:
#         return {"message": "No prospects linked to this campaign.", "created": 0}

#     # ── Step 1: create skeleton Sequence rows (idempotent) ───────────────────
#     # IMPORTANT: auto_generate_for_campaign() calls db.commit() internally.
#     # After commit, asyncpg returns the connection to the pool and the
#     # search_path resets to the pool default ("public"). We must re-set it
#     # explicitly after every commit() or all subsequent queries on _Seq
#     # will fail with UndefinedTableError: relation "Sequence" does not exist.
#     from sqlalchemy import text as _text
#     from fastapi import Request as _Request

#     # _reset_search_path: re-execute SET search_path after every db.commit().
#     # asyncpg returns the physical connection to the pool on commit, resetting
#     # search_path to "public". All subsequent ORM queries on tenant tables then
#     # fail with UndefinedTableError. Re-setting it after each commit restores
#     # the correct tenant schema context.
#     #
#     # We derive the schema from token.tenant_slug (always "tenant_{slug}")
#     # to avoid needing request.state (which caused a 422 when added to the
#     # FastAPI endpoint signature — FastAPI treated it as a query parameter).
#     _slug = getattr(token, "tenant_slug", None) or ""
#     _schema = f"tenant_{_slug}" if _slug else "public"

#     async def _reset_search_path() -> None:
#         """Re-set search_path to tenant schema after db.commit()."""
#         await db.execute(_text(f'SET search_path TO "{_schema}", public'))

#     seq_service = SequenceService()
#     total_created = 0
#     for pid in prospect_ids:
#         created = await seq_service.auto_generate_for_campaign(
#             db, campaign_id, prospect_id=pid, owner_user_id=token.sub,
#         )
#         total_created += len(created)
#     # Restore search_path after auto_generate_for_campaign's internal commit
#     await _reset_search_path()

#     # Restamp any "system"-owned rows so per-user list queries see them
#     restamp_stmt = _select(_Seq).where(
#         _Seq.campaignId == campaign_id,
#         _Seq.owner_user_id == "system",
#     )
#     if requested_prospect_id:
#         restamp_stmt = restamp_stmt.where(_Seq.prospectId == requested_prospect_id)
#     restamped = 0
#     for seq in (await db.execute(restamp_stmt)).scalars().all():
#         seq.owner_user_id = token.sub
#         restamped += 1
#     if restamped:
#         await db.commit()
#         await _reset_search_path()  # Restore after restamp commit

#     # ── Step 2: LLM content generation for touches with no body copy ─────────
#     # Includes both newly created rows AND pre-existing empty rows from before
#     # this fix was deployed — re-triggering Generate fills them all.
#     fill_stmt = _select(_Seq).where(
#         _Seq.campaignId == campaign_id,
#         _Seq.bodyCopy.is_(None),
#     )
#     if requested_prospect_id:
#         fill_stmt = fill_stmt.where(_Seq.prospectId == requested_prospect_id)
#     fill_stmt = fill_stmt.order_by(_Seq.prospectId, _Seq.touchNumber)
#     seqs_to_fill: list = list((await db.execute(fill_stmt)).scalars().all())

#     llm_filled = 0
#     if seqs_to_fill:
#         # Load campaign ICP profile once
#         icp = None
#         if campaign.icpProfileId:
#             icp = (await db.execute(
#                 _select(_IcpProfile).where(_IcpProfile.id == campaign.icpProfileId)
#             )).scalar_one_or_none()

#         # Cache prospect rows to avoid repeated DB hits
#         prospect_cache: dict[str, object] = {}

#         for i, seq in enumerate(seqs_to_fill):
#             if seq.prospectId not in prospect_cache:
#                 p = (await db.execute(
#                     _select(_Prospect).where(_Prospect.id == seq.prospectId)
#                 )).scalar_one_or_none()
#                 if p:
#                     prospect_cache[seq.prospectId] = p

#             prospect = prospect_cache.get(seq.prospectId)
#             if prospect is None:
#                 continue

#             subject, body_copy, qa_score = await _generate_touch_content(
#                 db,
#                 seq,
#                 prospect=prospect,
#                 campaign=campaign,
#                 icp=icp,
#                 framework_override=body.framework,
#             )

#             if subject or body_copy:
#                 seq.subjectLine = subject or None
#                 seq.bodyCopy    = body_copy or None
#                 seq.qaScore     = qa_score or None
#                 llm_filled += 1

#             # 5-second gap between LLM calls to respect Groq free-tier rate limits.
#             # Remove or reduce this delay if you are on a paid tier / using OpenAI.
#             if i < len(seqs_to_fill) - 1:
#                 await asyncio.sleep(5)

#         if llm_filled:
#             await db.commit()
#             await _reset_search_path()

#     return {
#         "message": (
#             f"Generated {total_created} new sequence rows for {len(prospect_ids)} prospect(s). "
#             f"LLM filled {llm_filled} touches."
#             + (f" Restamped {restamped} existing sequences." if restamped else "")
#         ),
#         "created": total_created,
#         "llm_filled": llm_filled,
#         "restamped": restamped,
#         "prospects": len(prospect_ids),
#     }


# __all__ = ["router"]



"""
campaigns.py — Phase 2 /api/v1/campaigns router.

Endpoints:
  GET    /campaigns                                list (REP sees own; MANAGER+ sees all)
  GET    /campaigns/my                             list current user's campaigns (convenience)
  GET    /campaigns/team                           MANAGER+ rollup with owner info
  POST   /campaigns                                create (stamps owner_user_id = token.sub)
  GET    /campaigns/campaign-prospects             list linked prospects (enriched with prospect data)
  POST   /campaigns/campaign-prospects             link prospect(s)
  DELETE /campaigns/campaign-prospects             unlink prospect (204)
  POST   /campaigns/clone                          clone campaign
  POST   /campaigns/preflight                      6-check gate
  POST   /campaigns/framework-recommend            LLM recommends framework
  POST   /campaigns/gtm-thesis                     LLM generates GTM thesis
  GET    /campaigns/{campaign_id}                  fetch one (REP: 404 if not own)
  PUT    /campaigns/{campaign_id}                  update
  DELETE /campaigns/{campaign_id}                  delete (204)
  POST   /campaigns/{campaign_id}/generate-sequences  LLM-write 7-touch sequence content

Role gate: Role.MANAGER for tenant-wide CRUD. The /my endpoint accepts Role.REP
so individual contributors can manage their own campaigns.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignListResponse,
    CampaignProspectLinkRequest,
    CampaignResponse,
    CampaignUpdate,
    CloneCampaignRequest,
    FrameworkRecommendRequest,
    FrameworkRecommendResponse,
    GtmThesisRequest,
    GtmThesisResponse,
    PreflightRequest,
    PreflightResult,
)
from app.features.campaigns.service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
_service = CampaignService()


def _role_value(token: TokenPayload) -> str:
    """Return the Role enum value as a plain string for service-level checks."""
    return token.role.value if hasattr(token.role, "value") else str(token.role)


# ── Per-angle word limits (matches frontend WORD_LIMITS exactly) ─────────────

_ANGLE_WORD_LIMITS: dict[str, int] = {
    "FirstTouch":      150,
    "NewEvidence":     120,
    "DifferentPain":   120,
    "IndustryInsight": 120,
    "DirectQuestion":   80,
    "Breakup":          60,
}

_ANGLE_INSTRUCTIONS: dict[str, str] = {
    "FirstTouch":
        "Opening cold email. Reference a specific trigger event or buying signal. "
        "Establish relevance immediately — no generic intros.",
    "NewEvidence":
        "Follow-up introducing new data, a case study, or a relevant metric the prospect cares about. "
        "Build on the first touch.",
    "DifferentPain":
        "Address a different pain point than touch 1. Show breadth of understanding of their challenges.",
    "IndustryInsight":
        "Lead with a relevant industry trend or insight. "
        "Position the sender as a knowledgeable peer, not a vendor.",
    "DirectQuestion":
        "Short, direct question that demands a reply. "
        "Example: 'Is pipeline velocity still a priority for Q3?' Max 80 words.",
    "Breakup":
        "Final breakup email. Polite, brief, no hard sell. Acknowledge it may not be the right time. "
        "Leave the door open.",
}


# ── LLM content generation helper ────────────────────────────────────────────

async def _generate_touch_content(
    db: AsyncSession,
    seq,
    *,
    prospect,
    campaign,
    icp,
    framework_override: str | None,
) -> tuple[str, str, int]:
    """
    Call the tenant's configured LLM to write one email touch.

    Returns (subject_line, body_copy, qa_score).
    Returns ("", "", 0) on any failure — caller keeps the skeleton row as Draft.
    """
    from app.services.llm_service import call_llm, get_default_llm_config, LlmGatewayError
    import structlog as _sl

    llm_config = await get_default_llm_config(db)
    if llm_config is None:
        _sl.get_logger(__name__).warning(
            "generate_sequences.no_llm_config",
            sequence_id=getattr(seq, "id", None),
        )
        return "", "", 0

    angle = seq.angle.value if hasattr(seq.angle, "value") else str(seq.angle)
    framework = framework_override or seq.framework or "AIDA"
    word_limit = _ANGLE_WORD_LIMITS.get(angle, 120)
    angle_instruction = _ANGLE_INSTRUCTIONS.get(angle, "Write a compelling cold outreach email.")

    # Prospect context
    p_name      = f"{prospect.firstName} {prospect.lastName}".strip()
    p_title     = prospect.title or "professional"
    p_company   = prospect.company or "their company"
    p_seniority = (
        prospect.seniority.value
        if hasattr(prospect.seniority, "value")
        else str(prospect.seniority)
    )

    # Buying signals — stored as JSON list on the Prospect model
    signals_raw = prospect.signals or []
    if isinstance(signals_raw, str):
        try:
            signals_raw = json.loads(signals_raw)
        except Exception:
            signals_raw = []
    signal_text = ""
    if signals_raw:
        first = signals_raw[0]
        signal_text = (
            f"Buying signal: {first}"
            if isinstance(first, str)
            else f"Buying signal: {first.get('signal') or str(first)}"
        )

    # Sender / ICP context
    sender_role    = (getattr(icp, "senderRole",    None) if icp else None) or getattr(campaign, "senderRole",    None) or "Account Executive"
    sender_company = (getattr(icp, "senderCompany", None) if icp else None) or getattr(campaign, "senderCompany", None) or "our company"
    sender_offer   = (getattr(icp, "senderOffer",   None) if icp else None) or ""
    proof_metric   = (getattr(icp, "proofMetric",   None) if icp else None) or ""
    persona_desc   = (getattr(icp, "persona",       None) if icp else None) or ""

    system_msg = (
        "You are an expert B2B cold email copywriter. "
        "Respond ONLY with a valid JSON object — no markdown fences, no preamble, no explanation."
    )

    user_msg = f"""Write touch #{seq.touchNumber} of a 7-touch cold email sequence.

PROSPECT
  Name: {p_name}
  Title: {p_title}
  Company: {p_company}
  Seniority: {p_seniority}
  {signal_text}

SENDER
  Role: {sender_role}
  Company: {sender_company}
  Offer: {sender_offer}
  Proof metric: {proof_metric}

ICP PERSONA: {persona_desc}

TOUCH INSTRUCTIONS
  Angle: {angle} — {angle_instruction}
  Framework: {framework}
  Word limit: {word_limit} words for the body (STRICT — do not exceed)
  Send day: {seq.sendDay}

Return JSON with exactly these four keys:
{{
  "subject": "subject line under 60 characters, no ALL CAPS",
  "body": "email body — {word_limit} words max, plain text, merge fields like {{{{first_name}}}} are allowed",
  "qa_score": integer 0-100,
  "personalisation_confidence": float 0.0-1.0
}}"""

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]

    try:
        response = await asyncio.wait_for(
            call_llm(llm_config, messages),
            timeout=45.0,
        )
        raw = response.content if hasattr(response, "content") else str(response)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        subject   = str(data.get("subject", "")).strip()
        body_copy = str(data.get("body", "")).strip()
        qa_score  = int(data.get("qa_score", 70))
        return subject, body_copy, qa_score
    except asyncio.TimeoutError:
        _sl.get_logger(__name__).warning(
            "generate_sequences.llm_timeout",
            sequence_id=getattr(seq, "id", None),
            touch=seq.touchNumber,
        )
        return "", "", 0
    except Exception as exc:  # noqa: BLE001
        _sl.get_logger(__name__).warning(
            "generate_sequences.llm_failed",
            sequence_id=getattr(seq, "id", None),
            touch=seq.touchNumber,
            angle=angle,
            error=str(exc),
        )
        return "", "", 0


# ── Request body for generate-sequences ──────────────────────────────────────

class _GenerateSequencesBody(BaseModel):
    """Optional JSON body for POST /{campaign_id}/generate-sequences.

    prospectId — when supplied, generate only for this specific prospect.
    framework  — override the sequence framework (optional).
    All extra fields sent by the frontend are silently ignored.
    """
    model_config = {"extra": "ignore"}
    prospectId: str | None = None
    framework: str | None = None


# ── Static routes (declared BEFORE /{campaign_id} per Pitfall #7) ───────────


@router.get("/my", response_model=CampaignListResponse)
async def list_my_campaigns(
    campaign_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> CampaignListResponse:
    """Return only the calling user's campaigns (always filtered by owner_user_id)."""
    items, total = await _service.list_campaigns(
        db,
        status=campaign_status,
        limit=limit,
        offset=offset,
        user_id=token.sub,
        role="REP",
    )
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/team", response_model=CampaignListResponse)
async def list_team_campaigns(
    campaign_status: str | None = Query(default=None, alias="status"),
    owner_user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignListResponse:
    """Return all tenant campaigns with owner info (MANAGER+ only)."""
    items, total = await _service.list_campaigns(
        db,
        status=campaign_status,
        limit=limit,
        offset=offset,
        user_id=None,
        role=_role_value(token),
    )
    if owner_user_id:
        items = [i for i in items if i.owner_user_id == owner_user_id]
        total = len(items)
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/campaign-prospects")
async def list_campaign_prospects(
    campaign_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> list[dict]:
    """Return all CampaignProspect rows for a campaign, enriched with prospect data."""
    from sqlalchemy import select as _select
    from app.models.campaign_models import CampaignProspect
    from app.models.prospect_models import Prospect

    result = await db.execute(
        _select(CampaignProspect).where(CampaignProspect.campaignId == campaign_id)
    )
    links = result.scalars().all()
    rows = []
    for link in links:
        p = (await db.execute(
            _select(Prospect).where(Prospect.id == link.prospectId)
        )).scalar_one_or_none()
        rows.append({
            "id": link.id,
            "campaignId": link.campaignId,
            "prospectId": link.prospectId,
            "status": link.status,
            "createdAt": link.createdAt.isoformat() if link.createdAt else None,
            "prospect": {
                "id": p.id,
                "firstName": p.firstName,
                "lastName": p.lastName,
                "email": p.email,
                "title": p.title,
                "company": p.company,
                "seniority": p.seniority,
            } if p else None,
        })
    return rows


@router.post("/campaign-prospects", status_code=201)
async def link_prospect(
    body: dict,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Link one or more prospects to a campaign.

    Accepts two body shapes:
      { campaignId, prospectId }           — singular (original form)
      { campaignId, prospectIds: [...] }   — plural array (sent by Sequence Builder)

    FIX: The Sequence Builder sends { prospectIds: [id], action: 'add' } but the
    old endpoint expected singular prospectId only. Pydantic silently dropped the
    array, so the link was never created and generate-sequences found zero linked
    prospects — producing empty sequences for manually-created prospects.
    """
    from app.features.sequences.service import SequenceService

    campaign_id: str = body.get("campaignId", "")
    if not campaign_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "campaignId is required.")

    raw_ids: list[str] = list(body.get("prospectIds") or [])
    singular = body.get("prospectId")
    if singular and singular not in raw_ids:
        raw_ids.insert(0, singular)
    if not raw_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "prospectId or prospectIds is required.",
        )

    seq_service = SequenceService()
    for pid in raw_ids:
        link_body = CampaignProspectLinkRequest(campaignId=campaign_id, prospectId=pid)
        await _service.link_prospect(db, link_body)
        try:
            await seq_service.auto_generate_for_campaign(
                db,
                campaign_id=campaign_id,
                prospect_id=pid,
                owner_user_id=token.sub,
            )
        except Exception as exc:  # noqa: BLE001
            import structlog as _sl
            _sl.get_logger(__name__).warning(
                "link_prospect.sequence_gen_failed",
                campaign_id=campaign_id,
                prospect_id=pid,
                error=str(exc),
            )

    return {"added": len(raw_ids), "prospectIds": raw_ids, "campaignId": campaign_id}


@router.delete(
    "/campaign-prospects", response_model=None, response_class=Response, status_code=204
)
async def unlink_prospect(
    body: CampaignProspectLinkRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.unlink_prospect(db, body)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign-prospect link not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/clone", response_model=CampaignResponse, status_code=201)
async def clone_campaign(
    body: CloneCampaignRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignResponse:
    """Clone a campaign — the clone's owner_user_id is the caller's token.sub."""
    item = await _service.clone(db, body, owner_user_id=token.sub)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source campaign not found.")
    return CampaignResponse.model_validate(item)


@router.post("/preflight", response_model=PreflightResult)
async def preflight(
    body: PreflightRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> PreflightResult:
    """6-check activation gate (sender, domain, ICP, LLM, MailBridge, prospects)."""
    return await _service.preflight(db, body)


@router.post("/framework-recommend", response_model=FrameworkRecommendResponse)
async def framework_recommend(
    body: FrameworkRecommendRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FrameworkRecommendResponse:
    """Ask the LLM to recommend a sales email framework for the campaign."""
    result = await _service.framework_recommend(db, body)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return result


@router.post("/gtm-thesis", response_model=GtmThesisResponse)
async def gtm_thesis(
    body: GtmThesisRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> GtmThesisResponse:
    """Ask the LLM to generate a GTM thesis for the campaign."""
    result = await _service.gtm_thesis(db, body)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return result


# ── Main CRUD endpoints ───────────────────────────────────────────────────────


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    campaign_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    # REP+ can list campaigns — the service layer filters by owner_user_id for
    # REPs (they only see their own) and returns all for MANAGER+.
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> CampaignListResponse:
    items, total = await _service.list_campaigns(
        db,
        status=campaign_status,
        limit=limit,
        offset=offset,
        user_id=token.sub,
        role=_role_value(token),
    )
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignResponse:
    """Create a campaign — owner_user_id is stamped from token.sub."""
    item = await _service.create(db, body, owner_user_id=token.sub)
    return CampaignResponse.model_validate(item)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    # REP+ can fetch a campaign — service enforces ownership (REPs only see their own).
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> CampaignResponse:
    item = await _service.get_for_user(
        db, campaign_id, user_id=token.sub, role=_role_value(token)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return CampaignResponse.model_validate(item)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignResponse:
    item = await _service.get_for_user(
        db, campaign_id, user_id=token.sub, role=_role_value(token)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    updated = await _service.update(db, campaign_id, body)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return CampaignResponse.model_validate(updated)


@router.delete("/{campaign_id}", response_model=None, response_class=Response, status_code=204)
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    item = await _service.get_for_user(
        db, campaign_id, user_id=token.sub, role=_role_value(token)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    ok = await _service.delete(db, campaign_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/generate-sequences", status_code=202)
async def generate_sequences(
    campaign_id: str,
    body: _GenerateSequencesBody = _GenerateSequencesBody(),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """
    Generate LLM-written 7-touch cadence Sequence rows for a campaign's prospects.

    FIXED (3 bugs corrected in this version):

    1. Accepts optional { prospectId } body — generates only for that one prospect.
       When omitted, generates for ALL linked prospects (original bulk behaviour).

    2. Self-heals missing CampaignProspect link — if prospectId is supplied but
       not yet linked (because the campaign-prospects call sent the wrong payload
       shape and was silently rejected), the link is created here before generation.

    3. LLM content generation — after skeleton rows are created (idempotent), each
       touch with null bodyCopy is sent to the tenant's configured LLM. The prompt
       includes prospect name/title/company/seniority/signals, sender/ICP context,
       touch angle with specific instructions, framework, and strict word limit.
       Touches are generated sequentially with a 5-second gap to respect rate limits.
    """
    from sqlalchemy import select as _select
    from app.models.campaign_models import CampaignProspect, Sequence as _Seq
    from app.models.prospect_models import Prospect as _Prospect, IcpProfile as _IcpProfile
    from app.features.sequences.service import SequenceService

    campaign = await _service.get_for_user(
        db, campaign_id, user_id=token.sub, role=_role_value(token)
    )
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")

    requested_prospect_id: str | None = body.prospectId or None

    # ── Self-heal: link the prospect if not already linked ───────────────────
    if requested_prospect_id:
        existing_link = (await db.execute(
            _select(CampaignProspect).where(
                CampaignProspect.campaignId == campaign_id,
                CampaignProspect.prospectId == requested_prospect_id,
            )
        )).scalar_one_or_none()
        if existing_link is None:
            await _service.link_prospect(
                db,
                CampaignProspectLinkRequest(
                    campaignId=campaign_id,
                    prospectId=requested_prospect_id,
                ),
            )

    # ── Determine which prospects to generate for ────────────────────────────
    all_linked = [
        row[0] for row in (await db.execute(
            _select(CampaignProspect.prospectId).where(
                CampaignProspect.campaignId == campaign_id
            )
        )).all()
    ]
    prospect_ids = [requested_prospect_id] if requested_prospect_id else all_linked
    if not prospect_ids:
        return {"message": "No prospects linked to this campaign.", "created": 0}

    # ── Step 1: create skeleton Sequence rows (idempotent) ───────────────────
    # IMPORTANT: auto_generate_for_campaign() calls db.commit() internally.
    # After commit, asyncpg returns the connection to the pool and the
    # search_path resets to the pool default ("public"). We must re-set it
    # explicitly after every commit() or all subsequent queries on _Seq
    # will fail with UndefinedTableError: relation "Sequence" does not exist.
    from sqlalchemy import text as _text
    from fastapi import Request as _Request

    # _reset_search_path: re-execute SET search_path after every db.commit().
    # asyncpg returns the physical connection to the pool on commit, resetting
    # search_path to "public". All subsequent ORM queries on tenant tables then
    # fail with UndefinedTableError. Re-setting it after each commit restores
    # the correct tenant schema context.
    #
    # We derive the schema from token.tenant_slug (always "tenant_{slug}")
    # to avoid needing request.state (which caused a 422 when added to the
    # FastAPI endpoint signature — FastAPI treated it as a query parameter).
    _slug = getattr(token, "tenant_slug", None) or ""
    _schema = f"tenant_{_slug}" if _slug else "public"

    async def _reset_search_path() -> None:
        """Re-set search_path to tenant schema after db.commit()."""
        await db.execute(_text(f'SET search_path TO "{_schema}", public'))

    seq_service = SequenceService()
    total_created = 0
    for pid in prospect_ids:
        created = await seq_service.auto_generate_for_campaign(
            db, campaign_id, prospect_id=pid, owner_user_id=token.sub,
        )
        total_created += len(created)
    # Restore search_path after auto_generate_for_campaign's internal commit
    await _reset_search_path()

    # Restamp any "system"-owned rows so per-user list queries see them
    restamp_stmt = _select(_Seq).where(
        _Seq.campaignId == campaign_id,
        _Seq.owner_user_id == "system",
    )
    if requested_prospect_id:
        restamp_stmt = restamp_stmt.where(_Seq.prospectId == requested_prospect_id)
    restamped = 0
    for seq in (await db.execute(restamp_stmt)).scalars().all():
        seq.owner_user_id = token.sub
        restamped += 1
    if restamped:
        await db.commit()
        await _reset_search_path()  # Restore after restamp commit

    # ── Step 2: LLM content generation for touches with no body copy ─────────
    # Includes both newly created rows AND pre-existing empty rows from before
    # this fix was deployed — re-triggering Generate fills them all.
    fill_stmt = _select(_Seq).where(
        _Seq.campaignId == campaign_id,
        _Seq.bodyCopy.is_(None),
    )
    if requested_prospect_id:
        fill_stmt = fill_stmt.where(_Seq.prospectId == requested_prospect_id)
    fill_stmt = fill_stmt.order_by(_Seq.prospectId, _Seq.touchNumber)
    seqs_to_fill: list = list((await db.execute(fill_stmt)).scalars().all())

    llm_filled = 0
    if seqs_to_fill:
        # Load campaign ICP profile once
        icp = None
        if campaign.icpProfileId:
            icp = (await db.execute(
                _select(_IcpProfile).where(_IcpProfile.id == campaign.icpProfileId)
            )).scalar_one_or_none()

        # Cache prospect rows to avoid repeated DB hits
        prospect_cache: dict[str, object] = {}

        for i, seq in enumerate(seqs_to_fill):
            if seq.prospectId not in prospect_cache:
                p = (await db.execute(
                    _select(_Prospect).where(_Prospect.id == seq.prospectId)
                )).scalar_one_or_none()
                if p:
                    prospect_cache[seq.prospectId] = p

            prospect = prospect_cache.get(seq.prospectId)
            if prospect is None:
                continue

            subject, body_copy, qa_score = await _generate_touch_content(
                db,
                seq,
                prospect=prospect,
                campaign=campaign,
                icp=icp,
                framework_override=body.framework,
            )

            if subject or body_copy:
                seq.subjectLine = subject or None
                seq.bodyCopy    = body_copy or None
                seq.qaScore     = qa_score or None
                llm_filled += 1

            # 5-second gap between LLM calls to respect Groq free-tier rate limits.
            # Remove or reduce this delay if you are on a paid tier / using OpenAI.
            if i < len(seqs_to_fill) - 1:
                await asyncio.sleep(5)

        if llm_filled:
            await db.commit()
            await _reset_search_path()

    return {
        "message": (
            f"Generated {total_created} new sequence rows for {len(prospect_ids)} prospect(s). "
            f"LLM filled {llm_filled} touches."
            + (f" Restamped {restamped} existing sequences." if restamped else "")
        ),
        "created": total_created,
        "llm_filled": llm_filled,
        "restamped": restamped,
        "prospects": len(prospect_ids),
    }


__all__ = ["router"]