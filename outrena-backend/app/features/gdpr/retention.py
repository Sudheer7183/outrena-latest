"""
retention.py — Retention policy CRUD + manual enforcement router.

SUPER_ADMIN only — these endpoints manage the platform-wide retention
policy catalog (public.retention_policies) and trigger manual enforcement
across all tenants. The in-memory defaults in
``RetentionService.RETENTION_POLICIES`` are the boot-strap; this router
lets the DPO override days / action / description per policy without a
code deploy.

Endpoints (all SUPER_ADMIN — TenantMiddleware-exempt via /api/v1/gdpr/platform
prefix overlap is NOT used here; this router has its own prefix):

  GET    /retention/policies                 list all policies
  GET    /retention/policies/{name}          get one policy
  PUT    /retention/policies/{name}          update days / action / description
  POST   /retention/enforce                  enforce across ALL tenants
  GET    /retention/status                   status across ALL tenants

The router lives under the /api/v1 prefix and is auto-discovered by the
v1 router aggregator. The platform-level scope means the calls must
bypass TenantMiddleware — the public.retention_policies table is queried
via get_db_public, and enforcement iterates active tenants server-side.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.features.gdpr.retention_service import RetentionService

router = APIRouter(prefix="/retention", tags=["Retention"])
_service = RetentionService()

# Allowed actions for retention policies.
_ALLOWED_ACTIONS: frozenset[str] = frozenset({"anonymize", "delete"})


# ── Schemas ──────────────────────────────────────────────────────────────────


class RetentionPolicyResponse(BaseModel):
    policy_name: str
    days: int
    action: str
    description: str
    scope: str  # tenant | public


class RetentionPolicyListResponse(BaseModel):
    policies: list[RetentionPolicyResponse]


class RetentionPolicyUpdate(BaseModel):
    days: int | None = Field(default=None, ge=1, le=36500)
    action: str | None = Field(default=None, description="anonymize | delete")
    description: str | None = Field(default=None, max_length=2000)


class RetentionEnforceAllResponse(BaseModel):
    enforced_tenants: int
    per_tenant: dict[str, dict[str, int]]
    errors: dict[str, str] = {}


class RetentionStatusAllResponse(BaseModel):
    tenants_count: int
    per_tenant: dict[str, dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/policies", response_model=RetentionPolicyListResponse)
async def list_policies(
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> RetentionPolicyListResponse:
    """List all retention policies (defaults + overrides from the DB)."""
    # Merge in-memory defaults with persisted overrides.
    persisted = (
        await db.execute(
            text(
                "SELECT policy_name, days, action, description "
                "FROM public.retention_policies"
            )
        )
    ).fetchall()
    persisted_map = {r.policy_name: r for r in persisted}

    out: list[RetentionPolicyResponse] = []
    for name, cfg in _service.RETENTION_POLICIES.items():
        if name in persisted_map:
            r = persisted_map[name]
            out.append(
                RetentionPolicyResponse(
                    policy_name=name,
                    days=r.days,
                    action=r.action,
                    description=r.description or cfg.get("description", ""),
                    scope=cfg.get("scope", "tenant"),
                )
            )
        else:
            out.append(
                RetentionPolicyResponse(
                    policy_name=name,
                    days=cfg["days"],
                    action=cfg["action"],
                    description=cfg.get("description", ""),
                    scope=cfg.get("scope", "tenant"),
                )
            )
    return RetentionPolicyListResponse(policies=out)


@router.get("/policies/{policy_name}", response_model=RetentionPolicyResponse)
async def get_policy(
    policy_name: str,
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> RetentionPolicyResponse:
    """Get a single retention policy by name."""
    if policy_name not in _service.RETENTION_POLICIES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found.")
    cfg = _service.RETENTION_POLICIES[policy_name]
    row = (
        await db.execute(
            text(
                "SELECT days, action, description "
                "FROM public.retention_policies WHERE policy_name = :name"
            ),
            {"name": policy_name},
        )
    ).fetchone()
    if row is not None:
        return RetentionPolicyResponse(
            policy_name=policy_name,
            days=row.days,
            action=row.action,
            description=row.description or cfg.get("description", ""),
            scope=cfg.get("scope", "tenant"),
        )
    return RetentionPolicyResponse(
        policy_name=policy_name,
        days=cfg["days"],
        action=cfg["action"],
        description=cfg.get("description", ""),
        scope=cfg.get("scope", "tenant"),
    )


@router.put("/policies/{policy_name}", response_model=RetentionPolicyResponse)
async def update_policy(
    policy_name: str,
    body: RetentionPolicyUpdate,
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> RetentionPolicyResponse:
    """Update days / action / description for a retention policy."""
    if policy_name not in _service.RETENTION_POLICIES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found.")
    cfg = _service.RETENTION_POLICIES[policy_name]
    new_days = body.days if body.days is not None else cfg["days"]
    new_action = body.action if body.action is not None else cfg["action"]
    new_desc = body.description if body.description is not None else cfg.get("description", "")
    if new_action not in _ALLOWED_ACTIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"action must be one of {sorted(_ALLOWED_ACTIONS)}",
        )

    await db.execute(
        text(
            "INSERT INTO public.retention_policies "
            "(policy_name, days, action, description, updated_at) "
            "VALUES (:name, :days, :action, :desc, now()) "
            "ON CONFLICT (policy_name) DO UPDATE SET "
            "  days = EXCLUDED.days, "
            "  action = EXCLUDED.action, "
            "  description = EXCLUDED.description, "
            "  updated_at = now()"
        ),
        {
            "name": policy_name,
            "days": new_days,
            "action": new_action,
            "desc": new_desc,
        },
    )
    await db.commit()
    return RetentionPolicyResponse(
        policy_name=policy_name,
        days=new_days,
        action=new_action,
        description=new_desc,
        scope=cfg.get("scope", "tenant"),
    )


@router.post("/enforce", response_model=RetentionEnforceAllResponse)
async def enforce_all_tenants(
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> RetentionEnforceAllResponse:
    """Manually enforce retention across ALL active tenants.

    Iterates every active tenant in public.tenants and runs all retention
    policies for that tenant. Errors per-tenant are collected but do NOT
    abort the overall run — partial enforcement is better than none.
    """
    rows = (
        await db.execute(
            text(
                "SELECT slug FROM public.tenants "
                "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
            )
        )
    ).fetchall()

    per_tenant: dict[str, dict[str, int]] = {}
    errors: dict[str, str] = {}
    for row in rows:
        slug = row.slug
        try:
            per_tenant[slug] = await _service.enforce_all_policies(slug)
        except Exception as exc:  # noqa: BLE001 — collect, don't abort
            errors[slug] = str(exc)
            per_tenant[slug] = {}

    return RetentionEnforceAllResponse(
        enforced_tenants=len(rows),
        per_tenant=per_tenant,
        errors=errors,
    )


@router.get("/status", response_model=RetentionStatusAllResponse)
async def get_status_all_tenants(
    db: AsyncSession = Depends(get_db_public),
    _: TokenPayload = Depends(require_role(Role.SUPER_ADMIN)),
) -> RetentionStatusAllResponse:
    """Get retention status across ALL active tenants (dry-run counts)."""
    rows = (
        await db.execute(
            text(
                "SELECT slug FROM public.tenants "
                "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
            )
        )
    ).fetchall()

    per_tenant: dict[str, dict[str, Any]] = {}
    for row in rows:
        slug = row.slug
        try:
            per_tenant[slug] = await _service.get_policy_status(slug)
        except Exception as exc:  # noqa: BLE001
            per_tenant[slug] = {"error": str(exc)}

    return RetentionStatusAllResponse(
        tenants_count=len(rows),
        per_tenant=per_tenant,
    )


__all__ = ["router"]
