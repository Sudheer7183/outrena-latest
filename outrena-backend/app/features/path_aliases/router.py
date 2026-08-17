# """
# path_aliases/router.py — Short-path aliases for frontend compatibility.

# The frontend apiClient.ts calls several endpoints at flat/short paths that
# differ from the backend's canonical nested paths. Rather than touching every
# existing router, all aliases are consolidated here so the mismatch surface
# is visible in one place.

# Alias map (frontend path → backend canonical path):
#   POST /framework-recommend       → POST /campaigns/framework-recommend
#   POST /gtm-thesis                → POST /campaigns/gtm-thesis
#   POST /icp-auto-discover         → POST /icp-profiles/auto-discover
#   POST /icp-suggest               → POST /icp-profiles/suggest
#   POST /dns-check                 → POST /domains/dns-check
#   GET  /flow-webhooks             → GET  /flows/webhooks
#   POST /flow-webhooks             → POST /flows/webhooks
#   POST /test-llm                  → POST /llm-configs/test-llm
#   POST /prospecting-test          → POST /integrations/test
#   POST /competitor-radar          → POST /competitors (scan stub)
#   GET  /feature-permissions       → GET  /permissions/feature-permissions
#   PUT  /feature-permissions/{key} → PUT  /permissions/feature-permissions/{key}

# Each alias delegates directly to the same service layer — no business logic
# lives here. All auth requirements match the canonical endpoint.
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db, get_db_public
# from app.api.security import get_current_user, require_role
# from app.schemas.auth import Role, TokenPayload

# # ── Service imports ─────────────────────────────────────────────────────────
# from app.features.campaigns.service import CampaignService
# from app.features.icp.service import IcpService
# from app.features.domains.service import DomainService
# from app.features.flows.service import FlowRunService
# from app.features.llm_config.service import LlmConfigService
# from app.features.integrations.service import IntegrationService
# from app.services.rbac_service import RbacService

# # ── Schema imports ───────────────────────────────────────────────────────────
# from app.schemas.campaigns import (
#     FrameworkRecommendRequest,
#     FrameworkRecommendResponse,
#     GtmThesisRequest,
#     GtmThesisResponse,
# )
# from app.schemas.icp import (
#     AutoDiscoverRequest,
#     AutoDiscoverResponse,
#     IcpSuggestRequest,
#     IcpSuggestResponse,
# )
# from app.schemas.domains import DnsCheckRequest, DnsCheckResult
# from app.schemas.flow_run import (
#     FlowWebhookCreate,
#     FlowWebhookListResponse,
#     FlowWebhookResponse,
# )
# from app.schemas.llm_config import TestLlmRequest, TestLlmResponse
# from app.schemas.integrations import (
#     IntegrationTestRequest,
#     IntegrationTestResponse,
# )

# # ── Service singletons ───────────────────────────────────────────────────────
# _campaign_svc = CampaignService()
# _icp_svc = IcpService()
# _domain_svc = DomainService()
# _flow_svc = FlowRunService()
# _llm_svc = LlmConfigService()
# _integration_svc = IntegrationService()
# _rbac_svc = RbacService()

# router = APIRouter(tags=["Path Aliases"])


# # ── /framework-recommend ─────────────────────────────────────────────────────

# @router.post(
#     "/framework-recommend",
#     response_model=FrameworkRecommendResponse,
#     operation_id="alias_framework_recommend",
# )
# async def alias_framework_recommend(
#     body: FrameworkRecommendRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FrameworkRecommendResponse:
#     """Alias: POST /framework-recommend → POST /campaigns/framework-recommend."""
#     result = await _campaign_svc.framework_recommend(db, body)
#     if result is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return result


# # ── /gtm-thesis ──────────────────────────────────────────────────────────────

# @router.post(
#     "/gtm-thesis",
#     response_model=GtmThesisResponse,
#     operation_id="alias_gtm_thesis",
# )
# async def alias_gtm_thesis(
#     body: GtmThesisRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> GtmThesisResponse:
#     """Alias: POST /gtm-thesis → POST /campaigns/gtm-thesis."""
#     result = await _campaign_svc.gtm_thesis(db, body)
#     if result is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
#     return result


# # ── /icp-auto-discover ───────────────────────────────────────────────────────

# @router.post(
#     "/icp-auto-discover",
#     response_model=AutoDiscoverResponse,
#     operation_id="alias_icp_auto_discover",
# )
# async def alias_icp_auto_discover(
#     body: AutoDiscoverRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> AutoDiscoverResponse:
#     """Alias: POST /icp-auto-discover → POST /icp-profiles/auto-discover."""
#     return await _icp_svc.auto_discover(db, body)


# # ── /icp-suggest ─────────────────────────────────────────────────────────────

# @router.post(
#     "/icp-suggest",
#     response_model=IcpSuggestResponse,
#     operation_id="alias_icp_suggest",
# )
# async def alias_icp_suggest(
#     body: IcpSuggestRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IcpSuggestResponse:
#     """Alias: POST /icp-suggest → POST /icp-profiles/suggest."""
#     return await _icp_svc.suggest(db, body)


# # ── /dns-check ───────────────────────────────────────────────────────────────

# @router.post(
#     "/dns-check",
#     response_model=DnsCheckResult,
#     operation_id="alias_dns_check",
# )
# async def alias_dns_check(
#     body: DnsCheckRequest,
#     _db: AsyncSession = Depends(get_db),
#     __: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> DnsCheckResult:
#     """Alias: POST /dns-check → POST /domains/dns-check."""
#     return await _domain_svc.dns_check(body)


# # ── /flow-webhooks ───────────────────────────────────────────────────────────

# @router.get(
#     "/flow-webhooks",
#     response_model=FlowWebhookListResponse,
#     operation_id="alias_list_flow_webhooks",
# )
# async def alias_list_flow_webhooks(
#     flow_id: str | None = Query(default=None),
#     is_active: bool | None = Query(default=None),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowWebhookListResponse:
#     """Alias: GET /flow-webhooks → GET /flows/webhooks."""
#     items, total = await _flow_svc.list_webhooks(
#         db, flow_id=flow_id, is_active=is_active, limit=limit, offset=offset
#     )
#     return FlowWebhookListResponse(
#         items=[FlowWebhookResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post(
#     "/flow-webhooks",
#     response_model=FlowWebhookResponse,
#     status_code=201,
#     operation_id="alias_create_flow_webhook",
# )
# async def alias_create_flow_webhook(
#     body: FlowWebhookCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowWebhookResponse:
#     """Alias: POST /flow-webhooks → POST /flows/webhooks."""
#     item = await _flow_svc.create_webhook(db, body)
#     return FlowWebhookResponse.model_validate(item)


# # ── /test-llm ────────────────────────────────────────────────────────────────

# @router.post(
#     "/test-llm",
#     response_model=TestLlmResponse,
#     operation_id="alias_test_llm",
# )
# async def alias_test_llm(
#     body: TestLlmRequest,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
# ) -> TestLlmResponse:
#     """Alias: POST /test-llm → POST /llm-configs/test-llm."""
#     return await _llm_svc.test_llm(db, body)


# # ── /prospecting-test ────────────────────────────────────────────────────────

# @router.post(
#     "/prospecting-test",
#     response_model=IntegrationTestResponse,
#     operation_id="alias_prospecting_test",
# )
# async def alias_prospecting_test(
#     body: IntegrationTestRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IntegrationTestResponse:
#     """Alias: POST /prospecting-test → POST /integrations/test."""
#     return await _integration_svc.test(db, body)


# # ── /competitor-radar ────────────────────────────────────────────────────────

# @router.post(
#     "/competitor-radar",
#     response_model=list[dict],
#     operation_id="competitor_radar_scan",
# )
# async def competitor_radar_scan(
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[dict]:
#     """Trigger a competitor mention radar scan.

#     Returns newly detected mentions. In the current implementation the scan
#     is a stub — the competitive intelligence signal pipeline (Phase 4) will
#     populate this with real LinkedIn/web mention data. Returns an empty list
#     so the frontend gracefully shows "no new mentions" rather than crashing.
#     """
#     # DEFERRED: full web/LinkedIn mention scan — Phase 4 competitive signals.
#     # The frontend falls back to MOCK_NEW_MENTIONS when this returns [].
#     return []


# # ── /feature-permissions ─────────────────────────────────────────────────────

# class _FeaturePermissionResponse:
#     """Inline schema — mirrors permissions.py:FeaturePermissionResponse."""


# from pydantic import BaseModel, ConfigDict


# class FeaturePermissionResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     feature_key: str
#     required_permission: str | None
#     description: str


# class FeaturePermissionUpdateRequest(BaseModel):
#     required_permission: str | None = None


# @router.get(
#     "/feature-permissions",
#     response_model=list[FeaturePermissionResponse],
#     operation_id="alias_list_feature_permissions",
# )
# async def alias_list_feature_permissions(
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(get_current_user),
# ) -> list[FeaturePermissionResponse]:
#     """Alias: GET /feature-permissions → GET /permissions/feature-permissions."""
#     rows = await _rbac_svc.list_feature_permissions(db)
#     return [FeaturePermissionResponse(**r) for r in rows]


# @router.put(
#     "/feature-permissions/{feature_key}",
#     response_model=FeaturePermissionResponse,
#     operation_id="alias_set_feature_permission",
# )
# async def alias_set_feature_permission(
#     feature_key: str,
#     body: FeaturePermissionUpdateRequest,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
# ) -> FeaturePermissionResponse:
#     """Alias: PUT /feature-permissions/{key} → PUT /permissions/feature-permissions/{key}."""
#     result = await _rbac_svc.set_feature_permission(
#         db,
#         feature_key=feature_key,
#         required_permission=body.required_permission,
#     )
#     return FeaturePermissionResponse(**result)


# __all__ = ["router"]

"""
path_aliases/router.py — Short-path aliases for frontend compatibility.

The frontend apiClient.ts calls several endpoints at flat/short paths that
differ from the backend's canonical nested paths. Rather than touching every
existing router, all aliases are consolidated here so the mismatch surface
is visible in one place.

Alias map (frontend path → backend canonical path):
  POST /framework-recommend       → POST /campaigns/framework-recommend
  POST /gtm-thesis                → POST /campaigns/gtm-thesis
  POST /icp-auto-discover         → POST /icp-profiles/auto-discover
  POST /icp-suggest               → POST /icp-profiles/suggest
  POST /dns-check                 → POST /domains/dns-check
  GET  /flow-webhooks             → GET  /flows/webhooks
  POST /flow-webhooks             → POST /flows/webhooks
  POST /test-llm                  → POST /llm-configs/test-llm
  POST /prospecting-test          → POST /integrations/test
  POST /competitor-radar          → POST /competitors (scan stub)
  GET  /feature-permissions       → GET  /permissions/feature-permissions
  PUT  /feature-permissions/{key} → PUT  /permissions/feature-permissions/{key}

Each alias delegates directly to the same service layer — no business logic
lives here. All auth requirements match the canonical endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_db_public
from app.api.security import get_current_user, require_role
from app.schemas.auth import Role, TokenPayload

# ── Service imports ─────────────────────────────────────────────────────────
from app.features.campaigns.service import CampaignService
from app.features.icp.service import IcpService
from app.features.domains.service import DomainService
from app.features.flows.service import FlowRunService
from app.features.llm_config.service import LlmConfigService
from app.features.integrations.service import IntegrationService
from app.services.rbac_service import RbacService

# ── Schema imports ───────────────────────────────────────────────────────────
from app.schemas.campaigns import (
    FrameworkRecommendRequest,
    FrameworkRecommendResponse,
    GtmThesisRequest,
    GtmThesisResponse,
)
from app.schemas.icp import (
    AutoDiscoverRequest,
    AutoDiscoverResponse,
    IcpSuggestRequest,
    IcpSuggestResponse,
)
from app.schemas.domains import DnsCheckRequest, DnsCheckResult
from app.schemas.flow_run import (
    FlowWebhookCreate,
    FlowWebhookListResponse,
    FlowWebhookResponse,
)
from app.schemas.llm_config import TestLlmRequest, TestLlmResponse
from app.schemas.integrations import (
    IntegrationTestRequest,
    IntegrationTestResponse,
)

# ── Service singletons ───────────────────────────────────────────────────────
_campaign_svc = CampaignService()
_icp_svc = IcpService()
_domain_svc = DomainService()
_flow_svc = FlowRunService()
_llm_svc = LlmConfigService()
_integration_svc = IntegrationService()
_rbac_svc = RbacService()

router = APIRouter(tags=["Path Aliases"])


# ── /framework-recommend ─────────────────────────────────────────────────────

@router.post(
    "/framework-recommend",
    response_model=FrameworkRecommendResponse,
    operation_id="alias_framework_recommend",
)
async def alias_framework_recommend(
    body: FrameworkRecommendRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FrameworkRecommendResponse:
    """Alias: POST /framework-recommend → POST /campaigns/framework-recommend."""
    result = await _campaign_svc.framework_recommend(db, body)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return result


# ── /gtm-thesis ──────────────────────────────────────────────────────────────

@router.post(
    "/gtm-thesis",
    response_model=GtmThesisResponse,
    operation_id="alias_gtm_thesis",
)
async def alias_gtm_thesis(
    body: GtmThesisRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> GtmThesisResponse:
    """Alias: POST /gtm-thesis → POST /campaigns/gtm-thesis."""
    result = await _campaign_svc.gtm_thesis(db, body)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found.")
    return result


# ── /icp-auto-discover ───────────────────────────────────────────────────────

@router.post(
    "/icp-auto-discover",
    response_model=AutoDiscoverResponse,
    operation_id="alias_icp_auto_discover",
)
async def alias_icp_auto_discover(
    body: AutoDiscoverRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutoDiscoverResponse:
    """Alias: POST /icp-auto-discover → POST /icp-profiles/auto-discover."""
    return await _icp_svc.auto_discover(db, body)


# ── /icp-suggest ─────────────────────────────────────────────────────────────

@router.post(
    "/icp-suggest",
    response_model=IcpSuggestResponse,
    operation_id="alias_icp_suggest",
)
async def alias_icp_suggest(
    body: IcpSuggestRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IcpSuggestResponse:
    """Alias: POST /icp-suggest → POST /icp-profiles/suggest."""
    return await _icp_svc.suggest(db, body)


# ── /dns-check ───────────────────────────────────────────────────────────────

@router.post(
    "/dns-check",
    response_model=DnsCheckResult,
    operation_id="alias_dns_check",
)
async def alias_dns_check(
    body: DnsCheckRequest,
    _db: AsyncSession = Depends(get_db),
    __: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DnsCheckResult:
    """Alias: POST /dns-check → POST /domains/dns-check."""
    return await _domain_svc.dns_check(body)


# ── /flow-webhooks ───────────────────────────────────────────────────────────

@router.get(
    "/flow-webhooks",
    response_model=FlowWebhookListResponse,
    operation_id="alias_list_flow_webhooks",
)
async def alias_list_flow_webhooks(
    flow_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowWebhookListResponse:
    """Alias: GET /flow-webhooks → GET /flows/webhooks."""
    items, total = await _flow_svc.list_webhooks(
        db, flow_id=flow_id, is_active=is_active, limit=limit, offset=offset
    )
    return FlowWebhookListResponse(
        items=[FlowWebhookResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/flow-webhooks",
    response_model=FlowWebhookResponse,
    status_code=201,
    operation_id="alias_create_flow_webhook",
)
async def alias_create_flow_webhook(
    body: FlowWebhookCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowWebhookResponse:
    """Alias: POST /flow-webhooks → POST /flows/webhooks."""
    item = await _flow_svc.create_webhook(db, body)
    return FlowWebhookResponse.model_validate(item)


# ── /test-llm ────────────────────────────────────────────────────────────────

@router.post(
    "/test-llm",
    response_model=TestLlmResponse,
    operation_id="alias_test_llm",
)
async def alias_test_llm(
    body: TestLlmRequest,
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> TestLlmResponse:
    """Alias: POST /test-llm → POST /llm-configs/test-llm."""
    return await _llm_svc.test_llm(db, body)


# ── /prospecting-test ────────────────────────────────────────────────────────

@router.post(
    "/prospecting-test",
    response_model=IntegrationTestResponse,
    operation_id="alias_prospecting_test",
)
async def alias_prospecting_test(
    body: IntegrationTestRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IntegrationTestResponse:
    """Alias: POST /prospecting-test → POST /integrations/test."""
    return await _integration_svc.test(db, body)


# ── /competitor-radar ────────────────────────────────────────────────────────

@router.post(
    "/competitor-radar",
    response_model=list[dict],
    operation_id="competitor_radar_scan",
)
async def competitor_radar_scan(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> list[dict]:
    """Trigger a competitor mention radar scan.

    Returns newly detected mentions. In the current implementation the scan
    is a stub — the competitive intelligence signal pipeline (Phase 4) will
    populate this with real LinkedIn/web mention data. Returns an empty list
    so the frontend gracefully shows "no new mentions" rather than crashing.
    """
    # DEFERRED: full web/LinkedIn mention scan — Phase 4 competitive signals.
    # The frontend falls back to MOCK_NEW_MENTIONS when this returns [].
    return []


# ── /feature-permissions ─────────────────────────────────────────────────────

class _FeaturePermissionResponse:
    """Inline schema — mirrors permissions.py:FeaturePermissionResponse."""


from pydantic import BaseModel, ConfigDict


class FeaturePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature_key: str
    required_permission: str | None
    description: str


class FeaturePermissionUpdateRequest(BaseModel):
    required_permission: str | None = None


@router.get(
    "/feature-permissions",
    response_model=list[FeaturePermissionResponse],
    operation_id="alias_list_feature_permissions",
)
async def alias_list_feature_permissions(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[FeaturePermissionResponse]:
    """Alias: GET /feature-permissions → GET /permissions/feature-permissions."""
    rows = await _rbac_svc.list_feature_permissions(db)
    return [FeaturePermissionResponse(**r) for r in rows]


@router.put(
    "/feature-permissions/{feature_key}",
    response_model=FeaturePermissionResponse,
    operation_id="alias_set_feature_permission",
)
async def alias_set_feature_permission(
    feature_key: str,
    body: FeaturePermissionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> FeaturePermissionResponse:
    """Alias: PUT /feature-permissions/{key} → PUT /permissions/feature-permissions/{key}."""
    result = await _rbac_svc.set_feature_permission(
        db,
        feature_key=feature_key,
        required_permission=body.required_permission,
    )
    return FeaturePermissionResponse(**result)


__all__ = ["router"]