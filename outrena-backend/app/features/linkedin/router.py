"""
linkedin.py — Phase 3 /api/v1/linkedin router.

Endpoints:
  GET    /linkedin/config                list configs
  POST   /linkedin/config                create config
  GET    /linkedin/config/{id}           fetch one
  PUT    /linkedin/config/{id}           update
  DELETE /linkedin/config/{id}           delete
  GET    /linkedin/engagements           list engagements
  POST   /linkedin/engagements           create engagement
  PUT    /linkedin/engagements/{id}      update (status, executedAt)
  GET    /linkedin/inbox                 list inbox messages (filter by status)
  POST   /linkedin/inbox/triage          bulk-update status
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.common import MessageResponse
from app.schemas.linkedin import (
    IcpMatchRequest,
    IcpMatchResponse,
    LinkedInConfigCreate,
    LinkedInConfigResponse,
    LinkedInConfigUpdate,
    LinkedInEngagementCreate,
    LinkedInEngagementResponse,
    LinkedInEngagementUpdate,
    LinkedInInboxMessageResponse,
    LinkedInInboxTriageRequest,
)
from app.features.linkedin.service import LinkedInService

# ── Internal child routers ─────────────────────────────────────────────────
# `_linkedin_router` carries the canonical /linkedin/* endpoints.
# `_alias_router` carries the spec-path aliases /linkedin-config,
# /linkedin-engagement, /linkedin-inbox (audit Recommendation #3).
# Public parent `router` (no prefix) mounts both at the bottom of this file.
_linkedin_router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])
_alias_router = APIRouter(prefix="", tags=["LinkedIn"])
router = APIRouter(tags=["LinkedIn"])
_service = LinkedInService()


# ── Config ─────────────────────────────────────────────────────────────────
@_linkedin_router.get("/config", response_model=list[LinkedInConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[LinkedInConfigResponse]:
    items = await _service.list_configs(db)
    return [LinkedInConfigResponse.model_validate(i) for i in items]


@_linkedin_router.post("/config", response_model=LinkedInConfigResponse, status_code=201)
async def create_config(
    body: LinkedInConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> LinkedInConfigResponse:
    item = await _service.create_config(db, body)
    return LinkedInConfigResponse.model_validate(item)


@_linkedin_router.get("/config/{config_id}", response_model=LinkedInConfigResponse)
async def get_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> LinkedInConfigResponse:
    item = await _service.get_config(db, config_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return LinkedInConfigResponse.model_validate(item)


@_linkedin_router.put("/config/{config_id}", response_model=LinkedInConfigResponse)
async def update_config(
    config_id: str,
    body: LinkedInConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> LinkedInConfigResponse:
    item = await _service.update_config(db, config_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return LinkedInConfigResponse.model_validate(item)


@_linkedin_router.delete("/config/{config_id}", response_model=None, response_class=Response, status_code=204)
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _service.delete_config(db, config_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Engagements ────────────────────────────────────────────────────────────
@_linkedin_router.get("/engagements", response_model=list[LinkedInEngagementResponse])
async def list_engagements(
    prospect_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[LinkedInEngagementResponse]:
    items = await _service.list_engagements(db, prospect_id=prospect_id)
    return [LinkedInEngagementResponse.model_validate(i) for i in items]


@_linkedin_router.post("/engagements", response_model=LinkedInEngagementResponse, status_code=201)
async def create_engagement(
    body: LinkedInEngagementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role(Role.REP)),
) -> LinkedInEngagementResponse:
    # Task 3-a / FIX 2: pass the current user's Keycloak sub to
    # create_engagement so it's stamped onto the new engagement's
    # owner_user_id column (added by migration 0011) + used for per-user
    # usage attribution in _record_usage.
    item = await _service.create_engagement(db, body, user_id=current_user.sub)
    return LinkedInEngagementResponse.model_validate(item)


@_linkedin_router.put("/engagements/{engagement_id}", response_model=LinkedInEngagementResponse)
async def update_engagement(
    engagement_id: str,
    body: LinkedInEngagementUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> LinkedInEngagementResponse:
    item = await _service.update_engagement(db, engagement_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engagement not found.")
    return LinkedInEngagementResponse.model_validate(item)


# ── Inbox ──────────────────────────────────────────────────────────────────
@_linkedin_router.get("/inbox", response_model=list[LinkedInInboxMessageResponse])
async def list_inbox(
    inbox_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[LinkedInInboxMessageResponse]:
    items = await _service.list_inbox(db, status=inbox_status)
    return [LinkedInInboxMessageResponse.model_validate(i) for i in items]


@_linkedin_router.post("/inbox/triage")
async def triage_inbox(
    body: LinkedInInboxTriageRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MessageResponse:
    count = await _service.triage(db, body)
    return MessageResponse(message=f"Triage complete: {count} message(s) updated.")


@_linkedin_router.post("/engagements/check-icp", response_model=IcpMatchResponse)
async def check_icp_matches(
    body: IcpMatchRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> IcpMatchResponse:
    """Batch-check LinkedIn engagements against ICP profiles using LLM."""
    return await _service.check_icp_matches(db, body)


# ── Compatibility alias routes (audit Recommendation #3) ───────────────────
# The migration-doc spec table uses hyphenated paths ``/api/linkedin-config``,
# ``/api/linkedin-engagement``, ``/api/linkedin-inbox`` (L226, L1004-1006) but
# the canonical implementation lives under ``/linkedin/{config,engagements,inbox}``
# (path-style). These aliases expose the spec paths with distinct operationIds
# (``_alias`` suffix) so they show up separately in OpenAPI / Swagger UI.
# Each alias delegates to the same service method so behaviour is identical to
# the canonical route.


# ── /linkedin-config (spec alias for /linkedin/config) ─────────────────────
@_alias_router.get(
    "/linkedin-config",
    response_model=list[LinkedInConfigResponse],
    operation_id="list_linkedin_configs_alias",
)
async def list_configs_alias(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[LinkedInConfigResponse]:
    items = await _service.list_configs(db)
    return [LinkedInConfigResponse.model_validate(i) for i in items]


@_alias_router.post(
    "/linkedin-config",
    response_model=LinkedInConfigResponse,
    status_code=201,
    operation_id="create_linkedin_config_alias",
)
async def create_config_alias(
    body: LinkedInConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> LinkedInConfigResponse:
    item = await _service.create_config(db, body)
    return LinkedInConfigResponse.model_validate(item)


@_alias_router.get(
    "/linkedin-config/{config_id}",
    response_model=LinkedInConfigResponse,
    operation_id="get_linkedin_config_alias",
)
async def get_config_alias(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> LinkedInConfigResponse:
    item = await _service.get_config(db, config_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return LinkedInConfigResponse.model_validate(item)


@_alias_router.put(
    "/linkedin-config/{config_id}",
    response_model=LinkedInConfigResponse,
    operation_id="update_linkedin_config_alias",
)
async def update_config_alias(
    config_id: str,
    body: LinkedInConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> LinkedInConfigResponse:
    item = await _service.update_config(db, config_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return LinkedInConfigResponse.model_validate(item)


@_alias_router.delete(
    "/linkedin-config/{config_id}",
    response_model=None,
    response_class=Response,
    operation_id="delete_linkedin_config_alias",
    status_code=204,
)
async def delete_config_alias(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _service.delete_config(db, config_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LinkedIn config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── /linkedin-engagement (spec alias for /linkedin/engagements) ───────────
@_alias_router.get(
    "/linkedin-engagement",
    response_model=list[LinkedInEngagementResponse],
    operation_id="list_linkedin_engagements_alias",
)
async def list_engagements_alias(
    prospect_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[LinkedInEngagementResponse]:
    items = await _service.list_engagements(db, prospect_id=prospect_id)
    return [LinkedInEngagementResponse.model_validate(i) for i in items]


@_alias_router.post(
    "/linkedin-engagement",
    response_model=LinkedInEngagementResponse,
    status_code=201,
    operation_id="create_linkedin_engagement_alias",
)
async def create_engagement_alias(
    body: LinkedInEngagementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role(Role.REP)),
) -> LinkedInEngagementResponse:
    # Task 3-a / FIX 2: pass current_user.sub so the engagement is
    # attributed to the real caller (not "system").
    item = await _service.create_engagement(db, body, user_id=current_user.sub)
    return LinkedInEngagementResponse.model_validate(item)


# ── /linkedin-inbox (spec alias for /linkedin/inbox) ──────────────────────
@_alias_router.get(
    "/linkedin-inbox",
    response_model=list[LinkedInInboxMessageResponse],
    operation_id="list_linkedin_inbox_alias",
)
async def list_inbox_alias(
    inbox_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[LinkedInInboxMessageResponse]:
    items = await _service.list_inbox(db, status=inbox_status)
    return [LinkedInInboxMessageResponse.model_validate(i) for i in items]


@_alias_router.post(
    "/linkedin-inbox",
    response_model=MessageResponse,
    operation_id="triage_linkedin_inbox_alias",
)
async def triage_inbox_alias(
    body: LinkedInInboxTriageRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> MessageResponse:
    count = await _service.triage(db, body)
    return MessageResponse(message=f"Triage complete: {count} message(s) updated.")


# Mount the child routers into the public parent router. The canonical
# routes live at /linkedin/{config,engagements,inbox} and the spec aliases
# live at /linkedin-{config,engagement,inbox} (no /linkedin prefix).
router.include_router(_linkedin_router)
router.include_router(_alias_router)
