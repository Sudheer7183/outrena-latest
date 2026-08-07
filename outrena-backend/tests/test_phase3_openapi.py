"""
test_phase3_openapi.py — Phase 3 exit-criteria tests.

Validates:
  1. All 22 Phase 3 module routers auto-mount via _wire_module_routers.
  2. OpenAPI spec generates with 137+ schemas.
  3. Every Phase 3 module path prefix is reachable in the OpenAPI spec.
  4. The 7-touch cadence constant has the expected day sequence.
  5. Auto-pilot eligibility rule constants are correct.
  6. CSV export produces RFC-4180-compliant output (UTF-8 BOM + CRLF).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the backend package is importable when pytest runs from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Set test env BEFORE importing app.* (settings is lru_cached).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/outrena")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SKIP_JWT_VERIFICATION", "true")

import pytest  # noqa: E402

from app.api.v1 import _MODULE_ROUTERS, _wire_module_routers, api_router  # noqa: E402
from app.main import app  # noqa: E402
from app.services.csv_export_service import rows_to_csv  # noqa: E402


# ── Exit criterion: all 22 routers auto-mount ────────────────────────────────

EXPECTED_PHASE3_MODULES: list[str] = [
    "ab-testing",
    "analytics",
    "collaterals",
    "competitors",
    "content-ideas",
    "dashboard",
    "deals",
    "domain-enrich",
    "email-studio",
    "exclusion-rules",
    "job-change-monitor",
    "linkedin",
    "mailbridge",
    "meeting-prep",
    "optimization-rules",
    "prospect-source",
    "reply-drafts",
    "scheduler",
    "sequences",
    "signals",
    "templates",
    "weekly-digest",
]


def test_all_phase3_module_routers_registered() -> None:
    """Auto-discovery must register every Phase 3 module router.

    With auto-discovery (audit M-06 fix), ``_wire_module_routers`` uses
    ``pkgutil.iter_modules`` to enumerate every submodule of ``app.api.v1``
    and collects any module-level ``router`` attribute that is an APIRouter.
    The discovered list therefore includes BOTH the 22 Phase 3 modules AND
    the Phase 2 modules (auth, autopilot, dashboard, llm_config, etc.) —
    total >= 22 Phase 3 + >= 8 Phase 2 = >= 30 routers.
    """
    discovered = _wire_module_routers()
    # Every Phase 3 module prefix must be reachable in the discovered router.
    paths = {route.path for route in discovered.routes if hasattr(route, "path")}
    for module in EXPECTED_PHASE3_MODULES:
        assert any(f"/{module}" in p for p in paths), (
            f"Phase 3 module '/{module}' is not reachable via auto-discovery. "
            f"Check that app/api/v1/{module.replace('-', '_')}.py exposes a "
            f"module-level `router = APIRouter(...)`."
        )


def test_api_router_auto_mounts_all_modules() -> None:
    """api_router must include every Phase 3 module prefix."""
    paths = {route.path for route in api_router.routes if hasattr(route, "path")}
    for module in EXPECTED_PHASE3_MODULES:
        # Each module prefix must appear in at least one route path.
        assert any(f"/{module}" in p for p in paths), (
            f"Module '/{module}' is not reachable in api_router."
        )


def test_main_app_includes_api_v1() -> None:
    """main.py must mount the api_router under /api/v1."""
    api_paths = [
        route.path for route in app.routes
        if hasattr(route, "path") and route.path.startswith("/api/v1")
    ]
    assert len(api_paths) > 0, "No /api/v1/* routes mounted in main.py."


# ── Exit criterion: OpenAPI generates with 137+ schemas ──────────────────────


def test_openapi_generates_cleanly() -> None:
    """app.openapi() must succeed without raising."""
    openapi = app.openapi()
    assert openapi["openapi"].startswith("3.")


def test_openapi_has_137_plus_schemas() -> None:
    """Phase 3 exit criterion: Full OpenAPI spec generates with 137+ schemas."""
    openapi = app.openapi()
    schemas = openapi.get("components", {}).get("schemas", {})
    assert len(schemas) >= 137, (
        f"Expected 137+ schemas, got {len(schemas)}."
    )


# ── 7-touch cadence ──────────────────────────────────────────────────────────


def test_seven_touch_cadence_days() -> None:
    """Phase 3 deliverable: 7-touch cadence on days 1/4/9/16/25/35."""
    from app.schemas.sequences import SEVEN_TOUCH_CADENCE

    send_days = [c.sendDay for c in SEVEN_TOUCH_CADENCE]
    # First 6 touches land on the documented cadence; 7th is a final breakup.
    assert send_days[:6] == [1, 4, 9, 16, 25, 35], (
        f"Cadence days must be 1/4/9/16/25/35, got {send_days[:6]}."
    )


# ── Auto-pilot eligibility rule ──────────────────────────────────────────────


def test_autopilot_eligibility_constants() -> None:
    """
    Phase 3 deliverable: auto-pilot eligibility = positive category +
    confidence >= 0.8 + status == 'approved'.
    """
    from app.features.reply_drafts.service import (
        AUTOPILOT_MIN_CONFIDENCE,
        AUTOPILOT_REQUIRED_STATUS,
        POSITIVE_CATEGORIES,
    )

    assert AUTOPILOT_MIN_CONFIDENCE == 0.8
    assert AUTOPILOT_REQUIRED_STATUS == "approved"
    assert "interested" in POSITIVE_CATEGORIES
    assert "meeting_request" in POSITIVE_CATEGORIES


def test_autopilot_eligibility_rule_logic() -> None:
    """The _is_autopilot_eligible helper enforces all three conditions."""
    from app.features.reply_drafts.service import ReplyDraftService

    svc = ReplyDraftService
    # All three met → eligible
    assert svc._is_autopilot_eligible("interested", 0.9, "approved") is True
    # Confidence below threshold → not eligible
    assert svc._is_autopilot_eligible("interested", 0.7, "approved") is False
    # Wrong status → not eligible
    assert svc._is_autopilot_eligible("interested", 0.9, "pending") is False
    # Non-positive category → not eligible
    assert svc._is_autopilot_eligible("negative_reply", 0.9, "approved") is False


# ── CSV export (RFC-4180 + UTF-8 BOM) ────────────────────────────────────────


def test_csv_export_has_utf8_bom_and_crlf() -> None:
    """Phase 3 deliverable: CSV export must be RFC-4180 (CRLF) + UTF-8 BOM."""
    csv_text = rows_to_csv(
        [{"name": "Tést, LLC", "value": 42}],
        ["name", "value"],
    )
    # BOM present
    assert csv_text.startswith("\ufeff"), "CSV must start with UTF-8 BOM."
    # CRLF line endings
    assert "\r\n" in csv_text, "CSV must use CRLF line endings (RFC-4180)."
    # Comma-containing field is quoted
    assert '"Tést, LLC"' in csv_text, "Comma-containing field must be quoted."


def test_csv_export_empty_iterable_produces_header_only() -> None:
    """Empty input must still produce a header-only CSV."""
    csv_text = rows_to_csv([], ["id", "name"])
    lines = csv_text.split("\r\n")
    # First non-BOM line is the header
    header_line = lines[0].lstrip("\ufeff")
    assert header_line == "id,name"


# ── Two-proportion z-test (A/B significance) ─────────────────────────────────


def test_ab_significance_two_proportion_z() -> None:
    """The z-test helper must produce a valid (z, p) tuple."""
    from app.features.ab_testing.service import AbTestingService

    svc = AbTestingService
    # 10/100 vs 20/100 — should detect a difference.
    z, p = svc._two_proportion_z(10, 100, 20, 100)
    assert isinstance(z, float)
    assert isinstance(p, float)
    assert 0.0 <= p <= 1.0
    # Same proportions → p should be 1.0 (no difference)
    z2, p2 = svc._two_proportion_z(10, 100, 10, 100)
    assert p2 == 1.0
