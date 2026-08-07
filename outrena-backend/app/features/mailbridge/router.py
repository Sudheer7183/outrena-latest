"""
mailbridge.py — Phase 3 /api/v1/mailbridge router.

Endpoints (under /mailbridge):
  GET    /mailbridge/config              list configs
  POST   /mailbridge/config              create
  GET    /mailbridge/config/{id}         fetch one
  PUT    /mailbridge/config/{id}         update
  DELETE /mailbridge/config/{id}         delete
  POST   /mailbridge/send                send an ad-hoc email
  POST   /mailbridge/webhook             inbound webhook from MailBridge (HMAC-verified)
  GET    /mailbridge/email-tracking      list tracking events (filterable)
  POST   /mailbridge/email-tracking      record a single tracking event
  POST   /mailbridge/email-tracking/sync bulk sync tracking events

Compatibility alias routes (audit-A2 HIGH — spec uses /mailbridge-config):
  GET    /mailbridge-config              → /mailbridge/config (list)
  POST   /mailbridge-config              → /mailbridge/config (create)
  GET    /mailbridge-config/{id}         → /mailbridge/config/{id}
  PUT    /mailbridge-config/{id}         → /mailbridge/config/{id}
  DELETE /mailbridge-config/{id}         → /mailbridge/config/{id}

The public surface is the `router` symbol exported below — it is a parent
router (no prefix) that mounts two child routers: one under `/mailbridge`
(all endpoints) and one under `/mailbridge-config` (config aliases only).
This keeps `app/api/v1/__init__.py` unchanged.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.core.config import get_settings
from app.models.campaign_models import Sequence
from app.models.config_models import MailBridgeConfig
from app.schemas.auth import Role, TokenPayload
from app.schemas.mailbridge import (
    MailBridgeConfigCreate,
    MailBridgeConfigResponse,
    MailBridgeConfigUpdate,
    MailBridgeSendRequest,
    MailBridgeSendResponse,
    MailBridgeTrackingEvent,
    MailBridgeWebhookPayload,
    MailBridgeWebhookResponse,
)
from app.features.mailbridge.mailbridge_config_service import MailBridgeConfigService
from app.features.mailbridge.service import MailBridgeService
from app.features.mailbridge.user_email_quota_service import UserEmailQuotaService

# ── Internal child routers ─────────────────────────────────────────────────
# `_mailbridge_router` carries every endpoint that lives under /mailbridge.
# `_alias_router` carries the /mailbridge-config compatibility aliases for
# the 5 config-CRUD endpoints only (audit-A2 HIGH finding).
_mailbridge_router = APIRouter(prefix="/mailbridge", tags=["MailBridge"])
_alias_router = APIRouter(prefix="/mailbridge-config", tags=["MailBridge"])

# Public parent router — exported as `router` for v1/__init__.py aggregation.
# NOTE: `include_router` is called at the BOTTOM of this file (after all
# `@_mailbridge_router.*` and `@_alias_router.*` decorators have run), because
# FastAPI's include_router snapshots the child router's `.routes` list at call
# time — calling it here would register zero routes.
router = APIRouter(tags=["MailBridge"])

_config_service = MailBridgeConfigService()
_send_service = MailBridgeService()

# Set of event types accepted by POST /email-tracking and POST /email-tracking/sync.
# Per task spec: sent/delivered/open/click/bounce/reply + SAAS2-USER-BE §I adds 'complaint'.
# The apply_tracking_event service maps these onto Sequence.status / *_At columns;
# unknown events are accepted but no-op (returned as rejected=False so callers can audit).
_TRACKING_EVENTS: set[str] = {
    "sent",
    "delivered",
    "open",
    "opened",
    "click",
    "clicked",
    "bounce",
    "bounced",
    "reply",
    "replied",
    "failed",
    "complaint",
    "complained",
}


# ── Config CRUD (under /mailbridge/config) ─────────────────────────────────
@_mailbridge_router.get("/config", response_model=list[MailBridgeConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[MailBridgeConfigResponse]:
    items = await _config_service.list(db)
    return [MailBridgeConfigResponse.model_validate(i) for i in items]


@_mailbridge_router.post("/config", response_model=MailBridgeConfigResponse, status_code=201)
async def create_config(
    body: MailBridgeConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> MailBridgeConfigResponse:
    item = await _config_service.create(db, body)
    return MailBridgeConfigResponse.model_validate(item)


@_mailbridge_router.get("/config/{config_id}", response_model=MailBridgeConfigResponse)
async def get_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> MailBridgeConfigResponse:
    item = await _config_service.get(db, config_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return MailBridgeConfigResponse.model_validate(item)


@_mailbridge_router.put("/config/{config_id}", response_model=MailBridgeConfigResponse)
async def update_config(
    config_id: str,
    body: MailBridgeConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> MailBridgeConfigResponse:
    item = await _config_service.update(db, config_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return MailBridgeConfigResponse.model_validate(item)


@_mailbridge_router.delete("/config/{config_id}", response_model=None, response_class=Response, status_code=204)
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _config_service.delete(db, config_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Compatibility aliases under /mailbridge-config (audit-A2 HIGH) ─────────
# These delegate to the same service methods so behaviour stays identical
# to the canonical /mailbridge/config routes. The spec table at
# MIGRATION_DOCUMENT.md L1009 lists `/api/mailbridge-config` GET, POST, PUT.
@_alias_router.get("", response_model=list[MailBridgeConfigResponse])
async def list_configs_alias(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[MailBridgeConfigResponse]:
    items = await _config_service.list(db)
    return [MailBridgeConfigResponse.model_validate(i) for i in items]


@_alias_router.post("", response_model=MailBridgeConfigResponse, status_code=201)
async def create_config_alias(
    body: MailBridgeConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> MailBridgeConfigResponse:
    item = await _config_service.create(db, body)
    return MailBridgeConfigResponse.model_validate(item)


@_alias_router.get("/{config_id}", response_model=MailBridgeConfigResponse)
async def get_config_alias(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> MailBridgeConfigResponse:
    item = await _config_service.get(db, config_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return MailBridgeConfigResponse.model_validate(item)


@_alias_router.put("/{config_id}", response_model=MailBridgeConfigResponse)
async def update_config_alias(
    config_id: str,
    body: MailBridgeConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> MailBridgeConfigResponse:
    item = await _config_service.update(db, config_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return MailBridgeConfigResponse.model_validate(item)


@_alias_router.delete("/{config_id}", response_model=None, response_class=Response, status_code=204)
async def delete_config_alias(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.TENANT_ADMIN)),
) -> Response:
    ok = await _config_service.delete(db, config_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MailBridge config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Send ───────────────────────────────────────────────────────────────────
@_mailbridge_router.post("/send", response_model=MailBridgeSendResponse)
async def send_email(
    body: MailBridgeSendRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> MailBridgeSendResponse:
    return await _send_service.send(
        db=db,
        to=body.to,
        subject=body.subject,
        body=body.body,
        sequence_id=body.sequenceId,
        config_id=body.configId,
    )


# ── Webhook (HMAC-verified inbound events) ─────────────────────────────────
async def _resolve_webhook_secret(db: AsyncSession) -> str | None:
    """Return the configured HMAC secret from the first active MailBridgeConfig.

    Per audit-A2 MEDIUM gap: the schema's `webhookSecret` column was never
    read. We read it here so each tenant can sign its own webhooks. If no
    config has a secret, returns None (caller decides whether to enforce).
    """
    result = await db.execute(
        select(MailBridgeConfig.webhookSecret)
        .where(MailBridgeConfig.isActive.is_(True))
        .where(MailBridgeConfig.webhookSecret.is_not(None))
        .order_by(MailBridgeConfig.updatedAt.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _verify_hmac(signature_header: str, secret: str, raw_body: bytes) -> bool:
    """Constant-time compare of hex HMAC-SHA256(raw_body, secret) vs header."""
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header, expected)


@_mailbridge_router.post("/webhook", response_model=MailBridgeWebhookResponse)
async def webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MailBridgeWebhookResponse:
    """Inbound tracking webhook from MailBridge. HMAC-verified when configured.

    Verification rules (audit-A2 MEDIUM gap fix):
      * In dev mode (`ENVIRONMENT=development`) → skip HMAC (caller may be a
        local MailBridge stub or curl).
      * Otherwise look up `MailBridgeConfig.webhookSecret` on the first
        active config. If none is configured, skip (cannot enforce without
        a secret — log a warning).
      * If a secret IS configured, require the `X-MailBridge-Signature`
        header (hex HMAC-SHA256 of the raw body) and compare with
        `hmac.compare_digest`. Missing or mismatched → 401.

    The raw request body is read exactly once and then re-parsed into the
    Pydantic `MailBridgeWebhookPayload` so HMAC is computed over the same
    bytes MailBridge signed.
    """
    settings = get_settings()
    raw_body = await request.body()

    if not settings.is_development:
        secret = await _resolve_webhook_secret(db)
        if secret:
            signature = request.headers.get("X-MailBridge-Signature", "")
            if not signature or not _verify_hmac(signature, secret, raw_body):
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "Invalid webhook signature",
                )
        # No secret configured → cannot enforce HMAC; fall through.

    try:
        # Task 3-a / FIX 3: MailBridgeTrackingEvent now carries a
        # ``payload`` field (dict[str, Any] | None). Pydantic auto-picks
        # it up from the raw JSON if MailBridge includes one — no code
        # change needed here. MailBridge should include the reply body at
        # ``payload.body`` or ``payload.text`` for "replied" events so
        # ``_auto_create_reply_draft`` can surface the actual reply text
        # in the auto-created ReplyDraft (instead of falling back to the
        # bounce/error reason or a placeholder).
        payload = MailBridgeWebhookPayload.model_validate_json(raw_body)
    except Exception as exc:  # noqa: BLE001 — surface as 400 not 500
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid webhook payload: {exc}",
        ) from exc

    accepted = 0
    rejected = 0
    for event in payload.events:
        ok = await _send_service.apply_tracking_event(db, event)
        if ok:
            accepted += 1
        else:
            rejected += 1
    return MailBridgeWebhookResponse(accepted=accepted, rejected=rejected)


# ── Email-tracking endpoints (audit-A2 CRITICAL gap fix) ───────────────────
# Spec: MIGRATION_DOCUMENT.md L1010-1012.
#   GET  /api/email-tracking         — list tracking events
#   POST /api/email-tracking         — record a tracking event
#   POST /api/email-tracking/sync    — bulk sync tracking events
# The implementation mounts these under /mailbridge/email-tracking so they
# share the mailbridge prefix and use the existing MailBridgeService.
def _sequence_to_event(seq: Sequence) -> MailBridgeTrackingEvent:
    """Project a Sequence row into its most recent tracking event.

    Sequences don't store a per-event log — they store the latest status +
    timestamps. We pick the most recent timestamp and emit a single event
    per sequence for the list endpoint.
    """
    event_name: str
    ts: datetime | None
    # Priority: replied > bounced > opened > sent (most "interesting" last).
    if seq.repliedAt:
        event_name, ts = "replied", seq.repliedAt
    elif seq.bouncedAt:
        event_name, ts = "bounced", seq.bouncedAt
    elif seq.openedAt:
        event_name, ts = "opened", seq.openedAt
    elif seq.sentAt:
        event_name, ts = "sent", seq.sentAt
    else:
        event_name, ts = "draft", seq.updatedAt or seq.createdAt

    return MailBridgeTrackingEvent(
        event=event_name,
        messageId=seq.mailBridgeMessageId or "",
        sequenceId=seq.id,
        timestamp=ts or datetime.now(timezone.utc),
        recipient=None,
        reason=seq.bounceReason,
    )


@_mailbridge_router.get(
    "/email-tracking",
    response_model=list[MailBridgeTrackingEvent],
)
async def list_tracking_events(
    campaign_id: str | None = None,
    prospect_id: str | None = None,
    since: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> list[MailBridgeTrackingEvent]:
    """List tracking events derived from Sequence rows.

    Query params:
      * `campaign_id` — filter to one campaign
      * `prospect_id` — filter to one prospect
      * `since`       — ISO-8601; only sequences with updatedAt >= since
    """
    stmt = select(Sequence)
    if campaign_id:
        stmt = stmt.where(Sequence.campaignId == campaign_id)
    if prospect_id:
        stmt = stmt.where(Sequence.prospectId == prospect_id)
    if since:
        stmt = stmt.where(Sequence.updatedAt >= since)
    stmt = stmt.order_by(Sequence.updatedAt.desc()).limit(500)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_sequence_to_event(s) for s in rows]


@_mailbridge_router.post(
    "/email-tracking",
    response_model=MailBridgeWebhookResponse,
)
async def record_tracking_event(
    event: MailBridgeTrackingEvent,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> MailBridgeWebhookResponse:
    """Record a single tracking event (sent/delivered/open/click/bounce/reply).

    Delegates to `MailBridgeService.apply_tracking_event` so the write-side
    behaviour is identical to the webhook path.
    """
    if event.event not in _TRACKING_EVENTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown tracking event '{event.event}'. "
            f"Allowed: {sorted(_TRACKING_EVENTS)}",
        )
    ok = await _send_service.apply_tracking_event(db, event)
    return MailBridgeWebhookResponse(accepted=1 if ok else 0, rejected=0 if ok else 1)


@_mailbridge_router.post(
    "/email-tracking/sync",
    response_model=MailBridgeWebhookResponse,
)
async def sync_tracking_events(
    payload: MailBridgeWebhookPayload,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.MANAGER)),
) -> MailBridgeWebhookResponse:
    """Bulk-sync tracking events from a MailBridge webhook batch.

    Same shape as POST /mailbridge/webhook but authenticated via Bearer
    token + role (used by internal sync jobs, not the public MailBridge
    ingress). Returns accepted/rejected counts.
    """
    accepted = 0
    rejected = 0
    for event in payload.events:
        if event.event not in _TRACKING_EVENTS:
            rejected += 1
            continue
        ok = await _send_service.apply_tracking_event(db, event)
        if ok:
            accepted += 1
        else:
            rejected += 1
    return MailBridgeWebhookResponse(accepted=accepted, rejected=rejected)


# ── Mount child routers into the public parent router ─────────────────────
# This MUST run AFTER all `@_mailbridge_router.*` and `@_alias_router.*`
# decorators above, because FastAPI's include_router snapshots `.routes` at
# call time. Calling it earlier would register zero routes.
router.include_router(_mailbridge_router)
router.include_router(_alias_router)


# ── Per-user quota + stats endpoints (SAAS2-USER-BE §I) ────────────────────
# Mounted directly on the parent router so they live at /mailbridge/... paths
# alongside the rest of the MailBridge surface. They are gated separately
# because the RBAC pattern differs (REP sees own; MANAGER+ sees any).


def _role_value(token: TokenPayload) -> str:
    return token.role.value if hasattr(token.role, "value") else str(token.role)


@router.get(
    "/mailbridge/quota-status",
    response_model=dict,
    tags=["MailBridge"],
)
async def get_my_quota_status(
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Return the current user's email quota + throttle status (today)."""
    quota_service = UserEmailQuotaService()
    return await quota_service.get_user_quota_status(db, token.sub)


@router.get(
    "/mailbridge/user-stats",
    response_model=dict,
    tags=["MailBridge"],
)
async def get_user_email_stats(
    user_id: str = Query(..., description="Keycloak user UUID to fetch stats for"),
    since: datetime | None = Query(
        default=None, description="ISO-8601 start (default: 30 days ago)"
    ),
    until: datetime | None = Query(
        default=None, description="ISO-8601 end (default: now)"
    ),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """Return per-user email activity stats over a date range.

    REP tokens may only query their own user_id; MANAGER+ may query any.
    """
    role = _role_value(token)
    if role.upper() == "REP" and user_id != token.sub:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="REP tokens may only query their own email stats.",
        )
    return await _send_service.get_user_email_stats(
        db, user_id, since=since, until=until
    )


__all__ = ["router"]
