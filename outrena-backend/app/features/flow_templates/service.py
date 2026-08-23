"""
flow_templates/service.py — FlowTemplateService.

Built-in templates are defined in BUILTIN_TEMPLATES (read-only, in-memory).
Custom templates are stored as ProspectingFlow rows with isTemplate=True.

clone_template() creates a regular ProspectingFlow (isTemplate=False) from
either a built-in template definition or a custom template row.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flow_models import ProspectingFlow
from app.features.flow_templates.schemas import (
    FlowTemplateCloneResponse,
    FlowTemplateCreateRequest,
    FlowTemplateResponse,
    FlowTemplateUpdateRequest,
)

logger = structlog.get_logger(__name__)

# ── Built-in template definitions (read-only — cannot be edited/deleted) ─────

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
            "requireCompanySize": True,
            "minCompanySize": 500,
            "llmScoreThreshold": 0.7,
            "excludeDomains": ["gmail.com", "yahoo.com", "hotmail.com"],
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
            "requireCompanySize": True,
            "minCompanySize": 10,
            "llmScoreThreshold": 0.55,
            "excludeDomains": ["gmail.com", "yahoo.com"],
        },
        "gate_strictness": "medium",
        "recommended_for": "Recruiting agencies/consultancies as channel partners",
    },
    {
        "id": "tpl-plg-volume",
        "name": "PLG Volume Flow",
        "description": (
            "Maximum volume sourcing for product-led growth motions. "
            "Loose gates prioritize coverage over precision."
        ),
        "source_platforms": ["ai_web_search", "linkedin", "apollo"],
        "enrichment_platforms": ["hunter"],
        "gate_config": {
            "requireEmail": True,
            "requireVerifiedEmail": False,
            "requireCompanySize": False,
            "minCompanySize": 0,
            "llmScoreThreshold": 0.4,
            "excludeDomains": ["gmail.com"],
        },
        "gate_strictness": "loose",
        "recommended_for": "SMB / self-serve / freemium where volume wins",
    },
]

_BUILTIN_IDS = {t["id"] for t in BUILTIN_TEMPLATES}


def _builtin_to_response(t: dict) -> FlowTemplateResponse:
    return FlowTemplateResponse(**t)


def _flow_to_response(flow: ProspectingFlow) -> FlowTemplateResponse:
    """Convert a ProspectingFlow (isTemplate=True) row to FlowTemplateResponse."""
    # Source and enrichment steps are stored as lists of {platform, enabled} dicts.
    # Extract just the platform keys for the template response.
    def extract_platforms(steps: object) -> list[str]:
        import json
        if not steps:
            return []
        try:
            arr = steps if isinstance(steps, list) else json.loads(str(steps))
            return [
                str(s.get("platform") or s.get("provider") or "")
                for s in arr
                if isinstance(s, dict) and (s.get("platform") or s.get("provider"))
            ]
        except Exception:
            return []

    def extract_gates(gates: object) -> dict:
        import json
        defaults = {
            "requireEmail": True,
            "requireVerifiedEmail": False,
            "requireCompanySize": False,
            "minCompanySize": 0,
            "llmScoreThreshold": 0.0,
            "excludeDomains": [],
        }
        if not gates:
            return defaults
        try:
            parsed = gates if isinstance(gates, dict) else json.loads(str(gates))
            return {**defaults, **parsed}
        except Exception:
            return defaults

    # Read templateTag-derived strictness from qualityGates if stored there,
    # else infer from gate config values.
    gates = extract_gates(flow.qualityGates)
    threshold = float(gates.get("llmScoreThreshold", 0))
    if threshold >= 0.65:
        strictness = "strict"
    elif threshold >= 0.50:
        strictness = "medium"
    else:
        strictness = "loose"

    # Allow override stored in the flow name prefix
    name_lower = (flow.name or "").lower()
    if "strict" in name_lower:
        strictness = "strict"
    elif "loose" in name_lower or "plg" in name_lower or "volume" in name_lower:
        strictness = "loose"

    return FlowTemplateResponse(
        id=str(flow.id),
        name=flow.name,
        description=flow.description or "",
        source_platforms=extract_platforms(flow.sourceSteps),
        enrichment_platforms=extract_platforms(flow.enrichmentSteps),
        gate_config=gates,
        gate_strictness=strictness,
        recommended_for="",
    )


class FlowTemplateService:
    """Manages built-in and custom flow templates."""

    async def list_templates(self, db: AsyncSession) -> list[FlowTemplateResponse]:
        """Return built-in templates + custom templates (isTemplate=True flows)."""
        builtin = [_builtin_to_response(t) for t in BUILTIN_TEMPLATES]

        # Custom templates stored as ProspectingFlow rows with isTemplate=True
        result = await db.execute(
            select(ProspectingFlow)
            .where(ProspectingFlow.isTemplate.is_(True))
            .order_by(ProspectingFlow.createdAt.asc())
        )
        custom = [_flow_to_response(f) for f in result.scalars().all()]

        return builtin + custom

    async def get_template(
        self, db: AsyncSession, template_id: str
    ) -> FlowTemplateResponse | None:
        """Return a single template by ID (built-in or custom)."""
        for t in BUILTIN_TEMPLATES:
            if t["id"] == template_id:
                return _builtin_to_response(t)

        result = await db.execute(
            select(ProspectingFlow)
            .where(ProspectingFlow.id == template_id)
            .where(ProspectingFlow.isTemplate.is_(True))
        )
        flow = result.scalar_one_or_none()
        return _flow_to_response(flow) if flow else None

    async def create_template(
        self, db: AsyncSession, body: FlowTemplateCreateRequest
    ) -> FlowTemplateResponse:
        """Create a new custom template (stored as ProspectingFlow with isTemplate=True)."""
        source_steps = [{"platform": p, "enabled": True, "order": i}
                        for i, p in enumerate(body.source_platforms)]
        enrich_steps = [{"platform": p, "enabled": True, "order": i}
                        for i, p in enumerate(body.enrichment_platforms)]

        flow = ProspectingFlow(
            name=body.name.strip(),
            description=body.description.strip(),
            sourceSteps=source_steps,
            enrichmentSteps=enrich_steps,
            qualityGates=body.gate_config,
            isTemplate=True,
            isActive=True,
            isDefault=False,
        )
        db.add(flow)
        await db.flush()
        flow_id = flow.id
        await db.commit()

        # Re-fetch to avoid DetachedInstanceError
        result = await db.execute(select(ProspectingFlow).where(ProspectingFlow.id == flow_id))
        flow = result.scalar_one()
        resp = _flow_to_response(flow)
        # Patch recommended_for and gate_strictness from the request (not derivable from steps)
        resp.recommended_for = body.recommended_for
        resp.gate_strictness = body.gate_strictness
        return resp

    async def update_template(
        self, db: AsyncSession, template_id: str, body: FlowTemplateUpdateRequest
    ) -> FlowTemplateResponse | None:
        """Update a custom template. Built-in templates cannot be updated."""
        if template_id in _BUILTIN_IDS:
            return None  # Router returns 400

        result = await db.execute(
            select(ProspectingFlow)
            .where(ProspectingFlow.id == template_id)
            .where(ProspectingFlow.isTemplate.is_(True))
        )
        flow = result.scalar_one_or_none()
        if flow is None:
            return None

        if body.name is not None:
            flow.name = body.name.strip()
        if body.description is not None:
            flow.description = body.description.strip()
        if body.source_platforms is not None:
            flow.sourceSteps = [
                {"platform": p, "enabled": True, "order": i}
                for i, p in enumerate(body.source_platforms)
            ]
        if body.enrichment_platforms is not None:
            flow.enrichmentSteps = [
                {"platform": p, "enabled": True, "order": i}
                for i, p in enumerate(body.enrichment_platforms)
            ]
        if body.gate_config is not None:
            flow.qualityGates = body.gate_config

        await db.commit()

        result = await db.execute(select(ProspectingFlow).where(ProspectingFlow.id == template_id))
        flow = result.scalar_one()
        resp = _flow_to_response(flow)
        if body.recommended_for is not None:
            resp.recommended_for = body.recommended_for
        if body.gate_strictness is not None:
            resp.gate_strictness = body.gate_strictness
        return resp

    async def delete_template(self, db: AsyncSession, template_id: str) -> bool:
        """Delete a custom template. Returns False if not found or is built-in."""
        if template_id in _BUILTIN_IDS:
            return False

        result = await db.execute(
            select(ProspectingFlow)
            .where(ProspectingFlow.id == template_id)
            .where(ProspectingFlow.isTemplate.is_(True))
        )
        flow = result.scalar_one_or_none()
        if flow is None:
            return False

        await db.delete(flow)
        await db.commit()
        return True

    async def clone_template(
        self, db: AsyncSession, body: FlowTemplateCloneRequest
    ) -> FlowTemplateCloneResponse:
        """Clone a template (built-in or custom) into a new regular ProspectingFlow."""
        # Look up built-in first
        builtin = next((t for t in BUILTIN_TEMPLATES if t["id"] == body.template_id), None)

        if builtin:
            source_steps = [{"platform": p, "enabled": True, "order": i}
                            for i, p in enumerate(builtin["source_platforms"])]
            enrich_steps = [{"platform": p, "enabled": True, "order": i}
                            for i, p in enumerate(builtin["enrichment_platforms"])]
            gate_config = builtin["gate_config"]
            template_name = builtin["name"]
        else:
            # Custom template
            result = await db.execute(
                select(ProspectingFlow)
                .where(ProspectingFlow.id == body.template_id)
                .where(ProspectingFlow.isTemplate.is_(True))
            )
            template_flow = result.scalar_one_or_none()
            if template_flow is None:
                return FlowTemplateCloneResponse(success=False, error="Template not found")

            source_steps = template_flow.sourceSteps if template_flow.sourceSteps else []
            enrich_steps = template_flow.enrichmentSteps if template_flow.enrichmentSteps else []
            gate_config = template_flow.qualityGates if template_flow.qualityGates else {}
            template_name = template_flow.name

        new_name = (body.new_name or "").strip() or f"{template_name} (Copy)"

        try:
            flow = ProspectingFlow(
                name=new_name,
                description=builtin["description"] if builtin else "",
                sourceSteps=source_steps,
                enrichmentSteps=enrich_steps,
                qualityGates=gate_config,
                isTemplate=False,
                isActive=True,
                isDefault=False,
            )
            db.add(flow)
            await db.flush()
            flow_id = flow.id
            await db.commit()

            logger.info("flow_templates.cloned", template_id=body.template_id,
                        new_flow_id=flow_id, name=new_name)
            return FlowTemplateCloneResponse(
                success=True, flow_id=str(flow_id), name=new_name
            )
        except Exception as exc:
            logger.error("flow_templates.clone_failed", error=str(exc))
            return FlowTemplateCloneResponse(success=False, error=str(exc))
