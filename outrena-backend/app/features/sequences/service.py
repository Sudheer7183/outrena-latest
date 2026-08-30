"""
sequence_service.py — Sequence CRUD + send-email + scheduled-send + 7-touch cadence.

FIX (search_path crash): Removed all post-commit db.get() / db.refresh() calls.
After db.commit() on a schema-per-tenant asyncpg session, the connection is
re-pooled and loses search_path. All methods now read from the in-memory ORM
object after commit. eager_defaults=True on Base ensures server-generated
columns (id, createdAt, updatedAt) are populated via RETURNING at INSERT time.

FIX (wrong sender mailbox): send_email() now accepts caller_user_id which the
router passes as token.sub. This is used as the user_id for MailBridge routing
instead of seq.owner_user_id — which was frequently "system" on auto-generated
sequences, causing all sends to go through the first connected mailbox.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status as http_status
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_models import Campaign, Sequence, SubjectLine
from app.models.enums import EmailStatus
from app.models.prospect_models import Prospect
from app.schemas.sequences import (
    SEVEN_TOUCH_CADENCE,
    ScheduledSendRequest,
    SequenceCreate,
    SequenceUpdate,
    SendEmailRequest,
    SendEmailResponse,
    SubjectLineCreate,
)
from app.features.mailbridge.service import MailBridgeService

logger = structlog.get_logger(__name__)


class SequenceService:
    """CRUD + send + cadence operations for Sequence rows."""

    def __init__(self, mailbridge: MailBridgeService | None = None) -> None:
        self._mailbridge = mailbridge or MailBridgeService()

    async def list_sequences(
        self,
        db: AsyncSession,
        *,
        campaign_id: str | None = None,
        prospect_id: str | None = None,
        status: EmailStatus | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        role: str | None = None,
    ) -> tuple[list[Sequence], int]:
        """List sequences, optionally filtered by owner_user_id."""
        stmt = (
            select(Sequence)
            .options(selectinload(Sequence.subjectLines))
            .offset(offset)
            .limit(limit)
        )
        if campaign_id:
            stmt = stmt.where(Sequence.campaignId == campaign_id)
        if prospect_id:
            stmt = stmt.where(Sequence.prospectId == prospect_id)
        if status:
            stmt = stmt.where(Sequence.status == status)
        # Bounced sequences are tenant-wide data — never scope by owner_user_id.
        # The Bounced tab must show ALL bounces for the tenant regardless of who
        # sent the email (REP, MANAGER, TENANT_ADMIN).  Per-user scoping caused
        # the tab count to diverge from the Bounced card, which counts all-tenant.
        # We still scope REP by owner for non-bounced statuses (normal behaviour).
        is_bounced_query = (
            status is not None
            and (
                (hasattr(status, "value") and status.value == "Bounced")
                or str(status) == "Bounced"
            )
        )
        if user_id is not None and role is not None and role.upper() == "REP" and not is_bounced_query:
            stmt = stmt.where(Sequence.owner_user_id == user_id)
        result = await db.execute(stmt)
        items = list(result.scalars().all())
        return items, len(items)

    async def get(self, db: AsyncSession, sequence_id: str) -> Sequence | None:
        result = await db.execute(
            select(Sequence)
            .options(selectinload(Sequence.subjectLines))
            .where(Sequence.id == sequence_id)
        )
        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        db: AsyncSession,
        sequence_id: str,
        *,
        user_id: str,
        role: str,
    ) -> Sequence | None:
        """Fetch a sequence, enforcing per-user ACL for REP role."""
        item = await self.get(db, sequence_id)
        if item is None:
            return None
        if role.upper() == "REP" and item.owner_user_id != user_id:
            return None
        return item

    async def create(
        self,
        db: AsyncSession,
        body: SequenceCreate,
        *,
        owner_user_id: str | None = None,
    ) -> Sequence:
        seq = Sequence(
            campaignId=body.campaignId,
            prospectId=body.prospectId,
            touchNumber=body.touchNumber,
            sendDay=body.sendDay,
            channel=body.channel,
            angle=body.angle,
            framework=body.framework,
            subjectLine=body.subjectLine,
            bodyCopy=body.bodyCopy,
            status=EmailStatus.Draft,
            owner_user_id=owner_user_id or "system",
        )
        db.add(seq)
        await db.commit()
        return seq

    async def update(
        self, db: AsyncSession, sequence_id: str, body: SequenceUpdate
    ) -> Sequence | None:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(seq, key, value)
        await db.commit()
        return seq

    async def delete(self, db: AsyncSession, sequence_id: str) -> bool:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return False
        await db.delete(seq)
        await db.commit()
        return True

    async def add_subject_line(
        self, db: AsyncSession, sequence_id: str, body: SubjectLineCreate
    ) -> SubjectLine | None:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None
        sl = SubjectLine(
            sequenceId=sequence_id,
            variant=body.variant,
            isSelected=body.isSelected,
        )
        db.add(sl)
        await db.commit()
        return sl

    async def list_subject_lines(
        self, db: AsyncSession, sequence_id: str
    ) -> list[SubjectLine]:
        result = await db.execute(
            select(SubjectLine).where(SubjectLine.sequenceId == sequence_id)
        )
        return list(result.scalars().all())

    async def schedule_send(
        self,
        db: AsyncSession,
        sequence_id: str,
        body: ScheduledSendRequest,
        caller_user_id: str | None = None,
    ) -> Sequence | None:
        seq = await self.get(db, sequence_id)
        if seq is None:
            return None

        # ── Terminal status guard ─────────────────────────────────────────────
        # Bounced, Replied, and Failed sequences are historical records — they
        # must never be overwritten by a re-send.  Each send attempt should
        # create a NEW Sequence row instead.  Allowing a re-send to mutate an
        # existing Bounced row causes:
        #   1. status gets reset to Scheduled → Sent, hiding the bounce
        #   2. bouncedAt stays set but status='Sent' → corrupted state
        #   3. Bounced card/tab count decreases every time a new email is sent
        _current_status = seq.status.value if hasattr(seq.status, "value") else str(seq.status)
        if _current_status in ("Bounced", "Replied", "Failed"):
            from fastapi import HTTPException as _HTTPEx
            raise _HTTPEx(
                status_code=422,
                detail=(
                    f"Cannot re-send a sequence that is already '{_current_status}'. "
                    "Create a new sequence for this prospect instead."
                ),
            )

        # ── Suppression gate ──────────────────────────────────────────────────
        # Two-layer check:
        #   Layer 1 — Prospect-level: suppressed=true OR consent_status='withdrawn'
        #   Layer 2 — Email-level: email address in EmailSuppression table
        #
        # Layer 2 catches duplicate Prospect rows and future imports of the same
        # email address that would otherwise bypass the prospect-level flag.
        # Use raw SQL to bypass the SQLAlchemy identity-map cache.
        from sqlalchemy import text as _t
        _sup_result = await db.execute(
            _t('SELECT suppressed, consent_status, email FROM "Prospect" WHERE id = :pid'),
            {"pid": seq.prospectId},
        )
        _sup_row = _sup_result.mappings().first()
        if _sup_row and (
            _sup_row.get("suppressed") is True
            or _sup_row.get("consent_status") == "withdrawn"
        ):
            from fastapi import HTTPException as _HTTPEx
            raise _HTTPEx(
                status_code=422,
                detail="Cannot schedule — this prospect has unsubscribed. No further emails will be sent to them.",
            )

        # Layer 2: check EmailSuppression by email address (catches duplicates
        # and future imports of the same email).
        if _sup_row and _sup_row.get("email"):
            _email_lower = (_sup_row["email"] or "").strip().lower()
            if _email_lower:
                _es_result = await db.execute(
                    _t('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
                    {"email": _email_lower},
                )
                if _es_result.fetchone() is not None:
                    from fastapi import HTTPException as _HTTPEx
                    raise _HTTPEx(
                        status_code=422,
                        detail=(
                            f"Cannot schedule — {_email_lower} has unsubscribed from this tenant's outreach. "
                            "No further emails will be sent to this address."
                        ),
                    )

        # FIX: stamp the approving user's UUID so the scheduler routes
        # the send through their connected MailBridge inbox, not 'system'.
        if caller_user_id and caller_user_id != "system":
            seq.owner_user_id = caller_user_id
        seq.status = EmailStatus.Scheduled
        await db.commit()
        return seq

    async def send_email(
        self,
        db: AsyncSession,
        sequence_id: str,
        body: SendEmailRequest,
        *,
        caller_user_id: str | None = None,
    ) -> SendEmailResponse:
        """Fire a sequence immediately via MailBridge.

        caller_user_id: token.sub from the router — the Keycloak UUID of the
          user clicking Send Now. Used as MailBridge external_user_id so the
          email routes through that user's connected mailbox (Gmail/Outlook).
          Takes priority over seq.owner_user_id, which is often "system" on
          auto-generated sequences.
        """
        seq = await self.get(db, sequence_id)
        if seq is None:
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Sequence not found",
            )

        if not body.force and seq.status not in (
            EmailStatus.QaPassed,
            EmailStatus.Scheduled,
        ):
            return SendEmailResponse(
                id=sequence_id,
                status=seq.status,
                mailBridgeMessageId=None,
                sentAt=None,
                message=(
                    f"Cannot send sequence in status '{seq.status.value}'. "
                    "Pass force=true to bypass."
                ),
            )

        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == seq.campaignId)
        )
        campaign = campaign_result.scalar_one_or_none()

        to_email = ""
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == seq.prospectId)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is not None:
            raw_email = getattr(prospect, "email", None) or ""
            if raw_email and not getattr(prospect, "anonymized", False):
                try:
                    from app.services.pii_service import PiiService
                    to_email = PiiService().decrypt_field(raw_email) or ""
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "sequence.send_email.email_decrypt_failed",
                        prospect_id=getattr(prospect, "id", None),
                        error=str(exc),
                    )
                    to_email = raw_email
            elif raw_email:
                to_email = raw_email

        if not to_email:
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Prospect email is missing — cannot send sequence.",
            )

        # ── Suppression gate ──────────────────────────────────────────────────
        # Two-layer check:
        #   Layer 1 — Prospect-level: suppressed=true OR consent_status='withdrawn'
        #   Layer 2 — Email-level: email address in EmailSuppression table
        #
        # Layer 2 catches duplicate Prospect rows and future imports of the same
        # email address that would otherwise bypass the prospect-level flag.
        # Use raw SQL to bypass identity-map cache (expire_on_commit=False).
        from sqlalchemy import text as _t
        _sup_result = await db.execute(
            _t('SELECT suppressed, consent_status FROM "Prospect" WHERE id = :pid'),
            {"pid": seq.prospectId},
        )
        _sup_row = _sup_result.mappings().first()
        if _sup_row and (
            _sup_row.get("suppressed") is True
            or _sup_row.get("consent_status") == "withdrawn"
        ):
            return SendEmailResponse(
                id=sequence_id,
                status=EmailStatus.Failed,
                mailBridgeMessageId=None,
                sentAt=None,
                message="Prospect has unsubscribed — email not sent.",
            )

        # Layer 2: check EmailSuppression by email address (catches duplicates
        # and future imports of the same address into new Prospect rows).
        if to_email:
            _email_lower = to_email.strip().lower()
            try:
                _es_result = await db.execute(
                    _t('SELECT 1 FROM "EmailSuppression" WHERE email = :email LIMIT 1'),
                    {"email": _email_lower},
                )
                if _es_result.fetchone() is not None:
                    return SendEmailResponse(
                        id=sequence_id,
                        status=EmailStatus.Failed,
                        mailBridgeMessageId=None,
                        sentAt=None,
                        message=(
                            f"{_email_lower} has unsubscribed from this tenant's outreach — email not sent."
                        ),
                    )
            except Exception:  # noqa: BLE001
                # EmailSuppression table may not exist yet (migration 0021 pending).
                # Fail open: do not block sends if the table is missing.
                pass

        # ── Replace {{unsubscribe_url}} with real URL ─────────────────────────
        # IMPORTANT: the URL must point to the backend GET endpoint
        # (GET /api/v1/public/unsubscribe?token=...&tenant_slug=...) which
        # returns an HTML confirmation page directly — NOT to the React SPA
        # at /p/unsubscribe.  The React page requires JavaScript to execute
        # and then makes a separate POST; email security scanners and plain-
        # text clients follow GET links only, so the React approach fails
        # silently.  The backend GET endpoint handles the unsubscribe in one
        # HTTP round-trip with no client-side JS needed.
        body_to_send = seq.bodyCopy or ""
        if "{{unsubscribe_url}}" in body_to_send and prospect is not None:
            try:
                from app.utils.tenant_context import resolve_tenant_slug as _rts
                from app.core.config import get_settings as _gs
                _tenant_slug = await _rts(db)
                _prospect_token = getattr(prospect, "unsubscribeToken", None) or ""
                _base = _gs().BASE_DOMAIN
                if not _prospect_token:
                    # Prospect has no unsubscribeToken — log a warning and leave
                    # the placeholder in place rather than silently emitting a
                    # broken link.  Run migration 0020 to backfill missing tokens.
                    logger.warning(
                        "sequence.send_email.missing_unsubscribe_token",
                        sequence_id=sequence_id,
                        prospect_id=seq.prospectId,
                        hint="Run alembic upgrade head (migration 0020) to backfill tokens.",
                    )
                elif _tenant_slug and _base:
                    # Direct backend GET — works in all email clients, security
                    # scanners, and one-click RFC 8058 unsubscribe handlers.
                    body_to_send = body_to_send.replace(
                        "{{unsubscribe_url}}",
                        f"https://{_base}/api/v1/public/unsubscribe"
                        f"?token={_prospect_token}&tenant_slug={_tenant_slug}",
                    )
            except Exception:  # noqa: BLE001
                pass

        # FIX: use caller_user_id (token.sub) as the authoritative sender.
        # Fall back to seq.owner_user_id only if it is a real user UUID
        # (not "system"). Never pass "system" to MailBridge — it skips
        # per-user routing and sends from the tenant's default mailbox.
        # seq_owner = getattr(seq, "owner_user_id", None)
        # effective_user_id = (
        #     caller_user_id
        #     or (seq_owner if seq_owner and seq_owner != "system" else None)
        # )

        # # send() never commits on this db session — all side effects use
        # # isolated AsyncSessionLocal() sessions internally.
        # result = await self._mailbridge.send(
        #     db=db,
        #     to=to_email,
        #     subject=seq.subjectLine or "",
        #     body=seq.bodyCopy or "",
        #     sequence_id=sequence_id,
        #     config_id=campaign.domainId if campaign else None,
        #     user_id=effective_user_id,
        # )

        seq_owner = getattr(seq, "owner_user_id", None)
        effective_user_id = (
            caller_user_id
            or (seq_owner if seq_owner and seq_owner != "system" else None)
        )

        # ── Domain warming gate (mirrors scheduler/_send_via_mailbridge) ──
        # Resolve the MailBridgeConfig for this user, then check the Domain
        # it points to — same three checks the scheduler runs on every tick.
        # body.force=true (MANAGER only) bypasses all three gates so admins
        # can override for testing or urgent manual sends.
        if not body.force:
            from app.features.mailbridge.service import MailBridgeService
            from app.models.config_models import Domain as _Domain, MailBridgeConfig as _MBConfig

            mb_config = await MailBridgeService._resolve_config(
                db, None, user_id=effective_user_id
            )
            if mb_config is not None and getattr(mb_config, "domainId", None):
                dom_result = await db.execute(
                    select(_Domain).where(_Domain.id == mb_config.domainId)
                )
                dom = dom_result.scalar_one_or_none()

                # Gate 1 — DNS verification
                if dom is not None and dom.lastChecked is not None:
                    failing = [
                        name for name, ok in (
                            ("SPF", dom.spfStatus),
                            ("DKIM", dom.dkimStatus),
                            ("DMARC", dom.dmarcStatus),
                        ) if not ok
                    ]
                    if failing:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"DNS verification failing for domain "
                                f"'{dom.domainName}': {', '.join(failing)}. "
                                "Fix the DNS records and re-verify in "
                                "Setup → Domains before sending."
                            ),
                        )

                # Gate 2 — warming week
                if dom is not None:
                    week = int(getattr(dom, "warmingWeek", 0) or 0)
                    if 1 <= week < 2:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"Domain '{dom.domainName}' has only completed "
                                f"{week} week(s) of warm-up. Click 'Auto-warm' "
                                "on Setup → Domains to advance to Week 2 before "
                                "sending."
                            ),
                        )

                # Gate 3 — daily cap
                if dom is not None:
                    _WARMUP_RAMP: dict[int, int] = {
                        1: 10, 2: 30, 3: 50, 4: 100, 5: 200, 6: 350, 7: 500
                    }
                    week = int(getattr(dom, "warmingWeek", 0) or 0)
                    base = int(getattr(dom, "dailySendLimit", 0) or 0) or 10_000
                    effective_cap = min(base, _WARMUP_RAMP[week]) if 1 <= week <= 7 else base
                    sent_today = (
                        await db.execute(
                            text(
                                'SELECT COUNT(*) FROM "Sequence" s '
                                'JOIN "Campaign" c ON c.id = s."campaignId" '
                                'WHERE c."domainId" = :dom_id '
                                "  AND s.\"sentAt\" >= date_trunc('day', now())"
                            ),
                            {"dom_id": dom.id},
                        )
                    ).scalar() or 0
                    if int(sent_today) >= effective_cap:
                        raise HTTPException(
                            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"Daily warm-up cap reached for domain "
                                f"'{dom.domainName}' "
                                f"({sent_today}/{effective_cap} emails, "
                                f"Week {dom.warmingWeek}). "
                                "Remaining sends will go out tomorrow."
                            ),
                        )

        # send() never commits on this db session — all side effects use
        # isolated AsyncSessionLocal() sessions internally.
        result = await self._mailbridge.send(
            db=db,
            to=to_email,
            subject=seq.subjectLine or "",
            body=body_to_send,
            sequence_id=sequence_id,
            config_id=None,  # FIX: campaign.domainId is a Domain PK, not a MailBridgeConfig PK.
            user_id=effective_user_id,
        )

        # Capture values before commit — no post-commit db.get() needed.
        new_status = EmailStatus.Sent if result.accepted else EmailStatus.Failed
        new_sent_at = datetime.now(timezone.utc) if result.accepted else None
        new_message_id = result.messageId

        seq.status = new_status
        seq.sentAt = new_sent_at
        seq.mailBridgeMessageId = new_message_id
        # FIX: stamp owner_user_id with the mailbox that actually sent the email.
        # effective_user_id is the Keycloak UUID MailBridge used for routing —
        # this is the same UUID registered as external_user_id in MailBridge's
        # users table. The reply poller uses owner_user_id to call
        # GET /auth/connect/replies, so it must match the mailbox that received
        # the reply, not the user who clicked Send Now.
        if result.accepted and effective_user_id:
            seq.owner_user_id = effective_user_id
        await db.commit()

        return SendEmailResponse(
            id=sequence_id,
            status=new_status,
            mailBridgeMessageId=new_message_id,
            sentAt=new_sent_at,
            message="Sent" if result.accepted else "Send failed",
        )

    @staticmethod
    def get_cadence() -> list[Any]:
        """Return the 7-touch cadence (days 1/4/9/16/25/35)."""
        return SEVEN_TOUCH_CADENCE

    async def auto_generate_for_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
        *,
        prospect_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[Sequence]:
        """Auto-generate the 7 Sequence rows for a campaign's 7-touch cadence."""
        from app.models.campaign_models import Sequence as _Seq

        if not prospect_id:
            return []

        created: list[Sequence] = []
        for touch in SEVEN_TOUCH_CADENCE:
            existing = (
                await db.execute(
                    select(_Seq).where(
                        _Seq.campaignId == campaign_id,
                        _Seq.prospectId == prospect_id,
                        _Seq.touchNumber == touch.touchNumber,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            seq = Sequence(
                campaignId=campaign_id,
                prospectId=prospect_id,
                touchNumber=touch.touchNumber,
                sendDay=touch.sendDay,
                channel="email",
                angle=touch.angle,
                framework=touch.defaultFramework,
                status=EmailStatus.Draft,
                owner_user_id=owner_user_id or "system",
            )
            db.add(seq)
            created.append(seq)

        if created:
            await db.commit()

        return created