# """
# database.py — Async SQLAlchemy 2.0 engine and session factory.

# Tenancy rule: application models are declared WITHOUT a schema= argument so
# they bind to whatever schema the session's search_path selects. Only the
# platform registry (public.tenants) is ever addressed with an explicit
# schema qualifier — and it is queried with text() SQL, not an ORM model,
# to keep the registry decoupled from tenant-schema metadata.
# """
# from __future__ import annotations

# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )
# from sqlalchemy.orm import DeclarativeBase

# from app.core.config import get_settings


# class Base(DeclarativeBase):
#     """Declarative base for all tenant-schema models (schema-unqualified)."""


# def _build_engine() -> AsyncEngine:
#     settings = get_settings()
#     return create_async_engine(
#         settings.DATABASE_URL,
#         echo=False,
#         pool_pre_ping=True,
#         pool_size=10,
#         max_overflow=20,
#     )


# engine: AsyncEngine = _build_engine()

# AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
#     bind=engine,
#     expire_on_commit=False,
#     autoflush=False,
# )

# """
# database.py — Async SQLAlchemy 2.0 engine and session factory.

# Tenancy rule: application models are declared WITHOUT a schema= argument so
# they bind to whatever schema the session's search_path selects. Only the
# platform registry (public.tenants) is ever addressed with an explicit
# schema qualifier — and it is queried with text() SQL, not an ORM model,
# to keep the registry decoupled from tenant-schema metadata.
# """
# from __future__ import annotations

# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )
# from sqlalchemy.orm import DeclarativeBase

# from app.core.config import get_settings


# class Base(DeclarativeBase):
#     """Declarative base for all tenant-schema models (schema-unqualified)."""


# def _build_engine() -> AsyncEngine:
#     settings = get_settings()
#     return create_async_engine(
#         settings.DATABASE_URL,
#         echo=False,
#         pool_pre_ping=True,
#         pool_size=10,
#         max_overflow=20,
#     )


# engine: AsyncEngine = _build_engine()

# AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
#     bind=engine,
#     expire_on_commit=False,
#     autoflush=False,
# )

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
    """Declarative base for all tenant-schema models (schema-unqualified).

    eager_defaults=True instructs SQLAlchemy to use RETURNING on INSERT/UPDATE
    (asyncpg supports this) to fetch server-generated column values such as
    createdAt / updatedAt (server_default=func.now()) immediately after the
    statement executes — without requiring a separate SELECT. This prevents
    MissingGreenlet errors when Pydantic reads those columns on the returned
    ORM object outside of an async context.
    """
    __mapper_args__ = {"eager_defaults": True}


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        # FIX: schema-per-tenant architecture is incompatible with asyncpg's
        # default prepared-statement caching. Each tenant SETs a different
        # search_path on the SAME pooled connection; asyncpg caches prepared
        # statement plans keyed by SQL text only, not by search_path. When a
        # connection is reused across tenants/search_paths, a cached plan
        # can reference stale type OIDs or resolve to the WRONG schema's
        # table, and Postgres reports this generically as "current
        # transaction is aborted" on a later, unrelated-looking statement.
        # Disabling the cache forces asyncpg to re-prepare every statement,
        # which is the standard fix for this exact schema-per-tenant pattern
        # (documented constraint: "Schema-per-tenant ENUMs are incompatible
        # with asyncpg statement/type caching — this requires specific
        # handling").
        connect_args={"statement_cache_size": 0},
    )


engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)