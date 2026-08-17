"""
email_studio_service.py — generate-email + anti-pattern + compliance-check + qa-score + subject-lines.

generate-email: LLM-generates a Sequence-shaped email + QA score.
anti-pattern: rule-based detection of spammy/salesy phrases.
compliance-check: CAN-SPAM + GDPR rule checks.
qa-score: 5-dimension LLM-based email quality audit (70 pts total).
subject-lines-generate: AI-generated subject-line variants.

FIX: All LLM-powered methods now use call_llm(config, messages) with the
tenant's configured LlmConfig — NOT the legacy get_llm_service() ZAI stub
that returned [LLM-STUB] placeholders when no ZAI key was set.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
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
from app.services.llm_service import call_llm, get_default_llm_config, LlmGatewayError
from app.models.global_llm_config import GlobalLlmConfig

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


def _parse_llm_json(raw: Any) -> dict:
    """Parse LLM output that may be a dict or a JSON string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text_val = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(text_val)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


async def _resolve_llm_config(db: AsyncSession, llm_config_id: str | None):
    """
    Resolve an LlmConfig by explicit ID, tenant default, or platform GlobalLlmConfig.

    Resolution order:
      1. Explicit llm_config_id → tenant LlmConfig row.
      2. Tenant default via get_default_llm_config() (isDefault=True, isActive=True).
      3. Platform-wide GlobalLlmConfig (public.global_llm_config, is_default=True,
         is_active=True) — used when the tenant has no LlmConfig rows at all
         (e.g. during onboarding or when tenant_slug is not yet bound).

    FIX: Previously returned None when the tenant had no LlmConfig rows, causing
    the "no_llm_config" error.  Now falls through to the platform-level config so
    the configured LLM model (Groq, OpenAI, etc.) is always resolved.
    """
    from app.models.config_models import LlmConfig

    if llm_config_id is not None:
        result = await db.execute(
            select(LlmConfig).where(LlmConfig.id == llm_config_id).limit(1)
        )
        cfg = result.scalar_one_or_none()
        if cfg is not None:
            return cfg

    # Fall back to tenant default (queries tenant schema LlmConfig table)
    tenant_cfg = await get_default_llm_config(db)
    if tenant_cfg is not None:
        return tenant_cfg

    # Final fallback: platform-wide GlobalLlmConfig (public schema).
    # This covers the case where the tenant has no LlmConfig rows but the
    # platform admin has configured a global default (e.g. Groq key set via
    # the SUPER_ADMIN LLM Models UI).
    logger.debug("email_studio.resolve_llm_config.falling_back_to_global")
    result = await db.execute(
        select(GlobalLlmConfig)
        .where(GlobalLlmConfig.is_default.is_(True))
        .where(GlobalLlmConfig.is_active.is_(True))
        .limit(1)
    )
    global_cfg = result.scalar_one_or_none()
    if global_cfg is not None:
        return _adapt_global_llm_config(global_cfg)

    # Try any active global config as last resort
    result = await db.execute(
        select(GlobalLlmConfig)
        .where(GlobalLlmConfig.is_active.is_(True))
        .order_by(GlobalLlmConfig.created_at.asc())
        .limit(1)
    )
    global_cfg = result.scalar_one_or_none()
    if global_cfg is not None:
        return _adapt_global_llm_config(global_cfg)

    return None


def _adapt_global_llm_config(global_cfg: GlobalLlmConfig):
    """
    Wrap a GlobalLlmConfig row in a SimpleNamespace that looks like a
    LlmConfig row so call_llm() / cast_llm_config() can consume it unchanged.

    Field mapping:
      GlobalLlmConfig.provider       → LlmConfig.provider
      GlobalLlmConfig.model_name     → LlmConfig.modelId
      GlobalLlmConfig.base_url       → LlmConfig.baseUrl
      GlobalLlmConfig.api_key_encrypted → resolved at call time via
                                          IntegrationCredentialsService
                                          (global_llm_config_id set)
    """
    return SimpleNamespace(
        id=str(global_cfg.id),
        name=global_cfg.display_name,
        provider=global_cfg.provider,
        modelId=global_cfg.model_name,
        # Leave apiKey empty so call_llm falls through to
        # _resolve_dual_path_api_key → IntegrationCredentialsService which
        # will Fernet-decrypt api_key_encrypted from this GlobalLlmConfig row.
        apiKey=None,
        baseUrl=global_cfg.base_url,
        isDefault=global_cfg.is_default,
        isActive=global_cfg.is_active,
        settings={},
        modelTier="standard",
        global_llm_config_id=global_cfg.id,
    )


async def _llm_generate_json(
    config: Any,
    messages: list[dict[str, str]],
    *,
    timeout_seconds: float = 60.0,
) -> dict:
    """
    Call the real LLM via call_llm() and parse the response as JSON.

    Returns {} on any failure — callers apply their own defaults.
    """
    try:
        response = await asyncio.wait_for(
            call_llm(config, messages),
            timeout=timeout_seconds,
        )
        raw = response.content if hasattr(response, "content") else str(response)
        return _parse_llm_json(raw)
    except asyncio.TimeoutError:
        logger.warning("email_studio.llm_timeout")
        return {}
    except LlmGatewayError as exc:
        logger.warning("email_studio.llm_gateway_error", error=str(exc))
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("email_studio.llm_unexpected_error", error=str(exc))
        return {}


class EmailStudioService:
    # ── generate_email ───────────────────────────────────────────────────────

    async def generate_email(
        self, db: AsyncSession, body: GenerateEmailRequest
    ) -> GenerateEmailResponse:
        """
        Generate a cold outreach email using the tenant's configured LLM.

        FIX: Previously called get_llm_service() (legacy ZAI stub → [LLM-STUB]).
             Now resolves the tenant LlmConfig from DB and dispatches via call_llm().
        """
        # ── 1. Fetch prospect ────────────────────────────────────────────────
        prospect_result = await db.execute(
            select(Prospect).where(Prospect.id == body.prospectId)
        )
        prospect = prospect_result.scalar_one_or_none()
        if prospect is None:
            return GenerateEmailResponse(prospectId=body.prospectId, emails=[])

        # ── 2. Resolve LLM config ────────────────────────────────────────────
        config = await _resolve_llm_config(db, None)
        if config is None:
            logger.error(
                "email_studio.generate_email.no_llm_config",
                prospectId=body.prospectId,
            )
            return GenerateEmailResponse(
                prospectId=body.prospectId,
                emails=[],
            )

        # ── 3. Build prompt ──────────────────────────────────────────────────
        system_msg = (
            "You are an expert cold-email copywriter. "
            "Respond ONLY with a valid JSON object — no markdown fences, no preamble."
        )
        user_msg = (
            f"Generate a cold outreach email for prospect "
            f"{prospect.firstName} {prospect.lastName} "
            f"({prospect.title} at {prospect.company}). "
            f"Touch #{body.touchNumber}, angle: {body.angle}, "
            f"framework: {body.framework or 'Trigger-Based'}, "
            f"tone: {body.tone}, max length: {body.maxLength} words. "
            "Return JSON: "
            '{"subject": "...", "body": "...", "qaScore": 75, '
            '"qaDetails": {"spamminess": 10, "personalization": 60, "clarity": 80}, '
            '"personalisationConfidence": 0.65}'
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        # ── 4. Call LLM ──────────────────────────────────────────────────────
        data = await _llm_generate_json(config, messages, timeout_seconds=60.0)

        # ── 5. Build response ────────────────────────────────────────────────
        subject = str(data.get("subject", "")).strip()
        body_text = str(data.get("body", "")).strip()
        qa_score = int(data.get("qaScore", 70))
        qa_details = data.get("qaDetails", {})
        personalisation_confidence = float(data.get("personalisationConfidence", 0.5))

        # If LLM returned empty content surface a clear indicator rather than
        # silently returning blank fields.
        if not subject and not body_text:
            logger.warning(
                "email_studio.generate_email.empty_llm_response",
                prospectId=body.prospectId,
                model=getattr(config, "modelId", "unknown"),
            )

        email = GeneratedEmail(
            subject=subject,
            body=body_text,
            qaScore=qa_score,
            qaDetails=qa_details if isinstance(qa_details, dict) else {},
            personalisationConfidence=personalisation_confidence,
            flagForManualReview=qa_score < 70,
        )
        return GenerateEmailResponse(
            prospectId=body.prospectId, emails=[email], selected=email
        )

    # ── anti_pattern ─────────────────────────────────────────────────────────

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

    # ── compliance_check ─────────────────────────────────────────────────────

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

    # ── qa_score ─────────────────────────────────────────────────────────────

    async def qa_score(self, db: AsyncSession, body: QaScoreRequest) -> QaScoreResponse:
        """
        LLM-based 5-dimension email quality audit.

        FIX: Previously called get_llm_service() (legacy ZAI stub).
             Now resolves tenant LlmConfig and calls call_llm().
        """
        config = await _resolve_llm_config(db, body.llm_config_id)
        if config is None:
            return QaScoreResponse(success=False, error="No LLM model configured for this tenant.")

        system_msg = (
            "You are an expert cold email quality auditor. "
            "Respond ONLY with a valid JSON object — no markdown fences, no preamble."
        )
        user_msg = f"""Score this email on 5 dimensions:

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

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        raw = await _llm_generate_json(config, messages, timeout_seconds=60.0)
        if not raw:
            return QaScoreResponse(success=False, error="LLM returned an empty or unparseable response.")

        try:
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
        except Exception as exc:
            logger.error("qa_score.parse_failed", error=str(exc))
            return QaScoreResponse(success=False, error=str(exc))

    # ── generate_subject_lines ────────────────────────────────────────────────

    async def generate_subject_lines(
        self, db: AsyncSession, body: SubjectLinesGenerateRequest
    ) -> SubjectLinesGenerateResponse:
        """
        AI-generate subject-line variants for an email body.

        FIX: Previously called get_llm_service() (legacy ZAI stub).
             Now resolves tenant LlmConfig and calls call_llm().
        """
        config = await _resolve_llm_config(db, body.llm_config_id)
        if config is None:
            return SubjectLinesGenerateResponse(
                success=False, error="No LLM model configured for this tenant."
            )

        system_msg = (
            "You are an expert cold email subject-line writer. "
            "Respond ONLY with a valid JSON object — no markdown fences, no preamble."
        )
        user_msg = f"""Generate {body.count} compelling cold email subject line variants for this email body:

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

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        raw = await _llm_generate_json(config, messages, timeout_seconds=60.0)
        if not raw:
            return SubjectLinesGenerateResponse(
                success=False, error="LLM returned an empty or unparseable response."
            )

        try:
            variants = [SubjectLineVariant(**v) for v in raw.get("variants", [])]
            return SubjectLinesGenerateResponse(success=True, variants=variants)
        except Exception as exc:
            logger.error("subject_lines.parse_failed", error=str(exc))
            return SubjectLinesGenerateResponse(success=False, error=str(exc))