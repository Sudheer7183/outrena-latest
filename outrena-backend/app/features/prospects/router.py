# """
# prospects.py — Phase 2 /api/v1/prospects router.

# Endpoints:
#   GET    /prospects                  list with pagination + filter
#   POST   /prospects                  create
#   POST   /prospects/import           CSV import (UploadFile)
#   POST   /prospects/enrich           enrich prospect
#   POST   /prospects/email-validate   validate email via MX lookup
#   GET    /prospects/export           CSV export (RFC-4180, UTF-8 BOM)
#   GET    /prospects/{prospect_id}    fetch one
#   PUT    /prospects/{prospect_id}    update
#   DELETE /prospects/{prospect_id}    delete (204 — soft-delete + anonymise)
#   GET    /prospects/{prospect_id}/consent          consent history
#   POST   /prospects/{prospect_id}/consent/grant    record consent
#   POST   /prospects/{prospect_id}/consent/withdraw withdraw consent

# Role gate: Role.REP. GDPR consent endpoints require Role.REP (any
# authenticated user can manage consent for prospects they can read).
# """
# from __future__ import annotations

# from datetime import datetime

# from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
# from fastapi.responses import PlainTextResponse, Response
# from pydantic import BaseModel, ConfigDict, Field
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role, verify_tenant
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.prospects import (
#     CsvImportResult,
#     EmailValidateRequest,
#     EmailValidateResponse,
#     EnrichRequest,
#     EnrichResponse,
#     ProspectCreate,
#     ProspectListResponse,
#     ProspectResponse,
#     ProspectUpdate,
# )
# from app.services.csv_export_service import rows_to_csv
# from app.features.gdpr.service import GdprService
# from app.features.prospects.service import ProspectService

# router = APIRouter(prefix="/prospects", tags=["Prospects"])
# _service = ProspectService()
# _gdpr = GdprService()

# _MAX_IMPORT_BYTES = 10 * 1024 * 1024  # 10MB

# _CSV_COLUMNS = [
#     "id", "firstName", "lastName", "email", "title", "company", "domain",
#     "linkedinUrl", "seniority", "qaScore", "emailValidated", "enrichmentTier",
#     "intentSource", "intentDetail", "intentStrength", "timezone", "status",
#     "icpProfileId", "icpFitScore", "urgencyTier", "createdAt",
# ]


# @router.get("", response_model=ProspectListResponse)
# async def list_prospects(
#     request: Request,
#     search: str | None = Query(default=None),
#     prospect_status: str | None = Query(default=None, alias="status"),
#     icp_profile_id: str | None = Query(default=None),
#     seniority: str | None = Query(default=None),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     include_deleted: bool = Query(default=False),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectListResponse:
#     """List prospects. Soft-deleted rows are hidden unless
#     ``include_deleted=true`` AND the caller is TENANT_ADMIN+."""
#     # Only TENANT_ADMIN+ may see soft-deleted (anonymised) rows.
#     can_see_deleted = token.role in (Role.TENANT_ADMIN, Role.SUPER_ADMIN)
#     effective_include_deleted = bool(include_deleted and can_see_deleted)
#     items, total = await _service.list_prospects(
#         db,
#         search=search,
#         status=prospect_status,
#         icp_profile_id=icp_profile_id,
#         seniority=seniority,
#         limit=limit,
#         offset=offset,
#         include_deleted=effective_include_deleted,
#     )
#     return ProspectListResponse(
#         items=[ProspectResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post("", response_model=ProspectResponse, status_code=201)
# async def create_prospect(
#     body: ProspectCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectResponse:
#     # item = await _service.create(db, body)
#     # return ProspectResponse.model_validate(item)
#     item = await _service.create(db, body)
#     return ProspectResponse.model_validate(item)


# # Static routes declared BEFORE /{prospect_id} (Pitfall #7).
# @router.post("/import", response_model=CsvImportResult)
# async def import_prospects(
#     file: UploadFile = File(...),
#     icp_profile_id: str | None = Query(
#         default=None,
#         description="Optional ICP to link all imported rows to + drive ICP scoring (FIX-BE-1).",
#     ),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> CsvImportResult:
#     """CSV import via UploadFile — RFC-4180 with UTF-8.

#     FIX-BE-1 / CRITICAL 3: an optional ``?icp_profile_id=`` query param
#     links all imported rows to that ICP and triggers ICP-fit scoring
#     (``icpFitScore`` / ``urgencyTier`` / ``icpScoreBreakdown``) on each
#     newly-created Prospect row. Per-row ``icpProfileId`` CSV header
#     takes precedence when present.
#     """
#     if file.content_type != "text/csv":
#         raise HTTPException(
#             status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#             "Only CSV files are accepted.",
#         )
#     content = await file.read()
#     if len(content) > _MAX_IMPORT_BYTES:
#         raise HTTPException(
#             status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
#             "File exceeds 10MB limit.",
#         )
#     text = content.decode("utf-8", errors="replace")
#     result = await _service.import_csv(db, text, icp_profile_id=icp_profile_id)
#     if isinstance(result, CsvImportResult):
#         return result
#     return CsvImportResult(**result)


# @router.post("/enrich", response_model=EnrichResponse)
# async def enrich_prospect(
#     body: EnrichRequest,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> EnrichResponse:
#     """Enrich prospect data (Phase 2 stub marks enrichmentTier=ENRICHED)."""
#     return await _service.enrich(db, body)


# @router.post("/email-validate", response_model=EmailValidateResponse)
# async def email_validate(
#     body: EmailValidateRequest,
#     _: AsyncSession = Depends(get_db),
#     __: TokenPayload = Depends(require_role(Role.REP)),
# ) -> EmailValidateResponse:
#     """Validate an email via MX lookup (dnspython if installed, else stdlib)."""
#     return await _service.email_validate(body)


# @router.get("/export", response_class=PlainTextResponse)
# async def export_prospects(
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> PlainTextResponse:
#     """CSV export of all prospects (RFC-4180, UTF-8 with BOM)."""
#     items, _ = await _service.list_prospects(db, limit=500)
#     rows = [
#         {
#             "id": p.id,
#             "firstName": p.firstName,
#             "lastName": p.lastName,
#             "email": p.email or "",
#             "title": p.title or "",
#             "company": p.company or "",
#             "domain": p.domain or "",
#             "linkedinUrl": p.linkedinUrl or "",
#             "seniority": p.seniority.value if p.seniority else "",
#             "qaScore": p.qaScore if p.qaScore is not None else "",
#             "emailValidated": p.emailValidated,
#             "enrichmentTier": p.enrichmentTier.value if p.enrichmentTier else "",
#             "intentSource": p.intentSource.value if p.intentSource else "",
#             "intentDetail": p.intentDetail or "",
#             "intentStrength": p.intentStrength if p.intentStrength is not None else "",
#             "timezone": p.timezone or "",
#             "status": p.status,
#             "icpProfileId": p.icpProfileId or "",
#             "icpFitScore": p.icpFitScore if p.icpFitScore is not None else "",
#             "urgencyTier": p.urgencyTier or "",
#             "createdAt": p.createdAt.isoformat() if p.createdAt else "",
#         }
#         for p in items
#     ]
#     csv_text = rows_to_csv(rows, _CSV_COLUMNS)
#     return PlainTextResponse(
#         csv_text,
#         media_type="text/csv; charset=utf-8",
#         headers={"Content-Disposition": "attachment; filename=\"prospects.csv\""},
#     )


# # ── Next Touches — Help Guide §Prospects: "earliest Scheduled sequence" ──────


# @router.get("/next-touches")
# async def get_next_touches(
#     prospect_ids: str | None = Query(
#         default=None,
#         description="Comma-separated prospect IDs to check. Omit for all.",
#     ),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> dict:
#     """
#     Return the earliest scheduled sequence touch for each prospect.

#     Help Guide §Prospects: "Next Touch column showing earliest Scheduled sequence."
#     This is a stub that returns empty — will be wired to the Sequence scheduler
#     when the next-touch query is implemented.
#     """
#     # TODO: Query SequenceStep joined with Prospect's active sequences
#     # to find the earliest scheduled step for each prospect.
#     return {"items": {}, "message": "Next-touch lookup not yet implemented — returns empty."}


# @router.get("/{prospect_id}", response_model=ProspectResponse)
# async def get_prospect(
#     prospect_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectResponse:
#     item = await _service.get(db, prospect_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     return ProspectResponse.model_validate(item)


# @router.put("/{prospect_id}", response_model=ProspectResponse)
# async def update_prospect(
#     prospect_id: str,
#     body: ProspectUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectResponse:
#     item = await _service.update(db, prospect_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     return ProspectResponse.model_validate(item)


# @router.delete("/{prospect_id}", response_model=None, response_class=Response, status_code=204)
# async def delete_prospect(
#     prospect_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> Response:
#     """SOFT-DELETE — anonymise PII + set deleted_at. Row is retained
#     for FK integrity + aggregate stats (GDPR Article 17(3)(e))."""
#     ok = await _service.delete(db, prospect_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # ── GDPR consent endpoints (tenant-scoped, Role.REP) ──────────────────────────
# # These complement the public /gdpr/consent/* endpoints (which accept just an
# # email + lawful_basis) by binding consent to a specific prospect_id within
# # the caller's tenant schema.


# class ConsentGrantRequest(BaseModel):
#     lawful_basis: str = Field(..., description="consent | legitimate_interest | contract | legal_obligation | vital_interest | public_task")
#     consent_text: str = Field(..., min_length=1, max_length=4000)


# class ConsentWithdrawRequest(BaseModel):
#     lawful_basis: str | None = Field(
#         default=None,
#         description="Withdraw a single lawful basis; omit to withdraw all bases for this prospect.",
#     )


# class ConsentResponse(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: int
#     prospect_id: str
#     email: str
#     lawful_basis: str
#     consent_status: str
#     consent_text: str
#     granted_at: datetime | None = None
#     withdrawn_at: datetime | None = None
#     created_at: datetime
#     updated_at: datetime


# @router.get("/{prospect_id}/consent", response_model=list[ConsentResponse])
# async def get_prospect_consent(
#     prospect_id: str,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[ConsentResponse]:
#     """List all consent records for a prospect (across all lawful bases)."""
#     verify_tenant(request, token)
#     # Ensure the prospect exists in the caller's tenant schema.
#     item = await _service.get(db, prospect_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     rows = await _gdpr.list_consents(db, prospect_id)
#     return [ConsentResponse.model_validate(r) for r in rows]


# @router.post(
#     "/{prospect_id}/consent/grant",
#     response_model=ConsentResponse,
#     status_code=status.HTTP_201_CREATED,
# )
# async def grant_prospect_consent(
#     prospect_id: str,
#     body: ConsentGrantRequest,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ConsentResponse:
#     """Record a consent grant for a prospect."""
#     verify_tenant(request, token)
#     item = await _service.get(db, prospect_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     ip = request.client.host if request.client else None
#     ua = request.headers.get("user-agent")
#     try:
#         consent = await _gdpr.record_consent(
#             db,
#             prospect_id=prospect_id,
#             email=item.email or "",
#             lawful_basis=body.lawful_basis,
#             consent_text=body.consent_text,
#             ip_address=ip,
#             user_agent=ua,
#         )
#     except ValueError as exc:
#         raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
#     return ConsentResponse.model_validate(consent)


# @router.post(
#     "/{prospect_id}/consent/withdraw",
#     response_model=list[ConsentResponse],
# )
# async def withdraw_prospect_consent(
#     prospect_id: str,
#     body: ConsentWithdrawRequest,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> list[ConsentResponse]:
#     """Withdraw consent for a prospect. Adds the prospect to the suppression list."""
#     verify_tenant(request, token)
#     item = await _service.get(db, prospect_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
#     if not item.email:
#         raise HTTPException(
#             status.HTTP_400_BAD_REQUEST,
#             "Prospect has no email on file — cannot withdraw consent.",
#         )
#     consents = await _gdpr.withdraw_consent(
#         db,
#         email=item.email,
#         lawful_basis=body.lawful_basis,
#     )
#     return [ConsentResponse.model_validate(c) for c in consents]


# __all__ = ["router"]


# # ── FR-015: prospect score override (MANAGER+) ───────────────────────────────


# @router.patch("/{prospect_id}/score-override")
# async def override_prospect_score(
#     prospect_id: str,
#     body: dict,
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> dict:
#     """
#     FR-015: MANAGER+ users may manually override a prospect's ICP-fit score.

#     Body: {"icpFitScore": 0-100, "reason": "optional note"}.
#     The override is recorded in icpScoreBreakdown so the audit trail shows
#     it was manual, by whom, and why — distinguishable from computed scores.
#     """
#     import json as _json
#     from datetime import datetime, timezone

#     from sqlalchemy import select
#     from app.models.prospect_models import Prospect

#     score = body.get("icpFitScore")
#     if not isinstance(score, int) or not (0 <= score <= 100):
#         raise HTTPException(
#             status_code=422, detail="icpFitScore must be an integer 0-100."
#         )
#     prospect = (
#         await db.execute(select(Prospect).where(Prospect.id == prospect_id))
#     ).scalar_one_or_none()
#     if prospect is None:
#         raise HTTPException(status_code=404, detail="Prospect not found")

#     previous = prospect.icpFitScore
#     prospect.icpFitScore = score
#     prospect.icpScoreBreakdown = _json.dumps(
#         {
#             "override": True,
#             "overriddenBy": token.sub,
#             "overriddenAt": datetime.now(timezone.utc).isoformat(),
#             "previousScore": previous,
#             "reason": (body.get("reason") or "")[:500],
#         }
#     )
#     await db.commit()
#     return {
#         "id": prospect.id,
#         "icpFitScore": score,
#         "previousScore": previous,
#         "overriddenBy": token.sub,
#     }

"""
prospects.py — Phase 2 /api/v1/prospects router.

Endpoints:
  GET    /prospects                  list with pagination + filter
  POST   /prospects                  create
  POST   /prospects/import           CSV import (UploadFile)
  POST   /prospects/enrich           enrich prospect
  POST   /prospects/email-validate   validate email via MX lookup
  GET    /prospects/export           CSV export (RFC-4180, UTF-8 BOM)
  GET    /prospects/{prospect_id}    fetch one
  PUT    /prospects/{prospect_id}    update
  DELETE /prospects/{prospect_id}    delete (204 — soft-delete + anonymise)
  GET    /prospects/{prospect_id}/consent          consent history
  POST   /prospects/{prospect_id}/consent/grant    record consent
  POST   /prospects/{prospect_id}/consent/withdraw withdraw consent

Role gate: Role.REP. GDPR consent endpoints require Role.REP (any
authenticated user can manage consent for prospects they can read).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.schemas.prospects import (
    CsvImportResult,
    EmailValidateRequest,
    EmailValidateResponse,
    EnrichRequest,
    EnrichResponse,
    ProspectCreate,
    ProspectListResponse,
    ProspectResponse,
    ProspectUpdate,
)
from app.services.csv_export_service import rows_to_csv
from app.features.gdpr.service import GdprService
from app.features.prospects.service import ProspectService

router = APIRouter(prefix="/prospects", tags=["Prospects"])
_service = ProspectService()
_gdpr = GdprService()

_MAX_IMPORT_BYTES = 10 * 1024 * 1024  # 10MB

_CSV_COLUMNS = [
    "id", "firstName", "lastName", "email", "title", "company", "domain",
    "linkedinUrl", "seniority", "qaScore", "emailValidated", "enrichmentTier",
    "intentSource", "intentDetail", "intentStrength", "timezone", "status",
    "icpProfileId", "icpFitScore", "urgencyTier", "createdAt",
]


@router.get("", response_model=ProspectListResponse)
async def list_prospects(
    request: Request,
    search: str | None = Query(default=None),
    prospect_status: str | None = Query(default=None, alias="status"),
    icp_profile_id: str | None = Query(default=None),
    seniority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectListResponse:
    """List prospects. Soft-deleted rows are hidden unless
    ``include_deleted=true`` AND the caller is TENANT_ADMIN+."""
    # Only TENANT_ADMIN+ may see soft-deleted (anonymised) rows.
    can_see_deleted = token.role in (Role.TENANT_ADMIN, Role.SUPER_ADMIN)
    effective_include_deleted = bool(include_deleted and can_see_deleted)
    items, total = await _service.list_prospects(
        db,
        search=search,
        status=prospect_status,
        icp_profile_id=icp_profile_id,
        seniority=seniority,
        limit=limit,
        offset=offset,
        include_deleted=effective_include_deleted,
    )
    return ProspectListResponse(
        items=[ProspectResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProspectResponse, status_code=201)
async def create_prospect(
    body: ProspectCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectResponse:
    # item = await _service.create(db, body)
    # return ProspectResponse.model_validate(item)
    item = await _service.create(db, body)
    return ProspectResponse.model_validate(item)


# Static routes declared BEFORE /{prospect_id} (Pitfall #7).
@router.post("/import", response_model=CsvImportResult)
async def import_prospects(
    file: UploadFile = File(...),
    icp_profile_id: str | None = Query(
        default=None,
        description="Optional ICP to link all imported rows to + drive ICP scoring (FIX-BE-1).",
    ),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> CsvImportResult:
    """CSV import via UploadFile — RFC-4180 with UTF-8.

    FIX-BE-1 / CRITICAL 3: an optional ``?icp_profile_id=`` query param
    links all imported rows to that ICP and triggers ICP-fit scoring
    (``icpFitScore`` / ``urgencyTier`` / ``icpScoreBreakdown``) on each
    newly-created Prospect row. Per-row ``icpProfileId`` CSV header
    takes precedence when present.
    """
    if file.content_type != "text/csv":
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only CSV files are accepted.",
        )
    content = await file.read()
    if len(content) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "File exceeds 10MB limit.",
        )
    # Strip the UTF-8 BOM (\xef\xbb\xbf) that Excel emits when saving
    # as "CSV UTF-8". Using utf-8-sig automatically removes it.
    text = content.decode("utf-8-sig", errors="replace")
    result = await _service.import_csv(db, text, icp_profile_id=icp_profile_id)
    if isinstance(result, CsvImportResult):
        return result
    return CsvImportResult(**result)


@router.post("/enrich", response_model=EnrichResponse)
async def enrich_prospect(
    body: EnrichRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> EnrichResponse:
    """Enrich prospect data (Phase 2 stub marks enrichmentTier=ENRICHED)."""
    return await _service.enrich(db, body)


@router.post("/email-validate", response_model=EmailValidateResponse)
async def email_validate(
    body: EmailValidateRequest,
    _: AsyncSession = Depends(get_db),
    __: TokenPayload = Depends(require_role(Role.REP)),
) -> EmailValidateResponse:
    """Validate an email via MX lookup (dnspython if installed, else stdlib)."""
    return await _service.email_validate(body)


@router.get("/export", response_class=PlainTextResponse)
async def export_prospects(
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> PlainTextResponse:
    """CSV export of all prospects (RFC-4180, UTF-8 with BOM)."""
    items, _ = await _service.list_prospects(db, limit=500)
    rows = [
        {
            "id": p.id,
            "firstName": p.firstName,
            "lastName": p.lastName,
            "email": p.email or "",
            "title": p.title or "",
            "company": p.company or "",
            "domain": p.domain or "",
            "linkedinUrl": p.linkedinUrl or "",
            "seniority": p.seniority.value if p.seniority else "",
            "qaScore": p.qaScore if p.qaScore is not None else "",
            "emailValidated": p.emailValidated,
            "enrichmentTier": p.enrichmentTier.value if p.enrichmentTier else "",
            "intentSource": p.intentSource.value if p.intentSource else "",
            "intentDetail": p.intentDetail or "",
            "intentStrength": p.intentStrength if p.intentStrength is not None else "",
            "timezone": p.timezone or "",
            "status": p.status,
            "icpProfileId": p.icpProfileId or "",
            "icpFitScore": p.icpFitScore if p.icpFitScore is not None else "",
            "urgencyTier": p.urgencyTier or "",
            "createdAt": p.createdAt.isoformat() if p.createdAt else "",
        }
        for p in items
    ]
    csv_text = rows_to_csv(rows, _CSV_COLUMNS)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=\"prospects.csv\""},
    )


# ── Next Touches — Help Guide §Prospects: "earliest Scheduled sequence" ──────


@router.get("/next-touches")
async def get_next_touches(
    prospect_ids: str | None = Query(
        default=None,
        description="Comma-separated prospect IDs to check. Omit for all.",
    ),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """
    Return the earliest scheduled sequence touch for each prospect.

    Help Guide §Prospects: "Next Touch column showing earliest Scheduled sequence."
    This is a stub that returns empty — will be wired to the Sequence scheduler
    when the next-touch query is implemented.
    """
    # TODO: Query SequenceStep joined with Prospect's active sequences
    # to find the earliest scheduled step for each prospect.
    return {"items": {}, "message": "Next-touch lookup not yet implemented — returns empty."}


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectResponse:
    item = await _service.get(db, prospect_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    return ProspectResponse.model_validate(item)


@router.put("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: str,
    body: ProspectUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectResponse:
    item = await _service.update(db, prospect_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    return ProspectResponse.model_validate(item)


@router.delete("/{prospect_id}", response_model=None, response_class=Response, status_code=204)
async def delete_prospect(
    prospect_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> Response:
    """SOFT-DELETE — anonymise PII + set deleted_at. Row is retained
    for FK integrity + aggregate stats (GDPR Article 17(3)(e))."""
    ok = await _service.delete(db, prospect_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── GDPR consent endpoints (tenant-scoped, Role.REP) ──────────────────────────
# These complement the public /gdpr/consent/* endpoints (which accept just an
# email + lawful_basis) by binding consent to a specific prospect_id within
# the caller's tenant schema.


class ConsentGrantRequest(BaseModel):
    lawful_basis: str = Field(..., description="consent | legitimate_interest | contract | legal_obligation | vital_interest | public_task")
    consent_text: str = Field(..., min_length=1, max_length=4000)


class ConsentWithdrawRequest(BaseModel):
    lawful_basis: str | None = Field(
        default=None,
        description="Withdraw a single lawful basis; omit to withdraw all bases for this prospect.",
    )


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prospect_id: str
    email: str
    lawful_basis: str
    consent_status: str
    consent_text: str
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


@router.get("/{prospect_id}/consent", response_model=list[ConsentResponse])
async def get_prospect_consent(
    prospect_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[ConsentResponse]:
    """List all consent records for a prospect (across all lawful bases)."""
    verify_tenant(request, token)
    # Ensure the prospect exists in the caller's tenant schema.
    item = await _service.get(db, prospect_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    rows = await _gdpr.list_consents(db, prospect_id)
    return [ConsentResponse.model_validate(r) for r in rows]


@router.post(
    "/{prospect_id}/consent/grant",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_prospect_consent(
    prospect_id: str,
    body: ConsentGrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> ConsentResponse:
    """Record a consent grant for a prospect."""
    verify_tenant(request, token)
    item = await _service.get(db, prospect_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        consent = await _gdpr.record_consent(
            db,
            prospect_id=prospect_id,
            email=item.email or "",
            lawful_basis=body.lawful_basis,
            consent_text=body.consent_text,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return ConsentResponse.model_validate(consent)


@router.post(
    "/{prospect_id}/consent/withdraw",
    response_model=list[ConsentResponse],
)
async def withdraw_prospect_consent(
    prospect_id: str,
    body: ConsentWithdrawRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> list[ConsentResponse]:
    """Withdraw consent for a prospect. Adds the prospect to the suppression list."""
    verify_tenant(request, token)
    item = await _service.get(db, prospect_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found.")
    if not item.email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Prospect has no email on file — cannot withdraw consent.",
        )
    consents = await _gdpr.withdraw_consent(
        db,
        email=item.email,
        lawful_basis=body.lawful_basis,
    )
    return [ConsentResponse.model_validate(c) for c in consents]


__all__ = ["router"]


# ── FR-015: prospect score override (MANAGER+) ───────────────────────────────


@router.patch("/{prospect_id}/score-override")
async def override_prospect_score(
    prospect_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> dict:
    """
    FR-015: MANAGER+ users may manually override a prospect's ICP-fit score.

    Body: {"icpFitScore": 0-100, "reason": "optional note"}.
    The override is recorded in icpScoreBreakdown so the audit trail shows
    it was manual, by whom, and why — distinguishable from computed scores.
    """
    import json as _json
    from datetime import datetime, timezone

    from sqlalchemy import select
    from app.models.prospect_models import Prospect

    score = body.get("icpFitScore")
    if not isinstance(score, int) or not (0 <= score <= 100):
        raise HTTPException(
            status_code=422, detail="icpFitScore must be an integer 0-100."
        )
    prospect = (
        await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    ).scalar_one_or_none()
    if prospect is None:
        raise HTTPException(status_code=404, detail="Prospect not found")

    previous = prospect.icpFitScore
    prospect.icpFitScore = score
    prospect.icpScoreBreakdown = _json.dumps(
        {
            "override": True,
            "overriddenBy": token.sub,
            "overriddenAt": datetime.now(timezone.utc).isoformat(),
            "previousScore": previous,
            "reason": (body.get("reason") or "")[:500],
        }
    )
    await db.commit()
    return {
        "id": prospect.id,
        "icpFitScore": score,
        "previousScore": previous,
        "overriddenBy": token.sub,
    }