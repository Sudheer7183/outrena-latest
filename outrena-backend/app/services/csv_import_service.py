

# # """
# # csv_import_service.py — CSV prospect import (per migration doc §6.5).

# # Parses a CSV string with Python stdlib ``csv.DictReader`` (RFC-4180 compliant,
# # UTF-8, handles quoted fields with embedded commas/newlines), validates each
# # row, and bulk-inserts valid rows as ``Prospect`` records.

# # Required CSV headers:
# #   - firstName (required)
# #   - lastName  (required)
# #   - email     (required, must contain '@')

# # Optional CSV headers:
# #   - title, company, domain, linkedinUrl, seniority, timezone, icpProfileId

# # The 10MB file-size limit is enforced by the router (per §6.5), not here.
# # This service is pure parser + inserter — it accepts the already-decoded
# # UTF-8 string and trusts the caller to have applied size + content-type
# # limits.

# # Returns an ``ImportResult`` with total/created/skipped counts + a list of
# # human-readable error strings (one per skipped row).

# # FIX-BE-1 / CRITICAL 3: after the bulk insert, ``import_csv`` invokes the
# # ``ProspectScorer`` on each newly-created row whose ``icpProfileId`` is set
# # (either via an explicit CSV column or via the ``icp_profile_id`` argument
# # passed by the caller) and persists ``icpFitScore`` / ``urgencyTier`` /
# # ``icpPersona`` / ``icpScoreBreakdown`` on the row. Scoring failures are
# # logged + skipped per-row — they never abort the import.
# # """
# # from __future__ import annotations

# # import csv
# # import io
# # import json
# # import re
# # from typing import Any

# # import structlog
# # from sqlalchemy import insert, select
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.models.enums import SeniorityTier
# # from app.models.prospect_models import IcpProfile, Prospect
# # from app.schemas.prospects import ImportResult

# # logger = structlog.get_logger(__name__)


# # # Canonical internal header names (camelCase) used throughout this service.
# # _REQUIRED_HEADERS: tuple[str, ...] = ("firstName", "lastName", "email")
# # _OPTIONAL_HEADERS: tuple[str, ...] = (
# #     "title",
# #     "company",
# #     "domain",
# #     "linkedinUrl",
# #     "seniority",
# #     "timezone",
# #     "icpProfileId",
# # )
# # _ALL_HEADERS: frozenset[str] = frozenset(_REQUIRED_HEADERS + _OPTIONAL_HEADERS)

# # # Maps every accepted alias → the canonical internal name.
# # # Allows users to upload CSVs with either snake_case (Excel-default) or
# # # camelCase column headers — both are normalised before validation.
# # _HEADER_ALIASES: dict[str, str] = {
# #     # required
# #     "first_name": "firstName",
# #     "firstname": "firstName",
# #     "last_name": "lastName",
# #     "lastname": "lastName",
# #     # optional
# #     "linkedin_url": "linkedinUrl",
# #     "linkedin": "linkedinUrl",
# #     "icp_profile_id": "icpProfileId",
# #     "icp_id": "icpProfileId",
# # }


# # def _normalise_row(raw_row: dict) -> dict:
# #     """Return a new dict with all keys mapped to their canonical names.

# #     Keys that are already canonical (or have no alias) pass through unchanged.
# #     This is applied to *both* the fieldnames check and every data row so the
# #     rest of the service never needs to know about the alias table.
# #     """
# #     return {
# #         _HEADER_ALIASES.get(k, k): v
# #         for k, v in raw_row.items()
# #         if k is not None
# #     }

# # _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# # # Map of allowed seniority values → enum members (accepts case-insensitive input)
# # _SENIORITY_LOOKUP: dict[str, SeniorityTier] = {
# #     "c_suite": SeniorityTier.C_Suite,
# #     "csuite": SeniorityTier.C_Suite,
# #     "c-suite": SeniorityTier.C_Suite,
# #     "director": SeniorityTier.Director,
# #     "ic": SeniorityTier.IC,
# #     "individual_contributor": SeniorityTier.IC,
# # }

# # # Soft cap on per-import row count (defensive; routers should pre-filter).
# # _MAX_ROWS_PER_IMPORT: int = 50_000


# # class CsvImportService:
# #     """CSV prospect importer (RFC-4180, stdlib csv, bulk-insert)."""

# #     async def import_csv(
# #         self,
# #         content: str,
# #         db: AsyncSession,
# #         *,
# #         icp_profile_id: str | None = None,
# #     ) -> ImportResult:
# #         """
# #         Parse + validate + bulk-insert prospects from a CSV string.

# #         Args:
# #             content:        UTF-8 decoded CSV text.
# #             db:             AsyncSession locked to the tenant's schema.
# #             icp_profile_id: Optional ICP to link all imported rows to. Per-row
# #                             ``icpProfileId`` CSV header takes precedence when
# #                             present. Used by FIX-BE-1 / CRITICAL 3 to drive
# #                             ICP scoring on import.

# #         Returns:
# #             ImportResult with counts + errors. Never raises on row-level
# #             validation failures — they're collected into ``errors``.
# #         """
# #         if not content or not content.strip():
# #             return ImportResult(total=0, created=0, skipped=0, errors=["CSV is empty."])

# #         reader = csv.DictReader(io.StringIO(content))
# #         # Normalise the header names so both snake_case and camelCase are accepted.
# #         raw_fieldnames: list[str] = list(reader.fieldnames or [])
# #         normalised_fieldnames: list[str] = [
# #             _HEADER_ALIASES.get(f, f) for f in raw_fieldnames
# #         ]
# #         missing_required = [h for h in _REQUIRED_HEADERS if h not in normalised_fieldnames]
# #         if missing_required:
# #             # Show both camelCase and snake_case equivalents in the error so
# #             # the message is useful regardless of which convention the user prefers.
# #             _alias_pairs = {v: k for k, v in _HEADER_ALIASES.items() if "_" in k}
# #             def _both(h: str) -> str:
# #                 snake = _alias_pairs.get(h, "")
# #                 return f"{h} (or {snake})" if snake else h
# #             return ImportResult(
# #                 total=0,
# #                 created=0,
# #                 skipped=0,
# #                 errors=[
# #                     f"Missing required CSV column(s): "
# #                     f"{', '.join(_both(h) for h in missing_required)}. "
# #                     f"Accepted formats: camelCase ({', '.join(_REQUIRED_HEADERS)}) "
# #                     f"or snake_case (first_name, last_name, email)."
# #                 ],
# #             )

# #         rows_to_insert: list[dict[str, Any]] = []
# #         errors: list[str] = []
# #         total_seen = 0
# #         skipped = 0

# #         for line_no, raw_row in enumerate(reader, start=2):
# #             total_seen += 1
# #             if len(rows_to_insert) >= _MAX_ROWS_PER_IMPORT:
# #                 errors.append(
# #                     f"Row {line_no}: import cap of {_MAX_ROWS_PER_IMPORT} reached; "
# #                     f"remaining rows skipped."
# #                 )
# #                 skipped += 1
# #                 continue

# #             # Normalise column names (snake_case → camelCase) then strip whitespace.
# #             row = {
# #                 k: (v.strip() if isinstance(v, str) else v)
# #                 for k, v in _normalise_row(raw_row).items()
# #                 if k is not None
# #             }

# #             # ── Required-field validation ──────────────────────────────────
# #             first_name = (row.get("firstName") or "").strip()
# #             last_name = (row.get("lastName") or "").strip()
# #             email = (row.get("email") or "").strip()

# #             if not first_name:
# #                 errors.append(f"Row {line_no}: missing firstName.")
# #                 skipped += 1
# #                 continue
# #             if not last_name:
# #                 errors.append(f"Row {line_no}: missing lastName.")
# #                 skipped += 1
# #                 continue
# #             if not email:
# #                 errors.append(f"Row {line_no}: missing email.")
# #                 skipped += 1
# #                 continue
# #             if not _EMAIL_RE.match(email):
# #                 errors.append(f"Row {line_no}: invalid email '{email}'.")
# #                 skipped += 1
# #                 continue

# #             # ── Optional-field validation ──────────────────────────────────
# #             seniority: SeniorityTier = SeniorityTier.IC
# #             raw_seniority = (row.get("seniority") or "").strip()
# #             if raw_seniority:
# #                 key = raw_seniority.lower().replace(" ", "_")
# #                 if key not in _SENIORITY_LOOKUP:
# #                     errors.append(
# #                         f"Row {line_no}: invalid seniority '{raw_seniority}' "
# #                         f"(expected one of: C_Suite, Director, IC). Defaulted to IC."
# #                     )
# #                     # Don't skip — just default
# #                 else:
# #                     seniority = _SENIORITY_LOOKUP[key]

# #             title = (row.get("title") or "").strip() or None
# #             company = (row.get("company") or "").strip() or None
# #             domain = (row.get("domain") or "").strip() or None
# #             if domain and not _is_valid_domain(domain):
# #                 errors.append(
# #                     f"Row {line_no}: invalid domain '{domain}' (kept as-is)."
# #                 )
# #             linkedin_url = (row.get("linkedinUrl") or "").strip() or None
# #             timezone = (row.get("timezone") or "").strip() or None
# #             # Optional per-row ICP override — falls back to the caller-
# #             # supplied icp_profile_id argument. Used by FIX-BE-1 / CRITICAL 3
# #             # to drive scoring on import.
# #             row_icp_id = (row.get("icpProfileId") or "").strip() or None
# #             effective_icp_id = row_icp_id or icp_profile_id or None

# #             row_dict: dict[str, Any] = {
# #                 "firstName": first_name,
# #                 "lastName": last_name,
# #                 "email": email,
# #                 "title": title,
# #                 "company": company,
# #                 "domain": domain,
# #                 "linkedinUrl": linkedin_url,
# #                 "seniority": seniority,
# #                 "timezone": timezone,
# #             }
# #             if effective_icp_id:
# #                 row_dict["icpProfileId"] = effective_icp_id
# #             rows_to_insert.append(row_dict)

# #         # ── FR-016: dedup against EXISTING prospects ────────────────────────
# #         # Two keys, per the URD: (1) email (case-insensitive), and
# #         # (2) domain + firstName + lastName (catches the same person imported
# #         # with a different address at the same company). In-file duplicates
# #         # are collapsed by the same keys so a single upload can't create two
# #         # copies either. Duplicates are counted as skipped with a reason.
# #         if rows_to_insert:
# #             from sqlalchemy import func as _func, or_ as _or

# #             emails = [r["email"].lower() for r in rows_to_insert if r.get("email")]
# #             dom_names = [
# #                 (r["domain"].lower(), r["firstName"].lower(), r["lastName"].lower())
# #                 for r in rows_to_insert
# #                 if r.get("domain")
# #             ]
# #             existing_emails: set[str] = set()
# #             existing_dom_names: set[tuple[str, str, str]] = set()
# #             try:
# #                 if emails:
# #                     res = await db.execute(
# #                         select(Prospect.email).where(
# #                             _func.lower(Prospect.email).in_(emails)
# #                         )
# #                     )
# #                     existing_emails = {
# #                         (e or "").lower() for (e,) in res.all() if e
# #                     }
# #                 if dom_names:
# #                     res = await db.execute(
# #                         select(
# #                             Prospect.domain, Prospect.firstName, Prospect.lastName
# #                         ).where(
# #                             _func.lower(Prospect.domain).in_(
# #                                 {d for d, _, _ in dom_names}
# #                             )
# #                         )
# #                     )
# #                     existing_dom_names = {
# #                         ((d or "").lower(), (f or "").lower(), (l or "").lower())
# #                         for d, f, l in res.all()
# #                     }
# #             except Exception as exc:  # noqa: BLE001 — encrypted-email schemas etc.
# #                 logger.warning("csv_import.dedup_lookup_failed", error=str(exc))

# #             deduped: list[dict[str, Any]] = []
# #             seen_emails: set[str] = set()
# #             seen_dom_names: set[tuple[str, str, str]] = set()
# #             for r in rows_to_insert:
# #                 email_key = (r.get("email") or "").lower()
# #                 dn_key = (
# #                     (r.get("domain") or "").lower(),
# #                     (r.get("firstName") or "").lower(),
# #                     (r.get("lastName") or "").lower(),
# #                 )
# #                 if email_key and (
# #                     email_key in existing_emails or email_key in seen_emails
# #                 ):
# #                     errors.append(
# #                         f"Duplicate skipped: {r['email']} already exists."
# #                     )
# #                     skipped += 1
# #                     continue
# #                 if r.get("domain") and (
# #                     dn_key in existing_dom_names or dn_key in seen_dom_names
# #                 ):
# #                     errors.append(
# #                         f"Duplicate skipped: {r['firstName']} {r['lastName']} "
# #                         f"@ {r['domain']} already exists."
# #                     )
# #                     skipped += 1
# #                     continue
# #                 seen_emails.add(email_key)
# #                 if r.get("domain"):
# #                     seen_dom_names.add(dn_key)
# #                 deduped.append(r)
# #             rows_to_insert = deduped

# #         created = 0
# #         created_ids: list[str] = []
# #         if rows_to_insert:
# #             try:
# #                 result = await db.execute(
# #                     insert(Prospect).values(rows_to_insert).returning(Prospect.id)
# #                 )
# #                 rows = result.fetchall()
# #                 created = len(rows)
# #                 created_ids = [str(r[0]) for r in rows]
# #                 await db.flush()
# #             except Exception as exc:
# #                 # Bulk-insert failure: surface to caller but preserve the
# #                 # parsed row count so the user knows what was attempted.
# #                 logger.error("csv_import.bulk_insert_failed", error=str(exc))
# #                 errors.append(f"Bulk insert failed: {exc}")
# #                 return ImportResult(
# #                     total=total_seen,
# #                     created=0,
# #                     skipped=skipped + len(rows_to_insert),
# #                     errors=errors,
# #                 )

# #         # ── FIX-BE-1 / CRITICAL 3: ICP scoring on import ──────────────────
# #         # Score each newly-created prospect against its linked IcpProfile
# #         # (per-row icpProfileId or the caller-supplied icp_profile_id).
# #         # Best-effort — per-row failures are logged + skipped; they never
# #         # abort the import or affect the created count.
# #         if created_ids:
# #             await _score_imported_prospects(db, created_ids)

# #         logger.info(
# #             "csv_import.complete",
# #             total=total_seen,
# #             created=created,
# #             skipped=skipped,
# #             error_count=len(errors),
# #         )
# #         return ImportResult(
# #             total=total_seen,
# #             created=created,
# #             skipped=skipped,
# #             errors=errors,
# #         )


# # def _is_valid_domain(domain: str) -> bool:
# #     """Lenient domain validator — must contain a dot and no spaces."""
# #     if not domain:
# #         return False
# #     if " " in domain:
# #         return False
# #     if "." not in domain:
# #         return False
# #     return True


# # async def _score_imported_prospects(
# #     db: AsyncSession, prospect_ids: list[str]
# # ) -> None:
# #     """FIX-BE-1 / CRITICAL 3 — score each newly-imported Prospect.

# #     Loads each Prospect + its IcpProfile (when set), invokes
# #     ``ProspectScorer.score_prospect``, and UPDATEs the row with
# #     ``icpFitScore`` / ``urgencyTier`` / ``icpPersona`` /
# #     ``icpScoreBreakdown``. Best-effort — per-row failures are logged +
# #     skipped; they never abort the import or affect the created count.
# #     """
# #     if not prospect_ids:
# #         return
# #     try:
# #         from app.features.prospects.prospect_scoring import ProspectScorer
# #     except ImportError as exc:  # pragma: no cover — defensive
# #         logger.warning("csv_import.scorer_unavailable", error=str(exc))
# #         return

# #     scorer = ProspectScorer()
# #     try:
# #         result = await db.execute(
# #             select(Prospect).where(Prospect.id.in_(prospect_ids))
# #         )
# #         prospects = list(result.scalars().all())
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning("csv_import.scoring_load_failed", error=str(exc))
# #         return

# #     # Pre-load all referenced IcpProfiles in one shot to avoid N+1 queries.
# #     icp_ids = {p.icpProfileId for p in prospects if p.icpProfileId}
# #     icp_map: dict[str, IcpProfile] = {}
# #     if icp_ids:
# #         try:
# #             icp_result = await db.execute(
# #                 select(IcpProfile).where(IcpProfile.id.in_(icp_ids))
# #             )
# #             icp_map = {row.id: row for row in icp_result.scalars().all()}
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning("csv_import.icp_load_failed", error=str(exc))

# #     scored = 0
# #     for prospect in prospects:
# #         icp_id = prospect.icpProfileId
# #         if not icp_id:
# #             continue
# #         icp_profile = icp_map.get(icp_id)
# #         if icp_profile is None:
# #             continue
# #         try:
# #             score = scorer.score_prospect(prospect, icp_profile)
# #         except Exception as exc:  # noqa: BLE001 — per-row isolation
# #             logger.warning(
# #                 "csv_import.scoring_row_failed",
# #                 prospect_id=prospect.id,
# #                 icp_profile_id=icp_id,
# #                 error=str(exc),
# #             )
# #             continue
# #         try:
# #             prospect.icpFitScore = int(score.total)
# #             prospect.urgencyTier = str(score.urgency_tier)
# #             prospect.icpPersona = (icp_profile.persona or "")[:200] or None
# #             prospect.icpScoreBreakdown = json.dumps(
# #                 {
# #                     "total": score.total,
# #                     "icp_fit": score.icp_fit,
# #                     "intent": score.intent,
# #                     "seniority": score.seniority,
# #                     "firmographic": score.firmographic,
# #                     "urgency_tier": score.urgency_tier,
# #                 }
# #             )
# #             scored += 1
# #         except Exception as exc:  # noqa: BLE001
# #             logger.warning(
# #                 "csv_import.scoring_persist_failed",
# #                 prospect_id=prospect.id,
# #                 error=str(exc),
# #             )
# #     try:
# #         if scored:
# #             await db.flush()
# #     except Exception as exc:  # noqa: BLE001
# #         logger.warning("csv_import.scoring_flush_failed", error=str(exc))
# #     logger.info(
# #         "csv_import.scoring_complete",
# #         total=len(prospects),
# #         scored=scored,
# #     )


# # def get_csv_import_service() -> CsvImportService:
# #     """Factory — return a fresh CsvImportService (stateless)."""
# #     return CsvImportService()


# # __all__: list[str] = [
# #     "CsvImportService",
# #     "get_csv_import_service",
# # ]

# """
# csv_import_service.py — CSV prospect import (per migration doc §6.5).

# Parses a CSV string with Python stdlib ``csv.DictReader`` (RFC-4180 compliant,
# UTF-8, handles quoted fields with embedded commas/newlines), validates each
# row, and bulk-inserts valid rows as ``Prospect`` records.

# Required CSV headers:
#   - firstName (required)
#   - lastName  (required)
#   - email     (required, must contain '@')

# Optional CSV headers:
#   - title, company, domain, linkedinUrl, seniority, timezone, icpProfileId

# The 10MB file-size limit is enforced by the router (per §6.5), not here.
# This service is pure parser + inserter — it accepts the already-decoded
# UTF-8 string and trusts the caller to have applied size + content-type
# limits.

# Returns an ``ImportResult`` with total/created/skipped counts + a list of
# human-readable error strings (one per skipped row).

# FIX-BE-1 / CRITICAL 3: after the bulk insert, ``import_csv`` invokes the
# ``ProspectScorer`` on each newly-created row whose ``icpProfileId`` is set
# (either via an explicit CSV column or via the ``icp_profile_id`` argument
# passed by the caller) and persists ``icpFitScore`` / ``urgencyTier`` /
# ``icpPersona`` / ``icpScoreBreakdown`` on the row. Scoring failures are
# logged + skipped per-row — they never abort the import.
# """
# from __future__ import annotations

# import csv
# import io
# import json
# import re
# from typing import Any

# import structlog
# from sqlalchemy import insert, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.enums import SeniorityTier
# from app.models.prospect_models import IcpProfile, Prospect
# from app.schemas.prospects import ImportResult

# logger = structlog.get_logger(__name__)


# # Canonical internal header names (camelCase) used throughout this service.
# _REQUIRED_HEADERS: tuple[str, ...] = ("firstName", "lastName", "email")
# _OPTIONAL_HEADERS: tuple[str, ...] = (
#     "title",
#     "company",
#     "domain",
#     "linkedinUrl",
#     "seniority",
#     "timezone",
#     "icpProfileId",
# )
# _ALL_HEADERS: frozenset[str] = frozenset(_REQUIRED_HEADERS + _OPTIONAL_HEADERS)

# # Maps every accepted alias → the canonical internal name.
# # Allows users to upload CSVs with either snake_case (Excel-default) or
# # camelCase column headers — both are normalised before validation.
# _HEADER_ALIASES: dict[str, str] = {
#     # required
#     "first_name": "firstName",
#     "firstname": "firstName",
#     "last_name": "lastName",
#     "lastname": "lastName",
#     # optional
#     "linkedin_url": "linkedinUrl",
#     "linkedin": "linkedinUrl",
#     "icp_profile_id": "icpProfileId",
#     "icp_id": "icpProfileId",
# }


# def _normalise_row(raw_row: dict) -> dict:
#     """Return a new dict with all keys mapped to their canonical names.

#     Keys that are already canonical (or have no alias) pass through unchanged.
#     This is applied to *both* the fieldnames check and every data row so the
#     rest of the service never needs to know about the alias table.
#     """
#     return {
#         _HEADER_ALIASES.get(k, k): v
#         for k, v in raw_row.items()
#         if k is not None
#     }

# _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# # Map of allowed seniority values → enum members (accepts case-insensitive input)
# _SENIORITY_LOOKUP: dict[str, SeniorityTier] = {
#     "c_suite": SeniorityTier.C_Suite,
#     "csuite": SeniorityTier.C_Suite,
#     "c-suite": SeniorityTier.C_Suite,
#     "director": SeniorityTier.Director,
#     "ic": SeniorityTier.IC,
#     "individual_contributor": SeniorityTier.IC,
# }

# # Soft cap on per-import row count (defensive; routers should pre-filter).
# _MAX_ROWS_PER_IMPORT: int = 50_000


# class CsvImportService:
#     """CSV prospect importer (RFC-4180, stdlib csv, bulk-insert)."""

#     async def import_csv(
#         self,
#         content: str,
#         db: AsyncSession,
#         *,
#         icp_profile_id: str | None = None,
#     ) -> ImportResult:
#         """
#         Parse + validate + bulk-insert prospects from a CSV string.

#         Args:
#             content:        UTF-8 decoded CSV text.
#             db:             AsyncSession locked to the tenant's schema.
#             icp_profile_id: Optional ICP to link all imported rows to. Per-row
#                             ``icpProfileId`` CSV header takes precedence when
#                             present. Used by FIX-BE-1 / CRITICAL 3 to drive
#                             ICP scoring on import.

#         Returns:
#             ImportResult with counts + errors. Never raises on row-level
#             validation failures — they're collected into ``errors``.
#         """
#         if not content or not content.strip():
#             return ImportResult(total=0, created=0, skipped=0, errors=["CSV is empty."])

#         reader = csv.DictReader(io.StringIO(content))
#         # Normalise the header names so both snake_case and camelCase are accepted.
#         raw_fieldnames: list[str] = list(reader.fieldnames or [])
#         normalised_fieldnames: list[str] = [
#             _HEADER_ALIASES.get(f, f) for f in raw_fieldnames
#         ]
#         missing_required = [h for h in _REQUIRED_HEADERS if h not in normalised_fieldnames]
#         if missing_required:
#             # Show both camelCase and snake_case equivalents in the error so
#             # the message is useful regardless of which convention the user prefers.
#             _alias_pairs = {v: k for k, v in _HEADER_ALIASES.items() if "_" in k}
#             def _both(h: str) -> str:
#                 snake = _alias_pairs.get(h, "")
#                 return f"{h} (or {snake})" if snake else h
#             return ImportResult(
#                 total=0,
#                 created=0,
#                 skipped=0,
#                 errors=[
#                     f"Missing required CSV column(s): "
#                     f"{', '.join(_both(h) for h in missing_required)}. "
#                     f"Accepted formats: camelCase ({', '.join(_REQUIRED_HEADERS)}) "
#                     f"or snake_case (first_name, last_name, email)."
#                 ],
#             )

#         rows_to_insert: list[dict[str, Any]] = []
#         errors: list[str] = []
#         total_seen = 0
#         skipped = 0

#         for line_no, raw_row in enumerate(reader, start=2):
#             total_seen += 1
#             if len(rows_to_insert) >= _MAX_ROWS_PER_IMPORT:
#                 errors.append(
#                     f"Row {line_no}: import cap of {_MAX_ROWS_PER_IMPORT} reached; "
#                     f"remaining rows skipped."
#                 )
#                 skipped += 1
#                 continue

#             # Normalise column names (snake_case → camelCase) then strip whitespace.
#             row = {
#                 k: (v.strip() if isinstance(v, str) else v)
#                 for k, v in _normalise_row(raw_row).items()
#                 if k is not None
#             }

#             # ── Required-field validation ──────────────────────────────────
#             first_name = (row.get("firstName") or "").strip()
#             last_name = (row.get("lastName") or "").strip()
#             email = (row.get("email") or "").strip()

#             if not first_name:
#                 errors.append(f"Row {line_no}: missing firstName.")
#                 skipped += 1
#                 continue
#             if not last_name:
#                 errors.append(f"Row {line_no}: missing lastName.")
#                 skipped += 1
#                 continue
#             if not email:
#                 errors.append(f"Row {line_no}: missing email.")
#                 skipped += 1
#                 continue
#             if not _EMAIL_RE.match(email):
#                 errors.append(f"Row {line_no}: invalid email '{email}'.")
#                 skipped += 1
#                 continue

#             # ── Optional-field validation ──────────────────────────────────
#             seniority: SeniorityTier = SeniorityTier.IC
#             raw_seniority = (row.get("seniority") or "").strip()
#             if raw_seniority:
#                 key = raw_seniority.lower().replace(" ", "_")
#                 if key not in _SENIORITY_LOOKUP:
#                     errors.append(
#                         f"Row {line_no}: invalid seniority '{raw_seniority}' "
#                         f"(expected one of: C_Suite, Director, IC). Defaulted to IC."
#                     )
#                     # Don't skip — just default
#                 else:
#                     seniority = _SENIORITY_LOOKUP[key]

#             title = (row.get("title") or "").strip() or None
#             company = (row.get("company") or "").strip() or None
#             domain = (row.get("domain") or "").strip() or None
#             if domain and not _is_valid_domain(domain):
#                 errors.append(
#                     f"Row {line_no}: invalid domain '{domain}' (kept as-is)."
#                 )
#             linkedin_url = (row.get("linkedinUrl") or "").strip() or None
#             timezone = (row.get("timezone") or "").strip() or None
#             # Auto-derive timezone from email domain when not present in CSV.
#             # Covers country-code TLDs (.in→Asia/Kolkata, .de→Europe/Berlin, etc.).
#             # Generic TLDs (.com, .io) return None — scheduler sends without
#             # business-hours restriction rather than assuming a wrong timezone.
#             if not timezone and email:
#                 timezone = _derive_tz(email)
#             # Optional per-row ICP override — falls back to the caller-
#             # supplied icp_profile_id argument. Used by FIX-BE-1 / CRITICAL 3
#             # to drive scoring on import.
#             row_icp_id = (row.get("icpProfileId") or "").strip() or None
#             effective_icp_id = row_icp_id or icp_profile_id or None

#             row_dict: dict[str, Any] = {
#                 "firstName": first_name,
#                 "lastName": last_name,
#                 "email": email,
#                 "title": title,
#                 "company": company,
#                 "domain": domain,
#                 "linkedinUrl": linkedin_url,
#                 "seniority": seniority,
#                 "timezone": timezone,
#             }
#             if effective_icp_id:
#                 row_dict["icpProfileId"] = effective_icp_id
#             rows_to_insert.append(row_dict)

#         # ── FR-016: dedup against EXISTING prospects ────────────────────────
#         # Two keys, per the URD: (1) email (case-insensitive), and
#         # (2) domain + firstName + lastName (catches the same person imported
#         # with a different address at the same company). In-file duplicates
#         # are collapsed by the same keys so a single upload can't create two
#         # copies either. Duplicates are counted as skipped with a reason.
#         if rows_to_insert:
#             from sqlalchemy import func as _func, or_ as _or

#             emails = [r["email"].lower() for r in rows_to_insert if r.get("email")]
#             dom_names = [
#                 (r["domain"].lower(), r["firstName"].lower(), r["lastName"].lower())
#                 for r in rows_to_insert
#                 if r.get("domain")
#             ]
#             existing_emails: set[str] = set()
#             existing_dom_names: set[tuple[str, str, str]] = set()
#             try:
#                 if emails:
#                     res = await db.execute(
#                         select(Prospect.email).where(
#                             _func.lower(Prospect.email).in_(emails)
#                         )
#                     )
#                     existing_emails = {
#                         (e or "").lower() for (e,) in res.all() if e
#                     }
#                 if dom_names:
#                     res = await db.execute(
#                         select(
#                             Prospect.domain, Prospect.firstName, Prospect.lastName
#                         ).where(
#                             _func.lower(Prospect.domain).in_(
#                                 {d for d, _, _ in dom_names}
#                             )
#                         )
#                     )
#                     existing_dom_names = {
#                         ((d or "").lower(), (f or "").lower(), (l or "").lower())
#                         for d, f, l in res.all()
#                     }
#             except Exception as exc:  # noqa: BLE001 — encrypted-email schemas etc.
#                 logger.warning("csv_import.dedup_lookup_failed", error=str(exc))

#             deduped: list[dict[str, Any]] = []
#             seen_emails: set[str] = set()
#             seen_dom_names: set[tuple[str, str, str]] = set()
#             for r in rows_to_insert:
#                 email_key = (r.get("email") or "").lower()
#                 dn_key = (
#                     (r.get("domain") or "").lower(),
#                     (r.get("firstName") or "").lower(),
#                     (r.get("lastName") or "").lower(),
#                 )
#                 if email_key and (
#                     email_key in existing_emails or email_key in seen_emails
#                 ):
#                     errors.append(
#                         f"Duplicate skipped: {r['email']} already exists."
#                     )
#                     skipped += 1
#                     continue
#                 if r.get("domain") and (
#                     dn_key in existing_dom_names or dn_key in seen_dom_names
#                 ):
#                     errors.append(
#                         f"Duplicate skipped: {r['firstName']} {r['lastName']} "
#                         f"@ {r['domain']} already exists."
#                     )
#                     skipped += 1
#                     continue
#                 seen_emails.add(email_key)
#                 if r.get("domain"):
#                     seen_dom_names.add(dn_key)
#                 deduped.append(r)
#             rows_to_insert = deduped

#         created = 0
#         created_ids: list[str] = []
#         if rows_to_insert:
#             try:
#                 result = await db.execute(
#                     insert(Prospect).values(rows_to_insert).returning(Prospect.id)
#                 )
#                 rows = result.fetchall()
#                 created = len(rows)
#                 created_ids = [str(r[0]) for r in rows]
#                 await db.flush()
#             except Exception as exc:
#                 # Bulk-insert failure: surface to caller but preserve the
#                 # parsed row count so the user knows what was attempted.
#                 logger.error("csv_import.bulk_insert_failed", error=str(exc))
#                 errors.append(f"Bulk insert failed: {exc}")
#                 return ImportResult(
#                     total=total_seen,
#                     created=0,
#                     skipped=skipped + len(rows_to_insert),
#                     errors=errors,
#                 )

#         # ── FIX-BE-1 / CRITICAL 3: ICP scoring on import ──────────────────
#         # Score each newly-created prospect against its linked IcpProfile
#         # (per-row icpProfileId or the caller-supplied icp_profile_id).
#         # Best-effort — per-row failures are logged + skipped; they never
#         # abort the import or affect the created count.
#         if created_ids:
#             await _score_imported_prospects(db, created_ids)

#         logger.info(
#             "csv_import.complete",
#             total=total_seen,
#             created=created,
#             skipped=skipped,
#             error_count=len(errors),
#         )
#         return ImportResult(
#             total=total_seen,
#             created=created,
#             skipped=skipped,
#             errors=errors,
#         )


# def _is_valid_domain(domain: str) -> bool:
#     """Lenient domain validator — must contain a dot and no spaces."""
#     if not domain:
#         return False
#     if " " in domain:
#         return False
#     if "." not in domain:
#         return False
#     return True


# async def _score_imported_prospects(
#     db: AsyncSession, prospect_ids: list[str]
# ) -> None:
#     """FIX-BE-1 / CRITICAL 3 — score each newly-imported Prospect.

#     Loads each Prospect + its IcpProfile (when set), invokes
#     ``ProspectScorer.score_prospect``, and UPDATEs the row with
#     ``icpFitScore`` / ``urgencyTier`` / ``icpPersona`` /
#     ``icpScoreBreakdown``. Best-effort — per-row failures are logged +
#     skipped; they never abort the import or affect the created count.
#     """
#     if not prospect_ids:
#         return
#     try:
#         from app.features.prospects.prospect_scoring import ProspectScorer
#     except ImportError as exc:  # pragma: no cover — defensive
#         logger.warning("csv_import.scorer_unavailable", error=str(exc))
#         return

#     scorer = ProspectScorer()
#     try:
#         result = await db.execute(
#             select(Prospect).where(Prospect.id.in_(prospect_ids))
#         )
#         prospects = list(result.scalars().all())
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("csv_import.scoring_load_failed", error=str(exc))
#         return

#     # Pre-load all referenced IcpProfiles in one shot to avoid N+1 queries.
#     icp_ids = {p.icpProfileId for p in prospects if p.icpProfileId}
#     icp_map: dict[str, IcpProfile] = {}
#     if icp_ids:
#         try:
#             icp_result = await db.execute(
#                 select(IcpProfile).where(IcpProfile.id.in_(icp_ids))
#             )
#             icp_map = {row.id: row for row in icp_result.scalars().all()}
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("csv_import.icp_load_failed", error=str(exc))

#     scored = 0
#     for prospect in prospects:
#         icp_id = prospect.icpProfileId
#         if not icp_id:
#             continue
#         icp_profile = icp_map.get(icp_id)
#         if icp_profile is None:
#             continue
#         try:
#             score = scorer.score_prospect(prospect, icp_profile)
#         except Exception as exc:  # noqa: BLE001 — per-row isolation
#             logger.warning(
#                 "csv_import.scoring_row_failed",
#                 prospect_id=prospect.id,
#                 icp_profile_id=icp_id,
#                 error=str(exc),
#             )
#             continue
#         try:
#             prospect.icpFitScore = int(score.total)
#             prospect.urgencyTier = str(score.urgency_tier)
#             prospect.icpPersona = (icp_profile.persona or "")[:200] or None
#             prospect.icpScoreBreakdown = json.dumps(
#                 {
#                     "total": score.total,
#                     "icp_fit": score.icp_fit,
#                     "intent": score.intent,
#                     "seniority": score.seniority,
#                     "firmographic": score.firmographic,
#                     "urgency_tier": score.urgency_tier,
#                 }
#             )
#             scored += 1
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "csv_import.scoring_persist_failed",
#                 prospect_id=prospect.id,
#                 error=str(exc),
#             )
#     try:
#         if scored:
#             await db.flush()
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("csv_import.scoring_flush_failed", error=str(exc))
#     logger.info(
#         "csv_import.scoring_complete",
#         total=len(prospects),
#         scored=scored,
#     )


# def get_csv_import_service() -> CsvImportService:
#     """Factory — return a fresh CsvImportService (stateless)."""
#     return CsvImportService()


# __all__: list[str] = [
#     "CsvImportService",
#     "get_csv_import_service",
# ]

# """
# csv_import_service.py — CSV prospect import (per migration doc §6.5).

# Parses a CSV string with Python stdlib ``csv.DictReader`` (RFC-4180 compliant,
# UTF-8, handles quoted fields with embedded commas/newlines), validates each
# row, and bulk-inserts valid rows as ``Prospect`` records.

# Required CSV headers:
#   - firstName (required)
#   - lastName  (required)
#   - email     (required, must contain '@')

# Optional CSV headers:
#   - title, company, domain, linkedinUrl, seniority, timezone, icpProfileId

# The 10MB file-size limit is enforced by the router (per §6.5), not here.
# This service is pure parser + inserter — it accepts the already-decoded
# UTF-8 string and trusts the caller to have applied size + content-type
# limits.

# Returns an ``ImportResult`` with total/created/skipped counts + a list of
# human-readable error strings (one per skipped row).

# FIX-BE-1 / CRITICAL 3: after the bulk insert, ``import_csv`` invokes the
# ``ProspectScorer`` on each newly-created row whose ``icpProfileId`` is set
# (either via an explicit CSV column or via the ``icp_profile_id`` argument
# passed by the caller) and persists ``icpFitScore`` / ``urgencyTier`` /
# ``icpPersona`` / ``icpScoreBreakdown`` on the row. Scoring failures are
# logged + skipped per-row — they never abort the import.
# """
# from __future__ import annotations

# import csv
# import io
# import json
# import re
# from typing import Any

# import structlog
# from sqlalchemy import insert, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.enums import SeniorityTier
# from app.models.prospect_models import IcpProfile, Prospect
# from app.schemas.prospects import ImportResult

# logger = structlog.get_logger(__name__)


# # Canonical internal header names (camelCase) used throughout this service.
# _REQUIRED_HEADERS: tuple[str, ...] = ("firstName", "lastName", "email")
# _OPTIONAL_HEADERS: tuple[str, ...] = (
#     "title",
#     "company",
#     "domain",
#     "linkedinUrl",
#     "seniority",
#     "timezone",
#     "icpProfileId",
# )
# _ALL_HEADERS: frozenset[str] = frozenset(_REQUIRED_HEADERS + _OPTIONAL_HEADERS)

# # Maps every accepted alias → the canonical internal name.
# # Allows users to upload CSVs with either snake_case (Excel-default) or
# # camelCase column headers — both are normalised before validation.
# _HEADER_ALIASES: dict[str, str] = {
#     # required
#     "first_name": "firstName",
#     "firstname": "firstName",
#     "last_name": "lastName",
#     "lastname": "lastName",
#     # optional
#     "linkedin_url": "linkedinUrl",
#     "linkedin": "linkedinUrl",
#     "icp_profile_id": "icpProfileId",
#     "icp_id": "icpProfileId",
# }


# def _normalise_row(raw_row: dict) -> dict:
#     """Return a new dict with all keys mapped to their canonical names.

#     Keys that are already canonical (or have no alias) pass through unchanged.
#     This is applied to *both* the fieldnames check and every data row so the
#     rest of the service never needs to know about the alias table.
#     """
#     return {
#         _HEADER_ALIASES.get(k, k): v
#         for k, v in raw_row.items()
#         if k is not None
#     }

# _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# # Map of allowed seniority values → enum members (accepts case-insensitive input)
# _SENIORITY_LOOKUP: dict[str, SeniorityTier] = {
#     "c_suite": SeniorityTier.C_Suite,
#     "csuite": SeniorityTier.C_Suite,
#     "c-suite": SeniorityTier.C_Suite,
#     "director": SeniorityTier.Director,
#     "ic": SeniorityTier.IC,
#     "individual_contributor": SeniorityTier.IC,
# }

# # Soft cap on per-import row count (defensive; routers should pre-filter).
# _MAX_ROWS_PER_IMPORT: int = 50_000


# class CsvImportService:
#     """CSV prospect importer (RFC-4180, stdlib csv, bulk-insert)."""

#     async def import_csv(
#         self,
#         content: str,
#         db: AsyncSession,
#         *,
#         icp_profile_id: str | None = None,
#     ) -> ImportResult:
#         """
#         Parse + validate + bulk-insert prospects from a CSV string.

#         Args:
#             content:        UTF-8 decoded CSV text.
#             db:             AsyncSession locked to the tenant's schema.
#             icp_profile_id: Optional ICP to link all imported rows to. Per-row
#                             ``icpProfileId`` CSV header takes precedence when
#                             present. Used by FIX-BE-1 / CRITICAL 3 to drive
#                             ICP scoring on import.

#         Returns:
#             ImportResult with counts + errors. Never raises on row-level
#             validation failures — they're collected into ``errors``.
#         """
#         if not content or not content.strip():
#             return ImportResult(total=0, created=0, skipped=0, errors=["CSV is empty."])

#         reader = csv.DictReader(io.StringIO(content))
#         # Normalise the header names so both snake_case and camelCase are accepted.
#         raw_fieldnames: list[str] = list(reader.fieldnames or [])
#         normalised_fieldnames: list[str] = [
#             _HEADER_ALIASES.get(f, f) for f in raw_fieldnames
#         ]
#         missing_required = [h for h in _REQUIRED_HEADERS if h not in normalised_fieldnames]
#         if missing_required:
#             # Show both camelCase and snake_case equivalents in the error so
#             # the message is useful regardless of which convention the user prefers.
#             _alias_pairs = {v: k for k, v in _HEADER_ALIASES.items() if "_" in k}
#             def _both(h: str) -> str:
#                 snake = _alias_pairs.get(h, "")
#                 return f"{h} (or {snake})" if snake else h
#             return ImportResult(
#                 total=0,
#                 created=0,
#                 skipped=0,
#                 errors=[
#                     f"Missing required CSV column(s): "
#                     f"{', '.join(_both(h) for h in missing_required)}. "
#                     f"Accepted formats: camelCase ({', '.join(_REQUIRED_HEADERS)}) "
#                     f"or snake_case (first_name, last_name, email)."
#                 ],
#             )

#         rows_to_insert: list[dict[str, Any]] = []
#         errors: list[str] = []
#         total_seen = 0
#         skipped = 0

#         for line_no, raw_row in enumerate(reader, start=2):
#             total_seen += 1
#             if len(rows_to_insert) >= _MAX_ROWS_PER_IMPORT:
#                 errors.append(
#                     f"Row {line_no}: import cap of {_MAX_ROWS_PER_IMPORT} reached; "
#                     f"remaining rows skipped."
#                 )
#                 skipped += 1
#                 continue

#             # Normalise column names (snake_case → camelCase) then strip whitespace.
#             row = {
#                 k: (v.strip() if isinstance(v, str) else v)
#                 for k, v in _normalise_row(raw_row).items()
#                 if k is not None
#             }

#             # ── Required-field validation ──────────────────────────────────
#             first_name = (row.get("firstName") or "").strip()
#             last_name = (row.get("lastName") or "").strip()
#             email = (row.get("email") or "").strip()

#             if not first_name:
#                 errors.append(f"Row {line_no}: missing firstName.")
#                 skipped += 1
#                 continue
#             if not last_name:
#                 errors.append(f"Row {line_no}: missing lastName.")
#                 skipped += 1
#                 continue
#             if not email:
#                 errors.append(f"Row {line_no}: missing email.")
#                 skipped += 1
#                 continue
#             if not _EMAIL_RE.match(email):
#                 errors.append(f"Row {line_no}: invalid email '{email}'.")
#                 skipped += 1
#                 continue

#             # ── Optional-field validation ──────────────────────────────────
#             seniority: SeniorityTier = SeniorityTier.IC
#             raw_seniority = (row.get("seniority") or "").strip()
#             if raw_seniority:
#                 key = raw_seniority.lower().replace(" ", "_")
#                 if key not in _SENIORITY_LOOKUP:
#                     errors.append(
#                         f"Row {line_no}: invalid seniority '{raw_seniority}' "
#                         f"(expected one of: C_Suite, Director, IC). Defaulted to IC."
#                     )
#                     # Don't skip — just default
#                 else:
#                     seniority = _SENIORITY_LOOKUP[key]

#             title = (row.get("title") or "").strip() or None
#             company = (row.get("company") or "").strip() or None
#             domain = (row.get("domain") or "").strip() or None
#             if domain and not _is_valid_domain(domain):
#                 errors.append(
#                     f"Row {line_no}: invalid domain '{domain}' (kept as-is)."
#                 )
#             linkedin_url = (row.get("linkedinUrl") or "").strip() or None
#             timezone = (row.get("timezone") or "").strip() or None
#             # Optional per-row ICP override — falls back to the caller-
#             # supplied icp_profile_id argument. Used by FIX-BE-1 / CRITICAL 3
#             # to drive scoring on import.
#             row_icp_id = (row.get("icpProfileId") or "").strip() or None
#             effective_icp_id = row_icp_id or icp_profile_id or None

#             row_dict: dict[str, Any] = {
#                 "firstName": first_name,
#                 "lastName": last_name,
#                 "email": email,
#                 "title": title,
#                 "company": company,
#                 "domain": domain,
#                 "linkedinUrl": linkedin_url,
#                 "seniority": seniority,
#                 "timezone": timezone,
#             }
#             if effective_icp_id:
#                 row_dict["icpProfileId"] = effective_icp_id
#             rows_to_insert.append(row_dict)

#         # ── FR-016: dedup against EXISTING prospects ────────────────────────
#         # Two keys, per the URD: (1) email (case-insensitive), and
#         # (2) domain + firstName + lastName (catches the same person imported
#         # with a different address at the same company). In-file duplicates
#         # are collapsed by the same keys so a single upload can't create two
#         # copies either. Duplicates are counted as skipped with a reason.
#         if rows_to_insert:
#             from sqlalchemy import func as _func, or_ as _or

#             emails = [r["email"].lower() for r in rows_to_insert if r.get("email")]
#             dom_names = [
#                 (r["domain"].lower(), r["firstName"].lower(), r["lastName"].lower())
#                 for r in rows_to_insert
#                 if r.get("domain")
#             ]
#             existing_emails: set[str] = set()
#             existing_dom_names: set[tuple[str, str, str]] = set()
#             try:
#                 if emails:
#                     res = await db.execute(
#                         select(Prospect.email).where(
#                             _func.lower(Prospect.email).in_(emails)
#                         )
#                     )
#                     existing_emails = {
#                         (e or "").lower() for (e,) in res.all() if e
#                     }
#                 if dom_names:
#                     res = await db.execute(
#                         select(
#                             Prospect.domain, Prospect.firstName, Prospect.lastName
#                         ).where(
#                             _func.lower(Prospect.domain).in_(
#                                 {d for d, _, _ in dom_names}
#                             )
#                         )
#                     )
#                     existing_dom_names = {
#                         ((d or "").lower(), (f or "").lower(), (l or "").lower())
#                         for d, f, l in res.all()
#                     }
#             except Exception as exc:  # noqa: BLE001 — encrypted-email schemas etc.
#                 logger.warning("csv_import.dedup_lookup_failed", error=str(exc))

#             deduped: list[dict[str, Any]] = []
#             seen_emails: set[str] = set()
#             seen_dom_names: set[tuple[str, str, str]] = set()
#             for r in rows_to_insert:
#                 email_key = (r.get("email") or "").lower()
#                 dn_key = (
#                     (r.get("domain") or "").lower(),
#                     (r.get("firstName") or "").lower(),
#                     (r.get("lastName") or "").lower(),
#                 )
#                 if email_key and (
#                     email_key in existing_emails or email_key in seen_emails
#                 ):
#                     errors.append(
#                         f"Duplicate skipped: {r['email']} already exists."
#                     )
#                     skipped += 1
#                     continue
#                 if r.get("domain") and (
#                     dn_key in existing_dom_names or dn_key in seen_dom_names
#                 ):
#                     errors.append(
#                         f"Duplicate skipped: {r['firstName']} {r['lastName']} "
#                         f"@ {r['domain']} already exists."
#                     )
#                     skipped += 1
#                     continue
#                 seen_emails.add(email_key)
#                 if r.get("domain"):
#                     seen_dom_names.add(dn_key)
#                 deduped.append(r)
#             rows_to_insert = deduped

#         created = 0
#         created_ids: list[str] = []
#         if rows_to_insert:
#             try:
#                 result = await db.execute(
#                     insert(Prospect).values(rows_to_insert).returning(Prospect.id)
#                 )
#                 rows = result.fetchall()
#                 created = len(rows)
#                 created_ids = [str(r[0]) for r in rows]
#                 await db.flush()
#             except Exception as exc:
#                 # Bulk-insert failure: surface to caller but preserve the
#                 # parsed row count so the user knows what was attempted.
#                 logger.error("csv_import.bulk_insert_failed", error=str(exc))
#                 errors.append(f"Bulk insert failed: {exc}")
#                 return ImportResult(
#                     total=total_seen,
#                     created=0,
#                     skipped=skipped + len(rows_to_insert),
#                     errors=errors,
#                 )

#         # ── FIX-BE-1 / CRITICAL 3: ICP scoring on import ──────────────────
#         # Score each newly-created prospect against its linked IcpProfile
#         # (per-row icpProfileId or the caller-supplied icp_profile_id).
#         # Best-effort — per-row failures are logged + skipped; they never
#         # abort the import or affect the created count.
#         if created_ids:
#             await _score_imported_prospects(db, created_ids)

#         logger.info(
#             "csv_import.complete",
#             total=total_seen,
#             created=created,
#             skipped=skipped,
#             error_count=len(errors),
#         )
#         return ImportResult(
#             total=total_seen,
#             created=created,
#             skipped=skipped,
#             errors=errors,
#         )


# def _is_valid_domain(domain: str) -> bool:
#     """Lenient domain validator — must contain a dot and no spaces."""
#     if not domain:
#         return False
#     if " " in domain:
#         return False
#     if "." not in domain:
#         return False
#     return True


# async def _score_imported_prospects(
#     db: AsyncSession, prospect_ids: list[str]
# ) -> None:
#     """FIX-BE-1 / CRITICAL 3 — score each newly-imported Prospect.

#     Loads each Prospect + its IcpProfile (when set), invokes
#     ``ProspectScorer.score_prospect``, and UPDATEs the row with
#     ``icpFitScore`` / ``urgencyTier`` / ``icpPersona`` /
#     ``icpScoreBreakdown``. Best-effort — per-row failures are logged +
#     skipped; they never abort the import or affect the created count.
#     """
#     if not prospect_ids:
#         return
#     try:
#         from app.features.prospects.prospect_scoring import ProspectScorer
#     except ImportError as exc:  # pragma: no cover — defensive
#         logger.warning("csv_import.scorer_unavailable", error=str(exc))
#         return

#     scorer = ProspectScorer()
#     try:
#         result = await db.execute(
#             select(Prospect).where(Prospect.id.in_(prospect_ids))
#         )
#         prospects = list(result.scalars().all())
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("csv_import.scoring_load_failed", error=str(exc))
#         return

#     # Pre-load all referenced IcpProfiles in one shot to avoid N+1 queries.
#     icp_ids = {p.icpProfileId for p in prospects if p.icpProfileId}
#     icp_map: dict[str, IcpProfile] = {}
#     if icp_ids:
#         try:
#             icp_result = await db.execute(
#                 select(IcpProfile).where(IcpProfile.id.in_(icp_ids))
#             )
#             icp_map = {row.id: row for row in icp_result.scalars().all()}
#         except Exception as exc:  # noqa: BLE001
#             logger.warning("csv_import.icp_load_failed", error=str(exc))

#     scored = 0
#     for prospect in prospects:
#         icp_id = prospect.icpProfileId
#         if not icp_id:
#             continue
#         icp_profile = icp_map.get(icp_id)
#         if icp_profile is None:
#             continue
#         try:
#             score = scorer.score_prospect(prospect, icp_profile)
#         except Exception as exc:  # noqa: BLE001 — per-row isolation
#             logger.warning(
#                 "csv_import.scoring_row_failed",
#                 prospect_id=prospect.id,
#                 icp_profile_id=icp_id,
#                 error=str(exc),
#             )
#             continue
#         try:
#             prospect.icpFitScore = int(score.total)
#             prospect.urgencyTier = str(score.urgency_tier)
#             prospect.icpPersona = (icp_profile.persona or "")[:200] or None
#             prospect.icpScoreBreakdown = json.dumps(
#                 {
#                     "total": score.total,
#                     "icp_fit": score.icp_fit,
#                     "intent": score.intent,
#                     "seniority": score.seniority,
#                     "firmographic": score.firmographic,
#                     "urgency_tier": score.urgency_tier,
#                 }
#             )
#             scored += 1
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "csv_import.scoring_persist_failed",
#                 prospect_id=prospect.id,
#                 error=str(exc),
#             )
#     try:
#         if scored:
#             await db.flush()
#     except Exception as exc:  # noqa: BLE001
#         logger.warning("csv_import.scoring_flush_failed", error=str(exc))
#     logger.info(
#         "csv_import.scoring_complete",
#         total=len(prospects),
#         scored=scored,
#     )


# def get_csv_import_service() -> CsvImportService:
#     """Factory — return a fresh CsvImportService (stateless)."""
#     return CsvImportService()


# __all__: list[str] = [
#     "CsvImportService",
#     "get_csv_import_service",
# ]

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


# Canonical internal header names (camelCase) used throughout this service.
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

# Maps every accepted alias → the canonical internal name.
# Allows users to upload CSVs with either snake_case (Excel-default) or
# camelCase column headers — both are normalised before validation.
_HEADER_ALIASES: dict[str, str] = {
    # required
    "first_name": "firstName",
    "firstname": "firstName",
    "last_name": "lastName",
    "lastname": "lastName",
    # optional
    "linkedin_url": "linkedinUrl",
    "linkedin": "linkedinUrl",
    "icp_profile_id": "icpProfileId",
    "icp_id": "icpProfileId",
}


def _normalise_row(raw_row: dict) -> dict:
    """Return a new dict with all keys mapped to their canonical names.

    Keys that are already canonical (or have no alias) pass through unchanged.
    This is applied to *both* the fieldnames check and every data row so the
    rest of the service never needs to know about the alias table.
    """
    return {
        _HEADER_ALIASES.get(k, k): v
        for k, v in raw_row.items()
        if k is not None
    }

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
        # Normalise the header names so both snake_case and camelCase are accepted.
        raw_fieldnames: list[str] = list(reader.fieldnames or [])
        normalised_fieldnames: list[str] = [
            _HEADER_ALIASES.get(f, f) for f in raw_fieldnames
        ]
        missing_required = [h for h in _REQUIRED_HEADERS if h not in normalised_fieldnames]
        if missing_required:
            # Show both camelCase and snake_case equivalents in the error so
            # the message is useful regardless of which convention the user prefers.
            _alias_pairs = {v: k for k, v in _HEADER_ALIASES.items() if "_" in k}
            def _both(h: str) -> str:
                snake = _alias_pairs.get(h, "")
                return f"{h} (or {snake})" if snake else h
            return ImportResult(
                total=0,
                created=0,
                skipped=0,
                errors=[
                    f"Missing required CSV column(s): "
                    f"{', '.join(_both(h) for h in missing_required)}. "
                    f"Accepted formats: camelCase ({', '.join(_REQUIRED_HEADERS)}) "
                    f"or snake_case (first_name, last_name, email)."
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

            # Normalise column names (snake_case → camelCase) then strip whitespace.
            row = {
                k: (v.strip() if isinstance(v, str) else v)
                for k, v in _normalise_row(raw_row).items()
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
            # Auto-derive timezone from email domain when not present in CSV.
            # Covers country-code TLDs (.in→Asia/Kolkata, .de→Europe/Berlin, etc.).
            # Generic TLDs (.com, .io) return None — scheduler sends without
            # business-hours restriction rather than assuming a wrong timezone.
            if not timezone and email:
                timezone = _derive_tz(email)
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


# ── Timezone-from-email-domain derivation ───────────────────────────────────
# NOTE: this is the same country-code-TLD mapping used by
# alembic/versions/0023_backfill_prospect_timezone.py to backfill existing
# Prospect rows. That migration is deliberately self-contained (migrations
# must not import app code), so it carries its own copy rather than
# importing this one — this is the one used going forward for every new
# import. Keep the two in sync if the mapping is ever extended.
_TZ_TLD_TO_TIMEZONE: dict[str, str] = {
    # South Asia
    "in": "Asia/Kolkata", "lk": "Asia/Colombo", "bd": "Asia/Dhaka",
    "np": "Asia/Kathmandu", "pk": "Asia/Karachi", "af": "Asia/Kabul",
    # Southeast Asia
    "sg": "Asia/Singapore", "my": "Asia/Kuala_Lumpur", "th": "Asia/Bangkok",
    "vn": "Asia/Ho_Chi_Minh", "ph": "Asia/Manila", "id": "Asia/Jakarta",
    "mm": "Asia/Rangoon", "kh": "Asia/Phnom_Penh",
    # East Asia
    "jp": "Asia/Tokyo", "kr": "Asia/Seoul", "tw": "Asia/Taipei",
    "hk": "Asia/Hong_Kong", "cn": "Asia/Shanghai",
    # Middle East
    "ae": "Asia/Dubai", "sa": "Asia/Riyadh", "il": "Asia/Jerusalem",
    "tr": "Europe/Istanbul", "ir": "Asia/Tehran", "iq": "Asia/Baghdad",
    "kw": "Asia/Kuwait", "qa": "Asia/Qatar", "bh": "Asia/Bahrain",
    "om": "Asia/Muscat", "jo": "Asia/Amman", "lb": "Asia/Beirut",
    # Central Asia
    "kz": "Asia/Almaty", "uz": "Asia/Tashkent", "az": "Asia/Baku",
    "ge": "Asia/Tbilisi", "am": "Asia/Yerevan",
    # Europe — Western
    "uk": "Europe/London", "gb": "Europe/London", "ie": "Europe/Dublin",
    "de": "Europe/Berlin", "fr": "Europe/Paris", "es": "Europe/Madrid",
    "it": "Europe/Rome", "nl": "Europe/Amsterdam", "be": "Europe/Brussels",
    "ch": "Europe/Zurich", "at": "Europe/Vienna", "pt": "Europe/Lisbon",
    "se": "Europe/Stockholm", "no": "Europe/Oslo", "dk": "Europe/Copenhagen",
    "fi": "Europe/Helsinki", "lu": "Europe/Luxembourg",
    # Europe — Eastern
    "pl": "Europe/Warsaw", "cz": "Europe/Prague", "sk": "Europe/Bratislava",
    "hu": "Europe/Budapest", "ro": "Europe/Bucharest", "bg": "Europe/Sofia",
    "hr": "Europe/Zagreb", "rs": "Europe/Belgrade", "ua": "Europe/Kiev",
    "by": "Europe/Minsk", "lt": "Europe/Vilnius", "lv": "Europe/Riga",
    "ee": "Europe/Tallinn", "ru": "Europe/Moscow", "gr": "Europe/Athens",
    # Americas
    "br": "America/Sao_Paulo", "mx": "America/Mexico_City",
    "ar": "America/Argentina/Buenos_Aires", "cl": "America/Santiago",
    "co": "America/Bogota", "pe": "America/Lima", "ve": "America/Caracas",
    "ec": "America/Guayaquil", "uy": "America/Montevideo",
    "bo": "America/La_Paz", "py": "America/Asuncion",
    "cr": "America/Costa_Rica", "pa": "America/Panama",
    "gt": "America/Guatemala", "cu": "America/Havana",
    "ca": "America/Toronto",
    # Africa
    "za": "Africa/Johannesburg", "ng": "Africa/Lagos", "ke": "Africa/Nairobi",
    "eg": "Africa/Cairo", "ma": "Africa/Casablanca", "gh": "Africa/Accra",
    "et": "Africa/Addis_Ababa", "tz": "Africa/Dar_es_Salaam",
    "ug": "Africa/Kampala", "sn": "Africa/Dakar",
    # Oceania
    "au": "Australia/Sydney", "nz": "Pacific/Auckland",
}

_TZ_SECOND_LEVEL: dict[str, str] = {
    "co.uk": "Europe/London", "org.uk": "Europe/London",
    "co.in": "Asia/Kolkata", "net.in": "Asia/Kolkata", "org.in": "Asia/Kolkata",
    "co.jp": "Asia/Tokyo", "ne.jp": "Asia/Tokyo",
    "com.au": "Australia/Sydney", "net.au": "Australia/Sydney",
    "co.nz": "Pacific/Auckland",
    "com.br": "America/Sao_Paulo",
    "com.mx": "America/Mexico_City",
    "com.ar": "America/Argentina/Buenos_Aires",
    "com.co": "America/Bogota",
    "com.sg": "Asia/Singapore",
    "com.my": "Asia/Kuala_Lumpur",
    "com.hk": "Asia/Hong_Kong",
    "com.tw": "Asia/Taipei",
    "com.cn": "Asia/Shanghai",
    "co.za": "Africa/Johannesburg",
    "co.ke": "Africa/Nairobi",
    "com.ng": "Africa/Lagos",
    "com.eg": "Africa/Cairo",
    "co.il": "Asia/Jerusalem",
    "co.ae": "Asia/Dubai",
    "com.sa": "Asia/Riyadh",
    "com.tr": "Europe/Istanbul",
    "co.kr": "Asia/Seoul",
    "com.ph": "Asia/Manila",
    "com.vn": "Asia/Ho_Chi_Minh",
    "com.pk": "Asia/Karachi",
}

_TZ_GENERIC_TLDS = frozenset({
    "com", "org", "net", "io", "co", "app", "dev", "ai", "tech",
    "info", "biz", "xyz", "online", "site", "web", "cloud",
})

_TZ_STRIP_RE = re.compile(r"^(?:www\d*\.|mail\.|smtp\.|mx\d*\.)+", re.IGNORECASE)


def _derive_tz(email: str) -> str | None:
    """Derive an IANA timezone from an email's country-code TLD.

    Generic TLDs (.com, .io, .co, etc.) return None on purpose — the
    scheduler treats a NULL Prospect.timezone as "no business-hours
    restriction" rather than guessing wrong. Only genuine country-code
    TLDs (and known second-level ones like .co.uk, .com.au) resolve to a
    timezone. Mirrors alembic/versions/0023_backfill_prospect_timezone.py's
    _tz_from_email exactly, so newly imported prospects get the same
    derivation as the historical backfill.
    """
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    domain = _TZ_STRIP_RE.sub("", domain)
    if not domain or "." not in domain:
        return None
    # Second-level ccTLD (e.g. co.uk, com.au) checked first — more specific.
    for suffix, tz in _TZ_SECOND_LEVEL.items():
        if domain.endswith("." + suffix):
            return tz
    # Single top-level TLD.
    tld = domain.rsplit(".", 1)[-1]
    if tld in _TZ_GENERIC_TLDS:
        return None
    return _TZ_TLD_TO_TIMEZONE.get(tld)


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