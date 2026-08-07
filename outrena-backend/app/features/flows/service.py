"""
flow_run_service.py — Flow execution engine: ProspectingFlow + FlowRun +
FlowRunStep + FlowAbTest + FlowWebhook CRUD.

Created by FIX-BE-1 / CRITICAL 1 (audit §D1): the underlying ORM models
in ``app/models/flow_models.py`` previously had NO service/route surface.

This service backs:
  - ``app/api/v1/flows.py`` (CRUD + list runs + run detail with steps)
  - ``app/services/autopilot_service.py`` (creates a FlowRun + FlowRunSteps
    per pipeline execution — see ``start_run`` / ``complete_run`` /
    ``fail_run`` / ``create_step`` / ``update_step`` below)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AutopilotQueueStatus,
    FlowAbTestStatus,
    FlowRunStatus,
    FlowRunStepKind,
    FlowRunStepStatus,
    WebhookDeliveryStatus,
    WebhookTriggerEvent,
)
from app.models.flow_models import (
    AutopilotQueue,
    FlowAbTest,
    FlowRun,
    FlowRunStep,
    FlowWebhook,
    FlowWebhookDelivery,
    ProspectingFlow,
)
from app.schemas.flow_run import (
    FlowAbTestCreate,
    FlowAbTestUpdate,
    FlowRunCreateRequest,
    FlowWebhookCreate,
    FlowWebhookUpdate,
    ProspectingFlowCreate,
    ProspectingFlowUpdate,
)

logger = structlog.get_logger(__name__)


_DEFAULT_FLOW_NAME = "Autopilot Default Flow"
_DEFAULT_FLOW_DESCRIPTION = (
    "Auto-created default ProspectingFlow for autopilot pipeline runs. "
    "Created by FlowRunService.get_or_create_default_flow on first autopilot "
    "execution (FIX-BE-1)."
)


class FlowRunService:
    """CRUD + lifecycle helpers for ProspectingFlow / FlowRun / FlowRunStep
    + FlowAbTest / FlowWebhook.

    All methods take an ``AsyncSession`` locked to the tenant's schema via
    ``Depends(get_db)`` — the search_path is set by the dependency, so we
    don't need to set it here.
    """

    # ── ProspectingFlow CRUD ──────────────────────────────────────────────

    async def list_flows(
        self,
        db: AsyncSession,
        *,
        is_active: bool | None = None,
        is_template: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ProspectingFlow], int]:
        stmt = select(ProspectingFlow)
        if is_active is not None:
            stmt = stmt.where(ProspectingFlow.isActive.is_(is_active))
        if is_template is not None:
            stmt = stmt.where(ProspectingFlow.isTemplate.is_(is_template))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(ProspectingFlow.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_flow(
        self, db: AsyncSession, flow_id: str
    ) -> ProspectingFlow | None:
        return (
            await db.execute(
                select(ProspectingFlow).where(ProspectingFlow.id == flow_id)
            )
        ).scalar_one_or_none()

    async def create_flow(
        self, db: AsyncSession, body: ProspectingFlowCreate
    ) -> ProspectingFlow:
        # Demote any prior default if this flow is being marked default.
        if body.isDefault:
            await self._demote_default_flows(db)
        item = ProspectingFlow(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(ProspectingFlow, item.id)
        return item

    async def update_flow(
        self,
        db: AsyncSession,
        flow_id: str,
        body: ProspectingFlowUpdate,
    ) -> ProspectingFlow | None:
        item = await self.get_flow(db, flow_id)
        if item is None:
            return None
        updates = body.model_dump(exclude_unset=True)
        if updates.get("isDefault"):
            await self._demote_default_flows(db, exclude_id=flow_id)
        for key, value in updates.items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(ProspectingFlow, item.id)
        return item

    async def delete_flow(self, db: AsyncSession, flow_id: str) -> bool:
        item = await self.get_flow(db, flow_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def get_or_create_default_flow(
        self, db: AsyncSession
    ) -> ProspectingFlow:
        """Find the tenant's default ProspectingFlow or create one.

        Used by ``autopilot_service.orchestrate_pipeline`` to attach each
        autopilot run to a FlowRun row. The default flow is a no-op
        definition (no source/enrichment steps configured) — the actual
        pipeline work runs inline in the autopilot orchestrator for
        performance, with FlowRunStep rows persisted as an audit trail
        (per FIX-BE-1 / CRITICAL 1 — documented in autopilot_service.py).
        """
        existing = (
            await db.execute(
                select(ProspectingFlow)
                .where(ProspectingFlow.isDefault.is_(True))
                .where(ProspectingFlow.isActive.is_(True))
                .order_by(ProspectingFlow.createdAt.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        # Fallback: any active flow.
        any_active = (
            await db.execute(
                select(ProspectingFlow)
                .where(ProspectingFlow.isActive.is_(True))
                .order_by(ProspectingFlow.createdAt.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if any_active is not None:
            return any_active
        # Create a default flow.
        await self._demote_default_flows(db)
        flow = ProspectingFlow(
            name=_DEFAULT_FLOW_NAME,
            description=_DEFAULT_FLOW_DESCRIPTION,
            isDefault=True,
            isActive=True,
            isTemplate=False,
            sourceSteps="[]",
            enrichmentSteps="[]",
            qualityGates="{}",
        )
        db.add(flow)
        await db.commit()
        flow = await db.get(ProspectingFlow, flow.id)
        return flow

    # ── FlowRun lifecycle (used by autopilot + router) ────────────────────

    async def list_runs(
        self,
        db: AsyncSession,
        *,
        flow_id: str | None = None,
        icp_profile_id: str | None = None,
        status_: FlowRunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FlowRun], int]:
        stmt = select(FlowRun)
        if flow_id:
            stmt = stmt.where(FlowRun.flowId == flow_id)
        if icp_profile_id:
            stmt = stmt.where(FlowRun.icpProfileId == icp_profile_id)
        if status_ is not None:
            stmt = stmt.where(FlowRun.status == status_)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(FlowRun.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_run(
        self, db: AsyncSession, run_id: str
    ) -> FlowRun | None:
        return (
            await db.execute(select(FlowRun).where(FlowRun.id == run_id))
        ).scalar_one_or_none()

    async def get_run_with_steps(
        self, db: AsyncSession, run_id: str
    ) -> FlowRun | None:
        """Fetch a FlowRun + eagerly load its FlowRunStep rows."""
        run = await self.get_run(db, run_id)
        if run is None:
            return None
        steps = (
            await db.execute(
                select(FlowRunStep)
                .where(FlowRunStep.runId == run_id)
                .order_by(FlowRunStep.order.asc())
            )
        ).scalars().all()
        # Attach steps to the run object so the router can serialize them.
        run.steps = list(steps)  # type: ignore[attr-defined]
        return run

    async def start_run(
        self,
        db: AsyncSession,
        *,
        flow: ProspectingFlow,
        icp_profile_id: str,
        triggered_by: str = "autopilot",
        triggered_by_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> FlowRun:
        """Create a FlowRun in RUNNING state.

        Used by ``autopilot_service.orchestrate_pipeline`` after the ICP
        discovery step succeeds (the FlowRun requires an IcpProfile row).
        """
        run = FlowRun(
            flowId=flow.id,
            icpProfileId=icp_profile_id,
            status=FlowRunStatus.RUNNING,
            triggeredBy=triggered_by,
            triggeredById=triggered_by_id,
            config=json.dumps(config or {}),
            stats="{}",
            importedProspectIds="[]",
            startedAt=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.flush()  # populate run.id
        return run

    async def complete_run(
        self,
        db: AsyncSession,
        run: FlowRun,
        *,
        stats: dict[str, Any] | None = None,
        imported_prospect_ids: list[str] | None = None,
    ) -> None:
        """Mark a FlowRun as COMPLETED + stamp stats + completedAt."""
        run.status = FlowRunStatus.COMPLETED
        if stats is not None:
            run.stats = json.dumps(stats)
        if imported_prospect_ids is not None:
            run.importedProspectIds = json.dumps(imported_prospect_ids)
        run.completedAt = datetime.now(timezone.utc)
        await db.flush()

    async def fail_run(
        self,
        db: AsyncSession,
        run: FlowRun,
        *,
        error_message: str,
        stats: dict[str, Any] | None = None,
    ) -> None:
        """Mark a FlowRun as FAILED + stamp errorMessage + completedAt."""
        run.status = FlowRunStatus.FAILED
        run.errorMessage = error_message[:1000] if error_message else None
        if stats is not None:
            run.stats = json.dumps(stats)
        run.completedAt = datetime.now(timezone.utc)
        await db.flush()

    async def cancel_run(self, db: AsyncSession, run: FlowRun) -> None:
        run.status = FlowRunStatus.CANCELLED
        run.completedAt = datetime.now(timezone.utc)
        await db.flush()

    # ── FlowRunStep lifecycle ─────────────────────────────────────────────

    async def create_step(
        self,
        db: AsyncSession,
        *,
        run: FlowRun,
        kind: FlowRunStepKind,
        step_key: str,
        order: int,
    ) -> FlowRunStep:
        """Create a FlowRunStep in PENDING state."""
        step = FlowRunStep(
            runId=run.id,
            kind=kind,
            stepKey=step_key,
            order=order,
            status=FlowRunStepStatus.PENDING,
            metrics="{}",
        )
        db.add(step)
        await db.flush()
        return step

    async def start_step(
        self, db: AsyncSession, step: FlowRunStep
    ) -> None:
        step.status = FlowRunStepStatus.RUNNING
        step.startedAt = datetime.now(timezone.utc)
        await db.flush()

    async def complete_step(
        self,
        db: AsyncSession,
        step: FlowRunStep,
        *,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        step.status = FlowRunStepStatus.SUCCESS
        if metrics is not None:
            step.metrics = json.dumps(metrics)
        step.completedAt = datetime.now(timezone.utc)
        if step.startedAt is not None:
            delta = step.completedAt - step.startedAt
            step.durationMs = int(delta.total_seconds() * 1000)
        await db.flush()

    async def skip_step(
        self,
        db: AsyncSession,
        step: FlowRunStep,
        *,
        reason: str | None = None,
    ) -> None:
        step.status = FlowRunStepStatus.SKIPPED
        if reason:
            step.errorMessage = reason[:500]
        step.completedAt = datetime.now(timezone.utc)
        await db.flush()

    async def fail_step(
        self,
        db: AsyncSession,
        step: FlowRunStep,
        *,
        error_message: str,
    ) -> None:
        step.status = FlowRunStepStatus.FAILED
        step.errorMessage = error_message[:1000] if error_message else None
        step.completedAt = datetime.now(timezone.utc)
        if step.startedAt is not None:
            delta = step.completedAt - step.startedAt
            step.durationMs = int(delta.total_seconds() * 1000)
        await db.flush()

    # ── AutopilotQueue (read-only view) ───────────────────────────────────

    async def list_queue(
        self,
        db: AsyncSession,
        *,
        status_: AutopilotQueueStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AutopilotQueue], int]:
        stmt = select(AutopilotQueue)
        if status_ is not None:
            stmt = stmt.where(AutopilotQueue.status == status_)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(AutopilotQueue.queuedAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def enqueue_run(
        self,
        db: AsyncSession,
        *,
        flow: ProspectingFlow,
        icp_profile_id: str,
        origin: str = "manual",
        config: dict[str, Any] | None = None,
    ) -> AutopilotQueue:
        """Insert an AutopilotQueue row pointing at a flow + ICP.

        The actual Celery task enqueue is performed by the router (so this
        method does not need to know about Celery). The router can pass
        the returned AutopilotQueue.id in the Celery payload so the worker
        can update its status + link the FlowRun once it starts.
        """
        item = AutopilotQueue(
            flowId=flow.id,
            icpProfileId=icp_profile_id,
            status=AutopilotQueueStatus.QUEUED,
            origin=origin,
            config=json.dumps(config or {}),
        )
        db.add(item)
        await db.commit()
        item = await db.get(AutopilotQueue, item.id)
        return item

    async def link_queue_to_run(
        self,
        db: AsyncSession,
        queue: AutopilotQueue,
        run: FlowRun,
    ) -> None:
        """Stamp ``AutopilotQueue.flowRunId`` once the run starts."""
        queue.flowRunId = run.id
        queue.status = AutopilotQueueStatus.RUNNING
        queue.pickedUpAt = datetime.now(timezone.utc)
        await db.flush()

    # ── FlowAbTest CRUD ───────────────────────────────────────────────────

    async def list_ab_tests(
        self,
        db: AsyncSession,
        *,
        icp_profile_id: str | None = None,
        status_: FlowAbTestStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FlowAbTest], int]:
        stmt = select(FlowAbTest)
        if icp_profile_id:
            stmt = stmt.where(FlowAbTest.icpProfileId == icp_profile_id)
        if status_ is not None:
            stmt = stmt.where(FlowAbTest.status == status_)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(FlowAbTest.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_ab_test(
        self, db: AsyncSession, ab_test_id: str
    ) -> FlowAbTest | None:
        return (
            await db.execute(
                select(FlowAbTest).where(FlowAbTest.id == ab_test_id)
            )
        ).scalar_one_or_none()

    async def create_ab_test(
        self, db: AsyncSession, body: FlowAbTestCreate
    ) -> FlowAbTest:
        """BUG-13 FIX: Catch FK violation and return 422 with clear message."""
        item = FlowAbTest(**body.model_dump())
        db.add(item)
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            exc_str = str(exc).lower()
            if "foreign" in exc_str or "foreignkey" in exc_str or "fkey" in exc_str:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=422,
                    detail="icpProfileId does not reference a valid ICP Profile. "
                           "Please select an existing ICP profile from the dropdown.",
                ) from exc
            raise
        item = await db.get(FlowRunStep, item.id)
        return item

    async def update_ab_test(
        self,
        db: AsyncSession,
        ab_test_id: str,
        body: FlowAbTestUpdate,
    ) -> FlowAbTest | None:
        item = await self.get_ab_test(db, ab_test_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        if body.status == FlowAbTestStatus.RUNNING and item.startedAt is None:
            item.startedAt = datetime.now(timezone.utc)
        if body.status == FlowAbTestStatus.COMPLETED and item.completedAt is None:
            item.completedAt = datetime.now(timezone.utc)
        await db.commit()
        item = await db.get(FlowRunStep, item.id)
        return item

    async def delete_ab_test(
        self, db: AsyncSession, ab_test_id: str
    ) -> bool:
        item = await self.get_ab_test(db, ab_test_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── FlowWebhook CRUD ──────────────────────────────────────────────────

    async def list_webhooks(
        self,
        db: AsyncSession,
        *,
        flow_id: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FlowWebhook], int]:
        stmt = select(FlowWebhook)
        if flow_id:
            stmt = stmt.where(FlowWebhook.flowId == flow_id)
        if is_active is not None:
            stmt = stmt.where(FlowWebhook.isActive.is_(is_active))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(FlowWebhook.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_webhook(
        self, db: AsyncSession, webhook_id: str
    ) -> FlowWebhook | None:
        return (
            await db.execute(
                select(FlowWebhook).where(FlowWebhook.id == webhook_id)
            )
        ).scalar_one_or_none()

    async def create_webhook(
        self, db: AsyncSession, body: FlowWebhookCreate
    ) -> FlowWebhook:
        item = FlowWebhook(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(FlowWebhook, item.id)
        return item

    async def update_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
        body: FlowWebhookUpdate,
    ) -> FlowWebhook | None:
        item = await self.get_webhook(db, webhook_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(FlowWebhook, item.id)
        return item

    async def delete_webhook(
        self, db: AsyncSession, webhook_id: str
    ) -> bool:
        item = await self.get_webhook(db, webhook_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    # ── FlowWebhookDelivery (audit-trail writes) ──────────────────────────

    async def record_webhook_delivery(
        self,
        db: AsyncSession,
        *,
        webhook: FlowWebhook,
        event: WebhookTriggerEvent,
        payload: dict[str, Any],
        status_code: int | None = None,
        response_body: str | None = None,
        status_: WebhookDeliveryStatus = WebhookDeliveryStatus.PENDING,
        attempts: int = 1,
        delivered_at: datetime | None = None,
    ) -> FlowWebhookDelivery:
        """Persist one FlowWebhookDelivery row (immutable audit trail).

        FIX-BE-1 / CRITICAL 1 (re-verification): FlowWebhookDelivery was
        the only one of the 9 flow_models classes that still had no write
        site. This method backs the POST /flows/webhooks/{id}/test route
        and is also the entry point for the future Celery webhook-delivery
        worker (which will retry PENDING deliveries with exponential
        backoff).
        """
        delivery = FlowWebhookDelivery(
            webhookId=webhook.id,
            event=event,
            payload=json.dumps(payload, default=str),
            statusCode=status_code,
            response=response_body,
            status=status_,
            attempts=attempts,
            deliveredAt=delivered_at,
        )
        db.add(delivery)
        await db.commit()
        delivery = await db.get(FlowWebhookDelivery, delivery.id)
        return delivery

    async def list_deliveries(
        self,
        db: AsyncSession,
        webhook_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FlowWebhookDelivery], int]:
        """List delivery audit-trail rows for a webhook (newest first)."""
        stmt = select(FlowWebhookDelivery).where(
            FlowWebhookDelivery.webhookId == webhook_id
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar() or 0)
        result = await db.execute(
            stmt.order_by(FlowWebhookDelivery.createdAt.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _demote_default_flows(
        self, db: AsyncSession, *, exclude_id: str | None = None
    ) -> None:
        result = await db.execute(
            select(ProspectingFlow).where(ProspectingFlow.isDefault.is_(True))
        )
        for existing in result.scalars().all():
            if exclude_id is not None and existing.id == exclude_id:
                continue
            existing.isDefault = False
        await db.flush()


__all__ = ["FlowRunService"]
