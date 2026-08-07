"""
email_studio_service.py — generate-email + anti-pattern + compliance-check + qa-score + subject-lines.

generate-email: LLM-generates a Sequence-shaped email + QA score.
anti-pattern: rule-based detection of spammy/salesy phrases.
compliance-check: CAN-SPAM + GDPR rule checks.
qa-score: 5-dimension LLM-based email quality audit (70 pts total).
subject-lines-generate: AI-generated subject-line variants.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect_models import Prospect
from app.schemas.email_studio import (
    AntiPatternFinding,
    AntiPatternResponse,
    ComplianceCheckResponse,
    ComplianceFinding,
    GenerateEmailRequest,
    GenerateEmailResponse,
    GeneratedEmail,
    QaScoreDimension,
    QaScoreRequest,
    QaScoreResponse,
    SubjectLineVariant,
    SubjectLinesGenerateRequest,
    SubjectLinesGenerateResponse,
)
from app.services.llm_service import get_llm_service, get_default_llm_config

logger = structlog.get_logger(__name__)

# Anti-pattern rules — (regex, severity, label, suggestion)
_ANTI_PATTERNS: list[tuple[str, str, str, str]] = [
    (r"\bjust (checking|touching) in\b", "medium", "Just checking in", "Open with value, not a check-in"),
    (r"\bcircling back\b", "medium", "Circling back", "State the new info you're adding"),
    (r"\bquick question\b", "low", "Quick question", "Ask the question directly"),
    (r"\bhop on a (call|zoom|chat)\b", "medium", "Hop on a call", "Offer a specific time + agenda"),
    (r"\bsynergy\b", "high", "Synergy", "Use concrete outcome language"),
    (r"\bleverage\b", "medium", "Leverage", "Use 'use' or 'apply'"),
    (r"\bgame[- ]changer\b", "high", "Game-changer", "Quantify the impact instead"),
    (r"\brevolutionary\b", "high", "Revolutionary", "Be specific about what's new"),
    (r"\b\${1,3}\d+\s*(million|billion|m|b)\b", "low", "Vague money claim", "Cite the source + metric"),
    (r"\b!\s*!\s*!", "high", "Multiple exclamation marks", "Use at most one exclamation mark"),
    (r"\bfree\b", "low", "Free", "Specify what's free and for how long"),
]

# Compliance rules (CAN-SPAM + GDPR baseline)
_REQUIRED_CAN_SPAM = ["unsubscribe", "physical address"]


class EmailStudioService:
    # ── Shared helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _get_llm_config(db: AsyncSession, llm_config_id: str | None):
        """Resolve an LlmConfig by ID or fall back to the tenant default."""
        from app.models.config_models import LlmConfig
        if llm_config_id is not None:
            result = await db.execute(
                select(LlmConfig).where(LlmConfig.id == llm_config_id).limit(1)
            )
            return result.scalar_one_or_none()
        return await get_default_llm_config(db)

    @staticmethod
    def _parse_llm_json(raw: Any) -> dict:
        """Parse LLM output that may be a dict or a JSON string."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(text)
        return {}
    async def generate_email(
        self, db: AsyncSession, body: GenerateEmailRequest
    ) -> GenerateEmailResponse:
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == body.prospectId)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return GenerateEmailResponse(prospectId=body.prospectId, emails=[])
        llm = get_llm_service()
        prompt = (
            f"Generate a cold outreach email for prospect "
            f"{prospect.firstName} {prospect.lastName} "
            f"({prospect.title} at {prospect.company}). "
            f"Touch #{body.touchNumber}, angle: {body.angle}, "
            f"tone: {body.tone}, max length: {body.maxLength} chars. "
            "Return JSON: {subject, body, qaScore (0-100), qaDetails: {"
            "spamminess, personalization, clarity}, personalisationConfidence (0-1)}"
        )
        data = await llm.generate_json(prompt=prompt)
        email = GeneratedEmail(
            subject=str(data.get("subject", "")),
            body=str(data.get("body", "")),
            qaScore=int(data.get("qaScore", 70)),
            qaDetails=data.get("qaDetails", {}),
            personalisationConfidence=float(data.get("personalisationConfidence", 0.5)),
            flagForManualReview=int(data.get("qaScore", 70)) < 70,
        )
        return GenerateEmailResponse(
            prospectId=body.prospectId, emails=[email], selected=email
        )

    async def anti_pattern(
        self, body_text: str, subject: str | None = None
    ) -> AntiPatternResponse:
        findings: list[AntiPatternFinding] = []
        full_text = f"{subject or ''}\n{body_text}"
        for pattern, severity, label, suggestion in _ANTI_PATTERNS:
            match = re.search(pattern, full_text, flags=re.IGNORECASE)
            if match:
                findings.append(
                    AntiPatternFinding(
                        pattern=label,
                        severity=severity,
                        snippet=match.group(0),
                        suggestion=suggestion,
                    )
                )
        # Score: start at 100, deduct by severity
        score = 100 - sum(
            {"low": 5, "medium": 10, "high": 20}[f.severity] for f in findings
        )
        return AntiPatternResponse(
            findings=findings,
            score=max(0, score),
            passed=score >= 80,
        )

    async def compliance_check(
        self,
        body_text: str,
        subject: str | None,
        sender_company: str | None,
        physical_address: str | None,
        unsubscribe_url: str | None,
    ) -> ComplianceCheckResponse:
        findings: list[ComplianceFinding] = []
        # CAN-SPAM: unsubscribe link
        if unsubscribe_url and "unsubscribe" in body_text.lower():
            findings.append(ComplianceFinding(
                rule="can_spam_unsubscribe", status="pass",
                detail="Unsubscribe link present."
            ))
        else:
            findings.append(ComplianceFinding(
                rule="can_spam_unsubscribe", status="fail",
                detail="CAN-SPAM requires a clear unsubscribe mechanism."
            ))
        # CAN-SPAM: physical address
        if physical_address:
            findings.append(ComplianceFinding(
                rule="can_spam_address", status="pass",
                detail=f"Physical address present: {physical_address[:50]}"
            ))
        else:
            findings.append(ComplianceFinding(
                rule="can_spam_address", status="fail",
                detail="CAN-SPAM requires a valid physical postal address."
            ))
        # CAN-SPAM: subject must not be misleading
        if subject and sender_company and sender_company.lower() not in subject.lower():
            findings.append(ComplianceFinding(
                rule="can_spam_subject", status="warn",
                detail="Subject does not identify the sender — consider branding."
            ))
        else:
            findings.append(ComplianceFinding(
                rule="can_spam_subject", status="pass",
                detail="Subject identifies the sender."
            ))
        # GDPR: consent mention (rough heuristic)
        if "consent" in body_text.lower() or "privacy policy" in body_text.lower():
            findings.append(ComplianceFinding(
                rule="gdpr_consent", status="pass",
                detail="Privacy/consent reference found."
            ))
        else:
            findings.append(ComplianceFinding(
                rule="gdpr_consent", status="warn",
                detail="EU recipients may require explicit consent reference."
            ))
        is_compliant = all(f.status == "pass" for f in findings)
        score = sum({"pass": 25, "warn": 10, "fail": 0}[f.status] for f in findings)
        return ComplianceCheckResponse(
            findings=findings, isCompliant=is_compliant, score=score
        )

    # ── QA Score (5-dimension, 70 pts total) ─────────────────────────────────
    async def qa_score(self, db: AsyncSession, body: QaScoreRequest) -> QaScoreResponse:
        """LLM-based 5-dimension email quality audit."""
        llm = get_llm_service()
        prompt = f"""You are an expert cold email quality auditor. Score this email on 5 dimensions:

Subject: {body.subject or 'N/A'}
Body:
{body.email_body}

Scoring rubric (70 points total):
1. Signal Relevance (14 pts) — Does the email reference a specific buying signal or trigger event?
2. Message-Market Fit (15 pts) — Does the value proposition match the recipient's likely priorities?
3. Clarity (16 pts) — Is the email clear, concise, and easy to scan?
4. Proof (12 pts) — Does it include social proof, metrics, or evidence?
5. Length & Tone (13 pts) — Is it the right length (<150 words) with appropriate tone?

Return JSON:
{{
  "dimensions": [
    {{"name": "Signal Relevance", "max_points": 14, "score": 10, "feedback": "..."}},
    {{"name": "Message-Market Fit", "max_points": 15, "score": 12, "feedback": "..."}},
    {{"name": "Clarity", "max_points": 16, "score": 14, "feedback": "..."}},
    {{"name": "Proof", "max_points": 12, "score": 8, "feedback": "..."}},
    {{"name": "Length & Tone", "max_points": 13, "score": 11, "feedback": "..."}}
  ],
  "flags": ["list of quality flags like 'no_social_proof', 'too_long', 'generic_opener'"],
  "suggested_rewrite": "A rewritten version of the email that scores higher, or null if score is already good"
}}"""
        try:
            raw = await asyncio.wait_for(llm.generate_json(prompt=prompt), timeout=60)
            if isinstance(raw, str):
                raw = self._parse_llm_json(raw)

            dimensions = [QaScoreDimension(**d) for d in raw.get("dimensions", [])]
            total = sum(d.score for d in dimensions)
            return QaScoreResponse(
                success=True,
                total_score=total,
                max_score=70,
                dimensions=dimensions,
                flags=raw.get("flags", []),
                suggested_rewrite=raw.get("suggested_rewrite"),
            )
        except Exception as e:
            logger.error("QA score failed: %s", e)
            return QaScoreResponse(success=False, error=str(e))

    # ── Subject Lines AI Generation ───────────────────────────────────────────
    async def generate_subject_lines(
        self, db: AsyncSession, body: SubjectLinesGenerateRequest
    ) -> SubjectLinesGenerateResponse:
        """AI-generate subject-line variants for an email body."""
        llm = get_llm_service()
        prompt = f"""Generate {body.count} compelling cold email subject line variants for this email body:

{body.email_body}

Rules:
- Under 50 characters each
- No clickbait or ALL CAPS
- Personalization cues where appropriate
- Vary the angle: curiosity, benefit, question, social proof

Return JSON:
{{
  "variants": [
    {{"subject": "...", "predicted_open_rate": 0.45, "rationale": "..."}},
    ...
  ]
}}"""
        try:
            raw = await asyncio.wait_for(llm.generate_json(prompt=prompt), timeout=60)
            if isinstance(raw, str):
                raw = self._parse_llm_json(raw)
            variants = [SubjectLineVariant(**v) for v in raw.get("variants", [])]
            return SubjectLinesGenerateResponse(success=True, variants=variants)
        except Exception as e:
            logger.error("Subject line generation failed: %s", e)
            return SubjectLinesGenerateResponse(success=False, error=str(e))
