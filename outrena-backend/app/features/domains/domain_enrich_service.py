"""domain_enrich_service.py — Domain enrichment (single + batch)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phase3_models import DomainEnrichment
from app.schemas.domain_enrich import (
    DomainEnrichBatchResponse,
    DomainEnrichmentResponse,
)
from app.services.llm_service import get_llm_service


class DomainEnrichService:
    async def get(
        self, db: AsyncSession, domain: str
    ) -> DomainEnrichment | None:
        result = await db.execute(
            select(DomainEnrichment).where(DomainEnrichment.domain == domain.lower())
        )
        return result.scalar_one_or_none()

    async def enrich(
        self, db: AsyncSession, domain: str, force_refresh: bool = False
    ) -> DomainEnrichment:
        """Fetch + cache enrichment for a single domain (LLM-stub in Phase 3)."""
        existing = await self.get(db, domain)
        if existing and not force_refresh:
            return existing
        llm = get_llm_service()
        data = await llm.generate_json(
            prompt=(
                f"Enrich company info for domain '{domain}'. "
                "Return JSON: companyName, industry, employeeCount, "
                "revenueRange, techStack (array), location, description."
            )
        )
        tech_stack = data.get("techStack", [])
        if isinstance(tech_stack, str):
            try:
                tech_stack = json.loads(tech_stack)
            except (json.JSONDecodeError, ValueError):
                tech_stack = [tech_stack]
        payload = {
            "companyName": data.get("companyName"),
            "industry": data.get("industry"),
            "employeeCount": data.get("employeeCount"),
            "revenueRange": data.get("revenueRange"),
            "techStack": tech_stack,
            "location": data.get("location"),
            "description": data.get("description"),
        }
        if existing:
            for key, value in payload.items():
                if key == "techStack":
                    existing.techStack = json.dumps(value)
                else:
                    setattr(existing, key, value)
            existing.lastEnrichedAt = datetime.now(timezone.utc)
            await db.commit()
            existing = await db.get(DomainEnrichment, existing.id)
            return existing
        item = DomainEnrichment(
            domain=domain.lower(),
            **{k: v for k, v in payload.items() if k != "techStack"},
            techStack=json.dumps(tech_stack),
            payload=json.dumps(data),
            lastEnrichedAt=datetime.now(timezone.utc),
        )
        db.add(item)
        await db.commit()
        item = await db.get(DomainEnrichment, item.id)
        return item

    async def enrich_batch(
        self, db: AsyncSession, domains: list[str]
    ) -> DomainEnrichBatchResponse:
        enriched: list[DomainEnrichment] = []
        failed: list[str] = []
        for domain in domains:
            try:
                item = await self.enrich(db, domain, force_refresh=False)
                enriched.append(item)
            except Exception:  # noqa: BLE001
                failed.append(domain)
        return DomainEnrichBatchResponse(enriched=enriched, failed=failed)
