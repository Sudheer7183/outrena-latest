import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.models.flow_models import ProspectingFlow, FlowRun
from app.features.flow_analytics.schemas import (
    FlowAnalyticsResponse,
    KpiCards,
    FunnelData,
    SourceYield,
    GatePassRate,
    RecentRun,
)

logger = logging.getLogger(__name__)


class FlowAnalyticsService:
    """Per-flow performance analytics: KPIs, funnel, source yield, gate rates."""

    async def get_analytics(self, db: AsyncSession, flow_id: str):
        flow = await db.get(ProspectingFlow, flow_id)
        if flow is None:
            return None

        # Get all runs for this flow
        stmt = (
            select(FlowRun)
            .where(FlowRun.flowId == flow_id)
            .order_by(FlowRun.startedAt.desc())
        )
        result = await db.execute(stmt)
        runs = list(result.scalars().all())

        # Calculate KPIs
        run_count = len(runs)
        success_count = sum(1 for r in runs if r.status == "COMPLETED")
        fail_count = sum(1 for r in runs if r.status == "FAILED")
        success_rate = (success_count / run_count * 100) if run_count > 0 else 0.0

        # Duration from startedAt/completedAt for completed runs
        durations = []
        for r in runs:
            if r.status == "COMPLETED" and r.startedAt and r.completedAt:
                durations.append(
                    (r.completedAt - r.startedAt).total_seconds() * 1000
                )
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        total_imported = sum(
            len(r.importedProspectIds or []) for r in runs if r.status == "COMPLETED"
        )

        # Calculate funnel data (from stats JSON)
        funnel = self._calculate_funnel(runs)

        # Calculate source yield (from stats JSON)
        source_yield = self._calculate_source_yield(runs)

        # Calculate gate pass rates (from qualityGates JSON on flow)
        gate_pass_rates = self._calculate_gate_pass_rates(flow, runs)

        # Recent runs
        recent_runs = [
            RecentRun(
                id=str(r.id),
                status=r.status.value if r.status else "UNKNOWN",
                trigger=r.triggeredBy or "manual",
                started_at=r.startedAt.isoformat() if r.startedAt else None,
                duration_ms=int(
                    (r.completedAt - r.startedAt).total_seconds() * 1000
                )
                if r.startedAt and r.completedAt
                else None,
                imported=len(r.importedProspectIds or []),
            )
            for r in runs[:20]
        ]

        return FlowAnalyticsResponse(
            flow_id=str(flow.id),
            flow_name=flow.name,
            kpis=KpiCards(
                run_count=run_count,
                success_count=success_count,
                fail_count=fail_count,
                success_rate=round(success_rate, 1),
                avg_duration_ms=round(avg_duration, 1),
                total_imported=total_imported,
            ),
            funnel=funnel,
            source_yield=source_yield,
            gate_pass_rates=gate_pass_rates,
            recent_runs=recent_runs,
        )

    def _calculate_funnel(self, runs):
        """Aggregate funnel counters from each run's ``stats`` JSON field.

        Expected ``stats`` keys: sourcedCount, dedupedCount, enrichedCount,
        gatedCount, importedCount.
        """
        sourced = 0
        deduped = 0
        enriched = 0
        gated = 0
        imported = 0
        for r in runs:
            s = r.stats or {}
            sourced += s.get("sourcedCount", 0)
            deduped += s.get("dedupedCount", 0)
            enriched += s.get("enrichedCount", 0)
            gated += s.get("gatedCount", 0)
            imported += s.get("importedCount", 0)
        return FunnelData(
            sourced=sourced, deduped=deduped, enriched=enriched, gated=gated, imported=imported
        )

    def _calculate_source_yield(self, runs):
        """Aggregate per-platform yield from each run's ``stats.sources`` JSON."""
        platform_data: dict[str, dict] = {}
        for r in runs:
            s = r.stats or {}
            sources = s.get("sources", {})
            for platform, data in sources.items():
                if platform not in platform_data:
                    platform_data[platform] = {"runs": 0, "found": 0, "after_dedup": 0}
                platform_data[platform]["runs"] += 1
                platform_data[platform]["found"] += data.get("found", 0)
                platform_data[platform]["after_dedup"] += data.get("afterDedup", 0)

        result = []
        for platform, data in platform_data.items():
            yield_pct = (
                data["after_dedup"] / data["found"] * 100 if data["found"] > 0 else 0.0
            )
            result.append(
                SourceYield(
                    platform=platform,
                    runs=data["runs"],
                    found=data["found"],
                    after_dedup=data["after_dedup"],
                    yield_pct=round(yield_pct, 1),
                )
            )
        return result

    def _calculate_gate_pass_rates(self, flow, runs):
        """Derive gate-level pass rates from ``flow.qualityGates`` and run stats."""
        gates = flow.qualityGates or {}
        results = []
        total_enriched = sum((r.stats or {}).get("enrichedCount", 0) for r in runs)
        total_gated = sum((r.stats or {}).get("gatedCount", 0) for r in runs)
        total_rejected = total_enriched - total_gated

        for gate_name, gate_value in gates.items():
            input_count = total_enriched
            passed = total_gated
            rejected = total_rejected
            pass_rate = (passed / input_count * 100) if input_count > 0 else 0.0
            results.append(
                GatePassRate(
                    gate=gate_name,
                    input_count=input_count,
                    passed=passed,
                    rejected=rejected,
                    pass_rate=round(pass_rate, 1),
                    top_rejection_reasons=[],
                )
            )
        return results

    async def list_analytics(self, db: AsyncSession, limit: int = 20, offset: int = 0):
        stmt = (
            select(ProspectingFlow)
            .where(ProspectingFlow.isActive == True)
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        flows = list(result.scalars().all())

        count_stmt = (
            select(func.count())
            .select_from(ProspectingFlow)
            .where(ProspectingFlow.isActive == True)
        )
        total = int((await db.execute(count_stmt)).scalar() or 0)

        items = []
        for flow in flows:
            analytics = await self.get_analytics(db, str(flow.id))
            if analytics:
                items.append(analytics)

        return items, total
