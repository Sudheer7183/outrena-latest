"""
csv_import_service.py — CSV prospect import (per migration doc §6.5).

Parses a CSV string with Python stdlib ``csv.DictReader`` (RFC-4180 compliant,
UTF-8, handles quoted fields with embedded commas/newlines), validates each
row, and bulk-inserts valid rows as ``Prospect`` records.

Required CSV headers:
  - firstName (required)
  - lastName  (required)
  - email     (required, must contain '@')

Optional CSV headers:
  - title, company, domain, linkedinUrl, seniority, timezone, icpProfileId

The 10MB file-size limit is enforced by the router (per §6.5), not here.
This service is pure parser + inserter — it accepts the already-decoded
UTF-8 string and trusts the caller to have applied size + content-type
limits.

Returns an ``ImportResult`` with total/created/skipped counts + a list of
human-readable error strings (one per skipped row).

FIX-BE-1 / CRITICAL 3: after the bulk insert, ``import_csv`` invokes the
``ProspectScorer`` on each newly-created row whose ``icpProfileId`` is set
(either via an explicit CSV column or via the ``icp_profile_id`` argument
passed by the caller) and persists ``icpFitScore`` / ``urgencyTier`` /
``icpPersona`` / ``icpScoreBreakdown`` on the row. Scoring failures are
logged + skipped per-row — they never abort the import.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

import structlog
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SeniorityTier
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.prospects import ImportResult

logger = structlog.get_logger(__name__)


_REQUIRED_HEADERS: tuple[str, ...] = ("firstName", "lastName", "email")
_OPTIONAL_HEADERS: tuple[str, ...] = (
    "title",
    "company",
    "domain",
    "linkedinUrl",
    "seniority",
    "timezone",
    "icpProfileId",
)
_ALL_HEADERS: frozenset[str] = frozenset(_REQUIRED_HEADERS + _OPTIONAL_HEADERS)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Map of allowed seniority values → enum members (accepts case-insensitive input)
_SENIORITY_LOOKUP: dict[str, SeniorityTier] = {
    "c_suite": SeniorityTier.C_Suite,
    "csuite": SeniorityTier.C_Suite,
    "c-suite": SeniorityTier.C_Suite,
    "director": SeniorityTier.Director,
    "ic": SeniorityTier.IC,
    "individual_contributor": SeniorityTier.IC,
}

# Soft cap on per-import row count (defensive; routers should pre-filter).
_MAX_ROWS_PER_IMPORT: int = 50_000


class CsvImportService:
    """CSV prospect importer (RFC-4180, stdlib csv, bulk-insert)."""

    async def import_csv(
        self,
        content: str,
        db: AsyncSession,
        *,
        icp_profile_id: str | None = None,
    ) -> ImportResult:
        """
        Parse + validate + bulk-insert prospects from a CSV string.

        Args:
            content:        UTF-8 decoded CSV text.
            db:             AsyncSession locked to the tenant's schema.
            icp_profile_id: Optional ICP to link all imported rows to. Per-row
                            ``icpProfileId`` CSV header takes precedence when
                            present. Used by FIX-BE-1 / CRITICAL 3 to drive
                            ICP scoring on import.

        Returns:
            ImportResult with counts + errors. Never raises on row-level
            validation failures — they're collected into ``errors``.
        """
        if not content or not content.strip():
            return ImportResult(total=0, created=0, skipped=0, errors=["CSV is empty."])

        reader = csv.DictReader(io.StringIO(content))
        fieldnames = reader.fieldnames or []
        missing_required = [h for h in _REQUIRED_HEADERS if h not in fieldnames]
        if missing_required:
            return ImportResult(
                total=0,
                created=0,
                skipped=0,
                errors=[
                    f"Missing required CSV header(s): {', '.join(missing_required)}. "
                    f"Required: {', '.join(_REQUIRED_HEADERS)}."
                ],
            )

        rows_to_insert: list[dict[str, Any]] = []
        errors: list[str] = []
        total_seen = 0
        skipped = 0

        for line_no, raw_row in enumerate(reader, start=2):
            total_seen += 1
            if len(rows_to_insert) >= _MAX_ROWS_PER_IMPORT:
                errors.append(
                    f"Row {line_no}: import cap of {_MAX_ROWS_PER_IMPORT} reached; "
                    f"remaining rows skipped."
                )
                skipped += 1
                continue

            # Strip whitespace from all string cells
            row = {
                k: (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
                if k is not None
            }

            # ── Required-field validation ──────────────────────────────────
            first_name = (row.get("firstName") or "").strip()
            last_name = (row.get("lastName") or "").strip()
            email = (row.get("email") or "").strip()

            if not first_name:
                errors.append(f"Row {line_no}: missing firstName.")
                skipped += 1
                continue
            if not last_name:
                errors.append(f"Row {line_no}: missing lastName.")
                skipped += 1
                continue
            if not email:
                errors.append(f"Row {line_no}: missing email.")
                skipped += 1
                continue
            if not _EMAIL_RE.match(email):
                errors.append(f"Row {line_no}: invalid email '{email}'.")
                skipped += 1
                continue

            # ── Optional-field validation ──────────────────────────────────
            seniority: SeniorityTier = SeniorityTier.IC
            raw_seniority = (row.get("seniority") or "").strip()
            if raw_seniority:
                key = raw_seniority.lower().replace(" ", "_")
                if key not in _SENIORITY_LOOKUP:
                    errors.append(
                        f"Row {line_no}: invalid seniority '{raw_seniority}' "
                        f"(expected one of: C_Suite, Director, IC). Defaulted to IC."
                    )
                    # Don't skip — just default
                else:
                    seniority = _SENIORITY_LOOKUP[key]

            title = (row.get("title") or "").strip() or None
            company = (row.get("company") or "").strip() or None
            domain = (row.get("domain") or "").strip() or None
            if domain and not _is_valid_domain(domain):
                errors.append(
                    f"Row {line_no}: invalid domain '{domain}' (kept as-is)."
                )
            linkedin_url = (row.get("linkedinUrl") or "").strip() or None
            timezone = (row.get("timezone") or "").strip() or None
            # Optional per-row ICP override — falls back to the caller-
            # supplied icp_profile_id argument. Used by FIX-BE-1 / CRITICAL 3
            # to drive scoring on import.
            row_icp_id = (row.get("icpProfileId") or "").strip() or None
            effective_icp_id = row_icp_id or icp_profile_id or None

            row_dict: dict[str, Any] = {
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "title": title,
                "company": company,
                "domain": domain,
                "linkedinUrl": linkedin_url,
                "seniority": seniority,
                "timezone": timezone,
            }
            if effective_icp_id:
                row_dict["icpProfileId"] = effective_icp_id
            rows_to_insert.append(row_dict)

        # ── FR-016: dedup against EXISTING prospects ────────────────────────
        # Two keys, per the URD: (1) email (case-insensitive), and
        # (2) domain + firstName + lastName (catches the same person imported
        # with a different address at the same company). In-file duplicates
        # are collapsed by the same keys so a single upload can't create two
        # copies either. Duplicates are counted as skipped with a reason.
        if rows_to_insert:
            from sqlalchemy import func as _func, or_ as _or

            emails = [r["email"].lower() for r in rows_to_insert if r.get("email")]
            dom_names = [
                (r["domain"].lower(), r["firstName"].lower(), r["lastName"].lower())
                for r in rows_to_insert
                if r.get("domain")
            ]
            existing_emails: set[str] = set()
            existing_dom_names: set[tuple[str, str, str]] = set()
            try:
                if emails:
                    res = await db.execute(
                        select(Prospect.email).where(
                            _func.lower(Prospect.email).in_(emails)
                        )
                    )
                    existing_emails = {
                        (e or "").lower() for (e,) in res.all() if e
                    }
                if dom_names:
                    res = await db.execute(
                        select(
                            Prospect.domain, Prospect.firstName, Prospect.lastName
                        ).where(
                            _func.lower(Prospect.domain).in_(
                                {d for d, _, _ in dom_names}
                            )
                        )
                    )
                    existing_dom_names = {
                        ((d or "").lower(), (f or "").lower(), (l or "").lower())
                        for d, f, l in res.all()
                    }
            except Exception as exc:  # noqa: BLE001 — encrypted-email schemas etc.
                logger.warning("csv_import.dedup_lookup_failed", error=str(exc))

            deduped: list[dict[str, Any]] = []
            seen_emails: set[str] = set()
            seen_dom_names: set[tuple[str, str, str]] = set()
            for r in rows_to_insert:
                email_key = (r.get("email") or "").lower()
                dn_key = (
                    (r.get("domain") or "").lower(),
                    (r.get("firstName") or "").lower(),
                    (r.get("lastName") or "").lower(),
                )
                if email_key and (
                    email_key in existing_emails or email_key in seen_emails
                ):
                    errors.append(
                        f"Duplicate skipped: {r['email']} already exists."
                    )
                    skipped += 1
                    continue
                if r.get("domain") and (
                    dn_key in existing_dom_names or dn_key in seen_dom_names
                ):
                    errors.append(
                        f"Duplicate skipped: {r['firstName']} {r['lastName']} "
                        f"@ {r['domain']} already exists."
                    )
                    skipped += 1
                    continue
                seen_emails.add(email_key)
                if r.get("domain"):
                    seen_dom_names.add(dn_key)
                deduped.append(r)
            rows_to_insert = deduped

        created = 0
        created_ids: list[str] = []
        if rows_to_insert:
            try:
                result = await db.execute(
                    insert(Prospect).values(rows_to_insert).returning(Prospect.id)
                )
                rows = result.fetchall()
                created = len(rows)
                created_ids = [str(r[0]) for r in rows]
                await db.flush()
            except Exception as exc:
                # Bulk-insert failure: surface to caller but preserve the
                # parsed row count so the user knows what was attempted.
                logger.error("csv_import.bulk_insert_failed", error=str(exc))
                errors.append(f"Bulk insert failed: {exc}")
                return ImportResult(
                    total=total_seen,
                    created=0,
                    skipped=skipped + len(rows_to_insert),
                    errors=errors,
                )

        # ── FIX-BE-1 / CRITICAL 3: ICP scoring on import ──────────────────
        # Score each newly-created prospect against its linked IcpProfile
        # (per-row icpProfileId or the caller-supplied icp_profile_id).
        # Best-effort — per-row failures are logged + skipped; they never
        # abort the import or affect the created count.
        if created_ids:
            await _score_imported_prospects(db, created_ids)

        logger.info(
            "csv_import.complete",
            total=total_seen,
            created=created,
            skipped=skipped,
            error_count=len(errors),
        )
        return ImportResult(
            total=total_seen,
            created=created,
            skipped=skipped,
            errors=errors,
        )


def _is_valid_domain(domain: str) -> bool:
    """Lenient domain validator — must contain a dot and no spaces."""
    if not domain:
        return False
    if " " in domain:
        return False
    if "." not in domain:
        return False
    return True


async def _score_imported_prospects(
    db: AsyncSession, prospect_ids: list[str]
) -> None:
    """FIX-BE-1 / CRITICAL 3 — score each newly-imported Prospect.

    Loads each Prospect + its IcpProfile (when set), invokes
    ``ProspectScorer.score_prospect``, and UPDATEs the row with
    ``icpFitScore`` / ``urgencyTier`` / ``icpPersona`` /
    ``icpScoreBreakdown``. Best-effort — per-row failures are logged +
    skipped; they never abort the import or affect the created count.
    """
    if not prospect_ids:
        return
    try:
        from app.features.prospects.prospect_scoring import ProspectScorer
    except ImportError as exc:  # pragma: no cover — defensive
        logger.warning("csv_import.scorer_unavailable", error=str(exc))
        return

    scorer = ProspectScorer()
    try:
        result = await db.execute(
            select(Prospect).where(Prospect.id.in_(prospect_ids))
        )
        prospects = list(result.scalars().all())
    except Exception as exc:  # noqa: BLE001
        logger.warning("csv_import.scoring_load_failed", error=str(exc))
        return

    # Pre-load all referenced IcpProfiles in one shot to avoid N+1 queries.
    icp_ids = {p.icpProfileId for p in prospects if p.icpProfileId}
    icp_map: dict[str, IcpProfile] = {}
    if icp_ids:
        try:
            icp_result = await db.execute(
                select(IcpProfile).where(IcpProfile.id.in_(icp_ids))
            )
            icp_map = {row.id: row for row in icp_result.scalars().all()}
        except Exception as exc:  # noqa: BLE001
            logger.warning("csv_import.icp_load_failed", error=str(exc))

    scored = 0
    for prospect in prospects:
        icp_id = prospect.icpProfileId
        if not icp_id:
            continue
        icp_profile = icp_map.get(icp_id)
        if icp_profile is None:
            continue
        try:
            score = scorer.score_prospect(prospect, icp_profile)
        except Exception as exc:  # noqa: BLE001 — per-row isolation
            logger.warning(
                "csv_import.scoring_row_failed",
                prospect_id=prospect.id,
                icp_profile_id=icp_id,
                error=str(exc),
            )
            continue
        try:
            prospect.icpFitScore = int(score.total)
            prospect.urgencyTier = str(score.urgency_tier)
            prospect.icpPersona = (icp_profile.persona or "")[:200] or None
            prospect.icpScoreBreakdown = json.dumps(
                {
                    "total": score.total,
                    "icp_fit": score.icp_fit,
                    "intent": score.intent,
                    "seniority": score.seniority,
                    "firmographic": score.firmographic,
                    "urgency_tier": score.urgency_tier,
                }
            )
            scored += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "csv_import.scoring_persist_failed",
                prospect_id=prospect.id,
                error=str(exc),
            )
    try:
        if scored:
            await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("csv_import.scoring_flush_failed", error=str(exc))
    logger.info(
        "csv_import.scoring_complete",
        total=len(prospects),
        scored=scored,
    )


def get_csv_import_service() -> CsvImportService:
    """Factory — return a fresh CsvImportService (stateless)."""
    return CsvImportService()


__all__: list[str] = [
    "CsvImportService",
    "get_csv_import_service",
]
