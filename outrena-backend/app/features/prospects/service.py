"""prospect_service.py — Prospect CRUD + CSV import + enrich + email-validate.

CSV import delegates to app.services.csv_import_service.import_csv (Fix-3);
email validation uses a stdlib socket-based MX lookup with optional
dnspython support if installed.

FIX-BE-1 / CRITICAL 3: ProspectScorer is now invoked after every
``create()`` and from ``import_csv()`` (via CsvImportService) so newly-
created Prospect rows have ``icpFitScore`` / ``urgencyTier`` / ``icpPersona``
/ ``icpScoreBreakdown`` populated whenever an IcpProfile is associated.
Scoring failures are logged + swallowed so prospect creation is never
blocked by a scoring bug.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.prospects import (
    EmailValidateRequest,
    EmailValidateResponse,
    EnrichRequest,
    EnrichResponse,
    ProspectCreate,
    ProspectUpdate,
)
from app.services.pii_service import PiiService
from app.utils.tenant_context import resolve_tenant_slug

logger = structlog.get_logger(__name__)

# Fields on Prospect that are PII and need encrypt-on-write / decrypt-on-read.
# Matches PiiService.PII_FIELDS but uses the camelCase names on the Prospect
# model (firstName, lastName, email). 'phone' is reserved for future use.
_PROSPECT_PII_FIELDS: tuple[str, ...] = ("firstName", "lastName", "email")


# Optional dnspython support — falls back to socket-based lookup if not installed.
try:
    import dns.resolver  # type: ignore
    import dns.exception  # type: ignore

    _HAS_DNSPYTHON = True
except ImportError:  # pragma: no cover — defensive
    _HAS_DNSPYTHON = False


class ProspectService:
    """CRUD + CSV import + enrich + email-validate for Prospect rows.

    GDPR compliance wiring (added in SAAS2-GDPR-BE):
      - PII fields (firstName, lastName, email) are encrypted at rest on
        create/update and decrypted on get/list via PiiService.
      - delete() is now SOFT-DELETE — sets deleted_at + anonymised PII to
        "[anonymized]". The row is retained for FK integrity + aggregate
        stats (GDPR Article 17(3)(e) carve-out).
      - list_prospects() filters out soft-deleted rows (deleted_at IS NULL)
        unless include_deleted=True is passed.
      - check_consent() is a pre-flight check for any outbound action
        (email send, LinkedIn outreach) — returns False if the prospect
        has withdrawn consent.
    """

    def __init__(self) -> None:
        self._pii = PiiService()

    async def list_prospects(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        status: str | None = None,
        icp_profile_id: str | None = None,
        seniority: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> tuple[list[Prospect], int]:
        stmt = select(Prospect)
        if not include_deleted:
            # GDPR soft-delete: hide anonymised / forgotten rows by default.
            stmt = stmt.where(Prospect.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Prospect.firstName.ilike(like),
                    Prospect.lastName.ilike(like),
                    Prospect.email.ilike(like),
                    Prospect.company.ilike(like),
                )
            )
        if status:
            stmt = stmt.where(Prospect.status == status)
        if icp_profile_id:
            stmt = stmt.where(Prospect.icpProfileId == icp_profile_id)
        if seniority:
            stmt = stmt.where(Prospect.seniority == seniority)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar() or 0)

        result = await db.execute(
            stmt.order_by(Prospect.createdAt.desc()).offset(offset).limit(limit)
        )
        items = list(result.scalars().all())
        # Decrypt PII on read so callers see cleartext.
        for item in items:
            self._decrypt_prospect_pii(item)
        return items, total

    async def get(
        self, db: AsyncSession, prospect_id: str, *, include_deleted: bool = False
    ) -> Prospect | None:
        stmt = select(Prospect).where(Prospect.id == prospect_id)
        if not include_deleted:
            stmt = stmt.where(Prospect.deleted_at.is_(None))
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if item is not None:
            self._decrypt_prospect_pii(item)
        return item

    async def create(
        self, db: AsyncSession, body: ProspectCreate
    ) -> Prospect:
        import secrets as _secrets
        data = body.model_dump()
        # Generate a unique one-click unsubscribe token if not provided.
        # The token is embedded in email footers as ?token=<token>&tenant_slug=<slug>.
        if not data.get("unsubscribeToken"):
            data["unsubscribeToken"] = _secrets.token_urlsafe(32)
        # Encrypt PII fields before persisting.
        self._pii.encrypt_prospect(data)
        item = Prospect(**data)
        db.add(item)
        await db.commit()
        # With eager_defaults=True on Base, asyncpg uses RETURNING on INSERT
        # so server-generated columns (createdAt, updatedAt) are populated
        # immediately — no db.refresh() needed and no MissingGreenlet risk.
        # expire_on_commit=False (AsyncSessionLocal) keeps all other attrs alive.
        self._decrypt_prospect_pii(item)
        # FIX-BE-1 / CRITICAL 3: score the prospect if an IcpProfile is
        # linked. Best-effort — never block prospect creation on scoring.
        await self._apply_icp_scoring(db, item)
        return item

    async def update(
        self, db: AsyncSession, prospect_id: str, body: ProspectUpdate
    ) -> Prospect | None:
        item = await self.get(db, prospect_id)
        if item is None:
            return None
        updates = body.model_dump(exclude_unset=True)
        # Re-encrypt PII fields if they appear in the update payload.
        for field in _PROSPECT_PII_FIELDS:
            if field in updates and updates[field]:
                updates[field] = self._pii.encrypt_field(updates[field])
        for key, value in updates.items():
            setattr(item, key, value)
        await db.commit()
        await db.refresh(item)
        # Decrypt in-memory for the response.
        self._decrypt_prospect_pii(item)
        # FIX-BE-1 / CRITICAL 3: re-score if the ICP linkage or scoring-
        # relevant fields changed (icpProfileId, intentSource, intentStrength,
        # seniority, enrichmentTier, title, company, domain).
        _scoring_relevant = {
            "icpProfileId", "intentSource", "intentStrength", "seniority",
            "enrichmentTier", "title", "company", "domain",
        }
        if _scoring_relevant & set(updates.keys()):
            await self._apply_icp_scoring(db, item)
        return item

    async def delete(self, db: AsyncSession, prospect_id: str) -> bool:
        """SOFT-DELETE — anonymise PII + set deleted_at. Row is retained.

        GDPR Article 17 (right to erasure) carve-out: the row is kept for
        FK integrity (campaigns, sequences, deals reference it) and for
        aggregate stats rendered anonymous. PII is replaced with
        "[anonymized]" and the anonymised flag is set so future reads
        know the row is no longer PII.
        """
        item = await self.get(db, prospect_id, include_deleted=True)
        if item is None:
            return False
        item.firstName = "[anonymized]"
        item.lastName = "[anonymized]"
        item.email = "[anonymized]"
        item.linkedinUrl = None
        item.notes = None
        item.deleted_at = datetime.now(timezone.utc)
        item.anonymized = True
        item.consent_status = "withdrawn"
        await db.commit()
        return True

    async def check_consent(
        self, db: AsyncSession, prospect_id: str
    ) -> tuple[bool, str]:
        """Pre-flight consent check before any outbound action.

        Returns ``(allowed, reason)``. ``allowed`` is False when the
        prospect has withdrawn consent OR is suppressed — in which case
        the caller MUST block the outbound action (email send, LinkedIn
        outreach) and log the suppression reason.
        """
        item = await self.get(db, prospect_id)
        if item is None:
            return False, "Prospect not found."
        if item.consent_status == "withdrawn":
            return False, "Consent withdrawn (GDPR)."
        if item.suppressed:
            return False, f"Suppressed: {item.suppressionReason or 'unspecified'}"
        return True, "OK"

    async def import_csv(
        self, db: AsyncSession, csv_content: str,
        *,
        icp_profile_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Delegate CSV import to Fix-3's csv_import_service.

        Fix-3 exposes ``CsvImportService.import_csv(content, db)`` returning
        an ``ImportResult`` (total/created/skipped/errors). We translate that
        to the legacy ``CsvImportResult`` shape (imported/skipped/errors/totalRows)
        so the router's response_model is unchanged.

        FIX-BE-1 / CRITICAL 3: ``icp_profile_id`` is forwarded to
        ``CsvImportService.import_csv`` so the scorer can populate
        ``icpFitScore`` / ``urgencyTier`` on each imported row.
        """
        try:
            from app.services.csv_import_service import CsvImportService  # type: ignore
        except ImportError:
            logger.warning("prospect.import_csv.service_not_ready")
            return {
                "imported": 0,
                "skipped": 0,
                "errors": ["csv_import_service not yet available"],
                "totalRows": 0,
            }
        try:
            service = CsvImportService()
            result = await service.import_csv(  # type: ignore[misc]
                csv_content, db, icp_profile_id=icp_profile_id
            )
            if hasattr(result, "model_dump"):
                data = result.model_dump()
            elif isinstance(result, dict):
                data = result
            else:
                data = {}
            # Translate ImportResult → CsvImportResult fields.
            return {
                "imported": int(data.get("created", data.get("imported", 0))),
                "skipped": int(data.get("skipped", 0)),
                "errors": list(data.get("errors", []) or []),
                "totalRows": int(data.get("total", data.get("totalRows", 0))),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("prospect.import_csv.failed", error=str(exc))
            return {
                "imported": 0,
                "skipped": 0,
                "errors": [str(exc)],
                "totalRows": 0,
            }

    async def enrich(
        self, db: AsyncSession, body: EnrichRequest
    ) -> EnrichResponse:
        """Stub enrichment — Phase 2 only marks enrichmentTier."""
        prospect: Prospect | None = None
        if body.prospectId:
            prospect = await self.get(db, body.prospectId)
        if prospect is None and body.email:
            result = await db.execute(
                select(Prospect).where(Prospect.email == body.email).limit(1)
            )
            prospect = result.scalar_one_or_none()
            if prospect is not None:
                self._decrypt_prospect_pii(prospect)

        if prospect is None:
            return EnrichResponse(
                prospectId=body.prospectId,
                enriched=False,
                detail="Prospect not found.",
            )

        # Minimal enrichment — populate domain from email if missing.
        fields: dict[str, Any] = {}
        if not prospect.domain and prospect.email and "@" in prospect.email:
            domain = prospect.email.split("@", 1)[1]
            prospect.domain = domain
            fields["domain"] = domain
        prospect.enrichmentTier = "ENRICHED"  # type: ignore[assignment]
        await db.commit()
        await db.refresh(prospect)
        # FIX-BE-1 / HIGH 8 (re-verification): record one usage_event
        # (prospect_enrich) for per-tenant cost roll-ups. Best-effort —
        # never blocks the enrich call. We use the local stub provider
        # 'internal' since this enrich path is a Phase 2 stub (real
        # enrichment via Apollo/Clay/etc. will pass provider=<slug>).
        try:
            tenant = await resolve_tenant_slug(db)
            if tenant:
                from app.features.usage.service import UsageService

                await UsageService().record_prospect_enrich(
                    tenant=tenant,
                    user_id=getattr(body, "user_id", None) or "system",
                    provider="internal",
                    count=1,
                    metadata={"prospect_id": getattr(prospect, "id", None)},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "prospect.enrich.usage_record_failed",
                error=str(exc),
            )
        # FIX-BE-1 / CRITICAL 3 (re-verification): re-score the prospect
        # against its linked ICP after enrichment, since enrichment may have
        # populated/updated firmographic inputs (domain -> company lookup)
        # used by ProspectScorer. Best-effort — failures are swallowed
        # inside _apply_icp_scoring so enrich never breaks on a scoring bug.
        await self._apply_icp_scoring(db, prospect)
        return EnrichResponse(
            prospectId=prospect.id,
            enriched=True,
            fields=fields,
            detail="Enrichment completed (Phase 2 stub).",
        )

    async def email_validate(
        self, body: EmailValidateRequest
    ) -> EmailValidateResponse:
        """Validate an email via MX record lookup (dnspython or stdlib)."""
        email = body.email.strip()
        if "@" not in email:
            return EmailValidateResponse(
                email=email,
                valid=False,
                mxFound=False,
                detail="Malformed email — missing '@'.",
            )
        domain = email.rsplit("@", 1)[1]
        mx_found = self._lookup_mx(domain)
        valid = mx_found and self._can_resolve(domain)
        return EmailValidateResponse(
            email=email,
            valid=bool(valid),
            mxFound=bool(mx_found),
            isCatchAll=False,
            detail="MX lookup complete." if mx_found else "No MX records found.",
        )

    # ── PII helpers ──────────────────────────────────────────────────────────

    def _decrypt_prospect_pii(self, item: Prospect) -> None:
        """Decrypt the PII fields of an in-memory Prospect object.

        Skips anonymised rows (PII already replaced with ``[anonymized]``).
        Mutates the object in place — callers see cleartext.
        """
        if getattr(item, "anonymized", False):
            return  # PII already purged — nothing to decrypt.
        for field in _PROSPECT_PII_FIELDS:
            value = getattr(item, field, None)
            if value:
                setattr(item, field, self._pii.decrypt_field(value))

    # ── ICP scoring (FIX-BE-1 / CRITICAL 3) ─────────────────────────────────

    async def _apply_icp_scoring(
        self, db: AsyncSession, prospect: Prospect
    ) -> None:
        """Score the prospect against its linked IcpProfile and persist
        ``icpFitScore`` / ``urgencyTier`` / ``icpPersona`` /
        ``icpScoreBreakdown`` on the row.

        Best-effort: any failure is logged + swallowed so prospect creation
        or update is never blocked by a scoring bug. Skips silently when no
        ``icpProfileId`` is set or the IcpProfile row is missing.

        Per migration §10 Phase 2: 100-pt weighted score + P0/P1/P2 urgency
        tier computed by ``app.services.prospect_scoring.ProspectScorer``.
        """
        icp_id = getattr(prospect, "icpProfileId", None)
        if not icp_id:
            return  # no ICP linked — nothing to score against

        try:
            result = await db.execute(
                select(IcpProfile).where(IcpProfile.id == icp_id).limit(1)
            )
            icp_profile = result.scalar_one_or_none()
        except Exception as exc:  # noqa: BLE001 — scoring must never break create
            logger.warning(
                "prospect.scoring.icp_lookup_failed",
                prospect_id=getattr(prospect, "id", None),
                icp_profile_id=icp_id,
                error=str(exc),
            )
            return

        if icp_profile is None:
            return  # ICP row deleted — skip silently

        try:
            from app.features.prospects.prospect_scoring import ProspectScorer

            scorer = ProspectScorer()
            # The scorer reads prospect.title / company / domain etc.
            # directly. PII fields are encrypted at rest — we only need
            # non-PII fields for scoring, so we can pass the encrypted
            # prospect object as-is (title/company/domain are not PII).
            score = scorer.score_prospect(prospect, icp_profile)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "prospect.scoring.failed",
                prospect_id=getattr(prospect, "id", None),
                icp_profile_id=icp_id,
                error=str(exc),
            )
            return

        breakdown = {
            "total": score.total,
            "icp_fit": score.icp_fit,
            "intent": score.intent,
            "seniority": score.seniority,
            "firmographic": score.firmographic,
            "urgency_tier": score.urgency_tier,
        }
        try:
            prospect.icpFitScore = int(score.total)
            prospect.urgencyTier = str(score.urgency_tier)
            prospect.icpPersona = (icp_profile.persona or "")[:200] or None
            prospect.icpScoreBreakdown = json.dumps(breakdown)
            await db.commit()
            logger.debug(
                "prospect.scoring.applied",
                prospect_id=getattr(prospect, "id", None),
                icp_profile_id=icp_id,
                total=score.total,
                urgency_tier=score.urgency_tier,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "prospect.scoring.persist_failed",
                prospect_id=getattr(prospect, "id", None),
                icp_profile_id=icp_id,
                error=str(exc),
            )

    # ── DNS helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _lookup_mx(domain: str) -> bool:
        """True if the domain has at least one MX record (or an A/AAAA fallback)."""
        if _HAS_DNSPYTHON:
            try:
                answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)  # type: ignore[union-attr]
                return any(answers)
            except Exception:  # noqa: BLE001
                pass
            try:
                answers = dns.resolver.resolve(domain, "A", lifetime=5.0)  # type: ignore[union-attr]
                return any(answers)
            except Exception:  # noqa: BLE001
                return False
        # Stdlib fallback — no native MX support; use A-record resolution.
        return ProspectService._can_resolve(domain)

    @staticmethod
    def _can_resolve(domain: str) -> bool:
        try:
            socket.gethostbyname(domain)
            return True
        except OSError:
            return False


__all__ = ["ProspectService"]