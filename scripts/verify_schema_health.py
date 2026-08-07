#!/usr/bin/env python3
"""
verify_schema_health.py — Detect tenant schema drift per §14 Risk #17.

Purpose:
    Iterate every active tenant in public.tenants, for each:
      - connect to the database
      - for every expected table in scripts/schema_baseline.yml:
          * confirm the table exists (SELECT 1 FROM <schema>.<table> LIMIT 0)
          * compare its column set against the baseline
      - record any missing tables, missing columns, or extra columns
    Exit non-zero if any drift is detected.

    The baseline is a *drift-detection subset* maintained alongside Alembic
    migrations (see scripts/schema_baseline.yml) — not the full 29-model set.
    Adding a column to the baseline requires a paired Alembic migration.

Usage:
    python verify_schema_health.py --database-url postgresql://user:pass@host:5432/dbname
        [--baseline scripts/schema_baseline.yml]
        [--tenants-schema public]
        [--verbose]

Exit codes:
    0  all tenant schemas match the baseline (no drift)
    1  one or more tenant schemas drifted (missing tables / missing columns / extra columns)
    2  usage / connection / baseline-parse error

Depends on:
    - Python 3.10+
    - asyncpg (assumed installed: pip install asyncpg)
    - PyYAML (assumed installed: pip install pyyaml)

Notes:
    - Async concurrency is capped (default 8 simultaneous tenants) to avoid
      connection-pool exhaustion on installations with many tenants.
    - All schema names are validated against `^[A-Za-z_][A-Za-z0-9_]*$` before
      being substituted into SQL — no SQL injection from the tenants table.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import asyncpg  # type: ignore[import-not-found]
except ImportError as e:  # pragma: no cover
    print("ERROR: asyncpg not installed. `pip install asyncpg`", file=sys.stderr)
    raise SystemExit(2) from e

try:
    import yaml  # type: ignore[import-not-found]
except ImportError as e:  # pragma: no cover
    print("ERROR: PyYAML not installed. `pip install pyyaml`", file=sys.stderr)
    raise SystemExit(2) from e


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COLUMN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TenantResult:
    """Per-tenant drift report."""

    slug: str
    schema: str
    status: str  # 'OK' | 'DRIFT' | 'ERROR'
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    extra_columns: dict[str, list[str]] = field(default_factory=dict)
    error: str | None = None

    @property
    def drift_count(self) -> int:
        return (
            len(self.missing_tables)
            + sum(len(v) for v in self.missing_columns.values())
            + sum(len(v) for v in self.extra_columns.values())
        )


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline(path: Path) -> dict[str, set[str]]:
    """
    Load schema_baseline.yml into {table_name: {column1, column2, ...}}.

    Expected YAML structure:
        tables:
          - name: tenants
            columns: [id, slug, schema_name, status, created_at]
          - name: messages
            columns: [id, tenant_id, role, content, created_at]
          ...
    """
    if not path.is_file():
        raise FileNotFoundError(f"baseline file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "tables" not in raw:
        raise ValueError(f"baseline {path}: missing top-level 'tables' key")
    tables_raw = raw["tables"]
    if not isinstance(tables_raw, list):
        raise ValueError(f"baseline {path}: 'tables' must be a list")

    out: dict[str, set[str]] = {}
    for entry in tables_raw:
        if not isinstance(entry, dict) or "name" not in entry or "columns" not in entry:
            raise ValueError(f"baseline {path}: each table entry needs 'name' + 'columns'")
        name = entry["name"]
        cols = entry["columns"]
        if not isinstance(name, str) or not _TABLE_NAME_RE.match(name):
            raise ValueError(f"baseline {path}: invalid table name '{name}'")
        if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
            raise ValueError(f"baseline {path}: columns for {name} must be a list of strings")
        for c in cols:
            if not _COLUMN_NAME_RE.match(c):
                raise ValueError(f"baseline {path}: invalid column name '{c}' in table {name}")
        out[name] = set(cols)
    return out


# ---------------------------------------------------------------------------
# Tenant discovery
# ---------------------------------------------------------------------------

async def fetch_tenants(conn: asyncpg.Connection, tenants_schema: str) -> list[tuple[str, str]]:
    """
    Return list of (slug, schema_name) tuples for active tenants.

    Reads from <tenants_schema>.tenants WHERE status='active'.
    """
    if not _SCHEMA_NAME_RE.match(tenants_schema):
        raise ValueError(f"invalid tenants_schema: {tenants_schema!r}")
    rows = await conn.fetch(
        f"SELECT slug, schema_name FROM {tenants_schema}.tenants WHERE status = 'active'"
    )
    out: list[tuple[str, str]] = []
    for r in rows:
        slug = r["slug"]
        schema = r["schema_name"]
        if not isinstance(slug, str) or not isinstance(schema, str):
            continue
        if not _SCHEMA_NAME_RE.match(schema):
            print(f"WARN: tenant slug={slug!r} has invalid schema_name={schema!r} — skipped",
                  file=sys.stderr)
            continue
        out.append((slug, schema))
    return out


# ---------------------------------------------------------------------------
# Per-tenant verification
# ---------------------------------------------------------------------------

async def verify_tenant(
    pool: asyncpg.Pool,
    slug: str,
    schema: str,
    baseline: dict[str, set[str]],
) -> TenantResult:
    """Connect (from pool), check each baseline table for the tenant's schema."""
    result = TenantResult(slug=slug, schema=schema, status="OK")

    async with pool.acquire() as conn:
        # 1. confirm schema exists
        schema_exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = $1", schema
        )
        if not schema_exists:
            result.status = "DRIFT"
            result.missing_tables = list(baseline.keys())
            result.error = f"schema '{schema}' does not exist"
            return result

        # 2. for each baseline table, check existence + columns
        for table, expected_cols in baseline.items():
            # Existence check via information_schema (safer than SELECT 1 — no permissions issues).
            table_exists = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
                """,
                schema, table,
            )
            if not table_exists:
                result.missing_tables.append(table)
                continue

            # Fetch actual columns.
            actual_rows = await conn.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
                """,
                schema, table,
            )
            actual_cols = {r["column_name"] for r in actual_rows}

            missing = expected_cols - actual_cols
            extra = actual_cols - expected_cols

            if missing:
                result.missing_columns[table] = sorted(missing)
            if extra:
                result.extra_columns[table] = sorted(extra)

        if result.missing_tables or result.missing_columns or result.extra_columns:
            result.status = "DRIFT"
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(results: list[TenantResult], verbose: bool) -> int:
    """Print human-readable report, return drift count."""
    print()
    print("=" * 90)
    print(f"{'TENANT':<25} {'SCHEMA':<25} {'STATUS':<8} {'#DRIFT':<7} DETAIL")
    print("-" * 90)
    drift_count = 0
    for r in results:
        if r.status == "DRIFT":
            drift_count += 1
            detail_bits: list[str] = []
            if r.missing_tables:
                detail_bits.append(f"missing tables: {','.join(r.missing_tables)}")
            for tbl, cols in r.missing_columns.items():
                detail_bits.append(f"{tbl} missing cols: {','.join(cols)}")
            for tbl, cols in r.extra_columns.items():
                detail_bits.append(f"{tbl} extra cols: {','.join(cols)}")
            if r.error:
                detail_bits.append(f"err: {r.error}")
            detail = "; ".join(detail_bits)
        elif r.status == "ERROR":
            drift_count += 1
            detail = f"err: {r.error}"
        else:
            detail = "ok"
        print(f"{r.slug:<25} {r.schema:<25} {r.status:<8} {r.drift_count:<7} {detail}")
        if verbose and r.status == "DRIFT":
            for tbl, cols in r.missing_columns.items():
                print(f"    [missing] {tbl}: {', '.join(cols)}")
            for tbl, cols in r.extra_columns.items():
                print(f"    [extra]   {tbl}: {', '.join(cols)}")
    print("=" * 90)
    ok_count = len(results) - drift_count
    print(f"Tenants OK={ok_count}  Drifted={drift_count}  Total={len(results)}")
    return drift_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline).resolve()
    try:
        baseline = load_baseline(baseline_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: baseline load failed: {e}", file=sys.stderr)
        return 2

    print(f"verify_schema_health: baseline={baseline_path} ({len(baseline)} tables)")
    print(f"  database: {args.database_url.split('@')[-1] if '@' in args.database_url else args.database_url}")
    print(f"  tenants table: {args.tenants_schema}.tenants")

    # Connect + fetch tenant list.
    try:
        conn = await asyncpg.connect(args.database_url)
    except Exception as e:
        print(f"ERROR: cannot connect to database: {e}", file=sys.stderr)
        return 2

    try:
        try:
            tenants = await fetch_tenants(conn, args.tenants_schema)
        except Exception as e:
            print(f"ERROR: cannot fetch tenants: {e}", file=sys.stderr)
            return 2
    finally:
        await conn.close()

    if not tenants:
        print("WARN: no active tenants found — nothing to verify (exit 0)")
        return 0

    print(f"  found {len(tenants)} active tenant(s)")

    # Pool for concurrent per-tenant verification.
    pool = await asyncpg.create_pool(
        dsn=args.database_url,
        min_size=2,
        max_size=args.concurrency,
        command_timeout=30,
    )
    if pool is None:  # pragma: no cover
        print("ERROR: asyncpg.create_pool returned None", file=sys.stderr)
        return 2

    try:
        sem = asyncio.Semaphore(args.concurrency)

        async def _bounded(slug: str, schema: str) -> TenantResult:
            async with sem:
                try:
                    return await verify_tenant(pool, slug, schema, baseline)
                except Exception as e:
                    return TenantResult(
                        slug=slug, schema=schema, status="ERROR",
                        error=f"unexpected: {type(e).__name__}: {e}",
                    )

        tasks = [_bounded(slug, schema) for slug, schema in tenants]
        results = await asyncio.gather(*tasks)
    finally:
        await pool.close()

    drift_count = print_report(list(results), verbose=args.verbose)
    if drift_count > 0:
        print(f"\nFAIL: {drift_count} tenant schema(s) drifted from baseline — "
              f"investigate before cutover (per §14 Risk #17).", file=sys.stderr)
        return 1
    print("\nOK: all tenant schemas match baseline.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify per-tenant schema health against a YAML baseline (§14 Risk #17).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exit codes:
  0 no drift | 1 drift detected | 2 usage / connection / baseline error

Examples:
  python verify_schema_health.py --database-url postgresql://outrena:secret@db:5432/outrena
  python verify_schema_health.py --database-url $DATABASE_URL --verbose
""",
    )
    parser.add_argument("--database-url", required=True,
                        help="PostgreSQL DSN (postgresql://user:pass@host:5432/db)")
    parser.add_argument("--baseline", default="scripts/schema_baseline.yml",
                        help="Path to schema_baseline.yml (default: scripts/schema_baseline.yml)")
    parser.add_argument("--tenants-schema", default="public",
                        help="Schema containing the tenants registry table (default: public)")
    parser.add_argument("--concurrency", type=int, default=8,
                        help="Max simultaneous tenant checks (default: 8)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-column drift detail")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
