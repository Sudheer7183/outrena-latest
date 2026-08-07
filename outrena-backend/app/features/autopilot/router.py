"""
autopilot.py — Phase 2 /api/v1/autopilot router.

Endpoints:
  POST /autopilot           enqueue a Celery autopilot.run_pipeline task → 202
  GET  /autopilot/{task_id} poll the Celery result backend for status

Role gate: Role.MANAGER.

Imports of Fix-4's app.services.autopilot_service and app.worker.celery_app
are deferred to function scope so the router compiles + imports even before
the worker module lands. The router raises HTTP 503 if the dependencies are
not yet present.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.features.usage.cap_gate import enforce_llm_cap
from app.schemas.autopilot import (
    AutopilotCreateRequest,
    AutopilotCreateResponse,
    AutopilotStatusResponse,
)

router = APIRouter(prefix="/autopilot", tags=["Autopilot"])


def _load_celery_app() -> Any:
    """Function-level import so the router compiles before Fix-4 lands.

    BUG-09 FIX: Returns None instead of raising when celery_app is unavailable,
    allowing callers to return a graceful degraded response.
    """
    try:
        from app.worker.celery_app import celery_app  # type: ignore
        return celery_app
    except (ImportError, Exception):  # noqa: BLE001
        return None


def _load_orchestrate_pipeline() -> Any:
    """Function-level import so the router compiles before Fix-4 lands."""
    try:
        from app.features.autopilot.service import orchestrate_pipeline  # type: ignore

        return orchestrate_pipeline
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Autopilot orchestrator not yet available "
                "(app.services.autopilot_service missing)."
            ),
        ) from exc


@router.post(
    "",
    response_model=AutopilotCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_llm_cap)],  # FR-114: throttle at tenant cap
)
async def enqueue_autopilot(
    body: AutopilotCreateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutopilotCreateResponse:
    """Enqueue a Celery autopilot.run_pipeline task and return its task_id."""
    celery_app = _load_celery_app()
    # BUG-09 FIX: Guard against celery_app being None (worker not running).
    if celery_app is None:
        from fastapi.responses import JSONResponse as _JSONResponse
        return AutopilotCreateResponse(
            task_id="celery_unavailable",
            status="unavailable",
            message="Background worker is not running. Start the Celery worker to use Autopilot.",
        )
    # Importing the orchestrator here ensures it exists (Fix-4 deliverable).
    # The task itself wraps orchestrate_pipeline in a synchronous Celery task.
    _load_orchestrate_pipeline()

    schema_name = body.schema_name or token.tenant_slug or "public"
    # Build the payload in snake_case (Fix-4's orchestrator expects this).
    payload: dict[str, Any] = {
        "schema_name": schema_name,
        "user_id": token.sub,
        "campaign_name": body.campaign_name,
        "target_count": body.target_count,
        "icp_hint": body.icp_hint,
        "sender_role": body.sender_role,
        "sender_company": body.sender_company,
        "sender_offer": body.sender_offer,
        "proof_metric": body.proof_metric,
        "sender_product": body.sender_product,
        "target_audience": body.target_audience,
        "framework": body.framework,
        "metadata": body.metadata or {},
    }

    run_pipeline = celery_app.tasks.get("autopilot.run_pipeline")
    if run_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Celery task 'autopilot.run_pipeline' not registered.",
        )
    async_result = run_pipeline.apply_async(args=[payload])
    task_id = getattr(async_result, "id", "") or ""
    return AutopilotCreateResponse(
        task_id=task_id,
        status="PENDING",
        message="Task enqueued.",
    )


@router.get("/{task_id}", response_model=AutopilotStatusResponse)
async def get_autopilot_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutopilotStatusResponse:
    """Poll the Celery result backend for the status of an autopilot task."""
    celery_app = _load_celery_app()
    # BUG-09 FIX (CC-01): Guard against celery_app being None.
    if celery_app is None:
        return AutopilotStatusResponse(
            task_id=task_id,
            status="PENDING",
            error="Background worker is not running.",
        )
    run_pipeline = celery_app.tasks.get("autopilot.run_pipeline")
    if run_pipeline is None:
        return AutopilotStatusResponse(
            task_id=task_id,
            status="PENDING",
            error="Celery task 'autopilot.run_pipeline' not registered.",
        )
    async_result = run_pipeline.AsyncResult(task_id)
    raw_state = str(getattr(async_result, "state", "PENDING"))
    ready = bool(getattr(async_result, "ready", lambda: False)())
    result: Any = None
    error: str | None = None
    try:
        if ready:
            successful = bool(
                getattr(async_result, "successful", lambda: False)()
            )
            if successful:
                result = async_result.result
            else:
                error = str(async_result.result)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    # Normalize Celery state names into the literal set the schema accepts.
    normalized_state = raw_state
    if normalized_state not in ("PENDING", "STARTED", "SUCCESS", "FAILURE"):
        # Map RETRY/REVOKED/etc. to FAILURE for schema compliance.
        normalized_state = "FAILURE" if not ready else "SUCCESS"

    return AutopilotStatusResponse(
        task_id=task_id,
        status=normalized_state,  # type: ignore[arg-type]
        result=result,
        error=error,
    )


__all__ = ["router"]
