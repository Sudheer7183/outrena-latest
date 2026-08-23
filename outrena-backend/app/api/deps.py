# """
# deps.py — Request-scoped database session with tenant search_path.

# Reference model Section 3.2. SET search_path is the FIRST statement on
# every session, and 'public' stays second so shared reference tables
# resolve without qualification. Connection pooling is safe because the
# search_path is re-set on every checkout via this dependency.
# """
# from __future__ import annotations

# from collections.abc import AsyncGenerator

# from fastapi import Request
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.database import AsyncSessionLocal


# async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
#     """
#     Yield an AsyncSession locked to the resolved tenant's schema.

#     Falls back to 'public' for TenantMiddleware-exempt routes
#     (e.g. /platform/*), which query only the registry.
#     """
#     tenant = getattr(request.state, "tenant", None)
#     async with AsyncSessionLocal() as session:
#         schema = tenant.schema_name if tenant else "public"
#         await session.execute(text(f'SET search_path TO "{schema}", public'))
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise


# async def get_db_public() -> AsyncGenerator[AsyncSession, None]:
#     """
#     Yield an AsyncSession locked to the public schema only.

#     Used by /platform/* routes that only touch the registry.
#     """
#     async with AsyncSessionLocal() as session:
#         await session.execute(text('SET search_path TO "public"'))
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise


"""
deps.py — Request-scoped database session with tenant search_path.

Reference model Section 3.2. SET search_path is the FIRST statement on
every session, and 'public' stays second so shared reference tables
resolve without qualification. Connection pooling is safe because the
search_path is re-set on every checkout via this dependency.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession locked to the resolved tenant's schema.

    Falls back to 'public' for TenantMiddleware-exempt routes
    (e.g. /platform/*), which query only the registry.
    """
    tenant = getattr(request.state, "tenant", None)
    async with AsyncSessionLocal() as session:
        schema = tenant.schema_name if tenant else "public"
        await session.execute(text(f'SET search_path TO "{schema}", public'))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_public() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession locked to the public schema only.

    Used by /platform/* routes that only touch the registry.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text('SET search_path TO "public"'))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise