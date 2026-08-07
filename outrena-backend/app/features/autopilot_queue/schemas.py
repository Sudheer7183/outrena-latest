"""autopilot_queue/schemas.py — Pydantic models for the autopilot_queue feature.

Extracted from router.py to avoid circular imports between router ↔ service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class QueueItemResponse(BaseModel):
    id: str
    flow_id: str
    flow_name: str
    icp_id: Optional[str] = None
    status: str  # QUEUED, RUNNING, COMPLETED, FAILED
    max_prospects: int = 50
    dry_run: bool = False
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[str] = None


class QueueListResponse(BaseModel):
    items: list[QueueItemResponse]
    total: int


class EnqueueRequest(BaseModel):
    flow_id: str
    icp_id: Optional[str] = None
    max_prospects: int = Field(default=50, ge=1, le=500)
    dry_run: bool = False


class EnqueueResponse(BaseModel):
    success: bool
    queue_id: Optional[str] = None
    error: Optional[str] = None


class QueueStatsResponse(BaseModel):
    queued: int = 0
    running: int = 0
    completed_24h: int = 0
    failed_24h: int = 0
    autonomous_mode: bool = False


class TriggerResponse(BaseModel):
    success: bool
    processed: int = 0
    error: Optional[str] = None


class AutonomousModeRequest(BaseModel):
    enabled: bool
