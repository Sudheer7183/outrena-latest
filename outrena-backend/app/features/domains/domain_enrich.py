"""
domain_enrich.py — Phase 3 /api/v1/domain-enrich router.

Endpoints:
  POST   /domain-enrich           enrich a single domain (fetch/cache)
  POST   /domain-enrich/batch     enrich many domains at once
  GET    /domain-enrich/{domain}  fetch cached enrichment for a domain
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role
from app.schemas.domain_enrich import (
    DomainEnrichBatchRequest,
    DomainEnrichBatchResponse,
    DomainEnrichRequest,
    DomainEnrichmentResponse,
)
from app.features.domains.domain_enrich_service import DomainEnrichService

router = APIRouter(prefix="/domain-enrich", tags=["Domain Enrichment"])
_service = DomainEnrichService()


@router.post("", response_model=DomainEnrichmentResponse)
async def enrich(
    body: DomainEnrichRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DomainEnrichmentResponse:
    item = await _service.enrich(db, body.domain, body.forceRefresh)
    return DomainEnrichmentResponse.model_validate(item)


@router.post("/batch", response_model=DomainEnrichBatchResponse)
async def enrich_batch(
    body: DomainEnrichBatchRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DomainEnrichBatchResponse:
    return await _service.enrich_batch(db, body.domains)


@router.get("/{domain}", response_model=DomainEnrichmentResponse)
async def get_enrichment(
    domain: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> DomainEnrichmentResponse:
    item = await _service.get(db, domain)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No enrichment cached for '{domain}'. POST /domain-enrich to fetch.",
        )
    return DomainEnrichmentResponse.model_validate(item)
