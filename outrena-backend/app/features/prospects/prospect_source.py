"""
prospect_source.py — Phase 3 /api/v1/prospect-source router.

Endpoints:
  GET    /prospect-source/configs              list source configs
  POST   /prospect-source/configs              create
  PUT    /prospect-source/configs/{source}     update
  DELETE /prospect-source/configs/{source}     delete
  GET    /prospect-source                      list prospect-source records
  POST   /prospect-source/nl-search            natural-language prospect search
  POST   /prospect-source/lookalike            find lookalike prospects
  POST   /prospect-source/ultimate-profile     build an ultimate profile
  POST   /prospect-source/brief                generate a prospect brief
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.prospect_source import (
    LookalikeRequest,
    LookalikeResponse,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    ProspectBriefRequest,
    ProspectBriefResponse,
    ProspectSourceResponse,
    SourceConfigCreate,
    SourceConfigResponse,
    SourceConfigUpdate,
    UltimateProfileRequest,
    UltimateProfileResponse,
)
from app.features.prospects.prospect_source_service import ProspectSourceService

# ── Internal child routers ─────────────────────────────────────────────────
# `_canonical_router` carries the /prospect-source/* endpoints.
# `_alias_router` carries the spec-path alias /prospect-search-nl (audit H-26).
# Public parent `router` (no prefix) mounts both at the bottom of this file.
_canonical_router = APIRouter(prefix="/prospect-source", tags=["Prospect Sources"])
_alias_router = APIRouter(prefix="", tags=["Prospect Sources"])
router = APIRouter(tags=["Prospect Sources"])
_service = ProspectSourceService()


# ── Source configs ─────────────────────────────────────────────────────────
@_canonical_router.get("/configs", response_model=list[SourceConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[SourceConfigResponse]:
    items = await _service.list_configs(db)
    return [SourceConfigResponse.model_validate(i) for i in items]


@_canonical_router.post("/configs", response_model=SourceConfigResponse, status_code=201)
async def create_config(
    body: SourceConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> SourceConfigResponse:
    item = await _service.create_config(db, body)
    return SourceConfigResponse.model_validate(item)


@_canonical_router.put("/configs/{source}", response_model=SourceConfigResponse)
async def update_config(
    source: str,
    body: SourceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> SourceConfigResponse:
    item = await _service.update_config(db, source, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source config not found.")
    return SourceConfigResponse.model_validate(item)


@_canonical_router.delete("/configs/{source}", response_model=None, response_class=Response, status_code=204)
async def delete_config(
    source: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _service.delete_config(db, source)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Prospect source records ────────────────────────────────────────────────
@_canonical_router.get("", response_model=list[ProspectSourceResponse])
async def list_sources(
    prospect_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> list[ProspectSourceResponse]:
    items = await _service.list_sources(db, prospect_id=prospect_id)
    return [ProspectSourceResponse.model_validate(i) for i in items]


# ── NL search + lookalike + profile + brief ────────────────────────────────
@_canonical_router.post("/nl-search", response_model=NaturalLanguageSearchResponse)
async def nl_search(
    body: NaturalLanguageSearchRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> NaturalLanguageSearchResponse:
    return await _service.natural_language_search(
        db, body.query, body.icpProfileId, body.limit
    )


@_canonical_router.post("/lookalike", response_model=LookalikeResponse)
async def lookalike(
    body: LookalikeRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> LookalikeResponse:
    return await _service.lookalike(db, body.prospectId, body.limit)


@_canonical_router.post("/ultimate-profile", response_model=UltimateProfileResponse)
async def ultimate_profile(
    body: UltimateProfileRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> UltimateProfileResponse:
    return await _service.ultimate_profile(db, body.prospectId)


@_canonical_router.post("/brief", response_model=ProspectBriefResponse)
async def brief(
    body: ProspectBriefRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> ProspectBriefResponse:
    return await _service.brief(db, body.prospectId, body.callType)


# ── Compatibility alias: /prospect-search-nl ──────────────────────────────
# The migration-doc spec table uses ``/api/prospect-search-nl`` while the
# canonical implementation lives at ``/prospect-source/nl-search`` (audit
# H-26). This alias exposes the spec path as a POST endpoint that delegates
# to the same service + request/response models so the public API contract
# matches the documented surface. Distinct operationId ensures it shows up
# separately in OpenAPI / Swagger UI.


@_alias_router.post(
    "/prospect-search-nl",
    response_model=NaturalLanguageSearchResponse,
    operation_id="prospect_search_nl_alias",
    summary="[Alias] Natural-language prospect search (spec path)",
    description=(
        "Compatibility alias for POST /prospect-source/nl-search. "
        "Delegates to the same handler. Provided so the spec path "
        "/api/prospect-search-nl resolves."
    ),
)
async def prospect_search_nl_alias(
    body: NaturalLanguageSearchRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> NaturalLanguageSearchResponse:
    return await _service.natural_language_search(
        db, body.query, body.icpProfileId, body.limit
    )


# Mount the child routers into the public parent router. The canonical routes
# live at /prospect-source/* and the spec alias lives at /prospect-search-nl
# (no /prospect-source prefix).
router.include_router(_canonical_router)
router.include_router(_alias_router)
