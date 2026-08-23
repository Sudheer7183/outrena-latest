# """
# api/v1/__init__.py — Phase 2 + Phase 3 router aggregator (auto-discovery).

# Wires every feature router (any submodule of ``app.features.*`` that exposes
# a module-level ``router`` attribute that is a FastAPI ``APIRouter``) into a
# single parent ``APIRouter`` that ``main.py`` mounts under ``/api/v1``.

# MODULAR-MONOLITH STRUCTURE (migration doc §3.2):
#   Each feature lives in ``app/features/{name}/`` and owns its own
#   ``router.py`` (+ ``service.py`` / ``models.py`` / ``schemas.py``).
#   Features with multiple routers (e.g. ``billing`` has ``router.py`` +
#   ``payments.py`` + ``tenant_signup.py``) keep each router as a separate
#   file in the feature folder; auto-discovery picks up any submodule that
#   exposes a ``router`` attribute.

# AUTO-DISCOVERY:
#   ``_discover_module_routers`` uses ``pkgutil.iter_modules`` to enumerate
#   every feature package under ``app.features``, then iterates the
#   submodules of each feature package, imports each one via
#   ``importlib.import_module``, and collects any module-level ``router``
#   attribute that is an ``APIRouter`` instance. Submodules without a
#   ``router`` (e.g. ``service.py``, ``models.py``, ``schemas.py``,
#   ``__init__``) are silently skipped.

#   This means a new feature router only requires creating
#   ``app/features/<feature>/<module>.py`` with ``router = APIRouter(...)``
#   — no edit to this file is required.

#   The platform router (``app.api.routes.platform``) is intentionally NOT
#   auto-discovered here — it lives in a different package and is mounted
#   separately by ``main.py`` because it bypasses ``TenantMiddleware``.

# Adding a new feature router (the only required step):
#   1. Create ``app/features/<feature>/<module>.py`` with
#      ``router = APIRouter(...)``.
#   2. ``main.py`` picks it up automatically on next reload — no edit here.

# The parent router is built lazily on first call (so import errors in any one
# submodule surface only when that module is imported, not at app startup).
# """
# from __future__ import annotations

# import importlib
# import pkgutil
# from typing import Any

# from fastapi import APIRouter

# import app.features as features_pkg

# # ── Module path of the features package ────────────────────────────────────
# _FEATURES_PATH = features_pkg.__path__  # app/features/__path__
# _FEATURES_PKG = features_pkg.__name__   # "app.features"


# def _is_api_router(obj: Any) -> bool:
#     """True iff ``obj`` is a FastAPI APIRouter instance."""
#     return isinstance(obj, APIRouter)


# def _discover_module_routers() -> list[APIRouter]:
#     """Return every APIRouter exposed by submodules of ``app.features.*``.

#     For each feature package (e.g. ``app.features.auth``), iterates its
#     submodules (``router``, ``payments``, ``tenant_signup``, ...). Any
#     submodule exposing a module-level ``router`` attribute that is an
#     ``APIRouter`` is collected.

#     Iteration order is ``pkgutil.iter_modules`` order (alphabetical by
#     feature name, then alphabetical by submodule name) — deterministic.
#     Skips ``__init__`` and any submodule that does not export a ``router``
#     attribute or whose ``router`` is not an ``APIRouter``.
#     """
#     discovered: list[APIRouter] = []
#     for feature_info in pkgutil.iter_modules(_FEATURES_PATH):
#         feature_name = feature_info.name
#         if feature_name == "__init__":
#             continue
#         feature_pkg_full = f"{_FEATURES_PKG}.{feature_name}"
#         try:
#             feature_pkg = importlib.import_module(feature_pkg_full)
#         except Exception:  # noqa: BLE001
#             import structlog

#             structlog.get_logger(__name__).error(
#                 "api.v1.feature_package_import_failed", feature=feature_pkg_full
#             )
#             raise
#         # Iterate submodules of this feature package
#         for sub_info in pkgutil.iter_modules(feature_pkg.__path__):
#             sub_name = sub_info.name
#             if sub_name == "__init__":
#                 continue
#             sub_full = f"{feature_pkg_full}.{sub_name}"
#             try:
#                 module = importlib.import_module(sub_full)
#             except Exception:  # noqa: BLE001 — one bad module must not break all
#                 import structlog

#                 structlog.get_logger(__name__).error(
#                     "api.v1.feature_module_import_failed", module=sub_full
#                 )
#                 raise
#             router_obj = getattr(module, "router", None)
#             if _is_api_router(router_obj):
#                 discovered.append(router_obj)
#     return discovered


# def _wire_module_routers() -> APIRouter:
#     """Mount every feature router under a single parent router.

#     Uses auto-discovery (see module docstring) so adding a new feature
#     module requires no edit to this file. Returns a freshly-built
#     ``APIRouter`` on every call so tests can re-discover routers after
#     monkeypatching modules.
#     """
#     parent = APIRouter()
#     for r in _discover_module_routers():
#         parent.include_router(r)
#     return parent


# # Module-level singleton — built once at import time. Tests can call
# # ``_wire_module_routers()`` directly to get a fresh parent router.
# api_router: APIRouter = _wire_module_routers()

# # Backwards-compat: prior versions of this module exposed a manual list of
# # routers under ``_MODULE_ROUTERS``. With auto-discovery the canonical source
# # is ``_discover_module_routers()``, but we still expose the list under the
# # legacy name so older tests / imports keep working. The list is rebuilt on
# # every access so it always reflects the current set of discovered routers.
# def __getattr__(name: str) -> Any:  # PEP 562 module-level __getattr__
#     if name == "_MODULE_ROUTERS":
#         return _discover_module_routers()
#     raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# __all__ = ["api_router", "_wire_module_routers", "_MODULE_ROUTERS"]


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


__all__ = [
    "api_router",
    "_MODULE_ROUTERS",
    "_discover_module_routers",
    "_wire_module_routers",
]
