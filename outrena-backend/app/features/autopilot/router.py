# # """
# # autopilot/router.py — /api/v1/autopilot endpoints.

# # ROOT CAUSE OF InFailedSQLTransactionError — ARCHITECTURAL FIX:

# # The previous fix attempted to call _get_global_llm_config() inside the
# # orchestrate_pipeline() function, which opens its own AsyncSessionLocal()
# # session. The problem: AsyncSessionLocal() draws from the SAME asyncpg
# # connection pool as the outer tenant session (passed in as `db`). When the
# # inner session's SET search_path ran on what asyncpg handed it from the pool,
# # it could be the same physical connection the outer tenant session held open.
# # Any error or transaction state change inside the inner session poisoned the
# # outer tenant session, causing every subsequent query on it to throw:

# #     InFailedSQLTransactionError: current transaction is aborted,
# #     commands ignored until end of transaction block

# # THE FIX — resolve LLM config in the ROUTER, BEFORE the tenant session opens:

# #     Router:
# #       1. Resolve LLM config (uses get_db_public() — a SEPARATE dedicated
# #          public-schema session, already designed for this exact use case)
# #       2. Open tenant session (get_db dependency)  ← clean, no prior state
# #       3. Call orchestrate_pipeline(db, payload, llm_cfg=llm_cfg)
# #          ← llm_cfg is now a plain SimpleNamespace value, not a DB call

# # The LLM config lookup and the tenant pipeline session NEVER share a
# # connection. The public session is fully closed before the tenant session
# # opens. Transaction isolation is absolute.
# # """
# # from __future__ import annotations

# # import asyncio
# # import uuid
# # from types import SimpleNamespace
# # from typing import Any

# # from fastapi import APIRouter, Depends, HTTPException, status
# # from sqlalchemy import select, text
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.api.deps import get_db, get_db_public
# # from app.api.security import require_role
# # from app.schemas.auth import Role, TokenPayload
# # from app.features.usage.cap_gate import enforce_llm_cap
# # from app.schemas.autopilot import (
# #     AutopilotCreateRequest,
# #     AutopilotCreateResponse,
# #     AutopilotResult,
# #     AutopilotStatusResponse,
# # )

# # router = APIRouter(prefix="/autopilot", tags=["Autopilot"])

# # # In-memory result store for inline (non-Celery) runs.
# # _SYNC_RESULTS: dict[str, dict] = {}
# # _RUNNING_TASKS: set[str] = set()


# # # ── LLM config resolution (public schema, dedicated session) ───────────────

# # async def _resolve_llm_config(pub_db: AsyncSession) -> SimpleNamespace | None:
# #     """
# #     Resolve the default active GlobalLlmConfig using the CALLER'S public
# #     session (get_db_public). This session is already scoped to public schema
# #     and is completely separate from the tenant session.

# #     This function does NOT open any new sessions. It only runs SELECT queries
# #     on the provided pub_db. The caller (router endpoint) owns the session
# #     lifecycle and closes it before the tenant session opens.
# #     """
# #     try:
# #         from app.models.global_llm_config import GlobalLlmConfig
# #         from app.services.secret_service import decrypt_at_rest

# #         # Try is_default=True first
# #         result = await pub_db.execute(
# #             select(GlobalLlmConfig)
# #             .where(GlobalLlmConfig.is_active.is_(True))
# #             .where(GlobalLlmConfig.is_default.is_(True))
# #             .limit(1)
# #         )
# #         row = result.scalar_one_or_none()

# #         if row is None:
# #             result = await pub_db.execute(
# #                 select(GlobalLlmConfig)
# #                 .where(GlobalLlmConfig.is_active.is_(True))
# #                 .order_by(GlobalLlmConfig.id)
# #                 .limit(1)
# #             )
# #             row = result.scalar_one_or_none()

# #         if row is None:
# #             return None

# #         api_key = decrypt_at_rest(row.api_key_encrypted)

# #         return SimpleNamespace(
# #             id=row.id,
# #             name=row.display_name,
# #             provider=row.provider,
# #             model=row.model_name,
# #             apiKey=api_key,
# #             baseUrl=row.base_url,
# #             maxTokens=row.max_tokens,
# #             temperature=row.temperature,
# #             isActive=True,
# #             isDefault=row.is_default,
# #         )
# #     except Exception as exc:  # noqa: BLE001
# #         import structlog
# #         structlog.get_logger(__name__).error(
# #             "autopilot.router.llm_resolve_failed", error=str(exc)
# #         )
# #         return None


# # def _load_celery_app() -> Any:
# #     try:
# #         from app.worker.celery_app import celery_app  # type: ignore
# #         return celery_app
# #     except (ImportError, Exception):  # noqa: BLE001
# #         return None


# # @router.post(
# #     "",
# #     response_model=AutopilotCreateResponse,
# #     status_code=status.HTTP_202_ACCEPTED,
# #     dependencies=[Depends(enforce_llm_cap)],
# # )
# # async def enqueue_autopilot(
# #     body: AutopilotCreateRequest,
# #     pub_db: AsyncSession = Depends(get_db_public),
# #     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# # ) -> AutopilotCreateResponse:
# #     """
# #     Start an autopilot pipeline run.

# #     ARCHITECTURAL FIX: Uses get_db_public (not get_db) so the LLM config
# #     lookup runs in an isolated public-schema session. The tenant session is
# #     never opened here — it is opened inside _run_inline() or by Celery,
# #     AFTER this public session is fully closed.
# #     """
# #     # Step 1: Resolve LLM config NOW, in the public session, before any
# #     # tenant session opens. pub_db is get_db_public — already scoped to
# #     # public schema, completely isolated from any tenant transaction.
# #     llm_cfg = await _resolve_llm_config(pub_db)
# #     if llm_cfg is None:
# #         raise HTTPException(
# #             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
# #             detail=(
# #                 "No active LLM configuration found. "
# #                 "Go to LLM Models and configure an active provider first."
# #             ),
# #         )

# #     schema_name = getattr(body, "schema_name", None) or token.tenant_slug or "public"
# #     task_id = str(uuid.uuid4())

# #     # Serialize llm_cfg as a plain dict so it can be passed through Celery
# #     # (SimpleNamespace is not JSON-serializable) or asyncio.create_task().
# #     llm_cfg_dict = {
# #         "id": llm_cfg.id,
# #         "name": llm_cfg.name,
# #         "provider": llm_cfg.provider,
# #         "model": llm_cfg.model,
# #         "apiKey": llm_cfg.apiKey,
# #         "baseUrl": llm_cfg.baseUrl,
# #         "maxTokens": llm_cfg.maxTokens,
# #         "temperature": llm_cfg.temperature,
# #         "isActive": True,
# #         "isDefault": llm_cfg.isDefault,
# #     }

# #     payload: dict[str, Any] = {
# #         "schema_name": schema_name,
# #         "user_id": token.sub,
# #         "task_id": task_id,
# #         "campaign_name": body.campaign_name,
# #         "target_count": body.target_count,
# #         "icp_hint": body.icp_hint,
# #         "sender_role": body.sender_role,
# #         "sender_company": body.sender_company,
# #         "sender_offer": body.sender_offer,
# #         "proof_metric": body.proof_metric,
# #         "sender_product": body.sender_product,
# #         "target_audience": body.target_audience,
# #         "framework": body.framework,
# #         "metadata": body.metadata or {},
# #         # Pass pre-resolved LLM config — orchestrator uses this directly,
# #         # never opens a second session to re-resolve it.
# #         "_llm_cfg": llm_cfg_dict,
# #     }

# #     celery_app = _load_celery_app()

# #     # ── Path A: Celery available ─────────────────────────────────────────
# #     if celery_app is not None:
# #         run_pipeline = celery_app.tasks.get("autopilot.run_pipeline")
# #         if run_pipeline is not None:
# #             async_result = run_pipeline.apply_async(args=[payload], task_id=task_id)
# #             celery_task_id = getattr(async_result, "id", task_id) or task_id
# #             return AutopilotCreateResponse(
# #                 task_id=celery_task_id,
# #                 status="PENDING",
# #                 message="Task enqueued to Celery worker.",
# #             )

# #     # ── Path B: Inline async (no Celery) ────────────────────────────────
# #     from app.core.database import AsyncSessionLocal
# #     from app.features.autopilot.service import orchestrate_pipeline

# #     _RUNNING_TASKS.add(task_id)

# #     async def _run_inline() -> None:
# #         """
# #         Open a FRESH tenant session AFTER the public session (pub_db) has
# #         been closed by FastAPI's dependency teardown. No session overlap.
# #         """
# #         import app.models.phase3_models          # noqa: F401
# #         import app.models.campaign_models        # noqa: F401
# #         import app.models.prospect_models        # noqa: F401
# #         import app.models.flow_models            # noqa: F401
# #         import app.models.global_llm_config
# #         try:
# #             async with AsyncSessionLocal() as tenant_db:
# #                 try:
# #                     await tenant_db.execute(
# #                         text(f'SET search_path TO "{schema_name}", public')
# #                     )
# #                 except Exception:  # noqa: BLE001
# #                     await tenant_db.rollback()
# #                     await tenant_db.execute(
# #                         text(f'SET search_path TO "{schema_name}", public')
# #                     )
# #                 result = await orchestrate_pipeline(tenant_db, payload)
# #                 await tenant_db.commit()
# #                 _SYNC_RESULTS[task_id] = result.model_dump(mode="json")
# #         except Exception as exc:  # noqa: BLE001
# #             _SYNC_RESULTS[task_id] = AutopilotResult(
# #                 campaign_id="",
# #                 prospect_count=0,
# #                 sequence_count=0,
# #                 task_id=task_id,
# #                 status="FAILURE",  # type: ignore[arg-type]
# #                 error=f"Pipeline error: {exc}",
# #             ).model_dump(mode="json")
# #         finally:
# #             _RUNNING_TASKS.discard(task_id)

# #     asyncio.create_task(_run_inline())

# #     return AutopilotCreateResponse(
# #         task_id=task_id,
# #         status="STARTED",
# #         message="Pipeline running inline. Poll every 3s for results.",
# #     )


# # @router.get("/{task_id}", response_model=AutopilotStatusResponse)
# # async def get_autopilot_status(
# #     task_id: str,
# #     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# # ) -> AutopilotStatusResponse:
# #     """Poll autopilot run status. No DB session needed — reads from cache or Celery."""

# #     # Inline result available
# #     if task_id in _SYNC_RESULTS:
# #         stored = _SYNC_RESULTS[task_id]
# #         try:
# #             result_obj = AutopilotResult.model_validate(stored)
# #         except Exception:  # noqa: BLE001
# #             result_obj = None

# #         raw_status = stored.get("status", "FAILURE")
# #         resp_status = "SUCCESS" if raw_status in ("SUCCESS", "PARTIAL") else "FAILURE"

# #         return AutopilotStatusResponse(
# #             task_id=task_id,
# #             status=resp_status,  # type: ignore[arg-type]
# #             currentStep=5 if resp_status == "SUCCESS" else None,
# #             errorMessage=stored.get("error") if resp_status == "FAILURE" else None,
# #             result=result_obj,
# #             error=stored.get("error") if resp_status == "FAILURE" else None,
# #         )

# #     # Still running inline
# #     if task_id in _RUNNING_TASKS:
# #         return AutopilotStatusResponse(
# #             task_id=task_id,
# #             status="STARTED",
# #             currentStep=0,
# #         )

# #     # Celery result
# #     celery_app = _load_celery_app()
# #     if celery_app is None:
# #         return AutopilotStatusResponse(
# #             task_id=task_id,
# #             status="STARTED",
# #             currentStep=0,
# #             error="Pipeline is running. Poll again shortly.",
# #         )

# #     run_pipeline = celery_app.tasks.get("autopilot.run_pipeline")
# #     if run_pipeline is None:
# #         return AutopilotStatusResponse(
# #             task_id=task_id,
# #             status="PENDING",
# #             error="Celery task not registered.",
# #         )

# #     async_result = run_pipeline.AsyncResult(task_id)
# #     raw_state = str(getattr(async_result, "state", "PENDING"))
# #     ready = bool(getattr(async_result, "ready", lambda: False)())

# #     current_step: int | None = None
# #     error_message: str | None = None
# #     try:
# #         meta = getattr(async_result, "info", None)
# #         if isinstance(meta, dict):
# #             current_step = meta.get("currentStep")
# #             error_message = meta.get("error")
# #     except Exception:  # noqa: BLE001
# #         pass

# #     result_obj = None
# #     error: str | None = error_message
# #     try:
# #         if ready:
# #             successful = bool(getattr(async_result, "successful", lambda: False)())
# #             if successful:
# #                 raw_result = async_result.result
# #                 if isinstance(raw_result, dict):
# #                     try:
# #                         result_obj = AutopilotResult.model_validate(raw_result)
# #                     except Exception as exc:  # noqa: BLE001
# #                         error = f"Result parse failed: {exc}"
# #                 else:
# #                     error = f"Unexpected result type: {type(raw_result).__name__}"
# #             else:
# #                 error = str(async_result.result) or "Task failed"
# #     except Exception as exc:  # noqa: BLE001
# #         error = str(exc)

# #     normalized_state = raw_state
# #     if normalized_state not in ("PENDING", "STARTED", "SUCCESS", "FAILURE"):
# #         normalized_state = "FAILURE" if ready else "PENDING"

# #     return AutopilotStatusResponse(
# #         task_id=task_id,
# #         status=normalized_state,  # type: ignore[arg-type]
# #         currentStep=current_step,
# #         errorMessage=error_message,
# #         result=result_obj,
# #         error=error,
# #     )


# # __all__ = ["router"]

# """
# autopilot/router.py — /api/v1/autopilot endpoints.

# BACKGROUND EXECUTION FIX (this round):

# The previous version ran the pipeline synchronously inside the HTTP
# request. That was correct and bug-free for schema resolution, but it has
# a real cost: with genuine LLM calls now working (ICP analysis + prospect
# extraction + 2 calls per touch × 7 touches × N prospects), a 10-prospect
# run makes ~142 sequential calls to the LLM provider. At even a modest
# 300-500ms per call that's well over a minute — long enough to hit the
# frontend's fetch/reverse-proxy timeout, which is exactly the "Failed to
# start autopilot — check backend connection" error, even though the
# backend logs show the pipeline completing successfully every time.

# THE FIX — run in the background via asyncio.create_task(), but capture the
# tenant schema name as a PLAIN STRING before the request returns:

#     schema_name = request.state.tenant.schema_name   # captured HERE, in-request

#     async def _run_bg():
#         async with AsyncSessionLocal() as bg_db:      # a FRESH session,
#             await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
#             ...

# This is safe because:
#   - `request.state.tenant` is a plain Python object attached to the
#     request; reading `.schema_name` off it into a local string happens
#     synchronously, before the response is returned, and does not depend
#     on any dependency-injected session's lifetime.
#   - The background task opens its OWN session via AsyncSessionLocal()
#     (same as every previous "inline" fallback), and manually sets
#     search_path using the captured string — not by re-deriving it from
#     token.tenant_slug (the bug that broke every previous Celery/background
#     attempt) and not by trying to reuse the request-scoped `db` session
#     (which FastAPI tears down right after the response is sent, making it
#     unsafe to touch from a task that outlives the request).

# The frontend's existing polling logic (unchanged) already handles this
# correctly: POST returns 202 immediately with a task_id, GET polls
# /autopilot/{task_id} every few seconds until status is SUCCESS/FAILURE.
# """
# from __future__ import annotations

# import asyncio
# import uuid
# from typing import Any

# from fastapi import APIRouter, Depends, HTTPException, Request, status
# from sqlalchemy import select, text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.deps import get_db_public
# from app.api.security import require_role
# from app.schemas.auth import Role, TokenPayload
# from app.features.usage.cap_gate import enforce_llm_cap
# from app.schemas.autopilot import (
#     AutopilotCreateRequest,
#     AutopilotCreateResponse,
#     AutopilotResult,
#     AutopilotStatusResponse,
# )

# router = APIRouter(prefix="/autopilot", tags=["Autopilot"])

# # In-memory result store, keyed by task_id. Single-process, no Celery.
# _RESULTS: dict[str, dict] = {}
# _RUNNING: set[str] = set()
# # Live progress signal, keyed by task_id -> (currentStep, detail message).
# # Updated by orchestrate_pipeline's on_progress callback as the background
# # task advances, so GET /autopilot/{task_id} can show real progress instead
# # of a static 0% for the whole run (which looked like a stuck/infinite loop
# # even though the pipeline was genuinely working — just slow due to LLM
# # provider rate-limit retries).
# _PROGRESS: dict[str, tuple[int, str]] = {}


# async def _resolve_llm_config(pub_db: AsyncSession):
#     """Resolve the default active GlobalLlmConfig on the public-schema session."""
#     from types import SimpleNamespace

#     try:
#         from app.models.global_llm_config import GlobalLlmConfig
#         from app.services.secret_service import decrypt_at_rest

#         result = await pub_db.execute(
#             select(GlobalLlmConfig)
#             .where(GlobalLlmConfig.is_active.is_(True))
#             .where(GlobalLlmConfig.is_default.is_(True))
#             .limit(1)
#         )
#         row = result.scalar_one_or_none()

#         if row is None:
#             result = await pub_db.execute(
#                 select(GlobalLlmConfig)
#                 .where(GlobalLlmConfig.is_active.is_(True))
#                 .order_by(GlobalLlmConfig.id)
#                 .limit(1)
#             )
#             row = result.scalar_one_or_none()

#         if row is None:
#             return None

#         api_key = decrypt_at_rest(row.api_key_encrypted)

#         return SimpleNamespace(
#             id=row.id,
#             name=row.display_name,
#             provider=row.provider,
#             modelId=row.model_name,   # cast_llm_config() reads .modelId, not .model
#             apiKey=api_key,
#             baseUrl=row.base_url,
#             maxTokens=row.max_tokens,
#             temperature=row.temperature,
#             isActive=True,
#             isDefault=row.is_default,
#             settings=None,
#         )
#     except Exception as exc:  # noqa: BLE001
#         import structlog
#         structlog.get_logger(__name__).error(
#             "autopilot.router.llm_resolve_failed", error=str(exc)
#         )
#         return None


# @router.post(
#     "",
#     response_model=AutopilotCreateResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     dependencies=[Depends(enforce_llm_cap)],
# )
# async def enqueue_autopilot(
#     request: Request,
#     body: AutopilotCreateRequest,
#     pub_db: AsyncSession = Depends(get_db_public),
#     token: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> AutopilotCreateResponse:
#     """
#     Start an autopilot pipeline run in the background and return
#     immediately. Poll GET /autopilot/{task_id} for the result.
#     """
#     llm_cfg = await _resolve_llm_config(pub_db)
#     if llm_cfg is None:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail=(
#                 "No active LLM configuration found. "
#                 "Go to LLM Models and configure an active provider first."
#             ),
#         )

#     # SCHEMA CAPTURE FIX: read the already-resolved schema name from
#     # request.state.tenant (set by TenantMiddleware) into a plain string,
#     # RIGHT NOW, before the request returns. This is the same value
#     # `deps.get_db` uses — never re-derived from token.tenant_slug (that
#     # was the exact bug that broke every earlier Celery/background attempt).
#     _tenant = getattr(request.state, "tenant", None)
#     schema_name: str = (
#         getattr(_tenant, "schema_name", None) if _tenant else None
#     ) or "public"

#     task_id = str(uuid.uuid4())

#     llm_cfg_dict = {
#         "id": llm_cfg.id,
#         "name": llm_cfg.name,
#         "provider": llm_cfg.provider,
#         "modelId": llm_cfg.modelId,
#         "apiKey": llm_cfg.apiKey,
#         "baseUrl": llm_cfg.baseUrl,
#         "maxTokens": llm_cfg.maxTokens,
#         "temperature": llm_cfg.temperature,
#         "isActive": True,
#         "isDefault": llm_cfg.isDefault,
#         "settings": None,
#     }

#     payload: dict[str, Any] = {
#         "task_id": task_id,
#         "campaign_name": body.campaign_name,
#         "target_count": body.target_count,
#         "icp_hint": body.icp_hint,
#         "sender_role": body.sender_role,
#         "sender_company": body.sender_company,
#         "sender_offer": body.sender_offer,
#         "proof_metric": body.proof_metric,
#         "sender_product": body.sender_product,
#         "target_audience": body.target_audience,
#         "framework": body.framework,
#         "metadata": body.metadata or {},
#         "_llm_cfg": llm_cfg_dict,
#     }

#     from app.core.database import AsyncSessionLocal
#     from app.features.autopilot.service import orchestrate_pipeline

#     _RUNNING.add(task_id)
#     _PROGRESS[task_id] = (0, "Queued")

#     def _on_progress(step: int, detail: str) -> None:
#         _PROGRESS[task_id] = (step, detail)

#     async def _run_background() -> None:
#         """
#         Runs AFTER the HTTP response has already been sent. Opens its own
#         fresh session (the request-scoped `db` from get_db is torn down
#         the moment the response goes out, so it CANNOT be reused here).
#         `schema_name` was captured above, as a plain string, before this
#         closure was even created — no dependency on request/session state.
#         """
#         try:
#             async with AsyncSessionLocal() as bg_db:
#                 try:
#                     await bg_db.execute(
#                         text(f'SET search_path TO "{schema_name}", public')
#                     )
#                 except Exception:  # noqa: BLE001
#                     await bg_db.rollback()
#                     await bg_db.execute(
#                         text(f'SET search_path TO "{schema_name}", public')
#                     )
#                 result = await orchestrate_pipeline(bg_db, payload, on_progress=_on_progress)
#                 await bg_db.commit()
#                 _RESULTS[task_id] = result.model_dump(mode="json")
#         except Exception as exc:  # noqa: BLE001
#             _RESULTS[task_id] = AutopilotResult(
#                 campaign_id="",
#                 prospect_count=0,
#                 sequence_count=0,
#                 task_id=task_id,
#                 status="FAILURE",  # type: ignore[arg-type]
#                 error=f"Pipeline error: {exc}",
#             ).model_dump(mode="json")
#         finally:
#             _RUNNING.discard(task_id)

#     asyncio.create_task(_run_background())

#     return AutopilotCreateResponse(
#         task_id=task_id,
#         status="STARTED",
#         message="Pipeline running in background. Poll for the result.",
#     )


# @router.get("/{task_id}", response_model=AutopilotStatusResponse)
# async def get_autopilot_status(
#     task_id: str,
#     _: TokenPayload = Depends(require_role(Role.MANAGER)),
# ) -> AutopilotStatusResponse:
#     """Poll autopilot run status."""
#     if task_id in _RESULTS:
#         stored = _RESULTS[task_id]
#         try:
#             result_obj = AutopilotResult.model_validate(stored)
#         except Exception:  # noqa: BLE001
#             result_obj = None

#         raw_status = stored.get("status", "FAILURE")
#         resp_status = "SUCCESS" if raw_status in ("SUCCESS", "PARTIAL") else "FAILURE"

#         return AutopilotStatusResponse(
#             task_id=task_id,
#             status=resp_status,  # type: ignore[arg-type]
#             currentStep=5 if resp_status == "SUCCESS" else None,
#             errorMessage=stored.get("error") if resp_status == "FAILURE" else None,
#             result=result_obj,
#             error=stored.get("error") if resp_status == "FAILURE" else None,
#         )

#     if task_id in _RUNNING:
#         step, detail = _PROGRESS.get(task_id, (0, "Running"))
#         return AutopilotStatusResponse(
#             task_id=task_id,
#             status="STARTED",
#             currentStep=step,
#             errorMessage=detail or None,
#         )

#     return AutopilotStatusResponse(
#         task_id=task_id,
#         status="PENDING",
#         error="Task not found (may not have started yet, or server restarted).",
#     )


# __all__ = ["router"]
"""
autopilot/router.py — /api/v1/autopilot endpoints.

BACKGROUND EXECUTION FIX (this round):

The previous version ran the pipeline synchronously inside the HTTP
request. That was correct and bug-free for schema resolution, but it has
a real cost: with genuine LLM calls now working (ICP analysis + prospect
extraction + 2 calls per touch × 7 touches × N prospects), a 10-prospect
run makes ~142 sequential calls to the LLM provider. At even a modest
300-500ms per call that's well over a minute — long enough to hit the
frontend's fetch/reverse-proxy timeout, which is exactly the "Failed to
start autopilot — check backend connection" error, even though the
backend logs show the pipeline completing successfully every time.

THE FIX — run in the background via asyncio.create_task(), but capture the
tenant schema name as a PLAIN STRING before the request returns:

    schema_name = request.state.tenant.schema_name   # captured HERE, in-request

    async def _run_bg():
        async with AsyncSessionLocal() as bg_db:      # a FRESH session,
            await bg_db.execute(text(f'SET search_path TO "{schema_name}", public'))
            ...

This is safe because:
  - `request.state.tenant` is a plain Python object attached to the
    request; reading `.schema_name` off it into a local string happens
    synchronously, before the response is returned, and does not depend
    on any dependency-injected session's lifetime.
  - The background task opens its OWN session via AsyncSessionLocal()
    (same as every previous "inline" fallback), and manually sets
    search_path using the captured string — not by re-deriving it from
    token.tenant_slug (the bug that broke every previous Celery/background
    attempt) and not by trying to reuse the request-scoped `db` session
    (which FastAPI tears down right after the response is sent, making it
    unsafe to touch from a task that outlives the request).

The frontend's existing polling logic (unchanged) already handles this
correctly: POST returns 202 immediately with a task_id, GET polls
/autopilot/{task_id} every few seconds until status is SUCCESS/FAILURE.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_public
from app.api.security import require_role
from app.schemas.auth import Role, TokenPayload
from app.features.usage.cap_gate import enforce_llm_cap
from app.schemas.autopilot import (
    AutopilotCreateRequest,
    AutopilotCreateResponse,
    AutopilotResult,
    AutopilotStatusResponse,
)

router = APIRouter(prefix="/autopilot", tags=["Autopilot"])

# In-memory result store, keyed by task_id. Single-process, no Celery.
_RESULTS: dict[str, dict] = {}
_RUNNING: set[str] = set()
# Live progress signal, keyed by task_id -> (currentStep, detail message).
# Updated by orchestrate_pipeline's on_progress callback as the background
# task advances, so GET /autopilot/{task_id} can show real progress instead
# of a static 0% for the whole run (which looked like a stuck/infinite loop
# even though the pipeline was genuinely working — just slow due to LLM
# provider rate-limit retries).
_PROGRESS: dict[str, tuple[int, str]] = {}


async def _resolve_llm_config(pub_db: AsyncSession):
    """Resolve the default active GlobalLlmConfig on the public-schema session."""
    from types import SimpleNamespace

    try:
        from app.models.global_llm_config import GlobalLlmConfig
        from app.services.secret_service import decrypt_at_rest

        result = await pub_db.execute(
            select(GlobalLlmConfig)
            .where(GlobalLlmConfig.is_active.is_(True))
            .where(GlobalLlmConfig.is_default.is_(True))
            .limit(1)
        )
        row = result.scalar_one_or_none()

        if row is None:
            result = await pub_db.execute(
                select(GlobalLlmConfig)
                .where(GlobalLlmConfig.is_active.is_(True))
                .order_by(GlobalLlmConfig.id)
                .limit(1)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        api_key = decrypt_at_rest(row.api_key_encrypted)

        return SimpleNamespace(
            id=row.id,
            name=row.display_name,
            provider=row.provider,
            modelId=row.model_name,   # cast_llm_config() reads .modelId, not .model
            apiKey=api_key,
            baseUrl=row.base_url,
            maxTokens=row.max_tokens,
            temperature=row.temperature,
            isActive=True,
            isDefault=row.is_default,
            settings=None,
        )
    except Exception as exc:  # noqa: BLE001
        import structlog
        structlog.get_logger(__name__).error(
            "autopilot.router.llm_resolve_failed", error=str(exc)
        )
        return None


@router.post(
    "",
    response_model=AutopilotCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_llm_cap)],
)
async def enqueue_autopilot(
    request: Request,
    body: AutopilotCreateRequest,
    pub_db: AsyncSession = Depends(get_db_public),
    token: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutopilotCreateResponse:
    """
    Start an autopilot pipeline run in the background and return
    immediately. Poll GET /autopilot/{task_id} for the result.
    """
    llm_cfg = await _resolve_llm_config(pub_db)
    if llm_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No active LLM configuration found. "
                "Go to LLM Models and configure an active provider first."
            ),
        )

    # SCHEMA CAPTURE FIX: read the already-resolved schema name from
    # request.state.tenant (set by TenantMiddleware) into a plain string,
    # RIGHT NOW, before the request returns. This is the same value
    # `deps.get_db` uses — never re-derived from token.tenant_slug (that
    # was the exact bug that broke every earlier Celery/background attempt).
    _tenant = getattr(request.state, "tenant", None)
    schema_name: str = (
        getattr(_tenant, "schema_name", None) if _tenant else None
    ) or "public"

    task_id = str(uuid.uuid4())

    llm_cfg_dict = {
        "id": llm_cfg.id,
        "name": llm_cfg.name,
        "provider": llm_cfg.provider,
        "modelId": llm_cfg.modelId,
        "apiKey": llm_cfg.apiKey,
        "baseUrl": llm_cfg.baseUrl,
        "maxTokens": llm_cfg.maxTokens,
        "temperature": llm_cfg.temperature,
        "isActive": True,
        "isDefault": llm_cfg.isDefault,
        "settings": None,
    }

    payload: dict[str, Any] = {
        "task_id": task_id,
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
        "_llm_cfg": llm_cfg_dict,
    }

    from app.core.database import AsyncSessionLocal
    from app.features.autopilot.service import orchestrate_pipeline

    _RUNNING.add(task_id)
    _PROGRESS[task_id] = (0, "Queued")

    # SAFETY-NET TIMEOUT: the per-touch hard timeout in service.py already
    # bounds each individual LLM call, and the retry logic in call_llm() is
    # itself bounded — so the pipeline should always finish. This is a
    # belt-and-suspenders ceiling on the WHOLE run: if something genuinely
    # unforeseen stalls it (e.g. a bug outside our own bounded-timeout code
    # paths), the task is guaranteed to resolve to a FAILURE result instead
    # of sitting in `_RUNNING` forever with no way for the frontend to ever
    # stop polling productively.
    _PIPELINE_TIMEOUT_SECONDS = 20 * 60  # 20 minutes

    def _on_progress(step: int, detail: str) -> None:
        _PROGRESS[task_id] = (step, detail)

    async def _run_background() -> None:
        """
        Runs AFTER the HTTP response has already been sent. Opens its own
        fresh session (the request-scoped `db` from get_db is torn down
        the moment the response goes out, so it CANNOT be reused here).
        `schema_name` was captured above, as a plain string, before this
        closure was even created — no dependency on request/session state.
        """
        try:
            async with AsyncSessionLocal() as bg_db:
                try:
                    await bg_db.execute(
                        text(f'SET search_path TO "{schema_name}", public')
                    )
                except Exception:  # noqa: BLE001
                    await bg_db.rollback()
                    await bg_db.execute(
                        text(f'SET search_path TO "{schema_name}", public')
                    )
                result = await asyncio.wait_for(
                    orchestrate_pipeline(bg_db, payload, on_progress=_on_progress),
                    timeout=_PIPELINE_TIMEOUT_SECONDS,
                )
                await bg_db.commit()
                _RESULTS[task_id] = result.model_dump(mode="json")
        except asyncio.TimeoutError:
            _RESULTS[task_id] = AutopilotResult(
                campaign_id="",
                prospect_count=0,
                sequence_count=0,
                task_id=task_id,
                status="FAILURE",  # type: ignore[arg-type]
                error=(
                    f"Pipeline exceeded the {_PIPELINE_TIMEOUT_SECONDS}s safety "
                    "timeout and was stopped. Check backend logs for "
                    "'autopilot.emails.heartbeat' entries to see how far it got."
                ),
            ).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            _RESULTS[task_id] = AutopilotResult(
                campaign_id="",
                prospect_count=0,
                sequence_count=0,
                task_id=task_id,
                status="FAILURE",  # type: ignore[arg-type]
                error=f"Pipeline error: {exc}",
            ).model_dump(mode="json")
        finally:
            _RUNNING.discard(task_id)

    asyncio.create_task(_run_background())

    return AutopilotCreateResponse(
        task_id=task_id,
        status="STARTED",
        message="Pipeline running in background. Poll for the result.",
    )


@router.get("/{task_id}", response_model=AutopilotStatusResponse)
async def get_autopilot_status(
    task_id: str,
    _: TokenPayload = Depends(require_role(Role.MANAGER)),
) -> AutopilotStatusResponse:
    """Poll autopilot run status."""
    if task_id in _RESULTS:
        stored = _RESULTS[task_id]
        try:
            result_obj = AutopilotResult.model_validate(stored)
        except Exception:  # noqa: BLE001
            result_obj = None

        raw_status = stored.get("status", "FAILURE")
        resp_status = "SUCCESS" if raw_status in ("SUCCESS", "PARTIAL") else "FAILURE"

        return AutopilotStatusResponse(
            task_id=task_id,
            status=resp_status,  # type: ignore[arg-type]
            currentStep=5 if resp_status == "SUCCESS" else None,
            errorMessage=stored.get("error") if resp_status == "FAILURE" else None,
            result=result_obj,
            error=stored.get("error") if resp_status == "FAILURE" else None,
        )

    if task_id in _RUNNING:
        step, detail = _PROGRESS.get(task_id, (0, "Running"))
        return AutopilotStatusResponse(
            task_id=task_id,
            status="STARTED",
            currentStep=step,
            errorMessage=detail or None,
        )

    return AutopilotStatusResponse(
        task_id=task_id,
        status="PENDING",
        error="Task not found (may not have started yet, or server restarted).",
    )


__all__ = ["router"]
