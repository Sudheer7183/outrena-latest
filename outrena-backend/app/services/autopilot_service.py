"""
autopilot_service.py — Autopilot orchestration service (stub).

This module provides the ``AutopilotService`` class that the
``flows/router.py`` run_flow endpoint imports. The full implementation
will be wired once the autopilot execution engine is production-ready;
this stub logs a warning and returns a failure result so that the
run_flow endpoint degrades gracefully instead of crashing with an
ImportError.
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class AutopilotService:
    """Stub autopilot service — logs a warning on execution attempts.

    The real implementation will:
      1. Load the ProspectingFlow definition
      2. Execute the SOURCE → ENRICH → GATE → SCORE → IMPORT steps
      3. Persist FlowRunStep rows for each step
      4. Update the FlowRun status to COMPLETED or FAILED

    Until then, this stub lets the flows router start a FlowRun
    without crashing. The run is marked FAILED with a clear message
    indicating the execution engine is not yet wired.
    """

    async def execute_flow_run(
        self,
        db: AsyncSession,
        run: object,
        *,
        flow: object | None = None,
        icp_profile_id: str | None = None,
    ) -> dict:
        """Attempt to execute a flow run — stub logs warning and marks FAILED.

        Parameters
        ----------
        db : AsyncSession
            Database session (used by the real implementation to persist steps).
        run : FlowRun
            The FlowRun ORM instance to execute.
        flow : ProspectingFlow, optional
            The flow definition (loaded by caller).
        icp_profile_id : str, optional
            The ICP profile to run against.

        Returns
        -------
        dict
            A result dict with ``success=False`` and an explanatory message.
        """
        logger.warning(
            "autopilot_service.execute_flow_run.stub_called",
            run_id=getattr(run, "id", None),
            flow_id=getattr(flow, "id", None) if flow else None,
            icp_profile_id=icp_profile_id,
            message="AutopilotService.execute_flow_run is a stub — "
            "the autopilot execution engine is not yet wired. "
            "The FlowRun has been marked FAILED.",
        )
        return {
            "success": False,
            "error": "Autopilot execution engine not yet wired — stub returned failure.",
        }

    async def orchestrate_pipeline(
        self,
        db: AsyncSession,
        *,
        flow_id: str,
        icp_profile_id: str,
        triggered_by: str = "autopilot",
        triggered_by_id: str | None = None,
    ) -> dict:
        """Orchestrate a full autopilot pipeline run — stub.

        This is the entry point called by the Celery task after
        POST /api/v1/autopilot enqueues a run. Returns a failure
        result so callers can handle the stub gracefully.
        """
        logger.warning(
            "autopilot_service.orchestrate_pipeline.stub_called",
            flow_id=flow_id,
            icp_profile_id=icp_profile_id,
        )
        return {
            "success": False,
            "error": "AutopilotService.orchestrate_pipeline is a stub.",
        }


__all__ = ["AutopilotService"]
