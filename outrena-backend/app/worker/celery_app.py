# """
# celery_app.py — Celery application + autopilot task.

# Phase 5 deliverable per migration §6.3 L873-897 + audit-A3 finding #5/#6:

#   - Defines `celery_app = Celery("outrena", broker=..., backend=...)`
#     consuming CELERY_BROKER_URL / CELERY_RESULT_BACKEND from settings.
#   - Configuration:
#       task_time_limit=900 (15 min, §6.3)
#       task_track_started=True
#       worker_prefetch_multiplier=1 (fair scheduling, one task per worker)
#       task_acks_late=True (re-queue on worker crash)
#   - Defines `@celery_app.task(name="autopilot.run_pipeline", bind=True)`
#     that wraps the async orchestrator `orchestrate_pipeline`.

# This file is the import target of the deployment's
# `celery -A app.worker.celery_app worker` command (referenced by
# docker-compose.prod.yml, k8s worker-deployment.yaml, ECS worker task
# definition, Terraform aws/ecs_worker.tf + azure/container_apps.tf).

# Note on graceful import: Celery is an optional dependency (the backend
# container does not run the worker, so Celery isn't needed there). We wrap the
# Celery import in a try/except so this module compiles + imports cleanly even
# when Celery isn't installed, but the @celery_app.task decorator is only
# registered when Celery IS installed — which it must be in the worker
# container that runs `celery -A app.worker.celery_app worker`.
# """
# from __future__ import annotations

# import asyncio
# from typing import Any

# from sqlalchemy import text

# from app.core.config import get_settings
# from app.core.database import AsyncSessionLocal

# # ── Celery import — graceful fallback if the package is missing ───────────
# #
# # py_compile never executes imports, so this module always compiles cleanly.
# # At runtime, if Celery is installed (the worker container has it), the
# # celery_app is fully functional. If Celery isn't installed (the FastAPI
# # app container, which never runs a worker), `celery_app` is None and the
# # @celery_app.task decorator degrades to a no-op pass-through.
# try:
#     from celery import Celery, Task  # type: ignore[import-untyped]
#     _CELERY_AVAILABLE = True
# except ImportError:  # pragma: no cover — exercised only on app container
#     _CELERY_AVAILABLE = False
#     Celery = None  # type: ignore[assignment, misc]
#     Task = object  # type: ignore[assignment, misc]


# def _crontab(*args: Any, **kwargs: Any) -> Any:
#     """Lazy wrapper around celery.schedules.crontab (only importable when
#     Celery is installed). When Celery isn't installed we return None —
#     the beat_schedule entries become inert (the worker process won't run
#     a beat scheduler anyway).
#     """
#     if not _CELERY_AVAILABLE:
#         return None
#     from celery.schedules import crontab  # type: ignore[import-untyped]

#     return crontab(*args, **kwargs)


# def _build_celery_app() -> "Celery | None":
#     """Construct the Celery application per §6.3."""
#     if not _CELERY_AVAILABLE:
#         return None
#     settings = get_settings()
#     app = Celery(
#         "outrena",
#         broker=settings.CELERY_BROKER_URL,
#         backend=settings.CELERY_RESULT_BACKEND,
#     )
#     app.conf.update(
#         task_time_limit=900,            # 15 min hard kill (§6.3 L897)
#         task_soft_time_limit=840,       # 14 min soft → raise SoftTimeLimitExceeded
#         task_track_started=True,        # expose STARTED state to pollers
#         worker_prefetch_multiplier=1,   # fair scheduling, one task per worker
#         task_acks_late=True,            # re-queue on worker crash
#         result_extended=True,           # include task name + args in result meta
#         result_expires=60 * 60 * 24,    # 24h
#         broker_connection_retry_on_startup=True,
#         # ── Beat schedule (FIX-BE-1 / HIGH 7 + MEDIUM 11 + MEDIUM 12) ───────
#         # Three nightly jobs wire the previously-orphaned service helpers:
#         #   1. usage.rebuild_cost_summaries — materializes cost_summaries
#         #      rows for every active tenant (UsageService.rebuild_all_tenants).
#         #   2. retention.enforce_all — runs the retention policy sweep across
#         #      every active tenant (RetentionService.enforce_all_policies).
#         #   3. weekly_digest.send_pending — sends any queued weekly digest
#         #      emails (WeeklyDigestService) on Monday 08:00 UTC.
#         # All three run via `celery -A app.worker.celery_app beat` (cron
#         # sidecar in k8s/terraform). Each entry uses a CrontabSchedule so
#         # the schedule survives worker restarts.
#         beat_schedule={
#             "usage-rebuild-cost-summaries-nightly": {
#                 "task": "usage.rebuild_cost_summaries",
#                 "schedule": _crontab(hour=2, minute=15),  # 02:15 UTC nightly
#             },
#             "retention-enforce-all-nightly": {
#                 "task": "retention.enforce_all",
#                 "schedule": _crontab(hour=3, minute=30),  # 03:30 UTC nightly
#             },
#             "weekly-digest-send-pending": {
#                 # FR-059: hourly on Mondays; each run only delivers to tenants
#                 # whose LOCAL time is currently 09:xx (local_hour_gate=9), so
#                 # every tenant receives their digest at 09:00 recipient-local.
#                 "task": "weekly_digest.send_pending",
#                 "schedule": _crontab(minute=0, day_of_week=1),  # Mon, every hour
#                 "kwargs": {"local_hour_gate": 9},
#             },
#         },
#     )
#     return app


# celery_app: "Celery | None" = _build_celery_app()


# def _register_autopilot_task(app: "Celery | None") -> Any:
#     """Register the autopilot.run_pipeline task on the Celery app.

#     If Celery isn't installed, returns a plain no-op function so the
#     module imports cleanly for the FastAPI process (which never invokes
#     the task directly — it enqueues via `app.send_task("autopilot.run_pipeline", ...)`
#     which itself only requires the broker URL, not the Celery package
#     on the producer side).
#     """
#     if app is None:
#         # Fallback for environments without Celery installed — callers
#         # can still execute the orchestrator directly (useful for tests).
#         def _noop_task(payload: dict[str, Any]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
#             from app.features.autopilot.service import orchestrate_pipeline

#             async def _run() -> dict[str, Any]:
#                 schema = payload.get("schema_name", "public")
#                 async with AsyncSessionLocal() as session:
#                     await session.execute(
#                         text(f'SET search_path TO "{schema}", public')
#                     )
#                     result = await orchestrate_pipeline(session, payload)
#                     await session.commit()
#                     return result.model_dump()

#             return asyncio.run(_run())

#         _noop_task.name = "autopilot.run_pipeline"  # type: ignore[attr-defined]
#         return _noop_task

#     @app.task(name="autopilot.run_pipeline", bind=True, time_limit=900, track_started=True)
#     def run_autopilot_pipeline(self: Task, payload: dict[str, Any]) -> dict[str, Any]:
#         """Synchronous Celery wrapper around the async orchestrator (§6.3).

#         Runs the entire ICP → source → campaign → email pipeline inside a
#         fresh asyncio event loop. `self` is the bound Task instance — used
#         by Celery for state tracking + retry semantics. The orchestrator
#         itself performs per-step try/except + partial-result persistence
#         (Risk #13 mitigation), so a single sub-task failure doesn't lose
#         the work done by earlier steps.
#         """
#         async def _run() -> dict[str, Any]:
#             schema = payload.get("schema_name", "public")
#             async with AsyncSessionLocal() as session:
#                 await session.execute(
#                     text(f'SET search_path TO "{schema}", public')
#                 )
#                 result = await orchestrate_pipeline(session, payload)
#                 await session.commit()
#                 return result.model_dump()

#         return asyncio.run(_run())

#     return run_autopilot_pipeline


# run_autopilot_pipeline = _register_autopilot_task(celery_app)


# def _register_nightly_tasks(app: "Celery | None") -> Any:
#     """Register the three nightly beat tasks.

#     FIX-BE-1 / HIGH 7 + MEDIUM 11 + MEDIUM 12: previously
#     UsageService.rebuild_cost_summaries / RetentionService.enforce_all_policies
#     / WeeklyDigestService.send_pending were defined but never invoked — the
#     retention router exposes a manual SUPER_ADMIN trigger, but production
#     needs an unattended nightly sweep. Each task is registered with a
#     unique name so the beat scheduler can address them by string id; if
#     Celery isn't installed, the fallback returns the underlying async
#     function (useful for tests / direct invocation).

#     Each task opens its own AsyncSessionLocal + commits independently —
#     they never share state with the request that scheduled them.
#     """
#     if app is None:
#         async def _rebuild_cost_summaries() -> dict[str, Any]:
#             from datetime import datetime, timezone

#             from app.features.usage.service import UsageService

#             period = datetime.now(timezone.utc).strftime("%Y-%m")
#             async with AsyncSessionLocal() as session:
#                 return await UsageService().rebuild_all_tenants(period)

#         async def _enforce_retention() -> dict[str, Any]:
#             from sqlalchemy import text

#             from app.features.gdpr.retention_service import RetentionService

#             results: dict[str, Any] = {}
#             async with AsyncSessionLocal() as session:
#                 await session.execute(text('SET search_path TO "public"'))
#                 rows = (
#                     await session.execute(
#                         text(
#                             "SELECT slug FROM public.tenants "
#                             "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
#                         )
#                     )
#                 ).fetchall()
#             for row in rows:
#                 try:
#                     results[row.slug] = await RetentionService().enforce_all_policies(
#                         row.slug
#                     )
#                 except Exception as exc:  # noqa: BLE001
#                     results[row.slug] = {"error": str(exc)}
#             return results

#         async def _send_weekly_digests(local_hour_gate: int | None = None) -> dict[str, Any]:
#             try:
#                 from app.features.weekly_digest.service import WeeklyDigestService

#                 return await WeeklyDigestService().send_pending(  # type: ignore[attr-defined]
#                     local_hour_gate=local_hour_gate
#                 )
#             except (AttributeError, ImportError):
#                 return {"ok": False, "message": "weekly_digest_service.send_pending not implemented"}

#         _rebuild_cost_summaries.name = "usage.rebuild_cost_summaries"  # type: ignore[attr-defined]
#         _enforce_retention.name = "retention.enforce_all"  # type: ignore[attr-defined]
#         _send_weekly_digests.name = "weekly_digest.send_pending"  # type: ignore[attr-defined]
#         return {
#             "usage.rebuild_cost_summaries": _rebuild_cost_summaries,
#             "retention.enforce_all": _enforce_retention,
#             "weekly_digest.send_pending": _send_weekly_digests,
#         }

#     @app.task(name="usage.rebuild_cost_summaries", time_limit=1800)
#     def rebuild_cost_summaries() -> dict[str, Any]:
#         """Nightly 02:15 UTC — materialize cost_summaries for every tenant.

#         Wraps UsageService.rebuild_all_tenants(period=current YYYY-MM).
#         """
#         async def _run() -> dict[str, Any]:
#             from datetime import datetime, timezone

#             from app.features.usage.service import UsageService

#             period = datetime.now(timezone.utc).strftime("%Y-%m")
#             return await UsageService().rebuild_all_tenants(period)

#         return asyncio.run(_run())

#     @app.task(name="retention.enforce_all", time_limit=3600)
#     def enforce_retention() -> dict[str, Any]:
#         """Nightly 03:30 UTC — run retention enforcement across all tenants.

#         Iterates public.tenants WHERE status='ACTIVE' and runs
#         RetentionService.enforce_all_policies for each slug. Per-tenant
#         errors are collected (one tenant failing does not abort the rest).
#         """
#         async def _run() -> dict[str, Any]:
#             from sqlalchemy import text

#             from app.features.gdpr.retention_service import RetentionService

#             results: dict[str, Any] = {}
#             async with AsyncSessionLocal() as session:
#                 await session.execute(text('SET search_path TO "public"'))
#                 rows = (
#                     await session.execute(
#                         text(
#                             "SELECT slug FROM public.tenants "
#                             "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
#                         )
#                     )
#                 ).fetchall()
#             for row in rows:
#                 try:
#                     results[row.slug] = await RetentionService().enforce_all_policies(
#                         row.slug
#                     )
#                 except Exception as exc:  # noqa: BLE001
#                     results[row.slug] = {"error": str(exc)}
#             return results

#         return asyncio.run(_run())

#     @app.task(name="weekly_digest.send_pending", time_limit=1800)
#     def send_weekly_digests(local_hour_gate: int | None = None) -> dict[str, Any]:
#         """Hourly on Mondays — deliver digests at 09:00 recipient-local.

#         FR-059: the beat schedule fires every hour on Mondays with
#         ``local_hour_gate=9``; only tenants whose configured local time is
#         currently 09:xx receive the digest on any given run. Tolerates the
#         method not being implemented yet so the beat scheduler still starts
#         cleanly during early Phase 3 bring-up.
#         """
#         async def _run() -> dict[str, Any]:
#             try:
#                 from app.features.weekly_digest.service import WeeklyDigestService

#                 return await WeeklyDigestService().send_pending(  # type: ignore[attr-defined]
#                     local_hour_gate=local_hour_gate
#                 )
#             except (AttributeError, ImportError) as exc:
#                 return {"ok": False, "message": str(exc)}

#         return asyncio.run(_run())

#     return {
#         "usage.rebuild_cost_summaries": rebuild_cost_summaries,
#         "retention.enforce_all": enforce_retention,
#         "weekly_digest.send_pending": send_weekly_digests,
#     }


# _nightly_tasks = _register_nightly_tasks(celery_app)


# __all__ = [
#     "celery_app",
#     "run_autopilot_pipeline",
#     "rebuild_cost_summaries",
#     "enforce_retention",
#     "send_weekly_digests",
# ]

# # Expose the registered task callables (or async fallbacks when Celery is
# # not installed) at module top-level for direct invocation in tests /
# # scripts.
# rebuild_cost_summaries = _nightly_tasks["usage.rebuild_cost_summaries"]
# enforce_retention = _nightly_tasks["retention.enforce_all"]
# send_weekly_digests = _nightly_tasks["weekly_digest.send_pending"]
"""
celery_app.py — Celery application + autopilot task.

Phase 5 deliverable per migration §6.3 L873-897 + audit-A3 finding #5/#6:

  - Defines `celery_app = Celery("outrena", broker=..., backend=...)`
    consuming CELERY_BROKER_URL / CELERY_RESULT_BACKEND from settings.
  - Configuration:
      task_time_limit=900 (15 min, §6.3)
      task_track_started=True
      worker_prefetch_multiplier=1 (fair scheduling, one task per worker)
      task_acks_late=True (re-queue on worker crash)
  - Defines `@celery_app.task(name="autopilot.run_pipeline", bind=True)`
    that wraps the async orchestrator `orchestrate_pipeline`.

This file is the import target of the deployment's
`celery -A app.worker.celery_app worker` command (referenced by
docker-compose.prod.yml, k8s worker-deployment.yaml, ECS worker task
definition, Terraform aws/ecs_worker.tf + azure/container_apps.tf).

Note on graceful import: Celery is an optional dependency (the backend
container does not run the worker, so Celery isn't needed there). We wrap the
Celery import in a try/except so this module compiles + imports cleanly even
when Celery isn't installed, but the @celery_app.task decorator is only
registered when Celery IS installed — which it must be in the worker
container that runs `celery -A app.worker.celery_app worker`.
"""
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
import app.models.config_models       # REQUIRED: registers LlmConfig, Domain, etc. before Campaign mapper resolves relationships
import app.models.phase3_models
import app.models.campaign_models
import app.models.global_llm_config
import app.models.prospect_models
import app.models.flow_models


# ── Celery import — graceful fallback if the package is missing ───────────
#
# py_compile never executes imports, so this module always compiles cleanly.
# At runtime, if Celery is installed (the worker container has it), the
# celery_app is fully functional. If Celery isn't installed (the FastAPI
# app container, which never runs a worker), `celery_app` is None and the
# @celery_app.task decorator degrades to a no-op pass-through.
try:
    from celery import Celery, Task  # type: ignore[import-untyped]
    _CELERY_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised only on app container
    _CELERY_AVAILABLE = False
    Celery = None  # type: ignore[assignment, misc]
    Task = object  # type: ignore[assignment, misc]


def _crontab(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper around celery.schedules.crontab (only importable when
    Celery is installed). When Celery isn't installed we return None —
    the beat_schedule entries become inert (the worker process won't run
    a beat scheduler anyway).
    """
    if not _CELERY_AVAILABLE:
        return None
    from celery.schedules import crontab  # type: ignore[import-untyped]

    return crontab(*args, **kwargs)


def _build_celery_app() -> "Celery | None":
    """Construct the Celery application per §6.3."""
    if not _CELERY_AVAILABLE:
        return None
    settings = get_settings()
    app = Celery(
        "outrena",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    app.conf.update(
        task_time_limit=900,            # 15 min hard kill (§6.3 L897)
        task_soft_time_limit=840,       # 14 min soft → raise SoftTimeLimitExceeded
        task_track_started=True,        # expose STARTED state to pollers
        worker_prefetch_multiplier=1,   # fair scheduling, one task per worker
        task_acks_late=True,            # re-queue on worker crash
        result_extended=True,           # include task name + args in result meta
        result_expires=60 * 60 * 24,    # 24h
        broker_connection_retry_on_startup=True,
        # ── Beat schedule (FIX-BE-1 / HIGH 7 + MEDIUM 11 + MEDIUM 12) ───────
        # Three nightly jobs wire the previously-orphaned service helpers:
        #   1. usage.rebuild_cost_summaries — materializes cost_summaries
        #      rows for every active tenant (UsageService.rebuild_all_tenants).
        #   2. retention.enforce_all — runs the retention policy sweep across
        #      every active tenant (RetentionService.enforce_all_policies).
        #   3. weekly_digest.send_pending — sends any queued weekly digest
        #      emails (WeeklyDigestService) on Monday 08:00 UTC.
        # All three run via `celery -A app.worker.celery_app beat` (cron
        # sidecar in k8s/terraform). Each entry uses a CrontabSchedule so
        # the schedule survives worker restarts.
        beat_schedule={
            "usage-rebuild-cost-summaries-nightly": {
                "task": "usage.rebuild_cost_summaries",
                "schedule": _crontab(hour=2, minute=15),  # 02:15 UTC nightly
            },
            "retention-enforce-all-nightly": {
                "task": "retention.enforce_all",
                "schedule": _crontab(hour=3, minute=30),  # 03:30 UTC nightly
            },
            "weekly-digest-send-pending": {
                # FR-059: hourly on Mondays; each run only delivers to tenants
                # whose LOCAL time is currently 09:xx (local_hour_gate=9), so
                # every tenant receives their digest at 09:00 recipient-local.
                "task": "weekly_digest.send_pending",
                "schedule": _crontab(minute=0, day_of_week=1),  # Mon, every hour
                "kwargs": {"local_hour_gate": 9},
            },
        },
    )
    return app


celery_app: "Celery | None" = _build_celery_app()


def _register_autopilot_task(app: "Celery | None") -> Any:
    """Register the autopilot.run_pipeline task on the Celery app.

    If Celery isn't installed, returns a plain no-op function so the
    module imports cleanly for the FastAPI process (which never invokes
    the task directly — it enqueues via `app.send_task("autopilot.run_pipeline", ...)`
    which itself only requires the broker URL, not the Celery package
    on the producer side).
    """
    if app is None:
        # Fallback for environments without Celery installed — callers
        # can still execute the orchestrator directly (useful for tests).
        def _noop_task(payload: dict[str, Any]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
            from app.features.autopilot.service import orchestrate_pipeline

            async def _run() -> dict[str, Any]:
                schema = payload.get("schema_name", "public")
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text(f'SET search_path TO "{schema}", public')
                    )
                    result = await orchestrate_pipeline(session, payload)
                    await session.commit()
                    return result.model_dump()

            return asyncio.run(_run())

        _noop_task.name = "autopilot.run_pipeline"  # type: ignore[attr-defined]
        return _noop_task

    @app.task(name="autopilot.run_pipeline", bind=True, time_limit=900, track_started=True)
    def run_autopilot_pipeline(self: Task, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous Celery wrapper around the async orchestrator (§6.3).

        Runs the entire ICP → source → campaign → email pipeline inside a
        fresh asyncio event loop. `self` is the bound Task instance — used
        by Celery for state tracking + retry semantics. The orchestrator
        itself performs per-step try/except + partial-result persistence
        (Risk #13 mitigation), so a single sub-task failure doesn't lose
        the work done by earlier steps.
        """
        async def _run() -> dict[str, Any]:
            # Create a FRESH engine + session inside this event loop to avoid
            # "Future attached to a different loop" from the module-level pool.
            from sqlalchemy.ext.asyncio import (
                async_sessionmaker,
                create_async_engine,
            )
            from app.core.config import get_settings
            settings = get_settings()
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=5,
                # FIX: see app/core/database.py._build_engine for full
                # rationale. Schema-per-tenant search_path switching is
                # incompatible with asyncpg's default prepared-statement
                # cache; disabling it prevents stale/mismatched cached plans
                # from surfacing as generic "current transaction is aborted"
                # errors on statements that are otherwise completely valid.
                connect_args={"statement_cache_size": 0},
            )
            _session_factory = async_sessionmaker(
                bind=_engine,
                expire_on_commit=False,
                autoflush=False,
            )
            from app.features.autopilot.service import orchestrate_pipeline as orchestrate_pipeline  # noqa: PLC0415
            # Import all models so SQLAlchemy mapper relationships resolve correctly
            import app.models.config_models    # noqa: F401, PLC0415  — registers LlmConfig mapper before Campaign
            import app.models.global_llm_config  # noqa: F401, PLC0415
            import app.models.phase3_models  # noqa: F401, PLC0415
            import app.models.campaign_models  # noqa: F401, PLC0415
            import app.models.prospect_models  # noqa: F401, PLC0415
            import app.models.flow_models  # noqa: F401, PLC0415
            schema = payload.get("schema_name", "public")
            try:
                async with _session_factory() as session:
                    # Set search_path; use ROLLBACK first to ensure clean state
                    try:
                        await session.execute(
                            text(f'SET search_path TO "{schema}", public')
                        )
                    except Exception:
                        await session.rollback()
                        await session.execute(
                            text(f'SET search_path TO "{schema}", public')
                        )
                    # Add tenant schema to payload so orchestrator can re-set if needed
                    payload["schema_name"] = schema
                    result = await orchestrate_pipeline(session, payload)

                    # DEFENSIVE COMMIT (fix): orchestrate_pipeline is expected to
                    # roll back internally on any failure, but if it doesn't —
                    # or if anything else left the session in a "pending
                    # rollback" state — calling session.commit() directly here
                    # would raise PendingRollbackError and crash the WHOLE
                    # Celery task with an unhandled exception, discarding the
                    # AutopilotResult we already have in `result`. Instead:
                    # try to commit; if that fails, roll back and still return
                    # the already-computed result (with its own status/error
                    # fields intact) rather than letting the task die.
                    try:
                        await session.commit()
                    except Exception as commit_exc:  # noqa: BLE001
                        import structlog
                        structlog.get_logger(__name__).error(
                            "autopilot.celery.commit_failed_after_pipeline",
                            error=str(commit_exc),
                            pipeline_status=getattr(result, "status", None),
                            exc_info=True,
                        )
                        try:
                            await session.rollback()
                        except Exception:  # noqa: BLE001
                            pass
                        # Surface the commit failure on the result instead of
                        # crashing the task, so the frontend gets a real
                        # FAILURE response instead of an opaque Celery error.
                        try:
                            result_dict = result.model_dump()
                        except Exception:  # noqa: BLE001
                            result_dict = {
                                "campaign_id": "", "prospect_count": 0,
                                "sequence_count": 0,
                                "task_id": payload.get("task_id", ""),
                                "status": "FAILURE",
                            }
                        result_dict["status"] = "FAILURE"
                        result_dict["error"] = (
                            f"Pipeline completed but commit failed: {commit_exc}"
                        )
                        return result_dict

                    return result.model_dump()
            finally:
                await _engine.dispose()

        return asyncio.run(_run())

    return run_autopilot_pipeline


run_autopilot_pipeline = _register_autopilot_task(celery_app)


def _register_nightly_tasks(app: "Celery | None") -> Any:
    """Register the three nightly beat tasks.

    FIX-BE-1 / HIGH 7 + MEDIUM 11 + MEDIUM 12: previously
    UsageService.rebuild_cost_summaries / RetentionService.enforce_all_policies
    / WeeklyDigestService.send_pending were defined but never invoked — the
    retention router exposes a manual SUPER_ADMIN trigger, but production
    needs an unattended nightly sweep. Each task is registered with a
    unique name so the beat scheduler can address them by string id; if
    Celery isn't installed, the fallback returns the underlying async
    function (useful for tests / direct invocation).

    Each task opens its own AsyncSessionLocal + commits independently —
    they never share state with the request that scheduled them.
    """
    if app is None:
        async def _rebuild_cost_summaries() -> dict[str, Any]:
            from datetime import datetime, timezone

            from app.features.usage.service import UsageService

            period = datetime.now(timezone.utc).strftime("%Y-%m")
            async with AsyncSessionLocal() as session:
                return await UsageService().rebuild_all_tenants(period)

        async def _enforce_retention() -> dict[str, Any]:
            from sqlalchemy import text

            from app.features.gdpr.retention_service import RetentionService

            results: dict[str, Any] = {}
            async with AsyncSessionLocal() as session:
                await session.execute(text('SET search_path TO "public"'))
                rows = (
                    await session.execute(
                        text(
                            "SELECT slug FROM public.tenants "
                            "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                        )
                    )
                ).fetchall()
            for row in rows:
                try:
                    results[row.slug] = await RetentionService().enforce_all_policies(
                        row.slug
                    )
                except Exception as exc:  # noqa: BLE001
                    results[row.slug] = {"error": str(exc)}
            return results

        async def _send_weekly_digests(local_hour_gate: int | None = None) -> dict[str, Any]:
            try:
                from app.features.weekly_digest.service import WeeklyDigestService

                return await WeeklyDigestService().send_pending(  # type: ignore[attr-defined]
                    local_hour_gate=local_hour_gate
                )
            except (AttributeError, ImportError):
                return {"ok": False, "message": "weekly_digest_service.send_pending not implemented"}

        _rebuild_cost_summaries.name = "usage.rebuild_cost_summaries"  # type: ignore[attr-defined]
        _enforce_retention.name = "retention.enforce_all"  # type: ignore[attr-defined]
        _send_weekly_digests.name = "weekly_digest.send_pending"  # type: ignore[attr-defined]
        return {
            "usage.rebuild_cost_summaries": _rebuild_cost_summaries,
            "retention.enforce_all": _enforce_retention,
            "weekly_digest.send_pending": _send_weekly_digests,
        }

    @app.task(name="usage.rebuild_cost_summaries", time_limit=1800)
    def rebuild_cost_summaries() -> dict[str, Any]:
        """Nightly 02:15 UTC — materialize cost_summaries for every tenant.

        Wraps UsageService.rebuild_all_tenants(period=current YYYY-MM).
        """
        async def _run() -> dict[str, Any]:
            from datetime import datetime, timezone

            from app.features.usage.service import UsageService

            period = datetime.now(timezone.utc).strftime("%Y-%m")
            return await UsageService().rebuild_all_tenants(period)

        return asyncio.run(_run())

    @app.task(name="retention.enforce_all", time_limit=3600)
    def enforce_retention() -> dict[str, Any]:
        """Nightly 03:30 UTC — run retention enforcement across all tenants.

        Iterates public.tenants WHERE status='ACTIVE' and runs
        RetentionService.enforce_all_policies for each slug. Per-tenant
        errors are collected (one tenant failing does not abort the rest).
        """
        async def _run() -> dict[str, Any]:
            from sqlalchemy import text

            from app.features.gdpr.retention_service import RetentionService

            results: dict[str, Any] = {}
            async with AsyncSessionLocal() as session:
                await session.execute(text('SET search_path TO "public"'))
                rows = (
                    await session.execute(
                        text(
                            "SELECT slug FROM public.tenants "
                            "WHERE deleted_at IS NULL AND status = 'ACTIVE'"
                        )
                    )
                ).fetchall()
            for row in rows:
                try:
                    results[row.slug] = await RetentionService().enforce_all_policies(
                        row.slug
                    )
                except Exception as exc:  # noqa: BLE001
                    results[row.slug] = {"error": str(exc)}
            return results

        return asyncio.run(_run())

    @app.task(name="weekly_digest.send_pending", time_limit=1800)
    def send_weekly_digests(local_hour_gate: int | None = None) -> dict[str, Any]:
        """Hourly on Mondays — deliver digests at 09:00 recipient-local.

        FR-059: the beat schedule fires every hour on Mondays with
        ``local_hour_gate=9``; only tenants whose configured local time is
        currently 09:xx receive the digest on any given run. Tolerates the
        method not being implemented yet so the beat scheduler still starts
        cleanly during early Phase 3 bring-up.
        """
        async def _run() -> dict[str, Any]:
            try:
                from app.features.weekly_digest.service import WeeklyDigestService

                return await WeeklyDigestService().send_pending(  # type: ignore[attr-defined]
                    local_hour_gate=local_hour_gate
                )
            except (AttributeError, ImportError) as exc:
                return {"ok": False, "message": str(exc)}

        return asyncio.run(_run())

    return {
        "usage.rebuild_cost_summaries": rebuild_cost_summaries,
        "retention.enforce_all": enforce_retention,
        "weekly_digest.send_pending": send_weekly_digests,
    }


_nightly_tasks = _register_nightly_tasks(celery_app)


__all__ = [
    "celery_app",
    "run_autopilot_pipeline",
    "rebuild_cost_summaries",
    "enforce_retention",
    "send_weekly_digests",
]

# Expose the registered task callables (or async fallbacks when Celery is
# not installed) at module top-level for direct invocation in tests /
# scripts.
rebuild_cost_summaries = _nightly_tasks["usage.rebuild_cost_summaries"]
enforce_retention = _nightly_tasks["retention.enforce_all"]
send_weekly_digests = _nightly_tasks["weekly_digest.send_pending"]