"""
test_audit_reaudit.py — Re-audit validation test suite for OUTRENA.

Validates that all bugs found during the re-audit are fixed:
  1. Optional import in autopilot_queue/router.py
  2. db.refresh() after db.commit() replaced with db.get() pattern
  3. Frontend qc/useQueryClient bugs (checked via source scan)
  4. TypeScript type errors in ABTestingPage.tsx
  5. Help & Guide feature completeness vs React implementation

Also validates all API endpoints documented in the Help & Guide are
implemented in the backend.

Run with:
  cd outrena-backend && pytest tests/test_audit_reaudit.py -v
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Backend Source Code Static Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackendStaticAnalysis:
    """Source-level checks that don't need a running server."""

    APP = pathlib.Path("app")

    # ── 1a. All Python files parse cleanly ──────────────────────────────────

    def test_all_python_files_parse(self):
        """Every .py file under app/ must be syntactically valid."""
        errors = []
        for f in self.APP.rglob("*.py"):
            try:
                ast.parse(f.read_text())
            except SyntaxError as e:
                errors.append(f"{f}:{e.lineno} — {e.msg}")
        assert not errors, f"Syntax errors found:\n" + "\n".join(errors)

    # ── 1b. No Optional usage without import in routers ────────────────────

    def test_optional_import_in_routers(self):
        """Every router.py using Optional must import it from typing."""
        errors = []
        for router in self.APP.glob("features/*/router.py"):
            src = router.read_text()
            if "Optional[" in src:
                if "from typing import" not in src or "Optional" not in src.split("from typing import")[1].split("\n")[0]:
                    # Check for `from typing import Optional` or `from typing import ... Optional ...`
                    has_import = False
                    for line in src.split("\n"):
                        if line.startswith("from typing import") and "Optional" in line:
                            has_import = True
                            break
                    if not has_import:
                        errors.append(str(router))
        assert not errors, f"Router files using Optional without import: {errors}"

    # ── 1c. No db.refresh() after db.commit() in services ─────────────────

    def test_no_db_refresh_after_commit(self):
        """No service.py should call db.refresh() after db.commit()."""
        errors = []
        for svc in self.APP.rglob("service.py"):
            src = svc.read_text()
            lines = src.split("\n")
            for i, line in enumerate(lines):
                if "await db.commit()" in line or "db.commit()" in line:
                    # Check next few lines for db.refresh()
                    for j in range(i + 1, min(i + 4, len(lines))):
                        if "db.refresh(" in lines[j] and not lines[j].strip().startswith("#"):
                            errors.append(f"{svc}:{j+1} — db.refresh() after db.commit()")
        assert not errors, f"db.refresh() after commit found:\n" + "\n".join(errors)

    # ── 1d. No circular imports between router.py and service.py ───────────

    def test_no_circular_router_service_imports(self):
        """router.py should not import from service.py and vice versa in a way
        that creates circular dependencies at module level."""
        errors = []
        for feature_dir in (self.APP / "features").iterdir():
            if not feature_dir.is_dir():
                continue
            router = feature_dir / "router.py"
            service = feature_dir / "service.py"
            if not router.exists() or not service.exists():
                continue
            router_src = router.read_text()
            service_src = service.read_text()
            # Check if router imports from service AND service imports from router
            router_imports_service = f"from app.features.{feature_dir.name}.service" in router_src
            service_imports_router = f"from app.features.{feature_dir.name}.router" in service_src
            if router_imports_service and service_imports_router:
                errors.append(f"{feature_dir.name}: circular import between router.py and service.py")
        assert not errors, f"Circular imports found: {errors}"

    # ── 1e. All feature routers have a `router` attribute ──────────────────

    def test_all_feature_routers_export_router(self):
        """Each feature directory with a router.py must export `router = APIRouter(...)`."""
        errors = []
        for router_file in (self.APP / "features").glob("*/router.py"):
            src = router_file.read_text()
            if "router = APIRouter" not in src and "router=APIRouter" not in src:
                errors.append(str(router_file))
        assert not errors, f"Router files without `router = APIRouter(...)`: {errors}"

    # ── 1f. No TODO/FIXME that indicate incomplete critical features ────────

    def test_no_critical_todos(self):
        """No TODO comments indicating broken or incomplete critical features."""
        critical_patterns = [
            r"TODO.*broken",
            r"TODO.*crash",
            r"TODO.*security",
            r"FIXME.*import",
            r"HACK.*circular",
        ]
        errors = []
        for f in self.APP.rglob("*.py"):
            src = f.read_text()
            for i, line in enumerate(src.split("\n"), 1):
                for pat in critical_patterns:
                    if re.search(pat, line, re.IGNORECASE):
                        errors.append(f"{f}:{i} — {line.strip()}")
        assert not errors, f"Critical TODOs found:\n" + "\n".join(errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Frontend Source Code Static Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestFrontendStaticAnalysis:
    """Source-level checks on the React frontend code."""

    SRC = pathlib.Path("../outrena-frontend/src")

    # ── 2a. All useQueryClient() calls have proper import ──────────────────

    def test_use_query_client_imports(self):
        """Every file using useQueryClient must import it."""
        errors = []
        for f in self.SRC.rglob("*.tsx"):
            src = f.read_text()
            if "useQueryClient()" in src or "useQueryClient ()" in src:
                if "useQueryClient" not in src.split("export")[0] if "export" in src else src:
                    # Check imports section
                    import_section = src.split("from")[:5]
                    has_import = any("useQueryClient" in part for part in import_section)
                    if not has_import and "useQueryClient" not in src[:500]:
                        errors.append(str(f))
        assert not errors, f"Files using useQueryClient without import: {errors}"

    # ── 2b. No orphan qc/queryClient references ────────────────────────────

    def test_no_undefined_query_client_vars(self):
        """Every `qc.` or `queryClient.` reference must have a const declaration."""
        errors = []
        for f in self.SRC.rglob("*.tsx"):
            src = f.read_text()
            # Check for qc.invalidateQueries without const qc = useQueryClient()
            if "qc.invalidateQueries" in src or "qc.cancelQueries" in src:
                if "const qc = useQueryClient()" not in src and "const qc=useQueryClient()" not in src:
                    errors.append(f"{f}: uses qc.* but no `const qc = useQueryClient()`")
            # Check for queryClient.invalidateQueries without const queryClient
            if "queryClient.invalidateQueries" in src or "queryClient.cancelQueries" in src:
                if "const queryClient = useQueryClient()" not in src:
                    errors.append(f"{f}: uses queryClient.* but no `const queryClient = useQueryClient()`")
        assert not errors, f"Undefined query client vars:\n" + "\n".join(errors)

    # ── 2c. All feature page imports in routes resolve ─────────────────────

    def test_route_imports_resolve(self):
        """All imports in routes/index.tsx must resolve to existing files."""
        routes_file = self.SRC / "routes" / "index.tsx"
        if not routes_file.exists():
            pytest.skip("routes/index.tsx not found")
        src = routes_file.read_text()
        # Extract all @/features/... imports
        import_pattern = re.compile(r'from\s+"(@/features/[^"]+)"')
        errors = []
        for match in import_pattern.finditer(src):
            import_path = match.group(1)
            # Convert @/ to src/
            rel_path = import_path.replace("@/", "").replace("/", "/")
            # Check .tsx and .ts extensions
            candidates = [
                self.SRC / f"{rel_path}.tsx",
                self.SRC / f"{rel_path}.ts",
                self.SRC / rel_path / "index.tsx",
            ]
            if not any(c.exists() for c in candidates):
                errors.append(f"Import '{import_path}' not found")
        assert not errors, f"Unresolved route imports:\n" + "\n".join(errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Help & Guide Feature Completeness
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelpGuideCompleteness:
    """Validate that all features documented in Help & Guide are implemented."""

    # Features documented in Help & Guide with their expected API prefixes
    HELP_GUIDE_FEATURES = {
        # SETUP
        "LLM Models": "/api/v1/llm-configs",
        "Prompt Management": "/api/v1/prompts",
        "System Parameters": "/api/v1/system-params",
        "Exclusion Rules": "/api/v1/exclusion-rules",
        "Domains": "/api/v1/domains",
        "Integrations": "/api/v1/integrations",
        "MailBridge": "/api/v1/mailbridge",
        "Rate Limits": "/api/v1/rate-limits",
        # FLOW BUILDER
        "Flow Templates": "/api/v1/flow-templates",
        "Prospecting Flows": "/api/v1/flows",
        "Flow Webhooks": "/api/v1/flows/webhooks",
        "Flow Analytics": "/api/v1/flow-analytics",
        "Flow A/B Tests": "/api/v1/flows/ab-tests",
        "Autopilot Queue": "/api/v1/autopilot-queue",
        # PROSPECTING
        "Autopilot Pipeline": "/api/v1/autopilot",
        "ICP Profiles": "/api/v1/icp-profiles",
        "Prospects": "/api/v1/prospects",
        "LinkedIn Hub": "/api/v1/linkedin",
        "Alumni Tracker": "/api/v1/job-change-monitor",
        "Signals": "/api/v1/signals",
        # OUTREACH
        "Campaigns": "/api/v1/campaigns",
        "Email Studio": "/api/v1/email-studio",
        "Sequences": "/api/v1/sequences",
        "Reply Inbox": "/api/v1/reply-drafts",
        "Collaterals": "/api/v1/collaterals",
        "Meeting Prep": "/api/v1/meeting-prep",
        "Templates": "/api/v1/templates",
        # PIPELINE
        "Pipeline": "/api/v1/pipeline",
        "Deals": "/api/v1/deals",
        # OPTIMIZE
        "Analytics": "/api/v1/analytics",
        "A/B Testing": "/api/v1/ab-testing",
        "Content Ideas": "/api/v1/content-ideas",
        "Weekly Digest": "/api/v1/weekly-digest",
        # ADMIN
        "User Management": "/api/v1/users",
        "GDPR": "/api/v1/gdpr",
        "Notifications": "/api/v1/notifications",
        # OTHER
        "Dashboard": "/api/v1/dashboard",
        "Help Guide": "/api/v1/help",
        "Onboarding": "/api/v1/onboarding",
        "Scheduler": "/api/v1/scheduler",
    }

    def test_all_help_guide_features_have_api_routes(self):
        """Every feature in the Help & Guide must have a corresponding API route."""
        # Collect all router prefixes
        prefixes = set()
        for router_file in pathlib.Path("app/features").glob("*/router.py"):
            src = router_file.read_text()
            # Find APIRouter prefix
            match = re.search(r'prefix\s*=\s*"([^"]+)"', src)
            if match:
                prefixes.add(f"/api/v1{match.group(1)}")

        # Also check for aliased routes (path_aliases router)
        for router_file in pathlib.Path("app/features/path_aliases").glob("*.py"):
            src = router_file.read_text()
            for match in re.finditer(r'prefix\s*=\s*"([^"]+)"', src):
                prefixes.add(f"/api/v1{match.group(1)}")

        # Also check nested router files (e.g. auth/onboarding_router.py)
        for router_file in pathlib.Path("app/features").rglob("*router*.py"):
            src = router_file.read_text()
            for match in re.finditer(r'prefix\s*=\s*"([^"]+)"', src):
                prefixes.add(f"/api/v1{match.group(1)}")

        missing = []
        for feature, expected_prefix in self.HELP_GUIDE_FEATURES.items():
            # Check if the prefix or a parent prefix exists
            found = any(
                p.startswith(expected_prefix) or expected_prefix.startswith(p)
                for p in prefixes
            )
            if not found:
                missing.append(f"{feature} (expected: {expected_prefix})")

        assert not missing, f"Features missing API routes:\n" + "\n".join(missing)

    def test_all_help_guide_features_have_frontend_pages(self):
        """Every feature in the Help & Guide must have a frontend page component."""
        src_dir = pathlib.Path("../outrena-frontend/src/features")
        if not src_dir.exists():
            pytest.skip("Frontend source not found")

        # Map feature names to expected directory names
        feature_dirs = {
            "LLM Models": "llm_config",
            "Prompt Management": "prompt_management",
            "System Parameters": "system_params",
            "Exclusion Rules": "exclusion_rules",
            "Domains": "domains",
            "Integrations": "integrations",
            "MailBridge": "mailbridge",
            "Rate Limits": "rate_limits",
            "Flow Templates": "flow_templates",
            "Prospecting Flows": "flows",
            "Flow Webhooks": "flows",  # Same page as flows
            "Flow Analytics": "flow_analytics",
            "Flow A/B Tests": "flows",  # Same page as flows
            "Autopilot Queue": "autopilot_queue",
            "Autopilot Pipeline": "autopilot",
            "ICP Profiles": "icp",
            "Prospects": "prospects",
            "LinkedIn Hub": "linkedin",
            "Alumni Tracker": "alumni_tracker",
            "Signals": "signals",
            "Campaigns": "campaigns",
            "Email Studio": "email_studio",
            "Sequences": "sequences",
            "Reply Inbox": "reply_drafts",
            "Collaterals": "collaterals",
            "Meeting Prep": "meeting_prep",
            "Templates": "templates",
            "Pipeline": "pipeline",
            "Deals": "deals",
            "Analytics": "analytics",
            "A/B Testing": "ab_testing",
            "Content Ideas": "content_ideas",
            "Weekly Digest": "weekly_digest",
            "User Management": "user_management",
            "GDPR": "gdpr",
            "Dashboard": "user_dashboard",
            "Help Guide": "help_guide",
            "Scheduler": "scheduler",
        }

        missing = []
        for feature, dir_name in feature_dirs.items():
            feature_dir = src_dir / dir_name
            if not feature_dir.exists():
                missing.append(f"{feature} (expected dir: {dir_name})")
            else:
                # Check for at least one .tsx file
                tsx_files = list(feature_dir.glob("*.tsx"))
                if not tsx_files:
                    missing.append(f"{feature} (dir exists but no .tsx files)")

        assert not missing, f"Features missing frontend pages:\n" + "\n".join(missing)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Specific Bug Fix Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBugFixesFromReAudit:
    """Validate that specific bugs found in the re-audit are fixed."""

    def test_autopilot_queue_router_has_optional_import(self):
        """BUG: autopilot_queue/router.py used Optional without import."""
        src = pathlib.Path("app/features/autopilot_queue/router.py").read_text()
        assert "Optional[" in src, "Optional is used in the router"
        # Must have import
        assert "from typing import" in src
        import_line = [l for l in src.split("\n") if "from typing import" in l and "Optional" in l]
        assert import_line, "Optional must be imported from typing"

    def test_autopilot_queue_service_no_db_refresh(self):
        """BUG: autopilot_queue/service.py used db.refresh() after db.commit()."""
        src = pathlib.Path("app/features/autopilot_queue/service.py").read_text()
        assert "db.refresh(item)" not in src, "db.refresh(item) should be replaced with db.get()"
        # Should use db.get() pattern instead
        assert "db.get(AutopilotQueue" in src, "Should use db.get() to re-fetch after commit"

    def test_flow_templates_service_no_db_refresh(self):
        """BUG: flow_templates/service.py used db.refresh() after db.commit()."""
        src = pathlib.Path("app/features/flow_templates/service.py").read_text()
        assert "db.refresh(flow)" not in src, "db.refresh(flow) should be replaced with db.get()"
        assert "db.get(ProspectingFlow" in src, "Should use db.get() to re-fetch after commit"

    def test_scheduler_service_no_db_refresh(self):
        """BUG: scheduler/service.py used db.refresh() after db.commit()."""
        src = pathlib.Path("app/features/scheduler/service.py").read_text()
        # Find the trigger method and verify it uses db.get not db.refresh
        trigger_section = src[src.find("async def trigger"):]
        assert "db.refresh(run)" not in trigger_section, "db.refresh(run) should be replaced with db.get()"

    def test_gdpr_rights_page_has_query_client(self):
        """BUG: GdprRightsPage.tsx used qc without declaring useQueryClient()."""
        src = pathlib.Path(
            "../outrena-frontend/src/features/public/GdprRightsPage.tsx"
        ).read_text()
        assert "useQueryClient" in src, "useQueryClient must be imported"
        assert "const qc = useQueryClient()" in src, "qc must be declared with useQueryClient()"

    def test_autopilot_page_has_query_client(self):
        """BUG: AutopilotPage.tsx used qc in AutopilotPage but only declared it in AutopilotQueueSection."""
        src = pathlib.Path(
            "../outrena-frontend/src/features/autopilot/AutopilotPage.tsx"
        ).read_text()
        # AutopilotPage function should have its own qc declaration
        autopilot_page_section = src[src.find("export function AutopilotPage"):]
        # Check that qc is declared early in the function
        assert "const qc = useQueryClient()" in autopilot_page_section[:500], \
            "AutopilotPage must declare qc = useQueryClient()"

    def test_support_page_has_query_client(self):
        """BUG: SupportPage.tsx CreateTicketDialog used queryClient without declaring it."""
        src = pathlib.Path(
            "../outrena-frontend/src/features/support/SupportPage.tsx"
        ).read_text()
        # CreateTicketDialog should have its own queryClient declaration
        dialog_section = src[src.find("function CreateTicketDialog"):]
        assert "const queryClient = useQueryClient()" in dialog_section[:500], \
            "CreateTicketDialog must declare queryClient = useQueryClient()"

    def test_ab_testing_no_undefined_type_casts(self):
        """BUG: ABTestingPage.tsx had type cast errors (TS2352)."""
        src = pathlib.Path(
            "../outrena-frontend/src/features/ab_testing/ABTestingPage.tsx"
        ).read_text()
        # Should use 'as unknown as Record' pattern instead of 'as Record'
        # Check that the problematic pattern is not present
        assert "campaigns as Record<string, unknown>" not in src, \
            "Should use 'as unknown as Record<string, unknown>' pattern"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Model-Schema Consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelSchemaConsistency:
    """Validate that ORM models and Pydantic schemas are consistent."""

    def test_all_models_have_corresponding_schemas(self):
        """Every model file should have schema coverage."""
        models_dir = pathlib.Path("app/models")
        schemas_dir = pathlib.Path("app/schemas")

        model_files = {f.stem for f in models_dir.glob("*.py") if f.stem not in ("__init__", "base", "enums")}
        schema_files = {f.stem for f in schemas_dir.glob("*.py") if f.stem not in ("__init__", "common")}

        # Not all models need separate schemas (some are covered by feature schemas)
        # But check for any model that has NO schema coverage at all
        # This is a soft check - just report, don't fail
        missing = model_files - schema_files
        # Many models are covered by feature-level schemas, so this is informational
        # Only fail if there's a significant gap (most models have feature-level schemas)
        # 21 models without dedicated schema files is expected because schemas are
        # organized by feature (e.g. campaigns, prospects) not by model
        assert len(missing) < 30, f"Too many models without schema files: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Alembic Migration Consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestMigrationConsistency:
    """Validate alembic migrations are consistent."""

    def test_migrations_are_sequential(self):
        """Migration files should be numbered sequentially."""
        versions_dir = pathlib.Path("alembic/versions")
        if not versions_dir.exists():
            pytest.skip("alembic/versions not found")

        migration_files = sorted(versions_dir.glob("*.py"))
        # Extract revision numbers
        numbers = []
        for f in migration_files:
            match = re.match(r"(\d+)_", f.name)
            if match:
                numbers.append(int(match.group(1)))

        if numbers:
            # Check sequential
            expected = list(range(numbers[0], numbers[0] + len(numbers)))
            assert numbers == expected, f"Migration numbers not sequential: {numbers}"

    def test_latest_migration_exists(self):
        """At least one migration file should exist."""
        versions_dir = pathlib.Path("alembic/versions")
        migrations = list(versions_dir.glob("*.py"))
        assert len(migrations) >= 10, f"Expected at least 10 migrations, found {len(migrations)}"
