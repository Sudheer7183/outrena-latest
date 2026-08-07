"""
flow_templates/service.py — FlowTemplateService with 3 built-in templates.

Built-in templates:
  1. Enterprise ABM   — strict gates, premium data sources, Fortune 500 targets
  2. Partner Recruitment — medium gates, balanced sourcing for partners
  3. PLG Volume       — loose gates, maximum volume for SMB/self-serve

Clone creates a ProspectingFlow row from a template's source/enrichment/gate
configuration. The resulting flow is immediately active and can be run or
further customised via PUT /flows/{flow_id}.
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flow_models import ProspectingFlow
from app.features.flow_templates.schemas import (
    FlowTemplateCloneResponse,
    FlowTemplateResponse,
)

logger = structlog.get_logger(__name__)

# ── Built-in template definitions ─────────────────────────────────────────────

BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "tpl-enterprise-abm",
        "name": "Enterprise ABM Flow",
        "description": (
            "High-precision account-based marketing for Fortune 500 targets. "
            "Uses premium data sources with strict quality gates."
        ),
        "source_platforms": ["linkedin", "apollo", "zoominfo"],
        "enrichment_platforms": ["clearbit", "hunter", "lusha"],
        "gate_config": {
            "requireEmail": True,
            "requireVerifiedEmail": True,
            "minCompanySize": 500,
            "llmScoreThreshold": 70,
            "excludeDomains": [],
        },
        "gate_strictness": "strict",
        "recommended_for": "Fortune 500 / enterprise where precision > volume",
    },
    {
        "id": "tpl-partner-recruitment",
        "name": "Partner Recruitment Flow",
        "description": (
            "Balanced sourcing for recruiting agencies and consultancies as "
            "channel partners. Medium gates allow more volume."
        ),
        "source_platforms": ["linkedin", "clay"],
        "enrichment_platforms": ["clearbit", "kaspr"],
        "gate_config": {
            "requireEmail": True,
            "requireVerifiedEmail": False,
            "minCompanySize": 10,
            "llmScoreThreshold": 60,
            "excludeDomains": [],
        },
        "gate_strictness": "medium",
        "recommended_for": "Recruiting agencies/consultancies as partners",
    },
    {
        "id": "tpl-plg-volume",
        "name": "PLG Volume Flow",
        "description": (
            "Maximum volume sourcing for product-led growth motions. "
            "Loose gates prioritize coverage over precision."
        ),
        "source_platforms": ["web_search", "linkedin", "apollo"],
        "enrichment_platforms": ["hunter"],
        "gate_config": {
            "requireEmail": True,
            "requireVerifiedEmail": False,
            "minCompanySize": 0,
            "llmScoreThreshold": 50,
            "excludeDomains": [],
        },
        "gate_strictness": "loose",
        "recommended_for": "SMB / self-serve / freemium where volume wins",
    },
]


class FlowTemplateService:
    """Manages built-in flow templates and clone-to-flow functionality."""

    async def list_templates(
        self, db: AsyncSession
    ) -> list[FlowTemplateResponse]:
        """Return all built-in templates."""
        return [FlowTemplateResponse(**t) for t in BUILTIN_TEMPLATES]

    async def get_template(
        self, db: AsyncSession, template_id: str
    ) -> FlowTemplateResponse | None:
        """Return a single template by ID, or None if not found."""
        for t in BUILTIN_TEMPLATES:
            if t["id"] == template_id:
                return FlowTemplateResponse(**t)
        return None

    async def clone_template(
        self, db: AsyncSession, body
    ) -> FlowTemplateCloneResponse:
        """Clone a template into a new ProspectingFlow row.

        Maps template fields to the ProspectingFlow ORM model:
          - source_platforms  → sourceSteps (list of {platform, enabled})
          - enrichment_platforms → enrichmentSteps (list of {platform, enabled})
          - gate_config → qualityGates
        """
        template = None
        for t in BUILTIN_TEMPLATES:
            if t["id"] == body.template_id:
                template = t
                break
        if template is None:
            return FlowTemplateCloneResponse(
                success=False, error="Template not found"
            )

        try:
            flow = ProspectingFlow(
                name=body.new_name or f"{template['name']} (Copy)",
                description=template["description"],
                sourceSteps=[
                    {"platform": p, "enabled": True}
                    for p in template["source_platforms"]
                ],
                enrichmentSteps=[
                    {"platform": p, "enabled": True}
                    for p in template["enrichment_platforms"]
                ],
                qualityGates=template["gate_config"],
                isActive=True,
                isDefault=False,
            )
            db.add(flow)
            await db.commit()
            # Re-fetch to get auto-generated ID (avoids DetachedInstanceError)
            flow = await db.get(ProspectingFlow, flow.id)
            return FlowTemplateCloneResponse(success=True, flow_id=str(flow.id))
        except Exception as exc:
            logger.error("flow_templates.clone_failed", error=str(exc))
            return FlowTemplateCloneResponse(success=False, error=str(exc))
