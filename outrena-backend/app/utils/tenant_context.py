"""tenant_context.py — helpers for resolving the current tenant slug.

Used by fire-and-forget usage / cost recorders that need to derive the
tenant slug from the caller's request-scoped AsyncSession. The session's
search_path is set by TenantMiddleware + get_db, so a SHOW search_path
query is sufficient to identify the active tenant schema.

FIX-BE-1 / HIGH 8 (re-verification): usage recorders in MailBridgeService,
ProspectService.enrich and LinkedInService.create_engagement all need a
tenant slug to lock their own short-lived recording session's search_path.
This helper is the single source of truth for that derivation.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_tenant_slug(db: AsyncSession) -> str:
    """Return the tenant slug for the session's current search_path.

    Walks the comma-separated search_path tokens and returns the first
    one that starts with ``tenant_``. Returns an empty string when no
    tenant schema is on the path (e.g. public-only sessions) — callers
    should treat that as a no-op signal (skip recording).
    """
    try:
        row = (await db.execute(text("SHOW search_path"))).fetchone()
        sp = (row[0] if row else "") or ""
    except Exception:  # noqa: BLE001 — best-effort, never break caller
        return ""
    for tok in sp.split(","):
        tok = tok.strip().strip('"')
        if tok.startswith("tenant_"):
            return tok[len("tenant_"):]
    return ""


__all__ = ["resolve_tenant_slug"]
