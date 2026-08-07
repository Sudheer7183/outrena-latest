"""
campaigns.py — Phase 2 /api/v1/campaigns router.

Endpoints:
  GET    /campaigns                                list (REP sees own; MANAGER+ sees all)
  GET    /campaigns/my                             list current user's campaigns (convenience)
  GET    /campaigns/team                           MANAGER+ rollup with owner info
  POST   /campaigns                                create (stamps owner_user_id = token.sub)
  POST   /campaigns/campaign-prospects             link prospect
  DELETE /campaigns/campaign-prospects             unlink prospect (204)
  POST   /campaigns/clone                          clone campaign
  POST   /campaigns/preflight                      6-check gate
  POST   /campaigns/framework-recommend            LLM recommends framework
  POST   /campaigns/gtm-thesis                     LLM generates GTM thesis
  GET    /campaigns/{campaign_id}                  fetch one (REP: 404 if not own)
  PUT    /campaigns/{campaign_id}                  update
  DELETE /campaigns/{campaign_id}                  delete (204)

Role gate: Role.MANAGER for tenant-wide CRUD. The /my endpoint accepts Role.REP
so individual contributors can manage their own campaigns.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
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
        role="REP",  # force per-user filter regardless of caller role
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
    owner_user_id: str | None = Query(
        default=None,
        description="Filter to a specific user (MANAGER+ only). Omit for all.",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignListResponse:
    """Return all tenant campaigns with owner info (MANAGER+ only).

    Optional ``?owner_user_id=`` filter restricts to one user's campaigns.
    """
    # MANAGER+ sees everything (no REP filter); the optional owner_user_id
    # query param is an explicit filter, not an ACL.
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


@router.post("/campaign-prospects", response_model=CampaignResponse)
async def link_prospect(
    body: CampaignProspectLinkRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignResponse:
    """Link a prospect to a campaign; returns the refreshed campaign."""
    await _service.link_prospect(db, body)
    item = await _service.get(db, body.campaignId)
    if item is None:  # defensive — should not happen after link
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return CampaignResponse.model_validate(item)


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
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Campaign-prospect link not found.",
        )
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
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Source campaign not found."
        )
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


# ── Main CRUD endpoints ────────────────────────────────────────────────────


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    campaign_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignListResponse:
    """List campaigns.

    REP tokens see only their own campaigns (filtered by owner_user_id).
    MANAGER+ tokens see all tenant campaigns.
    """
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
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> CampaignResponse:
    """Fetch one campaign. REP tokens receive 404 for campaigns they don't own."""
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
    """Update a campaign. REP tokens receive 404 for campaigns they don't own."""
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
    """Delete a campaign. REP tokens receive 404 for campaigns they don't own."""
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
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """
    Bulk-generate the 7-touch cadence Sequence rows for ALL prospects already
    linked to this campaign (FR-E4-006).

    This endpoint is idempotent — existing Sequence rows for a
    (campaignId, prospectId, touchNumber) combination are skipped.
    Returns the count of newly-created sequences.

    Callers should poll GET /campaigns/{id} or GET /sequences?campaign_id=…
    to see results; this endpoint returns 202 immediately (the work is
    done synchronously but framed as 202 to signal it may be slow for
    large prospect lists).
    """
    from sqlalchemy import select as _select
    from app.models.campaign_models import CampaignProspect
    from app.features.sequences.service import SequenceService

    campaign = await _service.get_for_user(
        db, campaign_id, user_id=token.sub, role=_role_value(token)
    )
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")

    # Get all prospect IDs linked to this campaign.
    result = await db.execute(
        _select(CampaignProspect.prospectId).where(
            CampaignProspect.campaignId == campaign_id
        )
    )
    prospect_ids = [row[0] for row in result.all()]
    if not prospect_ids:
        return {"message": "No prospects linked to this campaign.", "created": 0}

    seq_service = SequenceService()
    total_created = 0
    for pid in prospect_ids:
        created = await seq_service.auto_generate_for_campaign(
            db,
            campaign_id,
            prospect_id=pid,
            owner_user_id=token.sub,
        )
        total_created += len(created)

    return {
        "message": f"Generated {total_created} sequence rows for {len(prospect_ids)} prospect(s).",
        "created": total_created,
        "prospects": len(prospect_ids),
    }


__all__ = ["router"]
