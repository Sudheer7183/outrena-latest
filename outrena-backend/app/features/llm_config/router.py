

# """
# llm_config.py — /api/v1/llm-configs router.

# Endpoints:
#   GET    /llm-configs                list global configs
#   POST   /llm-configs                create global config
#   POST   /llm-configs/test-llm       call LLM with a test message
#   GET    /llm-configs/{config_id}    fetch one
#   PUT    /llm-configs/{config_id}    update
#   DELETE /llm-configs/{config_id}    soft-delete (is_active=false)
#   POST   /llm-configs/{config_id}/set-default  set platform default
#   POST   /llm-configs/{config_id}/test  test the config's API key

# Role gate: Role.SUPER_ADMIN (Phase 8 — was Role.MANAGER in Phase 2).

# The router reads/writes ``public.global_llm_config`` via
# ``LlmConfigService``. The session is the public-schema session (the
# TenantMiddleware exemption for SUPER_ADMIN tokens resolves to public
# anyway, but we use ``get_db_public`` for explicit clarity).
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from fastapi.responses import Response
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db_public
# from app.api.security import require_role
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.llm_config import (
#     LlmConfigCreate,
#     LlmConfigResponse,
#     LlmConfigUpdate,
#     TestLlmRequest,
#     TestLlmResponse,
# )
# from app.features.llm_config.service import LlmConfigService

# router = APIRouter(prefix="/llm-configs", tags=["LLM Configs"])
# _service = LlmConfigService()


# @router.get("", response_model=list[LlmConfigResponse])
# async def list_llm_configs(
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> list[LlmConfigResponse]:
#     items = await _service.list_configs(db, limit=limit, offset=offset)
#     return [LlmConfigResponse(**_service.to_response(i)) for i in items]


# @router.post("", response_model=LlmConfigResponse, status_code=201)
# async def create_llm_config(
#     body: LlmConfigCreate,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     try:
#         item = await _service.create(db, body)
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     return LlmConfigResponse(**_service.to_response(item))


# # Static route declared BEFORE /{config_id} (Pitfall #7).
# @router.post("/test-llm", response_model=TestLlmResponse)
# async def test_llm(
#     body: TestLlmRequest,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> TestLlmResponse:
#     """Call the configured LLM with a test message."""
#     return await _service.test_llm(db, body)


# @router.get("/{config_id}", response_model=LlmConfigResponse)
# async def get_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     item = await _service.get(db, config_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return LlmConfigResponse(**_service.to_response(item))


# @router.put("/{config_id}", response_model=LlmConfigResponse)
# async def update_llm_config(
#     config_id: int,
#     body: LlmConfigUpdate,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     try:
#         item = await _service.update(db, config_id, body)
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return LlmConfigResponse(**_service.to_response(item))


# @router.delete(
#     "/{config_id}", response_model=None, response_class=Response, status_code=204
# )
# async def delete_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> Response:
#     ok = await _service.delete(db, config_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# @router.post("/{config_id}/set-default", response_model=LlmConfigResponse)
# async def set_default_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     """Mark this config as the platform default; demote others."""
#     item = await _service.set_default(db, config_id)
#     if item is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND,
#             "LLM config not found or is inactive.",
#         )
#     return LlmConfigResponse(**_service.to_response(item))


# @router.post("/{config_id}/test", response_model=TestLlmResponse)
# async def test_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> TestLlmResponse:
#     """Send a tiny test prompt to verify the config's API key works."""
#     return await _service.test_llm(
#         db,
#         TestLlmRequest(
#             config_id=config_id,
#             message="Hello, please confirm you are operational.",
#         ),
#     )


# __all__ = ["router"]

# from __future__ import annotations
 
# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from fastapi.responses import Response
# from sqlalchemy.ext.asyncio import AsyncSession
 
# from app.api.deps import get_db_public
# from app.api.security import require_role
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.llm_config import (
#     LlmConfigCreate,
#     LlmConfigResponse,
#     LlmConfigUpdate,
#     TestLlmRequest,
#     TestLlmResponse,
# )
# from app.features.llm_config.service import LlmConfigService
 
# router = APIRouter(prefix="/llm-configs", tags=["LLM Configs"])
# _service = LlmConfigService()
 
 
# @router.get("", response_model=list[LlmConfigResponse])
# async def list_llm_configs(
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db_public),
#     # REP+ can read LLM configs — needed for model-selector dropdowns in
#     # Email Studio, Sequences, and anywhere the UI lets the user pick a model.
#     # TENANT_ADMIN gate is kept on write/delete/set-default below.
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[LlmConfigResponse]:
#     items = await _service.list_configs(db, limit=limit, offset=offset)
#     return [LlmConfigResponse(**_service.to_response(i)) for i in items]
 
 
# @router.post("", response_model=LlmConfigResponse, status_code=201)
# async def create_llm_config(
#     body: LlmConfigCreate,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     try:
#         item = await _service.create(db, body)
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     return LlmConfigResponse(**_service.to_response(item))
 
 
# # Static route declared BEFORE /{config_id} (Pitfall #7).
# @router.post("/test-llm", response_model=TestLlmResponse)
# async def test_llm(
#     body: TestLlmRequest,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> TestLlmResponse:
#     """Call the configured LLM with a test message."""
#     return await _service.test_llm(db, body)
 
 
# @router.get("/{config_id}", response_model=LlmConfigResponse)
# async def get_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     # REP+ can read a single config — needed for pre-filling the model selector.
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> LlmConfigResponse:
#     item = await _service.get(db, config_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return LlmConfigResponse(**_service.to_response(item))
 
 
# @router.put("/{config_id}", response_model=LlmConfigResponse)
# async def update_llm_config(
#     config_id: int,
#     body: LlmConfigUpdate,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     try:
#         item = await _service.update(db, config_id, body)
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return LlmConfigResponse(**_service.to_response(item))
 
 
# @router.delete(
#     "/{config_id}", response_model=None, response_class=Response, status_code=204
# )
# async def delete_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> Response:
#     ok = await _service.delete(db, config_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)
 
 
# @router.post("/{config_id}/set-default", response_model=LlmConfigResponse)
# async def set_default_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> LlmConfigResponse:
#     """Mark this config as the platform default; demote others."""
#     item = await _service.set_default(db, config_id)
#     if item is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND,
#             "LLM config not found or is inactive.",
#         )
#     return LlmConfigResponse(**_service.to_response(item))
 
 
# @router.post("/{config_id}/test", response_model=TestLlmResponse)
# async def test_llm_config(
#     config_id: int,
#     db: AsyncSession = Depends(get_db_public),
#     _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
# ) -> TestLlmResponse:
#     """Send a tiny test prompt to verify the config's API key works."""
#     return await _service.test_llm(
#         db,
#         TestLlmRequest(
#             config_id=config_id,
#             message="Hello, please confirm you are operational.",
#         ),
#     )
 
 
# __all__ = ["router"]


"""
llm_config.py — /api/v1/llm-configs router.

FIX (tenant isolation): Previously this router read/wrote public.global_llm_config
which has NO tenant_id column — every tenant saw every other tenant's LLM
configs. This is a data isolation breach.

Correct architecture:
  • TENANT_ADMIN / MANAGER / REP  →  per-tenant LlmConfig table (tenant schema)
                                      isolated by search_path, one config set
                                      per tenant.  Uses get_db (tenant session).
  • SUPER_ADMIN platform configs   →  public.global_llm_config (no change).
                                      The GlobalLlmConfigPage (/setup/global-llm)
                                      still uses that table.

This router (mounted at /setup/llm-models in the sidebar) now targets the
tenant-scoped LlmConfig table via TenantLlmConfigService.

Endpoints:
  GET    /llm-configs                list tenant's configs
  POST   /llm-configs                create in tenant schema
  POST   /llm-configs/test-llm       test a config
  GET    /llm-configs/{config_id}    fetch one
  PUT    /llm-configs/{config_id}    update
  DELETE /llm-configs/{config_id}    soft-delete (isActive=false)
  POST   /llm-configs/{config_id}/set-default  set tenant default
  POST   /llm-configs/{config_id}/test         test specific config

Role gate: TENANT_ADMIN for write; REP for read (model-selector dropdowns).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.llm_config import (
    LlmConfigCreate,
    LlmConfigResponse,
    LlmConfigUpdate,
    TestLlmRequest,
    TestLlmResponse,
)
from app.features.llm_config.tenant_service import TenantLlmConfigService

router = APIRouter(prefix="/llm-configs", tags=["LLM Configs"])
_service = TenantLlmConfigService()


@router.get("", response_model=list[LlmConfigResponse])
async def list_llm_configs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    # REP+ can read — needed for model-selector dropdowns in Email Studio etc.
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> list[LlmConfigResponse]:
    items = await _service.list_configs(db, limit=limit, offset=offset)
    return [_service.to_response(i) for i in items]


@router.post("", response_model=LlmConfigResponse, status_code=201)
async def create_llm_config(
    body: LlmConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> LlmConfigResponse:
    try:
        item = await _service.create(db, body)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    return _service.to_response(item)


# Static route declared BEFORE /{config_id} (Pitfall #7).
@router.post("/test-llm", response_model=TestLlmResponse)
async def test_llm(
    body: TestLlmRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> TestLlmResponse:
    """Call the configured LLM with a test message."""
    return await _service.test_llm(db, body)


@router.get("/{config_id}", response_model=LlmConfigResponse)
async def get_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> LlmConfigResponse:
    item = await _service.get(db, config_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
    return _service.to_response(item)


@router.put("/{config_id}", response_model=LlmConfigResponse)
async def update_llm_config(
    config_id: str,
    body: LlmConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> LlmConfigResponse:
    try:
        item = await _service.update(db, config_id, body)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
    return _service.to_response(item)


@router.delete(
    "/{config_id}", response_model=None, response_class=Response, status_code=204
)
async def delete_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _service.delete(db, config_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{config_id}/set-default", response_model=LlmConfigResponse)
async def set_default_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> LlmConfigResponse:
    """Mark this config as this tenant's default; demote others."""
    item = await _service.set_default(db, config_id)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "LLM config not found or is inactive.",
        )
    return _service.to_response(item)


@router.post("/{config_id}/test", response_model=TestLlmResponse)
async def test_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.TENANT_ADMIN)),
) -> TestLlmResponse:
    """Send a tiny test prompt to verify the config's API key works."""
    return await _service.test_llm(
        db,
        TestLlmRequest(
            config_id=config_id,
            message="Hello, please confirm you are operational.",
        ),
    )


__all__ = ["router"]