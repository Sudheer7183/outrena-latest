"""app.worker — Celery worker package.

Phase 5 deliverable (migration §6.3 L873-897). The Celery app lives in
``app.worker.celery_app`` and exposes the ``autopilot.run_pipeline`` task
that wraps the async autopilot orchestrator. The deployment's worker
container is launched with::

    celery -A app.worker.celery_app worker --loglevel=info
"""
from app.worker.celery_app import celery_app, run_autopilot_pipeline

__all__ = ["celery_app", "run_autopilot_pipeline"]
