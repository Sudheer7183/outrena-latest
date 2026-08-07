"""
gdpr_service.py — GDPR data-subject-request + consent + export orchestration.

Implements the six GDPR rights (Articles 15-22) against the OUTRENA
multitenant backend:

  - access         (Art 15)  → process_access_request
  - portability    (Art 20)  → process_portability_request
  - rectification  (Art 16)  → process_rectification_request
  - erasure        (Art 17)  → process_erasure_request
  - restriction    (Art 18)  → process_restriction_request
  - objection      (Art 21)  → process_objection_request

DSRs are stored in the PUBLIC schema (data_subject_requests table) so the
platform operator has a unified view across tenants. Consent records live
in the tenant schema (consents + consent_logs).

All operations are idempotent — re-running a completed DSR returns the
existing result without re-processing. SLA tracking (3-day acknowledgement,
30-day completion) is enforced at the runbook level (runbook 13).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.consent import (
    CONSENT_LOG_ACTIONS,  # noqa: F401  (exported for convenience)
    CONSENT_STATUSES,  # noqa: F401
    LAWFUL_BASES,  # noqa: F401
    Consent,
    ConsentLog,
)
from app.models.data_subject_request import (
    DSR_STATUSES,  # noqa: F401
    DSR_TYPES,  # noqa: F401
    DataSubjectRequest,
)
from app.services.pii_service import PiiService
from app.features.gdpr.retention_service import RetentionService
from app.utils.slug import schema_name_for

logger = structlog.get_logger(__name__)


class GdprService:
    """Orchestrates GDPR data-subject requests + consent management."""

    def __init__(self) -> None:
        self._pii = PiiService()
        self._retention = RetentionService()

    # ════════════════════════════════════════════════════════════════════════
    # Data Subject Requests
    # ════════════════════════════════════════════════════════════════════════

    async def submit_dsr(
        self,
        db: AsyncSession,
        *,
        email: str,
        tenant_slug: str | None,
        request_type: str,
        details: dict[str, Any] | None = None,
    ) -> DataSubjectRequest:
        """Create a new DSR with status=pending.

        If ``tenant_slug`` is not provided, attempt to auto-detect it by
        searching every active tenant's Prospect table for the email.
        Cross-tenant query — runs against public.tenants then per-tenant
        Prospect tables (limited to first match for efficiency).
        """
        if request_type not in DSR_TYPES:
            raise ValueError(
                f"request_type must be one of {DSR_TYPES}, got '{request_type}'"
            )

        email = email.strip().lower()

        if not tenant_slug:
            tenant_slug = await self._detect_tenant_for_email(email)
        if not tenant_slug:
            # Could not find the email in any tenant — record the DSR anyway
            # with tenant_slug="__unknown__" so the operator can investigate.
            tenant_slug = "__unknown__"

        dsr = DataSubjectRequest(
            email=email,
            tenant_slug=tenant_slug,
            request_type=request_type,
            details=details or {},
            status="pending",
        )
        db.add(dsr)
        await db.commit()
        dsr = await db.get(DataSubjectRequest, dsr.id)

        logger.info(
            "gdpr.dsr_submitted",
            dsr_id=dsr.id,
            email=email,
            tenant=tenant_slug,
            request_type=request_type,
        )
        return dsr

    async def get_dsr_status(
        self, db: AsyncSession, dsr_id: int
    ) -> DataSubjectRequest | None:
        result = await db.execute(
            select(DataSubjectRequest).where(DataSubjectRequest.id == dsr_id)
        )
        return result.scalar_one_or_none()

    async def list_dsrs(
        self,
        db: AsyncSession,
        *,
        tenant_slug: str | None = None,
        status_filter: str | None = None,
    ) -> list[DataSubjectRequest]:
        stmt = select(DataSubjectRequest).order_by(
            DataSubjectRequest.created_at.desc()
        )
        if tenant_slug is not None:
            stmt = stmt.where(DataSubjectRequest.tenant_slug == tenant_slug)
        if status_filter is not None:
            stmt = stmt.where(DataSubjectRequest.status == status_filter)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def assign_dsr(
        self, db: AsyncSession, dsr_id: int, assignee: str
    ) -> DataSubjectRequest | None:
        dsr = await self.get_dsr_status(db, dsr_id)
        if dsr is None:
            return None
        dsr.assigned_to = assignee
        if dsr.status == "pending":
            dsr.status = "in_progress"
        await db.commit()
        dsr = await db.get(DataSubjectRequest, dsr.id)
        return dsr

    # ── Per-right processors ────────────────────────────────────────────────

    async def process_dsr(
        self, db: AsyncSession, dsr_id: int
    ) -> DataSubjectRequest:
        """Dispatch the DSR to the right processor based on request_type."""
        dsr = await self.get_dsr_status(db, dsr_id)
        if dsr is None:
            raise ValueError(f"DSR {dsr_id} not found")
        if dsr.status in ("completed", "rejected"):
            return dsr  # idempotent — re-processing returns existing result

        dsr.status = "in_progress"
        await db.commit()
        dsr = await db.get(DataSubjectRequest, dsr.id)

        try:
            if dsr.request_type == "access":
                export_url = await self.process_access_request(dsr)
                await self.complete_dsr(db, dsr_id, export_url=export_url)
            elif dsr.request_type == "portability":
                export_url = await self.process_portability_request(dsr)
                await self.complete_dsr(db, dsr_id, export_url=export_url)
            elif dsr.request_type == "erasure":
                await self.process_erasure_request(dsr)
                await self.complete_dsr(db, dsr_id, notes="Prospect anonymised.")
            elif dsr.request_type == "rectification":
                corrections = (dsr.details or {}).get("corrections", {})
                await self.process_rectification_request(dsr, corrections)
                await self.complete_dsr(db, dsr_id, notes="Prospect rectified.")
            elif dsr.request_type == "objection":
                await self.process_objection_request(dsr)
                await self.complete_dsr(
                    db, dsr_id, notes="Prospect suppressed (objection)."
                )
            elif dsr.request_type == "restriction":
                await self.process_restriction_request(dsr)
                await self.complete_dsr(
                    db, dsr_id, notes="Processing restricted."
                )
            else:
                raise ValueError(f"Unknown request_type: {dsr.request_type}")
        except Exception as exc:  # noqa: BLE001
            logger.error("gdpr.dsr_processing_failed", dsr_id=dsr_id, error=str(exc))
            # Leave status="in_progress" so the operator can investigate.
            raise

        dsr = await db.get(DataSubjectRequest, dsr.id)
        return dsr

    async def process_access_request(self, dsr: DataSubjectRequest) -> str:
        """Export all data for the email across the tenant → return export URL.

        Generates a JSON bundle and stores the export URL on the DSR row.
        The actual data is fetched on-demand by the GET /gdpr/export/{id}
        endpoint (avoids storing large blobs in the DB).
        """
        # Mark URL — the router resolves the path at download time.
        export_url = f"/api/v1/gdpr/export/{dsr.id}"
        logger.info("gdpr.access_processed", dsr_id=dsr.id, email=dsr.email)
        return export_url

    async def process_portability_request(self, dsr: DataSubjectRequest) -> str:
        """Like access but in machine-readable JSON only (no CSV)."""
        export_url = f"/api/v1/gdpr/export/{dsr.id}?format=json"
        logger.info("gdpr.portability_processed", dsr_id=dsr.id, email=dsr.email)
        return export_url

    async def process_erasure_request(self, dsr: DataSubjectRequest) -> None:
        """Anonymise the prospect + soft-delete. Keep row for aggregate stats."""
        if dsr.tenant_slug == "__unknown__":
            return  # cannot process — no tenant context

        async with AsyncSessionLocal() as session:
            schema = schema_name_for(dsr.tenant_slug)
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            result = await session.execute(
                text(
                    'SELECT id FROM "Prospect" '
                    'WHERE lower("email") = :email '
                    '  AND COALESCE("anonymized", false) = false'
                ),
                {"email": dsr.email.lower()},
            )
            prospect_ids = [r.id for r in result.fetchall()]
            if not prospect_ids:
                return

            await session.execute(
                text(
                    'UPDATE "Prospect" SET '
                    '  "firstName" = \'[anonymized]\', '
                    '  "lastName" = \'[anonymized]\', '
                    '  "email" = \'[anonymized]\', '
                    '  "linkedinUrl" = NULL, '
                    '  "notes" = NULL, '
                    '  "deleted_at" = now(), '
                    '  "anonymized" = true, '
                    '  "consent_status" = \'withdrawn\' '
                    'WHERE id = ANY(:ids)'
                ),
                {"ids": prospect_ids},
            )
            await session.commit()

        logger.info(
            "gdpr.erasure_processed",
            dsr_id=dsr.id,
            email=dsr.email,
            affected=len(prospect_ids),
        )

    async def process_rectification_request(
        self, dsr: DataSubjectRequest, corrections: dict[str, Any]
    ) -> None:
        """Update the prospect's data per the corrections dict.

        Only fields present in ``corrections`` are updated; other fields
        are untouched. PII fields (firstName, lastName, email) are
        re-encrypted at rest by PiiService.
        """
        if dsr.tenant_slug == "__unknown__" or not corrections:
            return

        # Whitelist of fields a data subject may rectify.
        allowed = {"firstName", "lastName", "email", "title", "company", "domain"}
        updates = {k: v for k, v in corrections.items() if k in allowed}
        if not updates:
            return

        # Encrypt PII fields before persisting.
        pii_fields = {"firstName", "lastName", "email"}
        for k in pii_fields:
            if k in updates and updates[k]:
                updates[k] = self._pii.encrypt_field(updates[k])

        set_clauses = ", ".join(f'"{k}" = :{k}' for k in updates)
        params: dict[str, Any] = dict(updates)
        params["email"] = dsr.email.lower()

        async with AsyncSessionLocal() as session:
            schema = schema_name_for(dsr.tenant_slug)
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                text(
                    f'UPDATE "Prospect" SET {set_clauses} '
                    f'WHERE lower("email") = :email'
                ),
                params,
            )
            await session.commit()

        logger.info(
            "gdpr.rectification_processed",
            dsr_id=dsr.id,
            email=dsr.email,
            fields=list(updates.keys()),
        )

    async def process_objection_request(self, dsr: DataSubjectRequest) -> None:
        """Suppress the prospect — stop all outbound processing."""
        if dsr.tenant_slug == "__unknown__":
            return

        async with AsyncSessionLocal() as session:
            schema = schema_name_for(dsr.tenant_slug)
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                text(
                    'UPDATE "Prospect" SET '
                    '  "consent_status" = \'withdrawn\', '
                    '  "suppressed" = true, '
                    '  "suppressionReason" = \'gdpr_objection\', '
                    '  "suppressedAt" = now() '
                    'WHERE lower("email") = :email'
                ),
                {"email": dsr.email.lower()},
            )
            await session.commit()

        logger.info("gdpr.objection_processed", dsr_id=dsr.id, email=dsr.email)

    async def process_restriction_request(self, dsr: DataSubjectRequest) -> None:
        """Freeze processing — block all outbound actions for this prospect.

        Implemented via the same suppression flag as objection (both have
        the effect of stopping outbound processing); the distinction is
        recorded in the DSR details for the operator's audit trail.
        """
        if dsr.tenant_slug == "__unknown__":
            return

        async with AsyncSessionLocal() as session:
            schema = schema_name_for(dsr.tenant_slug)
            await session.execute(text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                text(
                    'UPDATE "Prospect" SET '
                    '  "consent_status" = \'withdrawn\', '
                    '  "suppressed" = true, '
                    '  "suppressionReason" = \'gdpr_restriction\', '
                    '  "suppressedAt" = now() '
                    'WHERE lower("email") = :email'
                ),
                {"email": dsr.email.lower()},
            )
            await session.commit()

        logger.info("gdpr.restriction_processed", dsr_id=dsr.id, email=dsr.email)

    # ── DSR lifecycle ───────────────────────────────────────────────────────

    async def complete_dsr(
        self,
        db: AsyncSession,
        dsr_id: int,
        notes: str = "",
        export_url: str | None = None,
    ) -> DataSubjectRequest | None:
        dsr = await self.get_dsr_status(db, dsr_id)
        if dsr is None:
            return None
        dsr.status = "completed"
        dsr.completed_at = datetime.now(timezone.utc)
        dsr.completion_notes = notes or None
        if export_url:
            dsr.export_url = export_url
        await db.commit()
        dsr = await db.get(DataSubjectRequest, dsr.id)
        logger.info("gdpr.dsr_completed", dsr_id=dsr_id)
        return dsr

    async def reject_dsr(
        self,
        db: AsyncSession,
        dsr_id: int,
        reason: str,
    ) -> DataSubjectRequest | None:
        dsr = await self.get_dsr_status(db, dsr_id)
        if dsr is None:
            return None
        dsr.status = "rejected"
        dsr.rejection_reason = reason
        dsr.completed_at = datetime.now(timezone.utc)
        await db.commit()
        dsr = await db.get(DataSubjectRequest, dsr.id)
        logger.info("gdpr.dsr_rejected", dsr_id=dsr_id, reason=reason)
        return dsr

    # ════════════════════════════════════════════════════════════════════════
    # Consent management (tenant-scoped)
    # ════════════════════════════════════════════════════════════════════════

    async def record_consent(
        self,
        db: AsyncSession,
        *,
        prospect_id: str,
        email: str,
        lawful_basis: str,
        consent_text: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Consent:
        """Record a consent grant for a prospect + append a ConsentLog entry.

        If a Consent row already exists for (prospect_id, lawful_basis),
        UPDATE its state to "granted" and append a new ConsentLog row
        (consent history is append-only — the previous grant is preserved
        in the log). Also bumps the prospect's consent_status field.
        """
        if lawful_basis not in LAWFUL_BASES:
            raise ValueError(f"lawful_basis must be one of {LAWFUL_BASES}")

        # Find or create the Consent row.
        result = await db.execute(
            select(Consent).where(
                Consent.prospect_id == prospect_id,
                Consent.lawful_basis == lawful_basis,
            )
        )
        consent = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if consent is None:
            consent = Consent(
                prospect_id=prospect_id,
                email=email.lower(),
                lawful_basis=lawful_basis,
                consent_status="granted",
                consent_text=consent_text,
                ip_address=ip_address,
                user_agent=user_agent,
                granted_at=now,
            )
            db.add(consent)
            await db.flush()
        else:
            consent.consent_status = "granted"
            consent.consent_text = consent_text
            consent.ip_address = ip_address
            consent.user_agent = user_agent
            consent.granted_at = now
            consent.withdrawn_at = None

        # Append the log entry.
        log_entry = ConsentLog(
            consent_id=consent.id,
            action="granted",
            details={
                "lawful_basis": lawful_basis,
                "consent_text": consent_text,
                "ip": ip_address,
                "user_agent": user_agent,
            },
        )
        db.add(log_entry)

        # Bump prospect.consent_status (only if lawful_basis is "consent";
        # other bases don't require explicit consent tracking on the prospect).
        if lawful_basis == "consent":
            await db.execute(
                text(
                    'UPDATE "Prospect" SET "consent_status" = \'granted\' '
                    'WHERE id = :pid'
                ),
                {"pid": prospect_id},
            )

        await db.commit()
        consent = await db.get(Consent, consent.id)
        logger.info(
            "gdpr.consent_granted",
            prospect_id=prospect_id,
            lawful_basis=lawful_basis,
        )
        return consent

    async def withdraw_consent(
        self,
        db: AsyncSession,
        *,
        email: str,
        lawful_basis: str | None = None,
    ) -> list[Consent]:
        """Withdraw consent for the given email (across all lawful bases).

        Also suppresses the prospect (sets suppressed=true) so outbound
        processing stops immediately.
        """
        email = email.strip().lower()
        stmt = select(Consent).where(Consent.email == email)
        if lawful_basis is not None:
            stmt = stmt.where(Consent.lawful_basis == lawful_basis)
        result = await db.execute(stmt)
        consents = list(result.scalars().all())
        if not consents:
            return []

        now = datetime.now(timezone.utc)
        for c in consents:
            c.consent_status = "withdrawn"
            c.withdrawn_at = now
            db.add(
                ConsentLog(
                    consent_id=c.id,
                    action="withdrawn",
                    details={"lawful_basis": c.lawful_basis, "reason": "user_request"},
                )
            )

        # Suppress the prospect.
        await db.execute(
            text(
                'UPDATE "Prospect" SET '
                '  "consent_status" = \'withdrawn\', '
                '  "suppressed" = true, '
                '  "suppressionReason" = \'consent_withdrawn\', '
                '  "suppressedAt" = now() '
                'WHERE lower("email") = :email'
            ),
            {"email": email},
        )
        await db.commit()

        for c in consents:
            c = await db.get(Consent, c.id)
        logger.info(
            "gdpr.consent_withdrawn",
            email=email,
            lawful_basis=lawful_basis,
            count=len(consents),
        )
        return consents

    async def get_consent_status(
        self, db: AsyncSession, email: str
    ) -> dict[str, Any]:
        """Return a summary of the consent state for an email."""
        email = email.strip().lower()
        result = await db.execute(
            select(Consent).where(Consent.email == email)
        )
        consents = list(result.scalars().all())
        return {
            "email": email,
            "consents": [
                {
                    "id": c.id,
                    "prospect_id": c.prospect_id,
                    "lawful_basis": c.lawful_basis,
                    "consent_status": c.consent_status,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
                    "consent_text": c.consent_text,
                }
                for c in consents
            ],
            "any_granted": any(c.consent_status == "granted" for c in consents),
            "all_withdrawn": bool(consents) and all(
                c.consent_status == "withdrawn" for c in consents
            ),
        }

    async def list_consents(
        self, db: AsyncSession, prospect_id: str
    ) -> list[Consent]:
        """List all consent records for a prospect (across all lawful bases)."""
        result = await db.execute(
            select(Consent)
            .where(Consent.prospect_id == prospect_id)
            .order_by(Consent.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_consent_logs(
        self, db: AsyncSession, consent_id: int
    ) -> list[ConsentLog]:
        """List the immutable audit log for a single consent record."""
        result = await db.execute(
            select(ConsentLog)
            .where(ConsentLog.consent_id == consent_id)
            .order_by(ConsentLog.created_at.desc())
        )
        return list(result.scalars().all())

    # ════════════════════════════════════════════════════════════════════════
    # Data export (DSR Article 15 + 20)
    # ════════════════════════════════════════════════════════════════════════

    async def export_user_data(
        self, tenant_slug: str, email: str
    ) -> dict[str, Any]:
        """Collect every record tied to ``email`` across the tenant.

        Returns a structured dict ready for JSON serialisation. Used by:
          - DSR Article 15 (access) — full export including CSV-friendly rows.
          - DSR Article 20 (portability) — JSON-only machine-readable export.
          - scripts/gdpr-data-export.py CLI.
        """
        if tenant_slug == "__unknown__":
            return {
                "email": email,
                "tenant_slug": tenant_slug,
                "error": "Tenant unknown — no data exported.",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        schema = schema_name_for(tenant_slug)
        email_lower = email.strip().lower()
        bundle: dict[str, Any] = {
            "email": email,
            "tenant_slug": tenant_slug,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prospect": None,
            "consents": [],
            "consent_logs": [],
            "sequences": [],
            "campaign_prospects": [],
            "deals": [],
            "reply_drafts": [],
            "meeting_preps": [],
            "meetings": [],
            "call_logs": [],
            "job_change_alerts": [],
            "support_tickets": [],
        }

        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}", public'))

            # ── Prospect (decrypt PII on read) ────────────────────────────
            prospect_row = (
                await session.execute(
                    text(
                        'SELECT * FROM "Prospect" WHERE lower("email") = :email '
                        'LIMIT 1'
                    ),
                    {"email": email_lower},
                )
            ).fetchone()
            if prospect_row is not None:
                prospect_dict = dict(prospect._mapping)
                # Decrypt PII for the export (subject is entitled to see
                # their own data in cleartext).
                self._pii.decrypt_prospect(prospect_dict)
                bundle["prospect"] = self._serialise(prospect_dict)

                prospect_id = prospect_dict.get("id")
                if prospect_id:
                    # ── Consents + logs ──────────────────────────────────
                    bundle["consents"] = await self._fetch_all(
                        session,
                        text("SELECT * FROM consents WHERE prospect_id = :pid"),
                        {"pid": prospect_id},
                    )
                    consent_ids = [c["id"] for c in bundle["consents"]]
                    if consent_ids:
                        bundle["consent_logs"] = await self._fetch_all(
                            session,
                            text(
                                "SELECT * FROM consent_logs "
                                "WHERE consent_id = ANY(:ids) "
                                "ORDER BY created_at DESC"
                            ),
                            {"ids": consent_ids},
                        )

                    # ── Sequence touches (email engagement) ──────────────
                    bundle["sequences"] = await self._fetch_all(
                        session,
                        text("SELECT * FROM \"Sequence\" WHERE \"prospectId\" = :pid"),
                        {"pid": prospect_id},
                    )

                    # ── CampaignProspect (campaign membership) ───────────
                    bundle["campaign_prospects"] = await self._fetch_all(
                        session,
                        text(
                            'SELECT * FROM "CampaignProspect" '
                            'WHERE "prospectId" = :pid'
                        ),
                        {"pid": prospect_id},
                    )

                    # ── Deals ────────────────────────────────────────────
                    bundle["deals"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "Deal" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

                    # ── Reply drafts ─────────────────────────────────────
                    bundle["reply_drafts"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "ReplyDraft" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

                    # ── Meeting prep briefs ──────────────────────────────
                    bundle["meeting_preps"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "MeetingPrep" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

                    # ── Meetings ─────────────────────────────────────────
                    bundle["meetings"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "Meeting" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

                    # ── Call logs ────────────────────────────────────────
                    bundle["call_logs"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "CallLog" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

                    # ── Job-change alerts ────────────────────────────────
                    bundle["job_change_alerts"] = await self._fetch_all(
                        session,
                        text('SELECT * FROM "JobChangeAlert" WHERE "prospectId" = :pid'),
                        {"pid": prospect_id},
                    )

        # ── Public-schema: DSR history for this email ──────────────────────
        async with AsyncSessionLocal() as session:
            await session.execute(text('SET search_path TO "public"'))
            dsrs = await self._fetch_all(
                session,
                text(
                    "SELECT id, request_type, status, created_at, completed_at "
                    "FROM public.data_subject_requests "
                    "WHERE lower(email) = :email ORDER BY created_at DESC"
                ),
                {"email": email_lower},
            )
            bundle["dsr_history"] = dsrs

        return bundle

    # ════════════════════════════════════════════════════════════════════════
    # Retention
    # ════════════════════════════════════════════════════════════════════════

    async def enforce_retention(self, tenant_slug: str) -> dict[str, int]:
        """Delegate to RetentionService — run all policies for the tenant."""
        return await self._retention.enforce_all_policies(tenant_slug)

    async def get_retention_status(
        self, tenant_slug: str
    ) -> dict[str, dict[str, Any]]:
        return await self._retention.get_policy_status(tenant_slug)

    # ════════════════════════════════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════════════════════════════════

    async def _detect_tenant_for_email(self, email: str) -> str | None:
        """Search every active tenant's Prospect table for the email.

        Returns the slug of the first tenant whose schema contains a
        Prospect row with the given email, or None if no match found.
        """
        async with AsyncSessionLocal() as session:
            await session.execute(text('SET search_path TO "public"'))
            rows = (
                await session.execute(
                    text(
                        "SELECT slug, schema_name FROM public.tenants "
                        "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                    )
                )
            ).fetchall()

        for row in rows:
            schema = row.schema_name
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(text(f'SET search_path TO "{schema}", public'))
                    found = (
                        await session.execute(
                            text(
                                'SELECT 1 FROM "Prospect" '
                                'WHERE lower("email") = :email '
                                '  AND COALESCE("anonymized", false) = false '
                                'LIMIT 1'
                            ),
                            {"email": email.lower()},
                        )
                    ).fetchone()
                    if found is not None:
                        return row.slug
            except Exception as exc:  # noqa: BLE001 — tenant schema may be mid-migration
                logger.debug(
                    "gdpr.tenant_search_skipped",
                    slug=row.slug,
                    error=str(exc),
                )
                continue
        return None

    @staticmethod
    async def _fetch_all(
        session: AsyncSession, stmt: text, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        rows = (await session.execute(stmt, params)).fetchall()
        return [GdprService._serialise(dict(r._mapping)) for r in rows]

    @staticmethod
    def _serialise(obj: dict[str, Any]) -> dict[str, Any]:
        """JSON-safe serialiser — converts datetimes to ISO strings."""
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, (list, dict)):
                out[k] = json.loads(json.dumps(v, default=str))
            else:
                out[k] = v
        return out


__all__ = ["GdprService"]
