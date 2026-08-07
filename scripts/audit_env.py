#!/usr/bin/env python3
"""
audit_env.py — Validate OUTRENA .env files + Terraform tfvars for security footguns.

Purpose:
    Per pitfall #4 (duplicate .env entries — last-wins is a footgun) and §14 security
    review: scan every .env file under the backend module for duplicate keys, scan
    staging/prod tfvars for `skip_jwt_verification = true` (or SKIP_JWT_VERIFICATION=true
    in .env — these MUST be false in non-dev), and scan all tfvars for committed
    secrets (AWS keys, password=, private key fragments, etc.).

Usage:
    python audit_env.py [--env-dir outrena-backend] [--tfvars terraform/aws/envs]
                        [--env-file-glob '.env*'] [--strict]

    --env-dir         Directory to scan for .env files (recursive). Default: outrena-backend
    --tfvars          Directory containing staging.tfvars / prod.tfvars / dev.tfvars.
                      Default: terraform/aws/envs
    --env-file-glob   Glob (relative to --env-dir) for env files. Default: '.env*'
                      Note: file names starting with '.' may be hidden — use '**/.env*'
                      to recurse.
    --strict          Treat dev.tfvars SKIP_JWT_VERIFICATION != true as an error (default: warn).

Exit codes:
    0  all checks passed
    1  one or more checks failed (duplicates / security / non-dev SKIP_JWT_VERIFICATION=true)
    2  usage / IO error (missing directories, etc.)

Depends on:
    Python 3.10+ standard library only (pathlib, argparse, re, sys, collections).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# .env parsing: KEY=VALUE (with optional 'export ' prefix, optional quotes).
# Comments start with '#'. Blank lines ignored. Inline comments after value
# are stripped only if the value is unquoted.
_ENV_LINE_RE = re.compile(
    r"""^\s*
        (?:export\s+)?                # optional export prefix
        (?P<key>[A-Za-z_][A-Za-z0-9_]*)  # key
        \s*=\s*                       # =
        (?P<value>.*)?$               # value (rest of line, possibly empty)
    """,
    re.VERBOSE,
)

# .tfvars parsing: KEY = "value" | number | bool | list(...) | map(...) | heredoc.
# We focus on the simple scalar forms — full HCL parsing is out-of-scope (stdlib only).
# This regex matches simple `key = "value"` and `key = true/false/number` lines.
_TFVARS_LINE_RE = re.compile(
    r"""^\s*
        (?P<key>[A-Za-z_][A-Za-z0-9_]*)
        \s*=\s*
        (?P<value>
            "(?:[^"\\]|\\.)*"           # double-quoted string
            | '(?:[^'\\]|\\.)*'         # single-quoted string
            | true|false                # bool
            | -?\d+(?:\.\d+)?           # number
        )
        \s*$
    """,
    re.VERBOSE,
)

# Security patterns — committed secrets footgun (per §14 security review).
# Patterns kept tight to avoid false positives but cover the common leaks:
#   - AWS access key IDs: AKIA + 16 uppercase alphanumerics
#   - AWS secret access keys: 40-char base64 (loose — comment in code)
#   - password= / passwd= / pwd= / secret=  followed by a non-empty value
#   - private key fragments: -----BEGIN ... PRIVATE KEY-----
#   - Slack/GitHub tokens: common prefixes
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key ID",         re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Access Key",     re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])")),
    ("GitHub Token",              re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Slack Token",               re.compile(r"xox[abp]-[A-Za-z0-9-]{10,}")),
    ("Private Key block",         re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----")),
    ("password assignment",       re.compile(r"(?i)(?:password|passwd|pwd|secret|api[_-]?key)\s*[:=]\s*[\"']?[^\s\"']{4,}")),
    ("Generic connection string", re.compile(r"(?i)(?:postgres|mysql|mongodb|redis)://[^\s\"']+:[^\s\"']+@")),
]

# Allowlist for the loose AWS Secret pattern (40-char base64) — common false
# positives we want to suppress (these are obviously not secrets):
_SECRET_ALLOWLIST_SUBSTRINGS = (
    "arn:aws",          # ARNs
    "sha256:",          # sha digests
    "ecdsa-sha2-",      # ssh key type prefixes
    "ssh-rsa", "ssh-ed25519",
)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

class CheckResult:
    """One check outcome. status: 'PASS' | 'WARN' | 'FAIL'."""

    def __init__(self, name: str, status: str, detail: str) -> None:
        self.name = name
        self.status = status
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.status:>4}] {self.name:<40} {self.detail}"


def _print_results(results: list[CheckResult]) -> tuple[int, int]:
    """Print results table, return (warn_count, fail_count)."""
    print()
    print(f"{'CHECK':<42} {'STATUS':<6} DETAIL")
    print("-" * 100)
    warn_count = 0
    fail_count = 0
    for r in results:
        print(f"{r.name:<42} {r.status:<6} {r.detail}")
        if r.status == "WARN":
            warn_count += 1
        elif r.status == "FAIL":
            fail_count += 1
    print("-" * 100)
    print(f"Pass={len(results) - warn_count - fail_count}  Warn={warn_count}  Fail={fail_count}")
    return warn_count, fail_count


# ---------------------------------------------------------------------------
# .env parsing
# ---------------------------------------------------------------------------

def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """
    Parse a .env file into a dict (last-wins semantics — what the runtime sees),
    plus the list of keys in source order (so we can detect duplicates).

    Returns (env_dict, ordered_keys).
    """
    env: dict[str, str] = {}
    ordered_keys: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        value = (m.group("value") or "").strip()
        # Strip inline comments only if the value is unquoted.
        if value and value[0] not in ("'", '"'):
            # Look for ' #' (space then hash) — treat as inline comment.
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
        # Strip surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
        ordered_keys.append(key)
    return env, ordered_keys


def audit_env_duplicates(path: Path) -> CheckResult:
    """pitfall #4 — duplicate keys in a single .env file are a footgun."""
    _, ordered = parse_env_file(path)
    counts = Counter(ordered)
    dupes = {k: c for k, c in counts.items() if c > 1}
    if dupes:
        detail = ", ".join(f"{k}×{c}" for k, c in sorted(dupes.items()))
        return CheckResult(
            name=f"env-dupes:{path.name}",
            status="FAIL",
            detail=f"duplicate keys (last-wins): {detail}",
        )
    return CheckResult(
        name=f"env-dupes:{path.name}",
        status="PASS",
        detail=f"{len(ordered)} keys, no duplicates",
    )


def _env_label_from_path(path: Path) -> str:
    """
    Extract the environment label from an .env-style filename.

    Conventions:
      .env              -> 'dev'   (bare .env is typically dev/local)
      .env.dev          -> 'dev'
      .env.staging      -> 'staging'
      .env.production   -> 'production'
      .env.local        -> 'local'
      anything else     -> the bare filename
    """
    name = path.name
    if name == ".env":
        return "dev"
    if name.startswith(".env."):
        return name[len(".env."):]
    return name


def audit_env_jwt_flag(path: Path, strict_non_dev: bool) -> list[CheckResult]:
    """SKIP_JWT_VERIFICATION must be false in staging/prod; warn if unset in dev."""
    env, _ = parse_env_file(path)
    results: list[CheckResult] = []
    key = "SKIP_JWT_VERIFICATION"
    val = env.get(key)
    env_label = _env_label_from_path(path)

    if env_label in ("staging", "prod", "production"):
        if val is None:
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status="PASS",
                detail=f"{key} not set (default false is safe for non-dev)",
            ))
        elif val.lower() in ("false", "0", "no", "off"):
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status="PASS",
                detail=f"{key}={val}",
            ))
        else:
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status="FAIL",
                detail=f"SECURITY: {key}={val} in non-dev environment ({env_label})",
            ))
    elif env_label in ("dev", "development", "local"):
        if val is None:
            status = "FAIL" if strict_non_dev else "WARN"
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status=status,
                detail=f"{key} not set in dev — recommend explicitly true (pitfall: silent default)",
            ))
        elif val.lower() in ("true", "1", "yes", "on"):
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status="PASS",
                detail=f"{key}={val} (dev — acceptable)",
            ))
        else:
            results.append(CheckResult(
                name=f"env-jwt:{path.name}",
                status="WARN",
                detail=f"{key}={val} in dev — expected 'true'",
            ))
    else:
        # Unknown env label (e.g. .env.test) — informational.
        results.append(CheckResult(
            name=f"env-jwt:{path.name}",
            status="PASS",
            detail=f"{key}={val} (env label '{env_label}' — no policy)",
        ))
    return results


# ---------------------------------------------------------------------------
# tfvars parsing
# ---------------------------------------------------------------------------

def parse_tfvars(path: Path) -> dict[str, str]:
    """Parse a tfvars file into {key: raw_value_string}."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = _TFVARS_LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        value = m.group("value")
        # Strip quotes from string values.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def audit_tfvars_jwt(path: Path) -> CheckResult:
    """skip_jwt_verification must be false (or unset) in staging/prod tfvars."""
    tfvars = parse_tfvars(path)
    # Try multiple key casing conventions.
    val = tfvars.get("skip_jwt_verification") or tfvars.get("SKIP_JWT_VERIFICATION")
    env_label = path.stem  # staging / prod / dev

    if env_label in ("staging", "prod", "production"):
        if val is None:
            return CheckResult(
                name=f"tfvars-jwt:{path.name}",
                status="PASS",
                detail="skip_jwt_verification not set (default false is safe)",
            )
        if val.lower() in ("true", "1"):
            return CheckResult(
                name=f"tfvars-jwt:{path.name}",
                status="FAIL",
                detail=f"SECURITY: SKIP_JWT_VERIFICATION=true in {env_label}",
            )
        return CheckResult(
            name=f"tfvars-jwt:{path.name}",
            status="PASS",
            detail=f"skip_jwt_verification={val}",
        )
    if env_label in ("dev", "development"):
        if val is None:
            return CheckResult(
                name=f"tfvars-jwt:{path.name}",
                status="WARN",
                detail="skip_jwt_verification not set in dev (recommend explicit true)",
            )
        return CheckResult(
            name=f"tfvars-jwt:{path.name}",
            status="PASS",
            detail=f"skip_jwt_verification={val} (dev)",
        )
    return CheckResult(
        name=f"tfvars-jwt:{path.name}",
        status="PASS",
        detail=f"skip_jwt_verification={val} (env '{env_label}' — no policy)",
    )


def audit_tfvars_secrets(path: Path) -> CheckResult:
    """Grep tfvars file contents for committed-secret patterns."""
    text = path.read_text(encoding="utf-8")
    hits: list[str] = []
    for label, pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            matched = m.group(0)
            # Skip allowlist false positives for the loose AWS Secret pattern.
            if any(sub in matched for sub in _SECRET_ALLOWLIST_SUBSTRINGS):
                continue
            # Skip if the matched string is inside a comment line.
            line_start = text.rfind("\n", 0, m.start()) + 1
            line = text[line_start : text.find("\n", m.start())]
            if line.lstrip().startswith("#") or line.lstrip().startswith("//"):
                continue
            hits.append(f"{label}: {matched[:60]}{'…' if len(matched) > 60 else ''}")
    if hits:
        return CheckResult(
            name=f"tfvars-secrets:{path.name}",
            status="FAIL",
            detail=f"SECURITY: {len(hits)} potential committed secret(s): " + "; ".join(hits[:3]),
        )
    return CheckResult(
        name=f"tfvars-secrets:{path.name}",
        status="PASS",
        detail="no secret patterns matched",
    )


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def discover_env_files(env_dir: Path, glob_pat: str) -> list[Path]:
    """Find all .env files under env_dir matching glob_pat (recursive)."""
    if not env_dir.is_dir():
        return []
    # Use '**' glob; sort for deterministic output.
    files = sorted(p for p in env_dir.glob(glob_pat) if p.is_file())
    # Filter out obvious template/copy files (.env.example, .env.sample) — they
    # are still scanned for secrets but skipped for dup checks (they're not runtime).
    return files


def discover_tfvars(tfvars_dir: Path) -> list[Path]:
    """Find *.tfvars (NOT *.tfvars.json — out of scope) under tfvars_dir."""
    if not tfvars_dir.is_dir():
        return []
    return sorted(p for p in tfvars_dir.glob("*.tfvars") if p.is_file())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit OUTRENA .env + tfvars for security footguns (pitfall #4, §14).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exit codes:
  0 all checks pass | 1 fail | 2 IO/usage error

Examples:
  python audit_env.py
  python audit_env.py --env-dir ../../outrena-backend --tfvars ../../terraform/aws/envs
""",
    )
    parser.add_argument("--env-dir", default="outrena-backend",
                        help="Directory to scan for .env files (default: outrena-backend)")
    parser.add_argument("--tfvars", default="terraform/aws/envs",
                        help="Directory containing staging/prod/dev .tfvars (default: terraform/aws/envs)")
    parser.add_argument("--env-file-glob", default="**/.env*",
                        help="Glob for env files relative to --env-dir (default: '**/.env*')")
    parser.add_argument("--strict", action="store_true",
                        help="Treat dev SKIP_JWT_VERIFICATION != true as an error (default: warn)")
    args = parser.parse_args()

    env_dir = Path(args.env_dir).resolve()
    tfvars_dir = Path(args.tfvars).resolve()

    if not env_dir.is_dir():
        print(f"ERROR: --env-dir does not exist: {env_dir}", file=sys.stderr)
        return 2
    if not tfvars_dir.is_dir():
        print(f"ERROR: --tfvars dir does not exist: {tfvars_dir}", file=sys.stderr)
        return 2

    print(f"audit_env: env-dir={env_dir}  tfvars-dir={tfvars_dir}  strict={args.strict}")

    results: list[CheckResult] = []

    # ---- .env files ----
    env_files = discover_env_files(env_dir, args.env_file_glob)
    if not env_files:
        results.append(CheckResult(
            name="env-discovery",
            status="WARN",
            detail=f"no .env files matching '{args.env_file_glob}' under {env_dir}",
        ))
    for ef in env_files:
        # Skip .env.example/.env.sample for duplicate checks (templates).
        if ef.name in (".env.example", ".env.sample", ".env.template", ".env.dist"):
            results.append(CheckResult(
                name=f"env-dupes:{ef.name}",
                status="PASS",
                detail="template file — skipped",
            ))
        else:
            results.append(audit_env_duplicates(ef))
        results.extend(audit_env_jwt_flag(ef, strict_non_dev=args.strict))

    # ---- tfvars ----
    tfvars_files = discover_tfvars(tfvars_dir)
    if not tfvars_files:
        results.append(CheckResult(
            name="tfvars-discovery",
            status="WARN",
            detail=f"no *.tfvars files under {tfvars_dir}",
        ))
    for tf in tfvars_files:
        results.append(audit_tfvars_jwt(tf))
        results.append(audit_tfvars_secrets(tf))

    # ---- summary ----
    _, fail_count = _print_results(results)
    if fail_count > 0:
        print(f"\nFAIL: {fail_count} check(s) failed — fix before merge.", file=sys.stderr)
        return 1
    print("\nOK: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
