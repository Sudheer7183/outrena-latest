"""
rbac_service.py — Data-driven role/permission management.

Roles are now per-tenant DATA-DRIVEN (each tenant has its own roles table
seeded with the 4 system roles REP/MANAGER/TENANT_ADMIN plus any custom
roles added by TENANT_ADMIN via /api/v1/roles). Each role is mapped to a
set of permission keys (RolePermission join table).

Permission resolution for a JWT-bearing user:
  1. SUPER_ADMIN (tenant_slug=None) → all permissions (short-circuit).
  2. Otherwise → look up the role row in the tenant's roles table by name
     matching the JWT ``role`` claim, then return its permission keys.

The permission catalog (Permission) and the feature→permission map
(FeaturePermission) live in the public schema and are read-only for
tenants. Only SUPER_ADMIN can edit FeaturePermission mappings.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_permission import FeaturePermission
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.schemas.auth import ROLE_HIERARCHY, Role as RoleEnum

logger = structlog.get_logger(__name__)


# ── System-role default permission seed (applied at tenant provisioning) ──────
# Each entry is (role_name, [permission_keys]). Mirrors the 4-role enum.
# MUST stay in sync with alembic/versions/0003_saas_platform.py::_SYSTEM_ROLE_PERMS
# — that migration seeds the same data into every tenant schema at provisioning.
SYSTEM_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "REP": [
        "prospects.read", "prospects.write", "prospects.import",
        "campaigns.read", "campaigns.write",
        "sequences.read", "sequences.write",
        "email_studio.write",
        "analytics.read", "dashboard.read",
        "deals.read", "meeting_prep.read",
        "support.read", "help.read",
        "icp.read",
    ],
    "MANAGER": [
        "prospects.read", "prospects.write", "prospects.import", "prospects.export",
        "campaigns.read", "campaigns.write", "campaigns.publish",
        "sequences.read", "sequences.write",
        "email_studio.write",
        "analytics.read", "analytics.export",
        "ab_testing.read", "ab_testing.write",
        "optimization.read", "optimization.write",
        "deals.read", "deals.write", "meeting_prep.read",
        "dashboard.read",
        "support.read", "help.read",
        "icp.read",
    ],
    "TENANT_ADMIN": [
        "prospects.read", "prospects.write", "prospects.delete", "prospects.import", "prospects.export",
        "campaigns.read", "campaigns.write", "campaigns.publish", "campaigns.delete",
        "sequences.read", "sequences.write", "sequences.delete",
        "email_studio.write",
        "analytics.read", "analytics.export",
        "ab_testing.read", "ab_testing.write", "ab_testing.delete",
        "optimization.read", "optimization.write",
        "deals.read", "deals.write", "deals.delete", "meeting_prep.read",
        "dashboard.read",
        "users.manage", "roles.manage", "billing.manage",
        "integrations.manage", "llm_config.manage",
        "domain_settings.manage", "linkedin.manage",
        "support.read", "support.manage", "help.read", "audit.read",
        "icp.read", "icp.write",
    ],
    # SUPER_ADMIN has every permission — resolved at runtime, never seeded.
}


class RbacService:
    """Per-tenant role + permission management."""

    # ── Role CRUD ───────────────────────────────────────────────────────────

    async def list_roles(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List all roles in the current tenant schema with their permission keys."""
        role_rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
        if not role_rows:
            return []
        role_ids = [r.id for r in role_rows]
        perm_rows = (
            await db.execute(
                select(RolePermission).where(RolePermission.role_id.in_(role_ids))
            )
        ).scalars().all()
        perm_map: dict[int, list[str]] = {}
        for p in perm_rows:
            perm_map.setdefault(p.role_id, []).append(p.permission_key)
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "is_system": r.is_system,
                "permissions": sorted(perm_map.get(r.id, [])),
                "created_at": r.created_at,
            }
            for r in role_rows
        ]

    async def create_role(
        self,
        db: AsyncSession,
        name: str,
        description: str,
        permission_keys: list[str],
    ) -> dict[str, Any]:
        """Create a new custom (is_system=False) role with the given permissions."""
        existing = await db.execute(select(Role).where(Role.name == name))
        if existing.scalar_one_or_none() is not None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{name}' already exists.",
            )
        role = Role(name=name, description=description, is_system=False)
        db.add(role)
        await db.flush()
        if permission_keys:
            await db.execute(
                insert(RolePermission),
                [
                    {"role_id": role.id, "permission_key": k}
                    for k in permission_keys
                ],
            )
        await db.commit()
        role = await db.get(Role, role.id)
        logger.info("rbac.role.created", role_id=role.id, name=name)
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "permissions": sorted(permission_keys),
            "created_at": role.created_at,
        }

    async def update_role(
        self,
        db: AsyncSession,
        role_id: int,
        name: str | None = None,
        description: str | None = None,
        permission_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing role. permission_keys (if given) replaces the set."""
        role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
        if role is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if permission_keys is not None:
            await db.execute(
                delete(RolePermission).where(RolePermission.role_id == role_id)
            )
            if permission_keys:
                await db.execute(
                    insert(RolePermission),
                    [
                        {"role_id": role_id, "permission_key": k}
                        for k in permission_keys
                    ],
                )
        await db.commit()
        role = await db.get(RolePermission, role.id)
        return await self._role_dict(db, role)

    async def delete_role(self, db: AsyncSession, role_id: int) -> None:
        """Delete a role. System roles (is_system=True) are immutable (409)."""
        from fastapi import HTTPException, status
        role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="System roles cannot be deleted.",
            )
        await db.delete(role)
        await db.commit()
        logger.info("rbac.role.deleted", role_id=role_id)

    # ── Permission catalog ──────────────────────────────────────────────────

    async def list_permissions(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List all permissions from the public catalog."""
        rows = (
            await db.execute(select(Permission).order_by(Permission.category, Permission.key))
        ).scalars().all()
        return [
            {
                "key": r.key,
                "display_name": r.display_name,
                "description": r.description,
                "category": r.category,
            }
            for r in rows
        ]

    async def list_feature_permissions(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List the feature_key → required_permission map."""
        rows = (
            await db.execute(select(FeaturePermission).order_by(FeaturePermission.feature_key))
        ).scalars().all()
        return [
            {
                "feature_key": r.feature_key,
                "required_permission": r.required_permission,
                "description": r.description,
            }
            for r in rows
        ]

    async def set_feature_permission(
        self,
        db: AsyncSession,
        feature_key: str,
        required_permission: str | None,
    ) -> dict[str, Any]:
        """Upsert a FeaturePermission row. SUPER_ADMIN only (enforced at router)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        row = (
            await db.execute(
                select(FeaturePermission).where(FeaturePermission.feature_key == feature_key)
            )
        ).scalar_one_or_none()
        if row is None:
            row = FeaturePermission(
                feature_key=feature_key,
                required_permission=required_permission,
                description="",
            )
            db.add(row)
        else:
            row.required_permission = required_permission
        await db.commit()
        row = await db.get(FeaturePermission, row.id)
        return {
            "feature_key": row.feature_key,
            "required_permission": row.required_permission,
            "description": row.description,
        }

    # ── Permission resolution ───────────────────────────────────────────────

    async def get_user_permissions(
        self,
        db: AsyncSession,
        role: RoleEnum,
        user_id: str | None = None,
    ) -> set[str]:
        """Resolve the set of permission keys held by the caller.

        SUPER_ADMIN short-circuits to the full catalog (every key).
        Otherwise: look up the role row in the tenant's roles table by name
        matching the JWT ``role`` claim, then return its permission keys.
        """
        if role is RoleEnum.SUPER_ADMIN:
            rows = (await db.execute(select(Permission.key))).scalars().all()
            return set(rows)
        role_row = (
            await db.execute(select(Role).where(Role.name == role.value))
        ).scalar_one_or_none()
        if role_row is None:
            # Role not seeded yet for this tenant — fall back to the static
            # SYSTEM_ROLE_PERMISSIONS map so endpoints still work pre-seed.
            return set(SYSTEM_ROLE_PERMISSIONS.get(role.value, []))
        perm_rows = (
            await db.execute(
                select(RolePermission.permission_key).where(
                    RolePermission.role_id == role_row.id
                )
            )
        ).scalars().all()
        return set(perm_rows)

    async def has_permission(
        self,
        db: AsyncSession,
        role: RoleEnum,
        permission_key: str,
        user_id: str | None = None,
    ) -> bool:
        """Return True iff the caller holds the given permission key."""
        perms = await self.get_user_permissions(db, role, user_id)
        return permission_key in perms

    # ── Tenant-provisioning hook (Step 4.5) ─────────────────────────────────

    @staticmethod
    async def seed_system_roles(db: AsyncSession) -> int:
        """Seed the 4 system roles + their default permissions.

        Called by TenantProvisioningService as Step 4.5 of the 6-step flow.
        Idempotent — uses ON CONFLICT DO NOTHING on (name) so re-runs are
        safe. Returns the number of role rows inserted.
        """
        inserted = 0
        for role_name, perms in SYSTEM_ROLE_PERMISSIONS.items():
            existing = (
                await db.execute(select(Role).where(Role.name == role_name))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            role = Role(
                name=role_name,
                description=f"System role: {role_name}",
                is_system=True,
            )
            db.add(role)
            await db.flush()
            inserted += 1
            if perms:
                await db.execute(
                    insert(RolePermission),
                    [
                        {"role_id": role.id, "permission_key": k}
                        for k in perms
                    ],
                )
        if inserted:
            await db.commit()
        logger.info("rbac.system_roles_seeded", inserted=inserted)
        return inserted

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _role_dict(self, db: AsyncSession, role: Role) -> dict[str, Any]:
        perms = (
            await db.execute(
                select(RolePermission.permission_key).where(
                    RolePermission.role_id == role.id
                )
            )
        ).scalars().all()
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "permissions": sorted(perms),
            "created_at": role.created_at,
        }


__all__ = ["RbacService", "SYSTEM_ROLE_PERMISSIONS"]
