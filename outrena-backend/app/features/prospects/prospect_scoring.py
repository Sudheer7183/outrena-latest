"""
prospect_scoring.py — 100-pt ICP scoring + P0/P1/P2 urgency tier.

Per migration doc §10 Phase 2: "prospect_scoring service: 100-pt ICP
scoring + P0/P1/P2 urgency".

Pure-Python (no LLM call) for sub-millisecond scoring of large prospect
lists. The score combines four weighted dimensions:

  | Dimension    | Max | Source                                       |
  | icp_fit      |  40 | IcpProfile painPoints/valueProps keyword     |
  |              |     | overlap with prospect title/company/domain;  |
  |              |     | or pre-computed Prospect.icpFitScore         |
  | intent       |  25 | Prospect.intentStrength × 2.5 + intentSource |
  |              |     | weight + enrichmentTier bonus                |
  | seniority    |  15 | C_Suite=15, Director=10, IC=5                |
  | firmographic |  20 | company + domain + IcpProfile.companyType    |
  |              |     | match + sender-role seniority alignment      |
  | total        | 100 | sum, clamped to [0, 100]                     |

Urgency tier:
  P0: total >= 80 OR intentStrength >= 8
  P1: total >= 60 (and not P0)
  P2: total < 60   (P2 is also the catch-all for scores below 40)

The scorer is stateless and safe to call concurrently.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from app.models.enums import EnrichmentTier, IntentSource, SeniorityTier
from app.models.prospect_models import IcpProfile, Prospect
from app.schemas.prospects import ProspectScore

logger = structlog.get_logger(__name__)


# ── Weights (per spec) ──────────────────────────────────────────────────────

W_ICP_FIT: int = 40
W_INTENT: int = 25
W_SENIORITY: int = 15
W_FIRMOGRAPHIC: int = 20

# ── Seniority scores (within the 15-pt envelope) ────────────────────────────

_SENIORITY_SCORES: dict[SeniorityTier, int] = {
    SeniorityTier.C_Suite: 15,
    SeniorityTier.Director: 10,
    SeniorityTier.IC: 5,
}

# ── Intent-source bonuses (within the 25-pt intent envelope) ────────────────

_INTENT_SOURCE_BONUS: dict[IntentSource, int] = {
    IntentSource.FUNDING_URGENCY: 10,
    IntentSource.HIRING_BUDGET: 8,
    IntentSource.REFERRAL: 8,
    IntentSource.INBOUND: 7,
    IntentSource.LINKEDIN_DEMAND: 5,
    IntentSource.FORUM_PAIN: 5,
    IntentSource.OTHER: 2,
}

# ── Enrichment-tier bonus (within the 25-pt intent envelope) ────────────────

_ENRICHMENT_TIER_BONUS: dict[EnrichmentTier, int] = {
    EnrichmentTier.ENRICHED: 5,
    EnrichmentTier.PARTIAL: 3,
    EnrichmentTier.UNENRICHABLE: 0,
}

# ── Urgency thresholds (per spec) ───────────────────────────────────────────

_URGENCY_P0_TOTAL: int = 80
_URGENCY_P0_INTENT: int = 8
_URGENCY_P1_TOTAL: int = 60

# ── Helpers ─────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str | None) -> set[str]:
    """Lowercase token set — used for keyword overlap."""
    if not text:
        return set()
    return set(_WORD_RE.findall(text.lower()))


def _parse_json_list(raw: str | None) -> list[str]:
    """
    Parse a TEXT-column JSON array. Returns [] on parse failure.

    The IcpProfile.topObjections/painPoints/valueProps columns are TEXT
    holding JSON strings (per §5.5). We tolerate non-list payloads by
    flattening dict values to their string form.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Fallback: split on commas as a last resort
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    if isinstance(parsed, dict):
        return [str(v) for v in parsed.values()]
    return [str(parsed)]


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value


# ── Per-dimension scorers ───────────────────────────────────────────────────


def _score_icp_fit(
    prospect: Prospect, icp_profile: IcpProfile | None
) -> int:
    """
    ICP-fit score in [0, 40].

    Priority:
      1. If Prospect.icpFitScore is pre-computed (e.g. from a prior LLM
         scoring run), use it scaled to 40.
      2. Else if IcpProfile is provided, compute keyword overlap of
         painPoints + valueProps against prospect.title + company + domain.
      3. Else neutral midpoint (20).
    """
    if prospect.icpFitScore is not None:
        # Pre-computed 0-100 → scale to 0-40
        try:
            pre = int(prospect.icpFitScore)
        except (TypeError, ValueError):
            pre = 0
        return _clamp(int(round(pre / 100 * W_ICP_FIT)), 0, W_ICP_FIT)

    if icp_profile is None:
        return W_ICP_FIT // 2  # neutral midpoint = 20

    pain_points = _parse_json_list(icp_profile.painPoints)
    value_props = _parse_json_list(icp_profile.valueProps)
    objections = _parse_json_list(icp_profile.topObjections)

    # Build the prospect's text corpus for keyword matching
    prospect_text = " ".join(
        filter(None, [prospect.title, prospect.company, prospect.domain])
    )
    if not prospect_text:
        return W_ICP_FIT // 4  # 10 — minimal signal

    prospect_tokens = _tokenize(prospect_text)

    # Pain-points overlap: 5 pts each, max 25
    pain_score = 0
    for kw in pain_points:
        kw_tokens = _tokenize(kw)
        if not kw_tokens:
            continue
        if kw_tokens & prospect_tokens:
            pain_score += 5
    pain_score = min(pain_score, 25)

    # Value-props overlap: 3 pts each, max 15
    value_score = 0
    for kw in value_props:
        kw_tokens = _tokenize(kw)
        if not kw_tokens:
            continue
        if kw_tokens & prospect_tokens:
            value_score += 3
    value_score = min(value_score, 15)

    # Objections overlap: small negative weight (matched objection = harder
    # sell, but confirms ICP fit). Cap contribution at 0 — we don't subtract.
    _ = objections  # noted but not currently subtracted from icp_fit

    return _clamp(pain_score + value_score, 0, W_ICP_FIT)


def _score_intent(prospect: Prospect) -> int:
    """Intent score in [0, 25]."""
    # intentStrength (0-10) → up to 20 pts
    strength = prospect.intentStrength or 0
    try:
        strength_int = int(strength)
    except (TypeError, ValueError):
        strength_int = 0
    strength_int = _clamp(strength_int, 0, 10)
    strength_pts = _clamp(int(round(strength_int * 2.0)), 0, 20)

    # intentSource bonus: 0-10 pts
    source_bonus = _INTENT_SOURCE_BONUS.get(prospect.intentSource, 2)

    # enrichmentTier bonus: 0-5 pts
    enrichment_bonus = _ENRICHMENT_TIER_BONUS.get(prospect.enrichmentTier, 0)

    return _clamp(strength_pts + source_bonus + enrichment_bonus, 0, W_INTENT)


def _score_seniority(prospect: Prospect) -> int:
    """Seniority score in [0, 15]."""
    return _SENIORITY_SCORES.get(prospect.seniority, 5)


def _score_firmographic(
    prospect: Prospect, icp_profile: IcpProfile | None
) -> int:
    """Firmographic score in [0, 20]."""
    score = 0
    if prospect.company:
        score += 5
    if prospect.domain:
        score += 5

    if icp_profile is not None and icp_profile.companyType and prospect.company:
        # Match IcpProfile.companyType against prospect.company (token overlap)
        target_tokens = _tokenize(icp_profile.companyType)
        company_tokens = _tokenize(prospect.company)
        if target_tokens and (target_tokens & company_tokens):
            score += 5

    if icp_profile is not None and icp_profile.senderRole and prospect.title:
        # Seniority alignment: if the ICP's senderRole hints at a senior
        # audience (VP, Director, Chief, Head) and the prospect's title
        # matches that seniority, give 5 pts.
        role_tokens = _tokenize(icp_profile.senderRole)
        title_tokens = _tokenize(prospect.title)
        seniority_words = {"vp", "director", "chief", "head", "vp", "cfo",
                           "ceo", "cto", "cro", "cmo", "cio", "coo", "president"}
        if (role_tokens & seniority_words) and (title_tokens & seniority_words):
            score += 5

    return _clamp(score, 0, W_FIRMOGRAPHIC)


def _urgency_tier(total: int, intent_strength: int | None) -> str:
    """
    P0 if total >= 80 OR intentStrength >= 8.
    P1 if total >= 60.
    P2 otherwise (also covers total < 40).
    """
    if total >= _URGENCY_P0_TOTAL:
        return "P0"
    if intent_strength is not None:
        try:
            if int(intent_strength) >= _URGENCY_P0_INTENT:
                return "P0"
        except (TypeError, ValueError):
            pass
    if total >= _URGENCY_P1_TOTAL:
        return "P1"
    return "P2"


# ── Main scorer ─────────────────────────────────────────────────────────────


class ProspectScorer:
    """
    Stateless pure-Python prospect scorer.

    Usage:
        scorer = ProspectScorer()
        score = scorer.score_prospect(prospect, icp_profile)
        if score.urgency_tier == "P0":
            ...
    """

    def score_prospect(
        self,
        prospect: Prospect,
        icp_profile: IcpProfile | None,
    ) -> ProspectScore:
        """Compute the 100-pt weighted score + urgency tier."""
        icp_fit = _score_icp_fit(prospect, icp_profile)
        intent = _score_intent(prospect)
        seniority = _score_seniority(prospect)
        firmographic = _score_firmographic(prospect, icp_profile)

        total = _clamp(icp_fit + intent + seniority + firmographic, 0, 100)
        tier = _urgency_tier(total, prospect.intentStrength)

        return ProspectScore(
            total=total,
            icp_fit=icp_fit,
            intent=intent,
            seniority=seniority,
            firmographic=firmographic,
            urgency_tier=tier,  # type: ignore[arg-type]
        )

    def score_many(
        self,
        prospects: list[tuple[Prospect, IcpProfile | None]],
    ) -> list[ProspectScore]:
        """Bulk-score a list of (prospect, icp_profile) tuples."""
        return [self.score_prospect(p, icp) for p, icp in prospects]


def get_prospect_scorer() -> ProspectScorer:
    """Factory — return a fresh ProspectScorer (stateless)."""
    return ProspectScorer()


__all__: list[str] = [
    "ProspectScorer",
    "get_prospect_scorer",
    "W_ICP_FIT",
    "W_INTENT",
    "W_SENIORITY",
    "W_FIRMOGRAPHIC",
]
