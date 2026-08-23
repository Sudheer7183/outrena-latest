# """
# tenant_signup.py — Self-serve tenant signup request queue (public schema).

# A prospective tenant submits this form from the public landing page
# (POST /api/v1/tenant-signup). The row sits in PENDING_APPROVAL until a
# SUPER_ADMIN approves or rejects it via /platform/admin/signups/{id}/approve
# or /reject. On approval, TenantProvisioningService runs the full 6-step
# flow and the row transitions to PROVISIONED with tenant_id back-filled.

# Status lifecycle:
#   PENDING_APPROVAL → APPROVED → PROVISIONED (terminal success)
#   PENDING_APPROVAL → REJECTED (terminal failure)
# """
# from __future__ import annotations

# from datetime import datetime

# from app.core.database import Base
# from sqlalchemy import DateTime, ForeignKey, Integer, String, func
# from sqlalchemy.orm import Mapped, mapped_column


# class TenantSignupRequest(Base):
#     """Self-serve signup request awaiting SUPER_ADMIN review."""

#     __tablename__ = "tenant_signup_requests"
#     __table_args__ = ({"schema": "public"},)

#     id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
#     company_name: Mapped[str] = mapped_column(String(255), nullable=False)
#     subdomain: Mapped[str] = mapped_column(String(63), nullable=False)
#     owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
#     owner_first_name: Mapped[str] = mapped_column(String(120), nullable=False)
#     owner_last_name: Mapped[str] = mapped_column(String(120), nullable=False)
#     plan_id: Mapped[int] = mapped_column(
#         Integer,
#         ForeignKey("public.plans.id", ondelete="RESTRICT"),
#         nullable=False,
#     )
#     # PENDING_APPROVAL | APPROVED | REJECTED | PROVISIONED
#     status: Mapped[str] = mapped_column(
#         String(20), nullable=False, default="PENDING_APPROVAL"
#     )
#     rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
#     tenant_id: Mapped[int | None] = mapped_column(
#         Integer,
#         ForeignKey("public.tenants.tenant_id", ondelete="SET NULL"),
#         nullable=True,
#     )
#     reviewed_at: Mapped[datetime | None] = mapped_column(
#         DateTime(timezone=True), nullable=True
#     )
#     reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
#     created_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True), nullable=False, server_default=func.now()
#     )
#     # NEW (migration 0004) — requested integrations mode at signup time.
#     # "platform_managed" | "tenant_managed" (default). Passed through to
#     # TenantProvisioningService.provision_tenant → public.tenant_config row.
#     integration_mode: Mapped[str] = mapped_column(
#         String(32),
#         nullable=False,
#         default="tenant_managed",
#         server_default="tenant_managed",
#     )


# __all__ = ["TenantSignupRequest"]

"""
tenant_signup.py — Self-serve tenant signup request queue (public schema).

A prospective tenant submits this form from the public landing page
(POST /api/v1/tenant-signup). The row sits in PENDING_APPROVAL until a
SUPER_ADMIN approves or rejects it via /platform/admin/signups/{id}/approve
or /reject. On approval, TenantProvisioningService runs the full 6-step
flow and the row transitions to PROVISIONED with tenant_id back-filled.

Status lifecycle:
  PENDING_APPROVAL → APPROVED → PROVISIONED (terminal success)
  PENDING_APPROVAL → REJECTED (terminal failure)

FIX (NoReferencedTableError):
  The FKs referencing public.tenants and public.plans used to cause
  sqlalchemy.exc.NoReferencedTableError at flush/commit time because neither
  Tenant nor Plan is imported into Base.metadata in the normal request path
  (they only appear in alembic/env.py). SQLAlchemy's flush code walks the FK
  graph to sort tables by dependency order; when it can't find the referenced
  table in metadata, it raises NoReferencedTableError before any SQL runs.

  Fix: use_alter=True defers FK resolution to DDL time only (an ALTER TABLE
  ADD CONSTRAINT statement). SQLAlchemy does NOT walk use_alter FKs during
  flush/commit — it treats them as post-creation constraints. This is the
  canonical SQLAlchemy solution for cross-schema FK references where the
  referenced model is not guaranteed to be loaded in the same metadata
  instance. The actual FK constraint still exists in the database (it was
  created by the Alembic migration); this setting only affects ORM metadata
  resolution, not database-level enforcement.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class TenantSignupRequest(Base):
    """Self-serve signup request awaiting SUPER_ADMIN review."""

    __tablename__ = "tenant_signup_requests"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(63), nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "public.plans.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_signup_requests_plan_id",
        ),
        nullable=False,
    )
    # PENDING_APPROVAL | APPROVED | REJECTED | PROVISIONED
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING_APPROVAL"
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "public.tenants.tenant_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_signup_requests_tenant_id",
        ),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # NEW (migration 0004) — requested integrations mode at signup time.
    # "platform_managed" | "tenant_managed" (default). Passed through to
    # TenantProvisioningService.provision_tenant → public.tenant_config row.
    integration_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="tenant_managed",
        server_default="tenant_managed",
    )


__all__ = ["TenantSignupRequest"]
