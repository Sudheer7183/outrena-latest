"""
tenant.py — Platform registry model (public schema only).

This is the ONLY model that lives in the ``public`` schema. It is queried
by TenantMiddleware on every request via raw text() SQL (see
middleware/tenant_middleware.py) to avoid coupling the registry to
tenant-schema metadata.

The ORM model exists for type-safe access in the platform admin routes
and for Alembic autogenerate support. It is NOT imported by tenant-
scoped code paths.
"""
from __future__ import annotations

from datetime import datetime

from app.core.database import Base
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Tenant(Base):
    """
    Platform tenant registry — lives in the ``public`` schema.

    One row per tenant. ``schema_name`` is the PostgreSQL schema that
    holds all tenant-scoped tables (``tenant_{slug}``). ``status``
    controls middleware access: ACTIVE → allowed, SUSPENDED → 403,
    PROVISIONING → 404 (treated as unknown until Step 6 completes).
    """

    __tablename__ = "tenants"
    __table_args__ = ({"schema": "public"},)  # explicit public schema

    tenant_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="STANDARD")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PROVISIONING"
    )  # PROVISIONING | ACTIVE | SUSPENDED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
