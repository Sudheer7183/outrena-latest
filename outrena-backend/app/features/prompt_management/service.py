# """prompt_management_service.py — PromptTemplate admin CRUD + /reset re-seed.

# The /reset endpoint delegates to the PromptService provided by Fix-3 if
# available (defensive import); otherwise it falls back to a no-op that
# returns the current row count.
# """
# from __future__ import annotations

# import structlog
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.config_models import PromptTemplate
# from app.schemas.prompt_management import PromptUpdate

# logger = structlog.get_logger(__name__)


# class PromptManagementService:
#     """Admin CRUD over PromptTemplate rows."""

#     async def list_prompts(
#         self, db: AsyncSession, *, category: str | None = None
#     ) -> list[PromptTemplate]:
#         stmt = select(PromptTemplate).order_by(
#             PromptTemplate.category, PromptTemplate.sortOrder
#         )
#         if category:
#             stmt = stmt.where(PromptTemplate.category == category)
#         result = await db.execute(stmt)
#         return list(result.scalars().all())

#     async def get_by_key(
#         self, db: AsyncSession, key: str
#     ) -> PromptTemplate | None:
#         result = await db.execute(
#             select(PromptTemplate).where(PromptTemplate.key == key)
#         )
#         return result.scalar_one_or_none()

#     async def update_template(
#         self, db: AsyncSession, key: str, body: PromptUpdate
#     ) -> PromptTemplate | None:
#         item = await self.get_by_key(db, key)
#         if item is None:
#             return None
#         if not item.isEditable:
#             logger.warning("prompt.update.not_editable", key=key)
#             return item
#         item.template = body.template
#         await db.commit()
#         item = await db.get(PromptTemplate, item.id)
#         return item

#     async def reset_all(self, db: AsyncSession) -> int:
#         """
#         Re-seed all prompts from prompt_defs.

#         Defensive import: PromptService is created by Fix-3 in parallel.
#         Calls ``PromptService.reset_prompts(db)`` (Fix-3 API) and falls back
#         to ``seed_prompts`` then to a no-op (returns current count) if
#         neither method is present.
#         """
#         try:
#             from app.features.prompt_management.prompt_service import PromptService  # type: ignore
#         except ImportError:
#             logger.warning("prompt_management.reset.service_not_ready")
#             result = await db.execute(select(PromptTemplate))
#             return len(list(result.scalars().all()))

#         service = PromptService()
#         reset_fn = getattr(service, "reset_prompts", None) or getattr(
#             service, "seed_prompts", None
#         )
#         if reset_fn is None:
#             logger.warning("prompt_management.reset.no_reset_method")
#             result = await db.execute(select(PromptTemplate))
#             return len(list(result.scalars().all()))
#         count = await reset_fn(db)  # type: ignore[misc]
#         return int(count) if count is not None else 0


# __all__ = ["PromptManagementService"]


"""prompt_management_service.py — PromptTemplate admin CRUD + /reset re-seed.

The /reset endpoint delegates to the PromptService provided by Fix-3 if
available (defensive import); otherwise it falls back to a no-op that
returns the current row count.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import PromptTemplate
from app.schemas.prompt_management import PromptUpdate

logger = structlog.get_logger(__name__)


class PromptManagementService:
    """Admin CRUD over PromptTemplate rows."""

    async def list_prompts(
        self, db: AsyncSession, *, category: str | None = None
    ) -> list[PromptTemplate]:
        # Auto-seed on first call: if the table is empty, run reset_all()
        # which delegates to PromptService.seed_prompts(). This ensures the
        # Prompt Management page is never blank on first load after a fresh
        # database — clicking Reset All manually should not be required.
        count_result = await db.execute(select(PromptTemplate).limit(1))
        if count_result.scalar_one_or_none() is None:
            try:
                await self.reset_all(db)
            except Exception as seed_exc:
                logger.warning("prompt_management.auto_seed_failed", error=str(seed_exc))

        stmt = select(PromptTemplate).order_by(
            PromptTemplate.category, PromptTemplate.sortOrder
        )
        if category:
            stmt = stmt.where(PromptTemplate.category == category)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_key(
        self, db: AsyncSession, key: str
    ) -> PromptTemplate | None:
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.key == key)
        )
        return result.scalar_one_or_none()

    async def update_template(
        self, db: AsyncSession, key: str, body: PromptUpdate
    ) -> PromptTemplate | None:
        item = await self.get_by_key(db, key)
        if item is None:
            return None
        if not item.isEditable:
            logger.warning("prompt.update.not_editable", key=key)
            return item
        item.template = body.template
        await db.commit()
        item = await db.get(PromptTemplate, item.id)
        return item

    async def reset_all(self, db: AsyncSession) -> int:
        """
        Re-seed all prompts from prompt_defs.

        Defensive import: PromptService is created by Fix-3 in parallel.
        Calls ``PromptService.reset_prompts(db)`` (Fix-3 API) and falls back
        to ``seed_prompts`` then to a no-op (returns current count) if
        neither method is present.
        """
        try:
            from app.features.prompt_management.prompt_service import PromptService  # type: ignore
        except ImportError:
            logger.warning("prompt_management.reset.service_not_ready")
            result = await db.execute(select(PromptTemplate))
            return len(list(result.scalars().all()))

        service = PromptService()
        reset_fn = getattr(service, "reset_prompts", None) or getattr(
            service, "seed_prompts", None
        )
        if reset_fn is None:
            logger.warning("prompt_management.reset.no_reset_method")
            result = await db.execute(select(PromptTemplate))
            return len(list(result.scalars().all()))
        count = await reset_fn(db)  # type: ignore[misc]
        return int(count) if count is not None else 0


__all__ = ["PromptManagementService"]