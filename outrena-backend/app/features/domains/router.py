"""
domains.py — Phase 2 /api/v1/domains router.

Endpoints:
  GET    /domains                list
  POST   /domains                create
  POST   /domains/dns-check      DNS check (MX/SPF/DKIM/DMARC)
  GET    /domains/{domain_id}    fetch one
  PUT    /domains/{domain_id}    update
  DELETE /domains/{domain_id}    delete (204)

Role gate: Role.MANAGER.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.domains import (
    DnsCheckRequest,
    DnsCheckResult,
    DomainCreate,
    DomainResponse,
    DomainUpdate,
)
from app.features.domains.service import DomainService

router = APIRouter(prefix="/domains", tags=["Domains"])
_service = DomainService()


@router.get("", response_model=list[DomainResponse])
async def list_domains(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> list[DomainResponse]:
    items = await _service.list_domains(db, limit=limit, offset=offset)
    return [DomainResponse.model_validate(i) for i in items]


@router.post("", response_model=DomainResponse, status_code=201)
async def create_domain(
    body: DomainCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DomainResponse:
    item = await _service.create(db, body)
    return DomainResponse.model_validate(item)


# Static route declared BEFORE /{domain_id} (Pitfall #7).
@router.post("/dns-check", response_model=DnsCheckResult)
async def dns_check(
    body: DnsCheckRequest,
    _: AsyncSession = Depends(get_db),
    __: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DnsCheckResult:
    """Run MX/SPF/DKIM/DMARC DNS lookups for a domain (dnspython or stdlib)."""
    return await _service.dns_check(body)


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DomainResponse:
    item = await _service.get(db, domain_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    return DomainResponse.model_validate(item)


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: str,
    body: DomainUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DomainResponse:
    item = await _service.update(db, domain_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    return DomainResponse.model_validate(item)


@router.delete("/{domain_id}", response_model=None, response_class=Response, status_code=204)
async def delete_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete(db, domain_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/{domain_id}/auto-warm", response_model=DomainResponse)
async def auto_warm_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> DomainResponse:
    """
    Auto-Warm button: advance the domain one week forward in the 7-week
    warming schedule. Updates warmingWeek and dailySendLimit together so the
    scheduler enforces the new cap immediately.

    Schedule (per Help Guide §Domains):
      Week 1=10, 2=30, 3=50, 4=100, 5=200, 6=350, 7=500 emails/day.
    Disabled at week 7 (fully warm).
    """
    from app.features.scheduler.service import WARMING_SCHEDULE

    item = await _service.get(db, domain_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    current_week = int(item.warmingWeek or 1)
    if current_week >= len(WARMING_SCHEDULE):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Domain is already fully warm (week {current_week} / {len(WARMING_SCHEDULE)}).",
        )
    next_week = current_week + 1
    new_limit = WARMING_SCHEDULE[next_week - 1]  # 0-indexed list
    from app.schemas.domains import DomainUpdate as _DomainUpdate
    updated = await _service.update(
        db, domain_id, _DomainUpdate(warmingWeek=next_week, dailySendLimit=new_limit)
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    return DomainResponse.model_validate(updated)


__all__ = ["router"]
