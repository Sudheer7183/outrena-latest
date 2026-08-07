"""
database.py — Async SQLAlchemy 2.0 engine and session factory.

Tenancy rule: application models are declared WITHOUT a schema= argument so
they bind to whatever schema the session's search_path selects. Only the
platform registry (public.tenants) is ever addressed with an explicit
schema qualifier — and it is queried with text() SQL, not an ORM model,
to keep the registry decoupled from tenant-schema metadata.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all tenant-schema models (schema-unqualified)."""


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)
