# """
# tenant_provisioning_service.py — Six-step compensating provisioning flow.

# Reference model Section 4:

#   Step 1   INSERT public.tenants (status='PROVISIONING')          [commit]
#   Step 2   CREATE SCHEMA "tenant_{slug}"                          [autocommit]
#   Step 3   Alembic subprocess with ALEMBIC_TARGET_SCHEMA set
#   Step 4   Seed the schema (47 prompts + 30 params + defaults)
#   Step 5   Create TENANT_ADMIN user in the identity provider
#   Step 5b  Register the tenant's redirect URIs        [NON-FATAL]
#   Step 6   status='ACTIVE'

#   Failure  DROP SCHEMA ... CASCADE + soft-delete the tenant record.

# OUTRENA adaptation: Step 4 seeds the 47 LLM prompt templates and 30+
# system parameters that every tenant needs at first boot. The seed data
# lives in app/services/prompt_defs.py and param_defs.py (Phase 2); this
# Phase 1 implementation seeds an empty schema and the seed step is a
# no-op stub that Phase 2 fills in.
# """
# from __future__ import annotations

# import asyncio
# import os
# import sys

# import structlog
# from fastapi import HTTPException, status
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.database import engine
# from app.services.keycloak_admin_service import (
#     KeycloakAdminService,
#     get_keycloak_admin_service,
# )
# from app.utils.slug import schema_name_for

# logger = structlog.get_logger(__name__)

# _ALEMBIC_TIMEOUT_SECONDS = 120


# class TenantProvisioningService:
#     """Creates (and on failure, fully tears down) a tenant."""

#     def __init__(self, keycloak: KeycloakAdminService | None = None) -> None:
#         self._keycloak = keycloak or get_keycloak_admin_service()

#     async def provision_tenant(
#         self,
#         *,
#         tenant_slug: str,
#         tenant_name: str,
#         tenant_type: str,
#         admin_email: str,
#         admin_first_name: str,
#         admin_last_name: str,
#         temporary_password: str | None,
#         send_invitation: bool,
#         db: AsyncSession,
#         integration_mode: str = "tenant_managed",
#     ) -> str:
#         """Provision a new tenant end to end. Returns the slug.

#         ``integration_mode`` ("platform_managed" | "tenant_managed",
#         default "tenant_managed") is recorded on the tenant_config row at
#         Step 4 and audited via the platform_audit_log.
#         """
#         # Normalize + validate integration_mode (defense-in-depth).
#         if integration_mode not in ("platform_managed", "tenant_managed"):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=(
#                     "integration_mode must be 'platform_managed' or "
#                     "'tenant_managed'."
#                 ),
#             )
#         schema_name = schema_name_for(tenant_slug)

#         # ── Step 1 — registry record ─────────────────────────────────────────
#         await db.execute(
#             text(
#                 "INSERT INTO public.tenants "
#                 "(slug, schema_name, name, tenant_type, status) "
#                 "VALUES (:slug, :schema, :name, :type, 'PROVISIONING')"
#             ),
#             {
#                 "slug": tenant_slug,
#                 "schema": schema_name,
#                 "name": tenant_name,
#                 "type": tenant_type,
#             },
#         )
#         await db.commit()
#         logger.info("provisioning.tenant_record_created", slug=tenant_slug)

#         try:
#             # ── Step 2 — schema (DDL must run on an autocommit connection) ───
#             await self._create_schema(schema_name)
#             logger.info("provisioning.schema_created", schema=schema_name)

#             # ── Step 3 — migrations, this schema only ────────────────────────
#             await self._run_alembic_migration(schema_name)
#             logger.info("provisioning.migrations_applied", schema=schema_name)

#             # ── Step 4 — seed defaults ───────────────────────────────────────
#             await self._seed_tenant_schema(schema_name, db, integration_mode=integration_mode)
#             logger.info(
#                 "provisioning.schema_seeded",
#                 schema=schema_name,
#                 integration_mode=integration_mode,
#             )

#             # ── Step 5 — identity-provider admin user ────────────────────────
#             keycloak_user_id = await self._keycloak.create_tenant_admin_user(
#                 email=admin_email,
#                 first_name=admin_first_name,
#                 last_name=admin_last_name,
#                 tenant_slug=tenant_slug,
#                 temporary_password=temporary_password,
#                 send_invitation=send_invitation,
#             )
#             logger.info(
#                 "provisioning.idp_user_created",
#                 slug=tenant_slug,
#                 keycloak_user_id=keycloak_user_id,
#             )

#             # ── Step 5b — redirect URIs (NON-FATAL by design) ────────────────
#             try:
#                 await self._keycloak.add_redirect_uris_to_frontend_client(tenant_slug)
#             except Exception as exc:  # noqa: BLE001 — deliberate broad catch
#                 logger.error(
#                     "provisioning.redirect_uri_registration_failed",
#                     slug=tenant_slug,
#                     error=str(exc),
#                     remediation="Register the redirect URI manually in the IdP admin console.",
#                 )

#             # ── Step 6 — activate ────────────────────────────────────────────
#             await db.execute(
#                 text("UPDATE public.tenants SET status = 'ACTIVE' WHERE slug = :slug"),
#                 {"slug": tenant_slug},
#             )
#             await db.commit()
#             logger.info("provisioning.tenant_active", slug=tenant_slug)

#             # ── Step 6b — welcome email (FR-008, NON-FATAL) ──────────────────
#             # Send a templated welcome email to the TENANT_ADMIN with login
#             # URL, role, and onboarding pointers. Follows the Step 5b pattern:
#             # a mail failure never fails provisioning — the tenant is ACTIVE.
#             try:
#                 await self._send_welcome_email(db, tenant_slug, admin_email)
#             except Exception as mail_exc:  # noqa: BLE001
#                 logger.warning(
#                     "provisioning.welcome_email_failed",
#                     slug=tenant_slug,
#                     error=str(mail_exc),
#                 )

#             return tenant_slug

#         except Exception as exc:
#             await self._rollback_provisioning(tenant_slug, schema_name, db)
#             logger.error("provisioning.failed", slug=tenant_slug, error=str(exc))
#             if isinstance(exc, HTTPException):
#                 raise
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=f"Tenant provisioning failed for '{tenant_slug}'.",
#             ) from exc

#     # ── Step implementations ────────────────────────────────────────────────

#     @staticmethod
#     async def _send_welcome_email(db, tenant_slug: str, admin_email: str) -> None:
#         """FR-008: templated welcome email to the new TENANT_ADMIN.

#         Sent via MailBridge (stub-safe in dev: falls back to a deterministic
#         stub message id when no MailBridge is configured, same as the
#         scheduler path)."""
#         from app.core.config import get_settings
#         from app.features.mailbridge.service import MailBridgeService

#         settings = get_settings()
#         base = getattr(settings, "BASE_DOMAIN", "outrena.com") or "outrena.com"
#         login_url = f"https://{tenant_slug}.{base}"
#         body = (
#             f"Welcome to OUTRENA!\n\n"
#             f"Your workspace is ready: {login_url}\n"
#             f"Role: TENANT_ADMIN\n\n"
#             "Next steps (also shown in your in-app onboarding checklist):\n"
#             "  1. Log in and set your password (and TOTP for admin security).\n"
#             "  2. Connect your MailBridge sender identity.\n"
#             "  3. Verify your sending domain's SPF/DKIM/DMARC records.\n"
#             "  4. Define your first ICP and import prospects.\n"
#             "  5. Create a campaign with the 7-Touch Cadence.\n\n"
#             "Need help? The Help Guide is available from every page, and you "
#             "can open a support ticket in-app at any time.\n\n"
#             "— The OUTRENA Team"
#         )
#         mb = MailBridgeService()
#         await mb.send(
#             db=db,
#             to=admin_email,
#             subject=f"Welcome to OUTRENA — your workspace '{tenant_slug}' is ready",
#             body=body,
#         )


#     @staticmethod
#     async def _create_schema(schema_name: str) -> None:
#         """CREATE SCHEMA cannot run inside the ORM transaction — autocommit."""
#         async with engine.connect() as conn:
#             autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
#             await autocommit.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

#     @staticmethod
#     async def _run_alembic_migration(schema_name: str) -> None:
#         """
#         Run `alembic upgrade head` as a subprocess with ALEMBIC_TARGET_SCHEMA
#         set, so env.py migrates ONLY the new schema (its registry row is
#         still 'PROVISIONING' and would be missed by active-tenant discovery).
#         """
#         env = {**os.environ, "ALEMBIC_TARGET_SCHEMA": schema_name}
#         process = await asyncio.create_subprocess_exec(
#             sys.executable,
#             "-m",
#             "alembic",
#             "upgrade",
#             "head",
#             env=env,
#             stdout=asyncio.subprocess.PIPE,
#             stderr=asyncio.subprocess.PIPE,
#         )
#         try:
#             stdout, stderr = await asyncio.wait_for(
#                 process.communicate(), timeout=_ALEMBIC_TIMEOUT_SECONDS
#             )
#         except TimeoutError as exc:
#             process.kill()
#             raise RuntimeError("Alembic migration timed out.") from exc
#         if process.returncode != 0:
#             raise RuntimeError(
#                 f"Alembic failed for {schema_name}: {stderr.decode(errors='replace')}"
#             )
#         logger.debug("provisioning.alembic_output", output=stdout.decode(errors="replace"))

#     @staticmethod
#     async def _seed_tenant_schema(
#         schema_name: str,
#         db: AsyncSession,
#         *,
#         integration_mode: str = "tenant_managed",
#     ) -> None:
#         """
#         Seed tenant defaults (reference model §4, Step 4).

#         Phase 2: seeds the platform_audit_log entry recording the provisioning,
#         plus a default TenantConfig row. Phase 3 adds the 47 LLM prompt
#         templates + 31 system parameters via PromptService.seed_prompts and
#         ParamService.seed_params (migration audit Recommendation #9).
#         Phase 8: the TenantConfig row now carries ``integration_mode`` and
#         a platform audit_log entry records the chosen mode.

#         Each seed call is wrapped in its own try/except so a failure in one
#         seed table does NOT abort the whole provisioning — the tenant is
#         still created and can be re-seeded later via the prompt/param reset
#         endpoints. Errors are logged with structlog so they show up in
#         alerting dashboards.
#         """
#         # Set search_path so subsequent INSERTs hit the right schema.
#         # Public tables (tenant_config) are still reachable via the second
#         # search_path entry.
#         from sqlalchemy import text as _text

#         await db.execute(_text(f'SET search_path TO "{schema_name}", public'))

#         # Insert a default tenant_config row (1:1 with public.tenants).
#         # Look up the tenant_id from public.tenants by schema_name.
#         result = await db.execute(
#             _text("SELECT tenant_id FROM public.tenants WHERE schema_name = :schema"),
#             {"schema": schema_name},
#         )
#         row = result.fetchone()
#         if row is not None:
#             # Phase 8: include integration_mode in the INSERT.
#             await db.execute(
#                 _text(
#                     "INSERT INTO public.tenant_config "
#                     "(tenant_id, plan, max_seats, features, integrations_shared, "
#                     " llm_provider_default, integration_mode) "
#                     "VALUES (:tid, 'alpha', 5, '{}'::jsonb, true, 'zai', :imode) "
#                     "ON CONFLICT (tenant_id) DO NOTHING"
#                 ),
#                 {"tid": row.tenant_id, "imode": integration_mode},
#             )

#             # Phase 8: audit-log the integration_mode selection so the
#             # platform team can trace any platform-managed → tenant-managed
#             # switches later. Failure here MUST NOT abort provisioning.
#             try:
#                 from app.services.audit_service import AuditService

#                 await AuditService().log(
#                     db,
#                     actor_user_id=None,
#                     actor_role="SUPER_ADMIN",
#                     tenant_slug=None,
#                     action="tenant.integration_mode_set",
#                     target_type="tenant_config",
#                     target_id=str(row.tenant_id),
#                     metadata={
#                         "schema": schema_name,
#                         "integration_mode": integration_mode,
#                     },
#                 )
#             except Exception as exc:  # noqa: BLE001
#                 logger.warning(
#                     "provisioning.integration_mode_audit_failed",
#                     schema=schema_name,
#                     error=str(exc),
#                 )

#         # ── Phase 3: seed the 47 PromptTemplate rows + 31 SystemParameter rows.
#         # These services were created by AUDIT-FIX-3; this is the wiring step
#         # (audit Recommendation #9). Each seed is wrapped in try/except so a
#         # failure in one doesn't abort the whole provisioning — the tenant
#         # can still be activated and re-seeded later via the reset endpoints.
#         from app.features.prompt_management.prompt_service import PromptService
#         from app.features.system_params.param_service import ParamService

#         try:
#             inserted_prompts = await PromptService().seed_prompts(db)
#             logger.info(
#                 "provisioning.prompts_seeded",
#                 schema=schema_name,
#                 inserted=inserted_prompts,
#             )
#         except Exception as exc:  # noqa: BLE001 — seeding must not abort provisioning
#             logger.error(
#                 "provisioning.prompt_seed_failed",
#                 schema=schema_name,
#                 error=str(exc),
#                 remediation=(
#                     "Run POST /api/v1/prompt-management/reset to re-seed "
#                     "the 47 PromptTemplate rows manually."
#                 ),
#             )

#         try:
#             inserted_params = await ParamService().seed_params(db)
#             logger.info(
#                 "provisioning.params_seeded",
#                 schema=schema_name,
#                 inserted=inserted_params,
#             )
#         except Exception as exc:  # noqa: BLE001 — seeding must not abort provisioning
#             logger.error(
#                 "provisioning.param_seed_failed",
#                 schema=schema_name,
#                 error=str(exc),
#                 remediation=(
#                     "Run POST /api/v1/system-params/reset to re-seed "
#                     "the 31 SystemParameter rows manually."
#                 ),
#             )

#         await db.commit()

#     @staticmethod
#     async def _rollback_provisioning(
#         tenant_slug: str, schema_name: str, db: AsyncSession
#     ) -> None:
#         """Compensating rollback: drop the schema, soft-delete the record."""
#         await db.rollback()
#         async with engine.connect() as conn:
#             autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
#             await autocommit.execute(
#                 text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
#             )
#         await db.execute(
#             text(
#                 "UPDATE public.tenants "
#                 "SET status = 'PROVISIONING', deleted_at = now() "
#                 "WHERE slug = :slug"
#             ),
#             {"slug": tenant_slug},
#         )
#         await db.commit()

"""
tenant_provisioning_service.py — Six-step compensating provisioning flow.

Reference model Section 4:

  Step 1   INSERT public.tenants (status='PROVISIONING')          [commit]
  Step 2   CREATE SCHEMA "tenant_{slug}"                          [autocommit]
  Step 3   Alembic subprocess with ALEMBIC_TARGET_SCHEMA set
  Step 4   Seed the schema (47 prompts + 30 params + defaults)
  Step 5   Create TENANT_ADMIN user in the identity provider
  Step 5b  Register the tenant's redirect URIs        [NON-FATAL]
  Step 6   status='ACTIVE'

  Failure  DROP SCHEMA ... CASCADE + soft-delete the tenant record.

OUTRENA adaptation: Step 4 seeds the 47 LLM prompt templates and 30+
system parameters that every tenant needs at first boot. The seed data
lives in app/services/prompt_defs.py and param_defs.py (Phase 2); this
Phase 1 implementation seeds an empty schema and the seed step is a
no-op stub that Phase 2 fills in.
"""
from __future__ import annotations

import asyncio
import os
import sys

import structlog
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.services.keycloak_admin_service import (
    KeycloakAdminService,
    get_keycloak_admin_service,
)
from app.utils.slug import schema_name_for

logger = structlog.get_logger(__name__)

_ALEMBIC_TIMEOUT_SECONDS = 120


class TenantProvisioningService:
    """Creates (and on failure, fully tears down) a tenant."""

    def __init__(self, keycloak: KeycloakAdminService | None = None) -> None:
        self._keycloak = keycloak or get_keycloak_admin_service()

    async def provision_tenant(
        self,
        *,
        tenant_slug: str,
        tenant_name: str,
        tenant_type: str,
        admin_email: str,
        admin_first_name: str,
        admin_last_name: str,
        temporary_password: str | None,
        send_invitation: bool,
        skip_mfa: bool = False,
        db: AsyncSession,
        integration_mode: str = "tenant_managed",
    ) -> str:
        """Provision a new tenant end to end. Returns the slug.

        ``integration_mode`` ("platform_managed" | "tenant_managed",
        default "tenant_managed") is recorded on the tenant_config row at
        Step 4 and audited via the platform_audit_log.
        """
        # Normalize + validate integration_mode (defense-in-depth).
        if integration_mode not in ("platform_managed", "tenant_managed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "integration_mode must be 'platform_managed' or "
                    "'tenant_managed'."
                ),
            )
        schema_name = schema_name_for(tenant_slug)

        # ── Step 1 — registry record ─────────────────────────────────────────
        await db.execute(
            text(
                "INSERT INTO public.tenants "
                "(slug, schema_name, name, tenant_type, status) "
                "VALUES (:slug, :schema, :name, :type, 'PROVISIONING')"
            ),
            {
                "slug": tenant_slug,
                "schema": schema_name,
                "name": tenant_name,
                "type": tenant_type,
            },
        )
        await db.commit()
        logger.info("provisioning.tenant_record_created", slug=tenant_slug)

        try:
            # ── Step 2 — schema (DDL must run on an autocommit connection) ───
            await self._create_schema(schema_name)
            logger.info("provisioning.schema_created", schema=schema_name)

            # ── Step 3 — migrations, this schema only ────────────────────────
            await self._run_alembic_migration(schema_name)
            logger.info("provisioning.migrations_applied", schema=schema_name)

            # ── Step 4 — seed defaults ───────────────────────────────────────
            await self._seed_tenant_schema(schema_name, db, integration_mode=integration_mode)
            logger.info(
                "provisioning.schema_seeded",
                schema=schema_name,
                integration_mode=integration_mode,
            )

            # ── Step 5 — identity-provider admin user ────────────────────────
            keycloak_user_id = await self._keycloak.create_tenant_admin_user(
                email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
                tenant_slug=tenant_slug,
                temporary_password=temporary_password,
                send_invitation=send_invitation,
                skip_mfa=skip_mfa,
            )
            logger.info(
                "provisioning.idp_user_created",
                slug=tenant_slug,
                keycloak_user_id=keycloak_user_id,
            )

            # ── Step 5b — redirect URIs (NON-FATAL by design) ────────────────
            try:
                await self._keycloak.add_redirect_uris_to_frontend_client(tenant_slug)
            except Exception as exc:  # noqa: BLE001 — deliberate broad catch
                logger.error(
                    "provisioning.redirect_uri_registration_failed",
                    slug=tenant_slug,
                    error=str(exc),
                    remediation="Register the redirect URI manually in the IdP admin console.",
                )

            # ── Step 6 — activate ────────────────────────────────────────────
            await db.execute(
                text("UPDATE public.tenants SET status = 'ACTIVE' WHERE slug = :slug"),
                {"slug": tenant_slug},
            )
            await db.commit()
            logger.info("provisioning.tenant_active", slug=tenant_slug)

            # ── Step 6b — welcome email (FR-008, NON-FATAL) ──────────────────
            # Send a templated welcome email to the TENANT_ADMIN with login
            # URL, role, and onboarding pointers. Follows the Step 5b pattern:
            # a mail failure never fails provisioning — the tenant is ACTIVE.
            try:
                await self._send_welcome_email(db, tenant_slug, admin_email)
            except Exception as mail_exc:  # noqa: BLE001
                logger.warning(
                    "provisioning.welcome_email_failed",
                    slug=tenant_slug,
                    error=str(mail_exc),
                )

            return tenant_slug

        except Exception as exc:
            await self._rollback_provisioning(tenant_slug, schema_name, db)
            logger.error("provisioning.failed", slug=tenant_slug, error=str(exc))
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tenant provisioning failed for '{tenant_slug}'.",
            ) from exc

    # ── Step implementations ────────────────────────────────────────────────

    @staticmethod
    async def _send_welcome_email(db, tenant_slug: str, admin_email: str) -> None:
        """FR-008: templated welcome email to the new TENANT_ADMIN.

        Sent via MailBridge (stub-safe in dev: falls back to a deterministic
        stub message id when no MailBridge is configured, same as the
        scheduler path)."""
        from app.core.config import get_settings
        from app.features.mailbridge.service import MailBridgeService

        settings = get_settings()
        base = getattr(settings, "BASE_DOMAIN", "outrena.com") or "outrena.com"
        login_url = f"https://{tenant_slug}.{base}"
        body = (
            f"Welcome to OUTRENA!\n\n"
            f"Your workspace is ready: {login_url}\n"
            f"Role: TENANT_ADMIN\n\n"
            "Next steps (also shown in your in-app onboarding checklist):\n"
            "  1. Log in and set your password (and TOTP for admin security).\n"
            "  2. Connect your MailBridge sender identity.\n"
            "  3. Verify your sending domain's SPF/DKIM/DMARC records.\n"
            "  4. Define your first ICP and import prospects.\n"
            "  5. Create a campaign with the 7-Touch Cadence.\n\n"
            "Need help? The Help Guide is available from every page, and you "
            "can open a support ticket in-app at any time.\n\n"
            "— The OUTRENA Team"
        )
        mb = MailBridgeService()
        await mb.send(
            db=db,
            to=admin_email,
            subject=f"Welcome to OUTRENA — your workspace '{tenant_slug}' is ready",
            body=body,
        )


    @staticmethod
    async def _create_schema(schema_name: str) -> None:
        """CREATE SCHEMA cannot run inside the ORM transaction — autocommit."""
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    @staticmethod
    async def _run_alembic_migration(schema_name: str) -> None:
        """
        Run `alembic upgrade head` as a subprocess with ALEMBIC_TARGET_SCHEMA
        set, so env.py migrates ONLY the new schema (its registry row is
        still 'PROVISIONING' and would be missed by active-tenant discovery).
        """
        env = {**os.environ, "ALEMBIC_TARGET_SCHEMA": schema_name}
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_ALEMBIC_TIMEOUT_SECONDS
            )
        except TimeoutError as exc:
            process.kill()
            raise RuntimeError("Alembic migration timed out.") from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"Alembic failed for {schema_name}: {stderr.decode(errors='replace')}"
            )
        logger.debug("provisioning.alembic_output", output=stdout.decode(errors="replace"))

    @staticmethod
    async def _seed_tenant_schema(
        schema_name: str,
        db: AsyncSession,
        *,
        integration_mode: str = "tenant_managed",
    ) -> None:
        """
        Seed tenant defaults (reference model §4, Step 4).

        Phase 2: seeds the platform_audit_log entry recording the provisioning,
        plus a default TenantConfig row. Phase 3 adds the 47 LLM prompt
        templates + 31 system parameters via PromptService.seed_prompts and
        ParamService.seed_params (migration audit Recommendation #9).
        Phase 8: the TenantConfig row now carries ``integration_mode`` and
        a platform audit_log entry records the chosen mode.

        Each seed call is wrapped in its own try/except so a failure in one
        seed table does NOT abort the whole provisioning — the tenant is
        still created and can be re-seeded later via the prompt/param reset
        endpoints. Errors are logged with structlog so they show up in
        alerting dashboards.
        """
        # Set search_path so subsequent INSERTs hit the right schema.
        # Public tables (tenant_config) are still reachable via the second
        # search_path entry.
        from sqlalchemy import text as _text

        await db.execute(_text(f'SET search_path TO "{schema_name}", public'))

        # Insert a default tenant_config row (1:1 with public.tenants).
        # Look up the tenant_id from public.tenants by schema_name.
        result = await db.execute(
            _text("SELECT tenant_id FROM public.tenants WHERE schema_name = :schema"),
            {"schema": schema_name},
        )
        row = result.fetchone()
        if row is not None:
            # Phase 8: include integration_mode in the INSERT.
            await db.execute(
                _text(
                    "INSERT INTO public.tenant_config "
                    "(tenant_id, plan, max_seats, features, integrations_shared, "
                    " llm_provider_default, integration_mode) "
                    "VALUES (:tid, 'alpha', 5, '{}'::jsonb, true, 'zai', :imode) "
                    "ON CONFLICT (tenant_id) DO NOTHING"
                ),
                {"tid": row.tenant_id, "imode": integration_mode},
            )

            # Phase 8: audit-log the integration_mode selection so the
            # platform team can trace any platform-managed → tenant-managed
            # switches later. Failure here MUST NOT abort provisioning.
            try:
                from app.services.audit_service import AuditService

                await AuditService().log(
                    db,
                    actor_user_id=None,
                    actor_role="SUPER_ADMIN",
                    tenant_slug=None,
                    action="tenant.integration_mode_set",
                    target_type="tenant_config",
                    target_id=str(row.tenant_id),
                    metadata={
                        "schema": schema_name,
                        "integration_mode": integration_mode,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "provisioning.integration_mode_audit_failed",
                    schema=schema_name,
                    error=str(exc),
                )

        # ── Phase 3: seed the 47 PromptTemplate rows + 31 SystemParameter rows.
        # These services were created by AUDIT-FIX-3; this is the wiring step
        # (audit Recommendation #9). Each seed is wrapped in try/except so a
        # failure in one doesn't abort the whole provisioning — the tenant
        # can still be activated and re-seeded later via the reset endpoints.
        from app.features.prompt_management.prompt_service import PromptService
        from app.features.system_params.param_service import ParamService

        try:
            inserted_prompts = await PromptService().seed_prompts(db)
            logger.info(
                "provisioning.prompts_seeded",
                schema=schema_name,
                inserted=inserted_prompts,
            )
        except Exception as exc:  # noqa: BLE001 — seeding must not abort provisioning
            logger.error(
                "provisioning.prompt_seed_failed",
                schema=schema_name,
                error=str(exc),
                remediation=(
                    "Run POST /api/v1/prompt-management/reset to re-seed "
                    "the 47 PromptTemplate rows manually."
                ),
            )

        try:
            inserted_params = await ParamService().seed_params(db)
            logger.info(
                "provisioning.params_seeded",
                schema=schema_name,
                inserted=inserted_params,
            )
        except Exception as exc:  # noqa: BLE001 — seeding must not abort provisioning
            logger.error(
                "provisioning.param_seed_failed",
                schema=schema_name,
                error=str(exc),
                remediation=(
                    "Run POST /api/v1/system-params/reset to re-seed "
                    "the 31 SystemParameter rows manually."
                ),
            )

        await db.commit()

    @staticmethod
    async def _rollback_provisioning(
        tenant_slug: str, schema_name: str, db: AsyncSession
    ) -> None:
        """Compensating rollback: drop the schema, soft-delete the record."""
        await db.rollback()
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
            )
        await db.execute(
            text(
                "UPDATE public.tenants "
                "SET status = 'PROVISIONING', deleted_at = now() "
                "WHERE slug = :slug"
            ),
            {"slug": tenant_slug},
        )
        await db.commit()