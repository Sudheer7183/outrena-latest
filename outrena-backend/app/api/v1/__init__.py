

# """
# app/api/v1/__init__.py — API v1 router assembly.

# Wires together all feature routers into the single ``api_router`` that
# main.py mounts under /api/v1.

# Auto-discovery:
#   _discover_module_routers() / _wire_module_routers() scans every
#   app/features/*/router.py and collects any module-level ``router``
#   attribute that is an APIRouter instance. This means adding a new
#   feature only requires dropping a router.py into the feature directory.

# Manual routers (not in features/):
#   - tenant_signup  — mounted explicitly because it lives under
#     app/features/billing/tenant_signup.py (not the billing router itself)
#     and is exempt from TenantMiddleware (no auth/tenant required).
# """
# from __future__ import annotations

# import importlib
# import pkgutil
# from pathlib import Path

# import structlog
# from fastapi import APIRouter
# from fastapi.routing import APIRouter as _APIRouter

# logger = structlog.get_logger(__name__)


# def _discover_module_routers() -> list[_APIRouter]:
#     """
#     Scan app/features/*/router.py and return every module-level APIRouter.

#     This is the auto-discovery mechanism referenced by tests as both
#     _discover_module_routers() and _wire_module_routers().
#     """
#     features_root = Path(__file__).parent.parent.parent / "features"
#     discovered: list[_APIRouter] = []

#     for pkg in sorted(features_root.iterdir()):
#         if not pkg.is_dir():
#             continue
#         router_path = pkg / "router.py"
#         if not router_path.exists() or router_path.stat().st_size == 0:
#             continue
#         module_name = f"app.features.{pkg.name}.router"
#         try:
#             mod = importlib.import_module(module_name)
#             router_obj = getattr(mod, "router", None)
#             if isinstance(router_obj, _APIRouter):
#                 discovered.append(router_obj)
#                 logger.debug("api_v1.discovered_router", module=module_name)
#         except Exception as exc:  # noqa: BLE001
#             logger.warning(
#                 "api_v1.router_import_failed",
#                 module=module_name,
#                 error=str(exc),
#             )

#     return discovered


# # Alias used by test_phase3_openapi.py
# _wire_module_routers = _discover_module_routers

# # Collected module routers (used by test assertions)
# _MODULE_ROUTERS: list[_APIRouter] = _discover_module_routers()


# # ── Root v1 router ────────────────────────────────────────────────────────────

# api_router = APIRouter()

# # ── 1. Auto-discovered feature routers ───────────────────────────────────────
# for _r in _MODULE_ROUTERS:
#     api_router.include_router(_r)

# # ── 2. Tenant signup (public, no auth) ───────────────────────────────────────
# # Mounted explicitly — lives in billing/ but is a public endpoint that must
# # not be gated by TenantMiddleware. The prefix /tenant-signup is added to
# # EXEMPT_PREFIXES in middleware/tenant_middleware.py.
# try:
#     from app.features.billing.tenant_signup import router as _signup_router

#     api_router.include_router(_signup_router)
#     logger.debug("api_v1.mounted_explicit_router", router="tenant_signup")
# except Exception as _exc:  # noqa: BLE001
#     logger.warning(
#         "api_v1.explicit_router_failed",
#         router="tenant_signup",
#         error=str(_exc),
#     )


# __all__ = [
#     "api_router",
#     "_MODULE_ROUTERS",
#     "_discover_module_routers",
#     "_wire_module_routers",
# ]

"""
app/api/v1/__init__.py — API v1 router assembly.

Wires together all feature routers into the single ``api_router`` that
main.py mounts under /api/v1.

Auto-discovery:
  _discover_module_routers() / _wire_module_routers() scans every
  app/features/*/router.py and collects any module-level ``router``
  attribute that is an APIRouter instance. This means adding a new
  feature only requires dropping a router.py into the feature directory.

Manual routers (not in features/):
  - tenant_signup  — mounted explicitly because it lives under
    app/features/billing/tenant_signup.py (not the billing router itself)
    and is exempt from TenantMiddleware (no auth/tenant required).
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi.routing import APIRouter as _APIRouter

logger = structlog.get_logger(__name__)


def _discover_module_routers() -> list[_APIRouter]:
    """
    Scan app/features/*/router.py and return every module-level APIRouter.

    This is the auto-discovery mechanism referenced by tests as both
    _discover_module_routers() and _wire_module_routers().
    """
    features_root = Path(__file__).parent.parent.parent / "features"
    discovered: list[_APIRouter] = []

    for pkg in sorted(features_root.iterdir()):
        if not pkg.is_dir():
            continue
        router_path = pkg / "router.py"
        if not router_path.exists() or router_path.stat().st_size == 0:
            continue
        module_name = f"app.features.{pkg.name}.router"
        try:
            mod = importlib.import_module(module_name)
            router_obj = getattr(mod, "router", None)
            if isinstance(router_obj, _APIRouter):
                discovered.append(router_obj)
                logger.debug("api_v1.discovered_router", module=module_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "api_v1.router_import_failed",
                module=module_name,
                error=str(exc),
            )

    return discovered


# Alias used by test_phase3_openapi.py
_wire_module_routers = _discover_module_routers

# Collected module routers (used by test assertions)
_MODULE_ROUTERS: list[_APIRouter] = _discover_module_routers()


# ── Root v1 router ────────────────────────────────────────────────────────────

api_router = APIRouter()

# ── 1. Auto-discovered feature routers ───────────────────────────────────────
for _r in _MODULE_ROUTERS:
    api_router.include_router(_r)

# ── 2. Tenant signup (public, no auth) ───────────────────────────────────────
# Mounted explicitly — lives in billing/ but is a public endpoint that must
# not be gated by TenantMiddleware. The prefix /tenant-signup is added to
# EXEMPT_PREFIXES in middleware/tenant_middleware.py.
try:
    from app.features.billing.tenant_signup import router as _signup_router

    api_router.include_router(_signup_router)
    logger.debug("api_v1.mounted_explicit_router", router="tenant_signup")
except Exception as _exc:  # noqa: BLE001
    logger.warning(
        "api_v1.explicit_router_failed",
        router="tenant_signup",
        error=str(_exc),
    )

# ── 3. Public one-click unsubscribe (no auth, TenantMiddleware-exempt) ────────
# Mounted explicitly so it is reachable without a Keycloak token.
# The /public prefix is added to EXEMPT_PREFIXES in tenant_middleware.py.
# URL shape: GET /api/v1/public/unsubscribe?token=…&tenant_slug=…
try:
    from app.features.public.unsubscribe_router import router as _unsub_router

    api_router.include_router(_unsub_router)
    logger.debug("api_v1.mounted_explicit_router", router="public_unsubscribe")
except Exception as _exc:  # noqa: BLE001
    logger.warning(
        "api_v1.explicit_router_failed",
        router="public_unsubscribe",
        error=str(_exc),
    )


__all__ = [
    "api_router",
    "_MODULE_ROUTERS",
    "_discover_module_routers",
    "_wire_module_routers",
]
