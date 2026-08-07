"""flow_analytics/schemas.py — Pydantic models for the flow_analytics feature.

Extracted from router.py to avoid circular imports between router ↔ service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class FunnelData(BaseModel):
    sourced: int = 0
    deduped: int = 0
    enriched: int = 0
    gated: int = 0
    imported: int = 0


class KpiCards(BaseModel):
    run_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_imported: int = 0


class SourceYield(BaseModel):
    platform: str
    runs: int = 0
    found: int = 0
    after_dedup: int = 0
    yield_pct: float = 0.0


class GatePassRate(BaseModel):
    gate: str
    input_count: int = 0
    passed: int = 0
    rejected: int = 0
    pass_rate: float = 0.0
    top_rejection_reasons: list[str] = []


class RecentRun(BaseModel):
    id: str
    status: str
    trigger: str
    started_at: Optional[str] = None
    duration_ms: Optional[int] = None
    imported: int = 0


class FlowAnalyticsResponse(BaseModel):
    flow_id: str
    flow_name: str
    kpis: KpiCards
    funnel: FunnelData
    source_yield: list[SourceYield] = []
    gate_pass_rates: list[GatePassRate] = []
    recent_runs: list[RecentRun] = []


class FlowAnalyticsListResponse(BaseModel):
    items: list[FlowAnalyticsResponse]
    total: int
