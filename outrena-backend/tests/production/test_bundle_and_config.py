"""
test_bundle_and_config.py — Verify frontend build config and production readiness.

Pure-Python static analysis tests. They check:
  1. vite.config.ts has manualChunks configured (bundle splitting).
  2. The brand-assets chunk is isolated.
  3. .env.example exists and has no production secrets hardcoded.
  4. docker-compose.yml does not have SKIP_JWT_VERIFICATION=false in prod comment.
  5. The backend requirements.txt contains all required production packages.
"""
from __future__ import annotations

import os
import re

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))  # outrena-backend/
ROOT = os.path.normpath(os.path.join(BASE, ".."))  # production/
FRONTEND = os.path.join(ROOT, "outrena-frontend")


def _read_rel(root: str, rel: str) -> str:
    with open(os.path.join(root, rel)) as f:
        return f.read()


# ── vite.config.ts ───────────────────────────────────────────────────────────

def test_vite_config_has_manual_chunks() -> None:
    content = _read_rel(FRONTEND, "vite.config.ts")
    assert "manualChunks" in content, (
        "vite.config.ts is missing manualChunks. "
        "The 1.94 MB single bundle causes long parse times for alpha users."
    )


def test_vite_config_isolates_brand_assets() -> None:
    content = _read_rel(FRONTEND, "vite.config.ts")
    assert "brand-assets" in content, (
        "vite.config.ts should isolate brand-assets into its own chunk "
        "(it's the largest single module due to base64 logo data)."
    )


def test_vite_config_splits_react_vendor() -> None:
    content = _read_rel(FRONTEND, "vite.config.ts")
    assert "react" in content and "vendor" in content.lower(), (
        "vite.config.ts should split React + react-dom into a vendor chunk."
    )


# ── .env.example ─────────────────────────────────────────────────────────────

def test_env_example_exists() -> None:
    path = os.path.join(BASE, ".env.example")
    assert os.path.isfile(path), ".env.example not found in outrena-backend/"


def test_env_example_no_real_secrets() -> None:
    content = _read_rel(BASE, ".env.example")
    # Only flag keys that have a non-empty, non-comment value that looks like a real secret.
    # Matches: KEY=<non-empty, non-whitespace value> — skips KEY= (empty) and inline comments.
    real_secrets = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        for key in ("STRIPE_SECRET_KEY", "ENCRYPTION_KEY"):
            m = re.match(rf'^{key}\s*=\s*(\S+)', line)
            if m:
                val = m.group(1)
                # Skip empty assignments and inline-comment-only values
                if val and not val.startswith("#"):
                    real_secrets.append(f"{key}={val}")
    assert not real_secrets, (
        f"Found potentially real secrets in .env.example: {real_secrets}"
    )


# ── requirements.txt ─────────────────────────────────────────────────────────

def test_requirements_has_fastapi() -> None:
    content = _read_rel(BASE, "requirements.txt")
    assert "fastapi" in content.lower()


def test_requirements_has_prometheus_client() -> None:
    content = _read_rel(BASE, "requirements.txt")
    assert "prometheus-client" in content.lower(), (
        "prometheus-client missing from requirements.txt — /metrics endpoint requires it."
    )


def test_requirements_has_sqlalchemy() -> None:
    content = _read_rel(BASE, "requirements.txt")
    assert "sqlalchemy" in content.lower()


def test_requirements_has_posthog() -> None:
    content = _read_rel(BASE, "requirements.txt")
    assert "posthog" in content.lower(), (
        "posthog SDK missing from requirements.txt — exception tracking requires it."
    )


# ── docker-compose.yml ────────────────────────────────────────────────────────

def test_docker_compose_has_all_services() -> None:
    content = _read_rel(ROOT, "docker-compose.yml")
    for service in ("postgres", "redis", "keycloak", "backend", "frontend"):
        assert f"{service}:" in content, f"docker-compose.yml missing '{service}' service"


def test_docker_compose_skip_jwt_dev_only_comment() -> None:
    content = _read_rel(ROOT, "docker-compose.yml")
    # Must document that SKIP_JWT_VERIFICATION is dev-only
    assert "NEVER true in production" in content or "dev only" in content.lower(), (
        "docker-compose.yml should note that SKIP_JWT_VERIFICATION is dev-only."
    )
