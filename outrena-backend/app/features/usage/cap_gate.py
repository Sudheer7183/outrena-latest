"""
cap_gate.py — FR-114 dependency: throttle non-critical LLM calls at the cap.

Attach ``Depends(enforce_llm_cap)`` to routes that trigger discretionary LLM
generation (email studio, content ideas, autopilot, GTM thesis, etc.).
Critical paths — reply triage, compliance, unsubscribe handling — must NOT
use this gate: they keep running even at the cap.

The cap is configured per tenant in public.tenant_config.features JSONB as
``{"monthly_cost_cap_cents": <int>}``; 0/absent means uncapped.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.features.usage.service import UsageService

_usage = UsageService()


async def enforce_llm_cap(
    request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    tenant = getattr(request.state, "tenant", None)
    tenant_id = getattr(tenant, "tenant_id", None) if tenant else None
    allowed, reason = await _usage.check_llm_cap(db, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=reason or "Monthly usage cap reached.",
        )
