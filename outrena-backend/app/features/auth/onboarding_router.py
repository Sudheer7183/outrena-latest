"""
onboarding_router.py — POST-login onboarding checklist (FR-E1-007/008).

Exposes GET /api/v1/onboarding/checklist returning the 6-item checklist
status for the calling user's tenant. Each item is marked done by checking
the relevant data in the tenant schema.

Checklist items:
  1. create_icp         — IcpProfile rows exist
  2. connect_mailbridge — MailBridgeConfig rows exist + isActive=True
  3. verify_domain      — Domain rows exist with isVerified=True
  4. import_prospects   — Prospect rows exist (at least 1)
  5. create_campaign    — Campaign rows exist (at least 1 non-draft)
  6. send_first_email   — Sequence rows with status=sent exist (at least 1)
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


CHECKLIST_ITEMS = [
    {
        "key": "create_icp",
        "label": "Create your first ICP Profile",
        "description": "Define your ideal customer so AI can personalise outreach.",
        "link": "/prospecting/icp-profiles",
        "order": 1,
    },
    {
        "key": "connect_mailbridge",
        "label": "Connect MailBridge",
        "description": "Set up your sending inbox so sequences can go out.",
        "link": "/setup/mailbridge",
        "order": 2,
    },
    {
        "key": "verify_domain",
        "label": "Verify your sending domain",
        "description": "Add DKIM, SPF, and DMARC records to protect deliverability.",
        "link": "/setup/domains",
        "order": 3,
    },
    {
        "key": "import_prospects",
        "label": "Import your first prospects",
        "description": "Upload a CSV or connect an integration to source contacts.",
        "link": "/prospects",
        "order": 4,
    },
    {
        "key": "create_campaign",
        "label": "Design a campaign",
        "description": "Bundle your ICP, cadence, and copy into a campaign.",
        "link": "/outreach/campaigns",
        "order": 5,
    },
    {
        "key": "send_first_email",
        "label": "Send your first email",
        "description": "Approve a sequence and watch it go out via MailBridge.",
        "link": "/outreach/sequences",
        "order": 6,
    },
]


async def _check_items(db: AsyncSession) -> dict[str, bool]:
    """Check which onboarding items are complete by querying the tenant schema."""
    from sqlalchemy import text

    results: dict[str, bool] = {item["key"]: False for item in CHECKLIST_ITEMS}

    try:
        # 1. ICP created
        r = await db.execute(text('SELECT COUNT(*) FROM "IcpProfile"'))
        results["create_icp"] = (r.scalar() or 0) > 0

        # 2. MailBridge connected
        r = await db.execute(text('SELECT COUNT(*) FROM "MailBridgeConfig" WHERE "isActive" = true'))
        results["connect_mailbridge"] = (r.scalar() or 0) > 0

        # 3. Domain verified
        r = await db.execute(text('SELECT COUNT(*) FROM "Domain" WHERE "isVerified" = true'))
        results["verify_domain"] = (r.scalar() or 0) > 0

        # 4. Prospects imported
        r = await db.execute(text('SELECT COUNT(*) FROM "Prospect"'))
        results["import_prospects"] = (r.scalar() or 0) > 0

        # 5. Campaign created (not draft)
        r = await db.execute(text("SELECT COUNT(*) FROM \"Campaign\" WHERE status != 'draft'"))
        results["create_campaign"] = (r.scalar() or 0) > 0

        # 6. Email sent
        r = await db.execute(text("SELECT COUNT(*) FROM \"Sequence\" WHERE status = 'Sent'"))
        results["send_first_email"] = (r.scalar() or 0) > 0
    except Exception:  # noqa: BLE001 — checklist never crashes the app
        pass

    return results


@router.get("/checklist")
async def get_checklist(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> dict:
    """Return the 6-item onboarding checklist with done status for each item."""
    done_map = await _check_items(db)
    items = [
        {**item, "done": done_map.get(item["key"], False)}
        for item in CHECKLIST_ITEMS
    ]
    completed = sum(1 for i in items if i["done"])
    return {
        "items": items,
        "completed": completed,
        "total": len(items),
        "all_done": completed == len(items),
    }
