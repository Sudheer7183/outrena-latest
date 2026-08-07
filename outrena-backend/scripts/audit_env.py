#!/usr/bin/env python3
"""
audit_env.py — Pre-deploy environment audit (OWASP A05 gate, Tech Doc §10.7).

Verifies production-critical environment settings BEFORE a deploy proceeds.
Exit code 0 = pass, 1 = fail (CI blocks the deploy).

Checks (production only — ENVIRONMENT in {production, prod}):
  1. SKIP_JWT_VERIFICATION must be false/unset
  2. ENCRYPTION_KEY must be set (Fernet at-rest crypto)
  3. SECRET_BACKEND must not be 'env'
  4. CORS_ALLOWED_ORIGINS must not contain '*'
  5. DATABASE_URL must not point at localhost
  6. POSTHOG_KEY should be set (warning only)

Usage:
    ENVIRONMENT=production python scripts/audit_env.py
CI usage (see .github/workflows/cd-prod-aws.yml):
    - run: python scripts/audit_env.py
"""
from __future__ import annotations

import os
import sys

FAIL = "\033[91mFAIL\033[0m"
PASS = "\033[92mPASS\033[0m"
WARN = "\033[93mWARN\033[0m"


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    env = (os.environ.get("ENVIRONMENT") or "development").strip().lower()
    is_prod = env in {"production", "prod"}

    print(f"audit_env: ENVIRONMENT={env} (prod checks {'ENABLED' if is_prod else 'skipped'})")
    if not is_prod:
        print(f"[{PASS}] Non-production environment — audit passes trivially.")
        return 0

    failures: list[str] = []
    warnings: list[str] = []

    # 1. SKIP_JWT_VERIFICATION
    if _truthy(os.environ.get("SKIP_JWT_VERIFICATION")):
        failures.append("SKIP_JWT_VERIFICATION is enabled — JWTs would NOT be verified in production.")
    else:
        print(f"[{PASS}] SKIP_JWT_VERIFICATION is disabled.")

    # 2. ENCRYPTION_KEY
    if not (os.environ.get("ENCRYPTION_KEY") or "").strip():
        failures.append("ENCRYPTION_KEY is unset — PII and credentials would be stored in PLAINTEXT.")
    else:
        print(f"[{PASS}] ENCRYPTION_KEY is set.")

    # 3. SECRET_BACKEND
    backend = (os.environ.get("SECRET_BACKEND") or "env").strip().lower()
    if backend == "env":
        failures.append("SECRET_BACKEND=env — production must use 'aws' or 'azure'.")
    else:
        print(f"[{PASS}] SECRET_BACKEND={backend}.")

    # 4. CORS wildcard
    cors = os.environ.get("CORS_ALLOWED_ORIGINS") or ""
    if "*" in cors:
        failures.append(f"CORS_ALLOWED_ORIGINS contains a wildcard: {cors!r}")
    else:
        print(f"[{PASS}] CORS_ALLOWED_ORIGINS has no wildcard.")

    # 5. DATABASE_URL localhost
    db = os.environ.get("DATABASE_URL") or ""
    if "localhost" in db or "127.0.0.1" in db:
        failures.append("DATABASE_URL points at localhost — not a production database.")
    else:
        print(f"[{PASS}] DATABASE_URL is not localhost.")

    # 6. POSTHOG_KEY (warning only)
    if not (os.environ.get("POSTHOG_KEY") or "").strip():
        warnings.append("POSTHOG_KEY is unset — exception tracking and analytics disabled.")

    for w in warnings:
        print(f"[{WARN}] {w}")
    for f in failures:
        print(f"[{FAIL}] {f}")

    if failures:
        print(f"\naudit_env: {len(failures)} failure(s) — deploy BLOCKED.")
        return 1
    print("\naudit_env: all checks passed — deploy may proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
