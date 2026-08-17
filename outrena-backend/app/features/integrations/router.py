# """
# integrations.py — /api/v1/integrations router (canonical) +
#                   /api/v1/prospecting-integrations backward-compat alias.

# Endpoints (served under BOTH prefixes):
#   GET    /integrations                        list
#   POST   /integrations                        create
#   POST   /integrations/test                   test connectivity
#   GET    /integrations/{id}/credentials-test  resolve + verify creds
#   PUT    /integrations/{id}                   update
#   DELETE /integrations/{id}                   delete (204)

# Role gate: Role.MANAGER.

# Phase 8 (dual-path integrations): the create/update payloads carry an
# optional ``key_source`` field ("tenant" | "platform"). The response shape
# exposes ``key_source`` + a masked ``apiKey`` (never the raw value).
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from fastapi.responses import Response
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.integrations import (
#     IntegrationCreate,
#     IntegrationResponse,
#     IntegrationTestRequest,
#     IntegrationTestResponse,
#     IntegrationUpdate,
# )
# from app.features.integrations.integration_credentials_service import (
#     IntegrationCredentialsService,
# )
# from app.features.integrations.service import IntegrationService

# # Canonical router — /api/v1/integrations (matches frontend apiClient.ts)
# router = APIRouter(prefix="/integrations", tags=["Integrations"])
# _service = IntegrationService()
# _credentials_service = IntegrationCredentialsService()


# def _mask(value: str | None) -> str | None:
#     if value is None:
#         return None
#     if len(value) <= 8:
#         return "****"
#     return f"{value[:4]}...{value[-4:]}"


# async def _to_response(
#     db: AsyncSession, item, *, include_resolved_mask: bool = False
# ) -> IntegrationResponse:
#     """Build an IntegrationResponse with a masked apiKey.

#     When ``include_resolved_mask`` is True (used for GET single + list), the
#     masked value reflects the RESOLVED credential (decrypted tenant key or
#     platform key). When False (create/update), we only mask the stored
#     tenant-side secret so the client doesn't see ciphertext in transit.
#     """
#     masked: str | None = None
#     if include_resolved_mask:
#         try:
#             resolved = await _credentials_service.resolve_credentials(
#                 db,
#                 integration_type="prospecting",
#                 integration_id=item.id,
#                 provider=item.platform,
#             )
#             masked = resolved.get("masked")
#         except Exception:  # noqa: BLE001 — never fail the GET on a mask error
#             masked = "****"
#     else:
#         # Show a static mask so the client knows a key is stored.
#         if item.api_key_encrypted:
#             masked = "****"
#     return IntegrationResponse(
#         id=item.id,
#         platform=item.platform,
#         name=item.name,
#         apiKey=masked,
#         key_source=item.key_source,
#         isActive=item.isActive,
#         settings=item.settings,
#         lastTestedAt=item.lastTestedAt,
#         lastTestResult=item.lastTestResult,
#         createdAt=item.createdAt,
#         updatedAt=item.updatedAt,
#     )


# @router.get("", response_model=list[IntegrationResponse])
# async def list_integrations(
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> list[IntegrationResponse]:
#     items = await _service.list_integrations(db, limit=limit, offset=offset)
#     return [await _to_response(db, i, include_resolved_mask=True) for i in items]


# @router.post("", response_model=IntegrationResponse, status_code=201)
# async def create_integration(
#     body: IntegrationCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IntegrationResponse:
#     try:
#         item = await _service.create(db, body)
#     except ValueError as exc:
#         raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     return await _to_response(db, item)


# # Static route declared BEFORE /{integration_id} (Pitfall #7).
# @router.post("/test", response_model=IntegrationTestResponse)
# async def test_integration(
#     body: IntegrationTestRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IntegrationTestResponse:
#     """Test a prospecting integration's connectivity."""
#     return await _service.test(db, body)


# # Static sub-path declared BEFORE /{integration_id} (Pitfall #7).
# @router.get("/{integration_id}/credentials-test", response_model=IntegrationTestResponse)
# async def credentials_test_integration(
#     integration_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IntegrationTestResponse:
#     """Resolve + verify the integration's credentials (no upstream ping)."""
#     return await _service.credentials_test(db, integration_id)


# @router.put("/{integration_id}", response_model=IntegrationResponse)
# async def update_integration(
#     integration_id: str,
#     body: IntegrationUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> IntegrationResponse:
#     try:
#         item = await _service.update(db, integration_id, body)
#     except ValueError as exc:
#         raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
#     except RuntimeError as exc:
#         raise HTTPException(
#             status.HTTP_500_INTERNAL_SERVER_ERROR,
#             f"Encryption backend not configured: {exc}",
#         ) from exc
#     if item is None:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND, "Integration not found."
#         )
#     return await _to_response(db, item)


# @router.delete(
#     "/{integration_id}", response_model=None, response_class=Response, status_code=204
# )
# async def delete_integration(
#     integration_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.delete(db, integration_id)
#     if not ok:
#         raise HTTPException(
#             status.HTTP_404_NOT_FOUND, "Integration not found."
#         )
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# __all__ = ["router"]


"""
integrations.py — /api/v1/integrations router (canonical) +
                  /api/v1/prospecting-integrations backward-compat alias.

Endpoints (served under BOTH prefixes):
  GET    /integrations                        list
  POST   /integrations                        create
  POST   /integrations/test                   test connectivity
  GET    /integrations/{id}/credentials-test  resolve + verify creds
  PUT    /integrations/{id}                   update
  DELETE /integrations/{id}                   delete (204)

Role gate: Role.MANAGER.

Phase 8 (dual-path integrations): the create/update payloads carry an
optional ``key_source`` field ("tenant" | "platform"). The response shape
exposes ``key_source`` + a masked ``apiKey`` (never the raw value).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.integrations import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationTestRequest,
    IntegrationTestResponse,
    IntegrationUpdate,
)
from app.features.integrations.integration_credentials_service import (
    IntegrationCredentialsService,
)
from app.features.integrations.service import IntegrationService

# Canonical router — /api/v1/integrations (matches frontend apiClient.ts)
router = APIRouter(prefix="/integrations", tags=["Integrations"])
_service = IntegrationService()
_credentials_service = IntegrationCredentialsService()


def _mask(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


async def _to_response(
    db: AsyncSession, item, *, include_resolved_mask: bool = False
) -> IntegrationResponse:
    """Build an IntegrationResponse with a masked apiKey.

    When ``include_resolved_mask`` is True (used for GET single + list), the
    masked value reflects the RESOLVED credential (decrypted tenant key or
    platform key). When False (create/update), we only mask the stored
    tenant-side secret so the client doesn't see ciphertext in transit.
    """
    masked: str | None = None
    if include_resolved_mask:
        try:
            resolved = await _credentials_service.resolve_credentials(
                db,
                integration_type="prospecting",
                integration_id=item.id,
                provider=item.platform,
            )
            masked = resolved.get("masked")
        except Exception:  # noqa: BLE001 — never fail the GET on a mask error
            masked = "****"
    else:
        # Show a static mask so the client knows a key is stored.
        if item.api_key_encrypted:
            masked = "****"
    return IntegrationResponse(
        id=item.id,
        platform=item.platform,
        name=item.name,
        apiKey=masked,
        key_source=item.key_source,
        isActive=item.isActive,
        settings=item.settings,
        lastTestedAt=item.lastTestedAt,
        lastTestResult=item.lastTestResult,
        createdAt=item.createdAt,
        updatedAt=item.updatedAt,
    )


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    # FIX: Lowered from MANAGER to REP — REPs need to view which integrations
    # are connected (CRM status shown in Integrations page sidebar). API keys
    # are always masked in the response; no sensitive data is exposed to REP.
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> list[IntegrationResponse]:
    items = await _service.list_integrations(db, limit=limit, offset=offset)
    return [await _to_response(db, i, include_resolved_mask=True) for i in items]


@router.post("", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    body: IntegrationCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IntegrationResponse:
    try:
        item = await _service.create(db, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    return await _to_response(db, item)


# Static route declared BEFORE /{integration_id} (Pitfall #7).
@router.post("/test", response_model=IntegrationTestResponse)
async def test_integration(
    body: IntegrationTestRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IntegrationTestResponse:
    """Test a prospecting integration's connectivity."""
    return await _service.test(db, body)


# Static sub-path declared BEFORE /{integration_id} (Pitfall #7).
@router.get("/{integration_id}/credentials-test", response_model=IntegrationTestResponse)
async def credentials_test_integration(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IntegrationTestResponse:
    """Resolve + verify the integration's credentials (no upstream ping)."""
    return await _service.credentials_test(db, integration_id)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    body: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> IntegrationResponse:
    try:
        item = await _service.update(db, integration_id, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Encryption backend not configured: {exc}",
        ) from exc
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Integration not found."
        )
    return await _to_response(db, item)


@router.delete(
    "/{integration_id}", response_model=None, response_class=Response, status_code=204
)
async def delete_integration(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, integration_id)
    if not ok:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Integration not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]