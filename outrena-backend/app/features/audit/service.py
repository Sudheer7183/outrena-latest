"""
Feature audit — thin re-export of the shared AuditService.

The ``AuditService`` is shared across many features (audit log reads,
platform admin audit views, middleware audit writes) so it stays in
``app/services/audit_service.py``. This file re-exports it under the
feature namespace so ``app/features/audit/`` is spec-compliant per the
migration doc §3.2 (each feature folder exposes a ``service.py``).
"""
from app.services.audit_service import AuditService  # noqa: F401

__all__ = ["AuditService"]
