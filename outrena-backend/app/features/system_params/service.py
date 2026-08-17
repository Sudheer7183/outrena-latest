# """system_params_service.py — SystemParameter admin CRUD + /reset re-seed.

# The /reset endpoint delegates to the ParamService provided by Fix-3 if
# available (defensive import); otherwise it falls back to a no-op.
# """
# from __future__ import annotations

# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.config_models import SystemParameter
# from app.schemas.system_params import SystemParamUpdate

# logger = structlog.get_logger(__name__)


# class SystemParamsService:
#     """Admin CRUD over SystemParameter rows."""

#     async def list_params(
#         self, db: AsyncSession, *, category: str | None = None
#     ) -> list[SystemParameter]:
#         stmt = select(SystemParameter).order_by(
#             SystemParameter.category, SystemParameter.label
#         )
#         if category:
#             stmt = stmt.where(SystemParameter.category == category)
#         result = await db.execute(stmt)
#         return list(result.scalars().all())

#     async def get_by_key(
#         self, db: AsyncSession, key: str
#     ) -> SystemParameter | None:
#         result = await db.execute(
#             select(SystemParameter).where(SystemParameter.key == key)
#         )
#         return result.scalar_one_or_none()

#     async def update_value(
#         self, db: AsyncSession, key: str, body: SystemParamUpdate
#     ) -> SystemParameter | None:
#         item = await self.get_by_key(db, key)
#         if item is None:
#             return None
#         # Range guard — only enforce if both bounds parse to float.
#         try:
#             new_val = float(body.value)
#             if item.minValue is not None:
#                 if new_val < float(item.minValue):
#                     return item  # caller should treat as no-op
#             if item.maxValue is not None:
#                 if new_val > float(item.maxValue):
#                     return item
#         except (TypeError, ValueError):
#             # Non-numeric valueType — accept as-is (string/bool/etc.).
#             pass

#         item.value = body.value
#         await db.commit()
#         item = await db.get(SystemParameter, item.id)
#         return item

#     async def reset_all(self, db: AsyncSession) -> int:
#         """
#         Re-seed all system params from param_defs.

#         Defensive import: ParamService is created by Fix-3 in parallel.
#         Calls ``ParamService.reset_params(db)`` (Fix-3 API) and falls back
#         to ``seed_params`` then to a no-op (returns current count) if
#         neither method is present.
#         """
#         try:
#             from app.features.system_params.param_service import ParamService  # type: ignore
#         except ImportError:
#             logger.warning("system_params.reset.service_not_ready")
#             result = await db.execute(select(SystemParameter))
#             return len(list(result.scalars().all()))

#         service = ParamService()
#         reset_fn = getattr(service, "reset_params", None) or getattr(
#             service, "seed_params", None
#         )
#         if reset_fn is None:
#             logger.warning("system_params.reset.no_reset_method")
#             result = await db.execute(select(SystemParameter))
#             return len(list(result.scalars().all()))
#         count = await reset_fn(db)  # type: ignore[misc]
#         return int(count) if count is not None else 0


# __all__ = ["SystemParamsService"]

"""system_params_service.py — SystemParameter admin CRUD + /reset re-seed.

The /reset endpoint delegates to the ParamService provided by Fix-3 if
available (defensive import); otherwise it falls back to a no-op.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import SystemParameter
from app.schemas.system_params import SystemParamUpdate

logger = structlog.get_logger(__name__)


class SystemParamsService:
    """Admin CRUD over SystemParameter rows."""

    async def list_params(
        self, db: AsyncSession, *, category: str | None = None
    ) -> list[SystemParameter]:
        # Auto-seed on first call: if the table is empty, run reset_all()
        # which delegates to ParamService.seed_params(). This ensures the
        # System Parameters page is never blank on first load after a fresh
        # database — the user only sees content, not an empty state.
        count_result = await db.execute(select(SystemParameter).limit(1))
        if count_result.scalar_one_or_none() is None:
            try:
                await self.reset_all(db)
            except Exception as seed_exc:
                logger.warning("system_params.auto_seed_failed", error=str(seed_exc))

        stmt = select(SystemParameter).order_by(
            SystemParameter.category, SystemParameter.label
        )
        if category:
            stmt = stmt.where(SystemParameter.category == category)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_key(
        self, db: AsyncSession, key: str
    ) -> SystemParameter | None:
        result = await db.execute(
            select(SystemParameter).where(SystemParameter.key == key)
        )
        return result.scalar_one_or_none()

    async def update_value(
        self, db: AsyncSession, key: str, body: SystemParamUpdate
    ) -> SystemParameter | None:
        item = await self.get_by_key(db, key)
        if item is None:
            return None
        # Range guard — only enforce if both bounds parse to float.
        try:
            new_val = float(body.value)
            if item.minValue is not None:
                if new_val < float(item.minValue):
                    return item  # caller should treat as no-op
            if item.maxValue is not None:
                if new_val > float(item.maxValue):
                    return item
        except (TypeError, ValueError):
            # Non-numeric valueType — accept as-is (string/bool/etc.).
            pass

        item.value = body.value
        await db.commit()
        item = await db.get(SystemParameter, item.id)
        return item

    async def reset_all(self, db: AsyncSession) -> int:
        """
        Re-seed all system params from param_defs.

        Defensive import: ParamService is created by Fix-3 in parallel.
        Calls ``ParamService.reset_params(db)`` (Fix-3 API) and falls back
        to ``seed_params`` then to a no-op (returns current count) if
        neither method is present.
        """
        try:
            from app.features.system_params.param_service import ParamService  # type: ignore
        except ImportError:
            logger.warning("system_params.reset.service_not_ready")
            result = await db.execute(select(SystemParameter))
            return len(list(result.scalars().all()))

        service = ParamService()
        reset_fn = getattr(service, "reset_params", None) or getattr(
            service, "seed_params", None
        )
        if reset_fn is None:
            logger.warning("system_params.reset.no_reset_method")
            result = await db.execute(select(SystemParameter))
            return len(list(result.scalars().all()))
        count = await reset_fn(db)  # type: ignore[misc]
        return int(count) if count is not None else 0


__all__ = ["SystemParamsService"]