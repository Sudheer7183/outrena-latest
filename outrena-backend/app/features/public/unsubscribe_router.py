

"""
unsubscribe_router.py — Public one-click unsubscribe endpoint.

PR: FR-E14-018 / NFR-18 — One-click unsubscribe without login, token-verified.
The token is the Prospect.unsubscribeToken (UUID-v4, unique, set at prospect
creation time). This endpoint is TenantMiddleware-exempt (mounted under
/api/v1/public which is in EXEMPT_PREFIXES), so no tenant context is required.

Because the endpoint must identify WHICH tenant schema to update, we accept
the tenant_slug in the query string (added to the unsubscribe URL by the
email generation service when it stamps the footer).

Endpoints:
  POST /public/unsubscribe          JSON body {token, tenant_slug}
  GET  /public/unsubscribe          Query params ?token=…&tenant_slug=…
                                    (for email client one-click GET support)
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/public", tags=["Public"])


class UnsubscribeRequest(BaseModel):
    token: str
    tenant_slug: str


async def _process_unsubscribe(token: str, tenant_slug: str) -> dict:
    """Core unsubscribe logic: find prospect by token, withdraw consent, suppress."""
    if not token or not tenant_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token and tenant_slug are required")

    schema = f"tenant_{tenant_slug.replace('-', '_')}"

    async with AsyncSessionLocal() as db:
        # Set search_path to tenant schema
        await db.execute(text(f'SET search_path TO "{schema}", public'))

        # Find the prospect by unsubscribeToken
        result = await db.execute(
            text("SELECT id, \"firstName\", email, consent_status FROM \"Prospect\" WHERE \"unsubscribeToken\" = :token LIMIT 1"),
            {"token": token},
        )
        row = result.mappings().first()
        if row is None:
            # Don't reveal if token is invalid — return success to avoid enumeration
            logger.warning("unsubscribe.token_not_found", tenant_slug=tenant_slug)
            return {"unsubscribed": True, "message": "You have been unsubscribed."}

        prospect_id = row["id"]
        first_name = row.get("firstName") or "there"

        # Already suppressed — idempotent
        if row.get("consent_status") == "withdrawn":
            return {"unsubscribed": True, "message": f"Hi {first_name}, you were already unsubscribed."}

        now = datetime.now(timezone.utc)

        # Update: withdraw consent, suppress
        await db.execute(
            text(
                'UPDATE "Prospect" SET consent_status = :status, suppressed = true, '
                '"suppressedAt" = :now, "updatedAt" = :now WHERE id = :id'
            ),
            {"status": "withdrawn", "now": now, "id": prospect_id},
        )

        # Write a ConsentLog entry if the table exists (best-effort)
        try:
            await db.execute(
                text(
                    'INSERT INTO "ConsentLog" (id, "prospectId", action, "performedBy", timestamp) '
                    "VALUES (gen_random_uuid()::text, :pid, 'unsubscribed', 'one_click_link', :now)"
                ),
                {"pid": prospect_id, "now": now},
            )
        except Exception:  # noqa: BLE001
            pass  # Table may not exist in all migration versions

        await db.commit()
        logger.info("unsubscribe.success", prospect_id=prospect_id, tenant_slug=tenant_slug)
        return {"unsubscribed": True, "message": f"Hi {first_name}, you have been unsubscribed successfully."}


@router.post("/unsubscribe", summary="One-click email unsubscribe (JSON)")
async def unsubscribe_post(body: UnsubscribeRequest) -> JSONResponse:
    """
    One-click unsubscribe via JSON POST.

    Sets Prospect.consent_status='withdrawn', suppressed=True.
    Returns 200 regardless of whether the token was found (avoids enumeration).
    No authentication required.
    """
    result = await _process_unsubscribe(body.token, body.tenant_slug)
    return JSONResponse(content=result)


@router.get("/unsubscribe", summary="One-click email unsubscribe (GET — email client support)")
async def unsubscribe_get(
    token: str = Query(..., description="Prospect unsubscribe token"),
    tenant_slug: str = Query(..., description="Tenant slug"),
) -> HTMLResponse:
    """
    One-click unsubscribe via GET (RFC 8058 / Gmail one-click support).

    Email clients that implement RFC 8058 List-Unsubscribe-Post send a POST,
    but many clients simply follow the link as a GET. This endpoint handles
    both. Returns an HTML confirmation page.
    """
    result = await _process_unsubscribe(token, tenant_slug)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Unsubscribed — OUTRENA</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;background:#f8fafc}}
.card{{background:#fff;border-radius:12px;padding:40px 48px;max-width:440px;
text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
h1{{font-size:1.4rem;color:#0f172a;margin:0 0 12px}}
p{{color:#64748b;line-height:1.6;margin:0}}</style></head>
<body><div class="card">
<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#22c55e"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
<h1>You've been unsubscribed</h1>
<p>{result['message']}<br><br>You will no longer receive outreach emails from this sender.</p>
</div></body></html>"""
    return HTMLResponse(content=html, status_code=200)
