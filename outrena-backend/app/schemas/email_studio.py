"""email_studio.py — Generate-email + anti-pattern + compliance + QA score + subject-line contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateEmailRequest(BaseModel):
    """Body for POST /email-studio/generate-email."""
    prospectId: str
    campaignId: str | None = None
    touchNumber: int = 1
    angle: str = "FirstTouch"
    framework: str | None = None
    tone: str = "professional"
    maxLength: int = 250


class GeneratedEmail(BaseModel):
    subject: str
    body: str
    qaScore: int  # 0-100
    qaDetails: dict
    personalisationConfidence: float
    flagForManualReview: bool


class GenerateEmailResponse(BaseModel):
    prospectId: str
    emails: list[GeneratedEmail]
    selected: GeneratedEmail | None = None


class AntiPatternRequest(BaseModel):
    """Body for POST /email-studio/anti-pattern — detect spammy patterns."""
    body: str
    subject: str | None = None


class AntiPatternFinding(BaseModel):
    pattern: str
    severity: str  # low | medium | high
    snippet: str
    suggestion: str


class AntiPatternResponse(BaseModel):
    findings: list[AntiPatternFinding]
    score: int  # 0-100, higher is cleaner
    passed: bool


class ComplianceCheckRequest(BaseModel):
    """Body for POST /email-studio/compliance-check — CAN-SPAM / GDPR."""
    body: str
    subject: str | None = None
    senderCompany: str | None = None
    physicalAddress: str | None = None
    unsubscribeUrl: str | None = None


class ComplianceFinding(BaseModel):
    rule: str  # can_spam_unsubscribe | can_spam_address | gdpr_consent | ...
    status: str  # pass | fail | warn
    detail: str


class ComplianceCheckResponse(BaseModel):
    findings: list[ComplianceFinding]
    isCompliant: bool
    score: int


# ── QA Score ────────────────────────────────────────────────────────────────

class QaScoreRequest(BaseModel):
    """Body for POST /email-studio/qa-score — LLM-based email quality audit."""
    email_body: str = Field(..., description="Email body to score")
    subject: str | None = None
    llm_config_id: str | None = None


class QaScoreDimension(BaseModel):
    name: str
    max_points: int
    score: int
    feedback: str


class QaScoreResponse(BaseModel):
    success: bool
    total_score: int = 0
    max_score: int = 70
    dimensions: list[QaScoreDimension] = []
    flags: list[str] = []
    suggested_rewrite: str | None = None
    error: str | None = None


# ── Subject Lines ────────────────────────────────────────────────────────────

class SubjectLinesGenerateRequest(BaseModel):
    """Body for POST /email-studio/subject-lines-generate — AI subject lines."""
    email_body: str = Field(..., description="Email body to generate subject lines for")
    count: int = Field(default=5, ge=1, le=10)
    llm_config_id: str | None = None


class SubjectLineVariant(BaseModel):
    subject: str
    predicted_open_rate: float | None = None
    rationale: str | None = None


class SubjectLinesGenerateResponse(BaseModel):
    success: bool
    variants: list[SubjectLineVariant] = []
    error: str | None = None


__all__ = [
    "GenerateEmailRequest",
    "GeneratedEmail",
    "GenerateEmailResponse",
    "AntiPatternRequest",
    "AntiPatternFinding",
    "AntiPatternResponse",
    "ComplianceCheckRequest",
    "ComplianceFinding",
    "ComplianceCheckResponse",
    "QaScoreRequest",
    "QaScoreDimension",
    "QaScoreResponse",
    "SubjectLinesGenerateRequest",
    "SubjectLineVariant",
    "SubjectLinesGenerateResponse",
]
