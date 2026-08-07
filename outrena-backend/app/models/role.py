"""
role.py — Tenant-scoped roles + role-permission association.

Roles are now DATA-DRIVEN per tenant (no longer the hard-coded 4-value
Role enum from schemas/auth.py — that enum stays as the system-role
identifier and is still embedded in the JWT, but each tenant can now add
custom roles via /api/v1/roles and assign permissions to them).

The four system roles — REP, MANAGER, TENANT_ADMIN, SUPER_ADMIN — are
seeded on every tenant provisioning (Step 4.5 of the 6-step flow) with
``is_system=True`` so they cannot be deleted. Custom roles added by
TENANT_ADMIN have ``is_system=False`` and are fully manageable.

Both tables live in the tenant schema (NOT public) so each tenant has its
own role set. SUPER_ADMIN is a platform-level concept and is NOT stored
here — it is implied by the Role enum claim in the JWT.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Role(Base):
    """Tenant-scoped role (custom or system)."""

    __tablename__ = "roles"
    # Schema-unqualified → binds to the tenant schema via search_path.

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.cast("false", Boolean)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RolePermission(Base):
    """Association table: role_id × permission_key (FK public.permissions.key)."""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_key: Mapped[str] = mapped_column(
        String(80),
        primary_key=True,
    )


__all__ = ["Role", "RolePermission"]
