"""
email_studio.py — Phase 3 /api/v1/email-studio router.

Endpoints:
  POST   /email-studio/generate-email        LLM-generate an email + QA score
  POST   /email-studio/anti-pattern          rule-based anti-pattern detection
  POST   /email-studio/compliance-check      CAN-SPAM + GDPR compliance check
  POST   /email-studio/qa-score              LLM-based email quality audit (5-dimension)
  POST   /email-studio/subject-lines-generate AI subject-line variants
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.schemas.email_studio import (
    AntiPatternRequest,
    AntiPatternResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    GenerateEmailRequest,
    GenerateEmailResponse,
    QaScoreRequest,
    QaScoreResponse,
    SubjectLinesGenerateRequest,
    SubjectLinesGenerateResponse,
)
from app.features.email_studio.service import EmailStudioService
from app.features.usage.cap_gate import enforce_llm_cap

router = APIRouter(prefix="/email-studio", tags=["Email Studio"])
_service = EmailStudioService()


@router.post("/generate-email", response_model=GenerateEmailResponse, dependencies=[Depends(enforce_llm_cap)])
async def generate_email(
    body: GenerateEmailRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_role(Role.REP)),
) -> GenerateEmailResponse:
    return await _service.generate_email(db, body)


@router.post("/anti-pattern", response_model=AntiPatternResponse)
async def anti_pattern(
    body: AntiPatternRequest,
    _: object = Depends(require_role(Role.REP)),
) -> AntiPatternResponse:
    return await _service.anti_pattern(body.body, body.subject)


@router.post("/compliance-check", response_model=ComplianceCheckResponse)
async def compliance_check(
    body: ComplianceCheckRequest,
    _: object = Depends(require_role(Role.REP)),
) -> ComplianceCheckResponse:
    return await _service.compliance_check(
        body.body,
        body.subject,
        body.senderCompany,
        body.physicalAddress,
        body.unsubscribeUrl,
    )


@router.post("/qa-score", response_model=QaScoreResponse)
async def qa_score_email(
    body: QaScoreRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> QaScoreResponse:
    """LLM-based 5-dimension QA audit for a cold email."""
    return await _service.qa_score(db, body)


@router.post("/subject-lines-generate", response_model=SubjectLinesGenerateResponse)
async def generate_subject_lines(
    body: SubjectLinesGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> SubjectLinesGenerateResponse:
    """AI-generate subject-line variants for an email body."""
    return await _service.generate_subject_lines(db, body)
