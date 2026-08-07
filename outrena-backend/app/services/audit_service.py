"""
audit_service.py — Write/read path for public.platform_audit_log.

Wraps the existing platform_audit_log table (created by migration 0001)
with the richer ORM model from app/models/audit_log.py. Adds the missing
columns (actor_role, target_id, request_id, ip_address) via migration
0003_saas_platform.

Used by:
  - AuditMiddleware (auto-logs every mutation)
  - Platform admin /platform/admin/audit-logs endpoint (SUPER_ADMIN)
  - Tenant admin /api/v1/audit-logs endpoint (TENANT_ADMIN, scoped)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    """Insert + list helpers for the platform audit log."""

    async def log(
        self,
        db: AsyncSession,
        *,
        actor_user_id: str | None,
        actor_role: str | None,
        tenant_slug: str | None,
        action: str,
        actor_email: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Insert one row into public.platform_audit_log.

        Fire-and-forget callers may catch+swallow exceptions — a failed
        audit-log write must NEVER break the request it is logging.
        """
        # We use raw text() so the writer does not depend on the model's
        # column-rename mapping being in sync with the migration. The
        # `target` column (legacy, single-string) is populated with
        # "{type}:{id}" for backward-compat with any 0001-era readers.
        target_legacy: str | None = None
        if target_type is not None:
            target_legacy = f"{target_type}:{target_id}" if target_id else target_type

        await db.execute(
            text(
                "INSERT INTO public.platform_audit_log "
                "(actor_sub, actor_email, actor_role, tenant_slug, action, target, "
                " target_id, metadata, request_id, ip_address) "
                "VALUES (:sub, :email, :role, :slug, :action, :target, "
                "        :target_id, CAST(:meta AS jsonb), :req_id, :ip)"
            ),
            {
                "sub": actor_user_id,
                "email": actor_email,
                "role": actor_role,
                "slug": tenant_slug,
                "action": action,
                "target": target_legacy,
                "target_id": target_id,
                "meta": _to_json(metadata or {}),
                "req_id": request_id,
                "ip": ip_address,
            },
        )
        await db.commit()

    async def list_logs(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
        tenant_slug: str | None = None,
        action: str | None = None,
        actor_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List audit log rows with optional filters. Returns newest first."""
        clauses = []
        params: dict[str, Any] = {"limit": limit}
        if tenant_slug is not None:
            clauses.append("tenant_slug = :slug")
            params["slug"] = tenant_slug
        if action is not None:
            clauses.append("action = :action")
            params["action"] = action
        if actor_user_id is not None:
            clauses.append("actor_sub = :sub")
            params["sub"] = actor_user_id
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = (
            await db.execute(
                text(
                    "SELECT id, actor_sub, actor_email, actor_role, tenant_slug, "
                    "action, target, target_id, metadata, request_id, ip_address, "
                    "created_at "
                    f"FROM public.platform_audit_log {where} "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                params,
            )
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def _to_json(value: Any) -> str:
    """Serialize to JSON string for the CAST(:meta AS jsonb) bind param."""
    import json

    return json.dumps(value, default=str)


__all__ = ["AuditService"]