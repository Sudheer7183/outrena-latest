# """
# flows.py — Phase 3 /api/v1/flows router.

# Created by FIX-BE-1 / CRITICAL 1 (audit §D1): the underlying ORM models
# in ``app/models/flow_models.py`` previously had NO service/route surface.

# Endpoints (all under /flows):

#   ── ProspectingFlow (flow definitions) ───────────────────────────────────
#   GET    /flows                       list (optional is_active/is_template filter)
#   POST   /flows                       create (MANAGER+)
#   GET    /flows/{flow_id}             fetch one
#   PUT    /flows/{flow_id}             update
#   DELETE /flows/{flow_id}             delete (204)

#   ── FlowRun (executions — also created by autopilot_service) ──────────────
#   GET    /flows/runs                  list runs (optional flow_id/icp_profile_id filter)
#   GET    /flows/runs/{run_id}         fetch one run + its FlowRunStep rows

#   ── FlowAbTest (flow-level A/B testing) ───────────────────────────────────
#   GET    /flows/ab-tests              list
#   POST   /flows/ab-tests              create (MANAGER+)
#   GET    /flows/ab-tests/{id}         fetch one
#   PUT    /flows/ab-tests/{id}         update (status transition)
#   DELETE /flows/ab-tests/{id}         delete (204)

#   ── FlowWebhook (outbound webhook triggers) ───────────────────────────────
#   GET    /flows/webhooks              list
#   POST   /flows/webhooks              create (MANAGER+)
#   GET    /flows/webhooks/{id}         fetch one
#   PUT    /flows/webhooks/{id}         update
#   DELETE /flows/webhooks/{id}         delete (204)

#   ── AutopilotQueue (queue view) ───────────────────────────────────────────
#   GET    /flows/queue                 list queue items (optional status filter)

# Role gate: Role.REP for reads, Role.MANAGER for writes. The actual flow
# execution (POST /flows/{id}/runs) is intentionally NOT exposed here —
# the existing POST /api/v1/autopilot endpoint remains the entry point
# for triggering an autopilot run (it enqueues a Celery task that calls
# ``autopilot_service.orchestrate_pipeline``, which now persists a
# FlowRun + FlowRunStep rows internally).
# """
# from __future__ import annotations

# from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db
# from app.api.security import require_role
# from app.models.enums import (
#     AutopilotQueueStatus,
#     FlowAbTestStatus,
#     FlowRunStatus,
#     WebhookDeliveryStatus,
#     WebhookTriggerEvent,
# )
# from app.schemas.auth import Role, TokenPayload
# from app.schemas.flow_run import (
#     AutopilotQueueListResponse,
#     AutopilotQueueResponse,
#     FlowAbTestCreate,
#     FlowAbTestListResponse,
#     FlowAbTestResponse,
#     FlowAbTestUpdate,
#     FlowRunListResponse,
#     FlowRunResponse,
#     FlowWebhookCreate,
#     FlowWebhookDeliveryListResponse,
#     FlowWebhookDeliveryResponse,
#     FlowWebhookListResponse,
#     FlowWebhookResponse,
#     FlowWebhookUpdate,
#     ProspectingFlowCreate,
#     ProspectingFlowListResponse,
#     ProspectingFlowResponse,
#     ProspectingFlowUpdate,
# )
# from app.features.flows.service import FlowRunService

# router = APIRouter(prefix="/flows", tags=["Flows"])
# _service = FlowRunService()


# # ── ProspectingFlow ───────────────────────────────────────────────────────


# @router.get("", response_model=ProspectingFlowListResponse)
# async def list_flows(
#     is_active: bool | None = Query(default=None),
#     is_template: bool | None = Query(default=None),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectingFlowListResponse:
#     items, total = await _service.list_flows(
#         db,
#         is_active=is_active,
#         is_template=is_template,
#         limit=limit,
#         offset=offset,
#     )
#     return ProspectingFlowListResponse(
#         items=[ProspectingFlowResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post("", response_model=ProspectingFlowResponse, status_code=201)
# async def create_flow(
#     body: ProspectingFlowCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> ProspectingFlowResponse:
#     item = await _service.create_flow(db, body)
#     return ProspectingFlowResponse.model_validate(item)


# @router.get("/queue", response_model=AutopilotQueueListResponse)
# async def list_queue(
#     queue_status: AutopilotQueueStatus | None = Query(
#         default=None, alias="status"
#     ),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> AutopilotQueueListResponse:
#     items, total = await _service.list_queue(
#         db,
#         status_=queue_status,
#         limit=limit,
#         offset=offset,
#     )
#     return AutopilotQueueListResponse(
#         items=[AutopilotQueueResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )

# # ── Sub-collection routes (registered BEFORE /{flow_id} to prevent shadowing) ──

# @router.get("/runs", response_model=FlowRunListResponse)
# async def list_runs(
#     flow_id: str | None = Query(default=None),
#     icp_profile_id: str | None = Query(default=None),
#     run_status: FlowRunStatus | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowRunListResponse:
#     items, total = await _service.list_runs(
#         db,
#         flow_id=flow_id,
#         icp_profile_id=icp_profile_id,
#         status_=run_status,
#         limit=limit,
#         offset=offset,
#     )
#     return FlowRunListResponse(
#         items=[FlowRunResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.get("/runs/{run_id}", response_model=FlowRunResponse)
# async def get_run(
#     run_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowRunResponse:
#     item = await _service.get_run_with_steps(db, run_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow run not found.")
#     return FlowRunResponse.model_validate(item)


# # ── FlowAbTest ────────────────────────────────────────────────────────────


# @router.get("/ab-tests", response_model=FlowAbTestListResponse)
# async def list_ab_tests(
#     icp_profile_id: str | None = Query(default=None),
#     ab_status: FlowAbTestStatus | None = Query(default=None, alias="status"),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowAbTestListResponse:
#     items, total = await _service.list_ab_tests(
#         db,
#         icp_profile_id=icp_profile_id,
#         status_=ab_status,
#         limit=limit,
#         offset=offset,
#     )
#     return FlowAbTestListResponse(
#         items=[FlowAbTestResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post("/ab-tests", response_model=FlowAbTestResponse, status_code=201)
# async def create_ab_test(
#     body: FlowAbTestCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowAbTestResponse:
#     item = await _service.create_ab_test(db, body)
#     return FlowAbTestResponse.model_validate(item)


# @router.get("/ab-tests/{ab_test_id}", response_model=FlowAbTestResponse)
# async def get_ab_test(
#     ab_test_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowAbTestResponse:
#     item = await _service.get_ab_test(db, ab_test_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
#     return FlowAbTestResponse.model_validate(item)


# @router.put("/ab-tests/{ab_test_id}", response_model=FlowAbTestResponse)
# async def update_ab_test(
#     ab_test_id: str,
#     body: FlowAbTestUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowAbTestResponse:
#     item = await _service.update_ab_test(db, ab_test_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
#     return FlowAbTestResponse.model_validate(item)


# @router.delete(
#     "/ab-tests/{ab_test_id}",
#     response_model=None,
#     response_class=Response,
#     status_code=204,
# )
# async def delete_ab_test(
#     ab_test_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.delete_ab_test(db, ab_test_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # ── FlowWebhook ───────────────────────────────────────────────────────────


# @router.get("/webhooks", response_model=FlowWebhookListResponse)
# async def list_webhooks(
#     flow_id: str | None = Query(default=None),
#     is_active: bool | None = Query(default=None),
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowWebhookListResponse:
#     items, total = await _service.list_webhooks(
#         db,
#         flow_id=flow_id,
#         is_active=is_active,
#         limit=limit,
#         offset=offset,
#     )
#     return FlowWebhookListResponse(
#         items=[FlowWebhookResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# @router.post("/webhooks", response_model=FlowWebhookResponse, status_code=201)
# async def create_webhook(
#     body: FlowWebhookCreate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowWebhookResponse:
#     item = await _service.create_webhook(db, body)
#     return FlowWebhookResponse.model_validate(item)


# @router.get("/webhooks/{webhook_id}", response_model=FlowWebhookResponse)
# async def get_webhook(
#     webhook_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowWebhookResponse:
#     item = await _service.get_webhook(db, webhook_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
#     return FlowWebhookResponse.model_validate(item)


# @router.put("/webhooks/{webhook_id}", response_model=FlowWebhookResponse)
# async def update_webhook(
#     webhook_id: str,
#     body: FlowWebhookUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowWebhookResponse:
#     item = await _service.update_webhook(db, webhook_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
#     return FlowWebhookResponse.model_validate(item)


# @router.delete(
#     "/webhooks/{webhook_id}",
#     response_model=None,
#     response_class=Response,
#     status_code=204,
# )
# async def delete_webhook(
#     webhook_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.delete_webhook(db, webhook_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # ── FlowWebhook test-fire + delivery audit trail ─────────────────────────
# # FIX-BE-1 / CRITICAL 1 (re-verification): these two endpoints are the
# # write surface for FlowWebhookDelivery (the only one of the 9 flow_models
# # classes that previously had no insert site).


# @router.post(
#     "/webhooks/{webhook_id}/test",
#     response_model=FlowWebhookDeliveryResponse,
#     status_code=201,
# )
# async def test_fire_webhook(
#     webhook_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> FlowWebhookDeliveryResponse:
#     """Fire a FLOW_RUN_COMPLETED test event at the webhook + record the
#     delivery attempt as a FlowWebhookDelivery row.

#     Best-effort HTTP delivery — the row is persisted regardless of the
#     upstream response (status=DELIVERED on 2xx, FAILED otherwise). Used
#     by the Flow Webhooks UI 'Send test event' button.
#     """
#     import json as _json
#     from datetime import datetime, timezone

#     import httpx

#     webhook = await _service.get_webhook(db, webhook_id)
#     if webhook is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
#     payload = {
#         "event": "FLOW_RUN_COMPLETED",
#         "webhook_id": webhook.id,
#         "test": True,
#         "fired_at": datetime.now(timezone.utc).isoformat(),
#     }
#     status_code: int | None = None
#     response_body: str | None = None
#     delivery_status = WebhookDeliveryStatus.FAILED
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             resp = await client.post(
#                 webhook.url,
#                 json=payload,
#                 headers={"Content-Type": "application/json"},
#             )
#             status_code = resp.status_code
#             response_body = resp.text[:2000]
#             if 200 <= resp.status_code < 300:
#                 delivery_status = WebhookDeliveryStatus.DELIVERED
#     except Exception as exc:  # noqa: BLE001 — delivery errors are recorded, not raised
#         response_body = f"delivery_error: {exc}"
#     delivery = await _service.record_webhook_delivery(
#         db,
#         webhook=webhook,
#         event=WebhookTriggerEvent.FLOW_RUN_COMPLETED,
#         payload=payload,
#         status_code=status_code,
#         response_body=response_body,
#         status_=delivery_status,
#         attempts=1,
#         delivered_at=datetime.now(timezone.utc) if delivery_status == WebhookDeliveryStatus.DELIVERED else None,
#     )
#     return FlowWebhookDeliveryResponse.model_validate(delivery)


# @router.get(
#     "/webhooks/{webhook_id}/deliveries",
#     response_model=FlowWebhookDeliveryListResponse,
# )
# async def list_webhook_deliveries(
#     webhook_id: str,
#     limit: int = Query(default=50, ge=1, le=500),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> FlowWebhookDeliveryListResponse:
#     """List the FlowWebhookDelivery audit-trail rows for a webhook."""
#     items, total = await _service.list_deliveries(
#         db, webhook_id, limit=limit, offset=offset
#     )
#     return FlowWebhookDeliveryListResponse(
#         items=[FlowWebhookDeliveryResponse.model_validate(i) for i in items],
#         total=total,
#         limit=limit,
#         offset=offset,
#     )


# # ── ProspectingFlow single-resource CRUD ─────────────────────────────────────

# @router.get("/{flow_id}", response_model=ProspectingFlowResponse)
# async def get_flow(
#     flow_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.REP)),
# ) -> ProspectingFlowResponse:
#     item = await _service.get_flow(db, flow_id)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
#     return ProspectingFlowResponse.model_validate(item)


# @router.put("/{flow_id}", response_model=ProspectingFlowResponse)
# async def update_flow(
#     flow_id: str,
#     body: ProspectingFlowUpdate,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> ProspectingFlowResponse:
#     item = await _service.update_flow(db, flow_id, body)
#     if item is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
#     return ProspectingFlowResponse.model_validate(item)


# @router.delete(
#     "/{flow_id}",
#     response_model=None,
#     response_class=Response,
#     status_code=204,
# )
# async def delete_flow(
#     flow_id: str,
#     db: AsyncSession = Depends(get_db),
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> Response:
#     ok = await _service.delete_flow(db, flow_id)
#     if not ok:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# # ── FlowRun (list + detail) ───────────────────────────────────────────────
# # NOTE: POST /flows/{id}/runs is intentionally NOT exposed — autopilot
# # runs are enqueued via POST /api/v1/autopilot, which calls
# # autopilot_service.orchestrate_pipeline (which in turn persists the
# # FlowRun + FlowRunStep rows internally per FIX-BE-1 / CRITICAL 1).


# @router.post("/{flow_id}/run", status_code=202)
# async def run_flow(
#     flow_id: str,
#     icp_profile_id: str = Query(..., description="ICP Profile ID to run the flow against"),
#     db: AsyncSession = Depends(get_db),
#     token: TokenPayload = Depends(require_role(Role.REP)),
# ) -> dict:
#     """
#     Trigger an ad-hoc flow run (FR-E10-003).

#     Creates a FlowRun in PENDING status and returns the run_id immediately.
#     The run executes inline (SOURCE → ENRICH → GATE → SCORE → IMPORT) and
#     is marked COMPLETED or FAILED on return. For large flows with external
#     provider calls this may take up to 60 seconds.

#     To schedule recurring runs, use POST /api/v1/autopilot instead.
#     """
#     from sqlalchemy import select as _select
#     from app.models.flow_models import ProspectingFlow, FlowRun
#     from app.models.enums import FlowRunStatus

#     # Fetch the flow
#     flow_result = await db.execute(
#         _select(ProspectingFlow).where(ProspectingFlow.id == flow_id)
#     )
#     flow = flow_result.scalar_one_or_none()
#     if flow is None:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")

#     if not flow.isActive:
#         raise HTTPException(status.HTTP_400_BAD_REQUEST, "Flow is inactive. Activate it before running.")

#     # Create a FlowRun record
#     run = await _service.start_run(
#         db,
#         flow=flow,
#         icp_profile_id=icp_profile_id,
#         triggered_by="manual",
#         triggered_by_id=token.sub,
#     )
#     await db.commit()
#     run = await db.get(FlowRun, run.id)

#     # Attempt inline execution (best-effort — failures update run status)
#     try:
#         from app.services.autopilot_service import AutopilotService  # noqa: F401
#     except ImportError:
#         import structlog as _log
#         _log.get_logger(__name__).warning(
#             "autopilot_service module not found — skipping inline execution",
#             flow_id=flow_id,
#         )
#         run.status = FlowRunStatus.FAILED
#         await db.commit()
#     else:
#         try:
#             ap = AutopilotService()
#             await ap.execute_flow_run(db, run, flow=flow, icp_profile_id=icp_profile_id)
#         except Exception as exc:  # noqa: BLE001
#             import structlog as _log
#             _log.get_logger(__name__).error("flow.run.execution_failed", flow_id=flow_id, error=str(exc))
#             run.status = FlowRunStatus.FAILED
#             await db.commit()

#     return {
#         "run_id": run.id,
#         "status": run.status.value if hasattr(run.status, "value") else str(run.status),
#         "message": "Flow run triggered. Use GET /api/v1/flows/runs/{run_id} to track progress.",
#     }


# __all__ = ["router"]

"""
flows.py — Phase 3 /api/v1/flows router.

Created by FIX-BE-1 / CRITICAL 1 (audit §D1): the underlying ORM models
in ``app/models/flow_models.py`` previously had NO service/route surface.

Endpoints (all under /flows):

  ── ProspectingFlow (flow definitions) ───────────────────────────────────
  GET    /flows                       list (optional is_active/is_template filter)
  POST   /flows                       create (MANAGER+)
  GET    /flows/{flow_id}             fetch one
  PUT    /flows/{flow_id}             update
  DELETE /flows/{flow_id}             delete (204)

  ── FlowRun (executions — also created by autopilot_service) ──────────────
  GET    /flows/runs                  list runs (optional flow_id/icp_profile_id filter)
  GET    /flows/runs/{run_id}         fetch one run + its FlowRunStep rows

  ── FlowAbTest (flow-level A/B testing) ───────────────────────────────────
  GET    /flows/ab-tests              list
  POST   /flows/ab-tests              create (MANAGER+)
  GET    /flows/ab-tests/{id}         fetch one
  PUT    /flows/ab-tests/{id}         update (status transition)
  DELETE /flows/ab-tests/{id}         delete (204)

  ── FlowWebhook (outbound webhook triggers) ───────────────────────────────
  GET    /flows/webhooks              list
  POST   /flows/webhooks              create (MANAGER+)
  GET    /flows/webhooks/{id}         fetch one
  PUT    /flows/webhooks/{id}         update
  DELETE /flows/webhooks/{id}         delete (204)

  ── AutopilotQueue (queue view) ───────────────────────────────────────────
  GET    /flows/queue                 list queue items (optional status filter)

Role gate: Role.REP for reads, Role.MANAGER for writes. The actual flow
execution (POST /flows/{id}/runs) is intentionally NOT exposed here —
the existing POST /api/v1/autopilot endpoint remains the entry point
for triggering an autopilot run (it enqueues a Celery task that calls
``autopilot_service.orchestrate_pipeline``, which now persists a
FlowRun + FlowRunStep rows internally).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.models.enums import (
    AutopilotQueueStatus,
    FlowAbTestStatus,
    FlowRunStatus,
    WebhookDeliveryStatus,
    WebhookTriggerEvent,
)
from app.schemas.auth import Role, TokenPayload
from app.schemas.flow_run import (
    AutopilotQueueListResponse,
    AutopilotQueueResponse,
    FlowAbTestCreate,
    FlowAbTestListResponse,
    FlowAbTestResponse,
    FlowAbTestUpdate,
    FlowRunListResponse,
    FlowRunResponse,
    FlowWebhookCreate,
    FlowWebhookDeliveryListResponse,
    FlowWebhookDeliveryResponse,
    FlowWebhookListResponse,
    FlowWebhookResponse,
    FlowWebhookUpdate,
    ProspectingFlowCreate,
    ProspectingFlowListResponse,
    ProspectingFlowResponse,
    ProspectingFlowUpdate,
)
from app.features.flows.service import FlowRunService

router = APIRouter(prefix="/flows", tags=["Flows"])
_service = FlowRunService()


# ── ProspectingFlow ───────────────────────────────────────────────────────


@router.get("", response_model=ProspectingFlowListResponse)
async def list_flows(
    is_active: bool | None = Query(default=None),
    is_template: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectingFlowListResponse:
    items, total = await _service.list_flows(
        db,
        is_active=is_active,
        is_template=is_template,
        limit=limit,
        offset=offset,
    )
    return ProspectingFlowListResponse(
        items=[ProspectingFlowResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProspectingFlowResponse, status_code=201)
async def create_flow(
    body: ProspectingFlowCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> ProspectingFlowResponse:
    item = await _service.create_flow(db, body)
    return ProspectingFlowResponse.model_validate(item)


@router.get("/queue", response_model=AutopilotQueueListResponse)
async def list_queue(
    queue_status: AutopilotQueueStatus | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutopilotQueueListResponse:
    items, total = await _service.list_queue(
        db,
        status_=queue_status,
        limit=limit,
        offset=offset,
    )
    return AutopilotQueueListResponse(
        items=[AutopilotQueueResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )

# ── Sub-collection routes (registered BEFORE /{flow_id} to prevent shadowing) ──

@router.get("/runs", response_model=FlowRunListResponse)
async def list_runs(
    flow_id: str | None = Query(default=None),
    icp_profile_id: str | None = Query(default=None),
    run_status: FlowRunStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowRunListResponse:
    items, total = await _service.list_runs(
        db,
        flow_id=flow_id,
        icp_profile_id=icp_profile_id,
        status_=run_status,
        limit=limit,
        offset=offset,
    )
    return FlowRunListResponse(
        items=[FlowRunResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=FlowRunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowRunResponse:
    item = await _service.get_run_with_steps(db, run_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow run not found.")
    return FlowRunResponse.model_validate(item)


# ── FlowAbTest ────────────────────────────────────────────────────────────


@router.get("/ab-tests", response_model=FlowAbTestListResponse)
async def list_ab_tests(
    icp_profile_id: str | None = Query(default=None),
    ab_status: FlowAbTestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowAbTestListResponse:
    items, total = await _service.list_ab_tests(
        db,
        icp_profile_id=icp_profile_id,
        status_=ab_status,
        limit=limit,
        offset=offset,
    )
    return FlowAbTestListResponse(
        items=[FlowAbTestResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/ab-tests", response_model=FlowAbTestResponse, status_code=201)
async def create_ab_test(
    body: FlowAbTestCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowAbTestResponse:
    item = await _service.create_ab_test(db, body)
    return FlowAbTestResponse.model_validate(item)


@router.get("/ab-tests/{ab_test_id}", response_model=FlowAbTestResponse)
async def get_ab_test(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowAbTestResponse:
    item = await _service.get_ab_test(db, ab_test_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return FlowAbTestResponse.model_validate(item)


@router.put("/ab-tests/{ab_test_id}", response_model=FlowAbTestResponse)
async def update_ab_test(
    ab_test_id: str,
    body: FlowAbTestUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowAbTestResponse:
    item = await _service.update_ab_test(db, ab_test_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return FlowAbTestResponse.model_validate(item)


@router.delete(
    "/ab-tests/{ab_test_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_ab_test(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_ab_test(db, ab_test_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── FlowWebhook ───────────────────────────────────────────────────────────


@router.get("/webhooks", response_model=FlowWebhookListResponse)
async def list_webhooks(
    flow_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowWebhookListResponse:
    items, total = await _service.list_webhooks(
        db,
        flow_id=flow_id,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return FlowWebhookListResponse(
        items=[FlowWebhookResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/webhooks", response_model=FlowWebhookResponse, status_code=201)
async def create_webhook(
    body: FlowWebhookCreate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowWebhookResponse:
    item = await _service.create_webhook(db, body)
    return FlowWebhookResponse.model_validate(item)


@router.get("/webhooks/{webhook_id}", response_model=FlowWebhookResponse)
async def get_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowWebhookResponse:
    item = await _service.get_webhook(db, webhook_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    return FlowWebhookResponse.model_validate(item)


@router.put("/webhooks/{webhook_id}", response_model=FlowWebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: FlowWebhookUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowWebhookResponse:
    item = await _service.update_webhook(db, webhook_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    return FlowWebhookResponse.model_validate(item)


@router.delete(
    "/webhooks/{webhook_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_webhook(db, webhook_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── FlowWebhook test-fire + delivery audit trail ─────────────────────────
# FIX-BE-1 / CRITICAL 1 (re-verification): these two endpoints are the
# write surface for FlowWebhookDelivery (the only one of the 9 flow_models
# classes that previously had no insert site).


@router.post(
    "/webhooks/{webhook_id}/test",
    response_model=FlowWebhookDeliveryResponse,
    status_code=201,
)
async def test_fire_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> FlowWebhookDeliveryResponse:
    """Fire a FLOW_RUN_COMPLETED test event at the webhook + record the
    delivery attempt as a FlowWebhookDelivery row.

    Best-effort HTTP delivery — the row is persisted regardless of the
    upstream response (status=DELIVERED on 2xx, FAILED otherwise). Used
    by the Flow Webhooks UI 'Send test event' button.
    """
    import json as _json
    from datetime import datetime, timezone

    import httpx

    webhook = await _service.get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    payload = {
        "event": "FLOW_RUN_COMPLETED",
        "webhook_id": webhook.id,
        "test": True,
        "fired_at": datetime.now(timezone.utc).isoformat(),
    }
    status_code: int | None = None
    response_body: str | None = None
    delivery_status = WebhookDeliveryStatus.FAILED
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                webhook.url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            status_code = resp.status_code
            response_body = resp.text[:2000]
            if 200 <= resp.status_code < 300:
                delivery_status = WebhookDeliveryStatus.DELIVERED
    except Exception as exc:  # noqa: BLE001 — delivery errors are recorded, not raised
        response_body = f"delivery_error: {exc}"
    delivery = await _service.record_webhook_delivery(
        db,
        webhook=webhook,
        event=WebhookTriggerEvent.FLOW_RUN_COMPLETED,
        payload=payload,
        status_code=status_code,
        response_body=response_body,
        status_=delivery_status,
        attempts=1,
        delivered_at=datetime.now(timezone.utc) if delivery_status == WebhookDeliveryStatus.DELIVERED else None,
    )
    return FlowWebhookDeliveryResponse.model_validate(delivery)


@router.get(
    "/webhooks/{webhook_id}/deliveries",
    response_model=FlowWebhookDeliveryListResponse,
)
async def list_webhook_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> FlowWebhookDeliveryListResponse:
    """List the FlowWebhookDelivery audit-trail rows for a webhook."""
    items, total = await _service.list_deliveries(
        db, webhook_id, limit=limit, offset=offset
    )
    return FlowWebhookDeliveryListResponse(
        items=[FlowWebhookDeliveryResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── ProspectingFlow single-resource CRUD ─────────────────────────────────────

@router.get("/{flow_id}", response_model=ProspectingFlowResponse)
async def get_flow(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.REP)),
) -> ProspectingFlowResponse:
    item = await _service.get_flow(db, flow_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
    return ProspectingFlowResponse.model_validate(item)


@router.put("/{flow_id}", response_model=ProspectingFlowResponse)
async def update_flow(
    flow_id: str,
    body: ProspectingFlowUpdate,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> ProspectingFlowResponse:
    item = await _service.update_flow(db, flow_id, body)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
    return ProspectingFlowResponse.model_validate(item)


@router.delete(
    "/{flow_id}",
    response_model=None,
    response_class=Response,
    status_code=204,
)
async def delete_flow(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> Response:
    ok = await _service.delete_flow(db, flow_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── FlowRun (list + detail) ───────────────────────────────────────────────
# NOTE: POST /flows/{id}/runs is intentionally NOT exposed — autopilot
# runs are enqueued via POST /api/v1/autopilot, which calls
# autopilot_service.orchestrate_pipeline (which in turn persists the
# FlowRun + FlowRunStep rows internally per FIX-BE-1 / CRITICAL 1).


@router.post("/{flow_id}/run", status_code=202)
async def run_flow(
    flow_id: str,
    icp_profile_id: str = Query(..., description="ICP Profile ID to run the flow against"),
    llm_config_id: str | None = Query(default=None, description="Optional: specific LLM config ID to use"),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.REP)),
) -> dict:
    """
    Trigger an ad-hoc flow run.

    Returns run_id immediately (HTTP 202). The pipeline executes as a
    background asyncio task so the HTTP request is not held open during
    Tavily searches and LLM calls (which can take 30–120 seconds).

    Poll GET /api/v1/flows/runs/{run_id} every 2 seconds to track progress.
    """
    import asyncio as _asyncio
    from sqlalchemy import select as _select, text as _text
    from app.models.flow_models import ProspectingFlow
    from app.models.enums import FlowRunStatus
    from app.core.database import AsyncSessionLocal as _SessionLocal

    # Fetch the flow
    flow_result = await db.execute(
        _select(ProspectingFlow).where(ProspectingFlow.id == flow_id)
    )
    flow = flow_result.scalar_one_or_none()
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flow not found.")

    if not flow.isActive:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Flow is inactive. Activate it before running.")

    # Create the FlowRun record in the request session (tenant schema already set)
    run = await _service.start_run(
        db,
        flow=flow,
        icp_profile_id=icp_profile_id,
        triggered_by="manual",
        triggered_by_id=token.sub,
    )
    # Capture everything we need BEFORE the commit re-pools the connection
    run_id = run.id

    # Capture the tenant schema name now while search_path is still set
    schema_result = await db.execute(_text("SELECT current_schema()"))
    tenant_schema: str = schema_result.scalar_one_or_none() or "public"

    # Capture flow data as plain Python values (ORM object won't be usable
    # after the session closes; background task gets its own session)
    flow_id_str: str = flow.id
    flow_source_steps = flow.sourceSteps
    flow_enrich_steps = flow.enrichmentSteps
    flow_quality_gates = flow.qualityGates
    flow_is_active = flow.isActive
    flow_name: str = flow.name

    await db.commit()

    # ── Background task ─────────────────────────────────────────────────────
    # Opens a FRESH AsyncSession (not the request session which closes after
    # this endpoint returns) and runs the full pipeline.
    async def _background_execute() -> None:
        import structlog as _log
        _bg_log = _log.get_logger("autopilot.background")
        _bg_log.info("background_task.start", run_id=run_id, schema=tenant_schema)

        try:
            from app.services.autopilot_service import AutopilotService

            # Build a lightweight flow proxy so autopilot_service can read
            # getattr(flow, "sourceSteps") etc. without an ORM session.
            from types import SimpleNamespace as _NS
            flow_proxy = _NS(
                id=flow_id_str,
                name=flow_name,
                isActive=flow_is_active,
                sourceSteps=flow_source_steps,
                enrichmentSteps=flow_enrich_steps,
                qualityGates=flow_quality_gates,
            )

            # Fresh session with the correct tenant search_path
            async with _SessionLocal() as bg_db:
                await bg_db.execute(
                    _text(f'SET search_path TO "{tenant_schema}", public')
                )

                # Re-fetch the FlowRun in this session so autopilot_service can
                # update it (ORM objects are session-bound)
                from app.models.flow_models import FlowRun as _FlowRun
                run_result = await bg_db.execute(
                    _select(_FlowRun).where(_FlowRun.id == run_id)
                )
                bg_run = run_result.scalar_one_or_none()
                if bg_run is None:
                    _bg_log.error("background_task.run_not_found", run_id=run_id)
                    return

                ap = AutopilotService()
                result = await ap.execute_flow_run(
                    bg_db, bg_run,
                    flow=flow_proxy,
                    icp_profile_id=icp_profile_id,
                    llm_config_id=llm_config_id,
                )
                _bg_log.info("background_task.done", run_id=run_id, **result)

        except Exception as exc:  # noqa: BLE001
            import structlog as _log2
            _log2.get_logger("autopilot.background").error(
                "background_task.unhandled_exception",
                run_id=run_id,
                error=str(exc),
            )

    # Fire and forget — returns immediately to the caller
    _asyncio.create_task(_background_execute())

    return {
        "run_id": run_id,
        "status": FlowRunStatus.RUNNING.value,
        "message": (
            "Flow run started in the background. "
            "Poll GET /api/v1/flows/runs/{run_id} every 2 seconds for live progress."
        ),
    }


__all__ = ["router"]
