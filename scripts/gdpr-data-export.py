#!/usr/bin/env python3
"""
gdpr-data-export.py — CLI to export a user's data (GDPR Article 15 + 20).

Usage:
    python scripts/gdpr-data-export.py \\
        --email user@example.com \\
        --tenant-slug acme \\
        --output /tmp/export.json

Connects to the OUTRENA database, runs GdprService.export_user_data, and
writes the result to the specified output path. If the output path ends
in .json, only the JSON file is written. If it ends in .csv or is
omitted, both JSON and CSV are written side-by-side (CSV is a flat
projection of the prospect record only — the full bundle is the JSON).

Used by:
  - DSR processing (runbook 13) — DPO runs this CLI to generate the
    export bundle for the data subject.
  - Customer onboarding audits — customer asks for a sample export to
    verify OUTRENA's data holdings.
  - Regulator requests — DPO runs this CLI to respond to a supervisory
    authority's data-access request.

Exit codes:
  0  export succeeded
  1  export failed (DB error, tenant not found, prospect not found)
  2  usage error (missing required args)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Add the backend app to the import path so we can use GdprService
# directly. The script is intended to run from the migration/ root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "outrena-backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


def _validate_email(email: str) -> str:
    if "@" not in email or "." not in email.split("@", 1)[1]:
        raise ValueError(f"Invalid email: {email}")
    return email.lower()


def _validate_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid tenant slug '{slug}' — must be 3-63 chars, "
            "lowercase alphanumeric + hyphens."
        )
    return slug


async def run_export(email: str, tenant_slug: str, output: Path) -> dict[str, Any]:
    """Run the export + write JSON + CSV. Returns the bundle dict."""
    # Import inside the function so --help works without the backend env.
    from app.core.config import get_settings  # noqa: F401  (init settings)
    from app.services.gdpr_service import GdprService

    service = GdprService()
    bundle = await service.export_user_data(tenant_slug, email)

    # Always write the JSON bundle.
    json_path = output if output.suffix == ".json" else output.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    print(f"  ✓ JSON export written: {json_path}  ({json_path.stat().st_size:,} bytes)")

    # Write a CSV projection of the prospect record (best-effort).
    prospect = bundle.get("prospect")
    if prospect:
        csv_path = output.with_suffix(".csv")
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["field", "value"])
            for k, v in prospect.items():
                writer.writerow([k, _csv_safe(v)])
        print(f"  ✓ CSV prospect projection written: {csv_path}")

    return bundle


def _csv_safe(value: Any) -> str:
    """Stringify + truncate long values for CSV readability."""
    if value is None:
        return ""
    s = str(value)
    if len(s) > 500:
        return s[:497] + "..."
    return s


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a user's data (GDPR Article 15 + 20)."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="The data subject's email address.",
    )
    parser.add_argument(
        "--tenant-slug",
        required=True,
        help="The tenant slug (e.g. 'acme').",
    )
    parser.add_argument(
        "--output",
        required=False,
        default="/tmp/gdpr-export.json",
        help="Output path (default: /tmp/gdpr-export.json). "
        "If suffix is .csv, both .json and .csv are written.",
    )
    args = parser.parse_args()

    try:
        email = _validate_email(args.email)
        slug = _validate_slug(args.tenant_slug)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    output_path = Path(args.output)

    print(f"Exporting data for {email} from tenant '{slug}'...")
    try:
        bundle = asyncio.run(run_export(email, slug, output_path))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: export failed: {exc}", file=sys.stderr)
        return 1

    # Summary.
    print("\nExport summary:")
    for k, v in bundle.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} record(s)")
        elif isinstance(v, dict):
            print(f"  {k}: {len(v)} field(s)")
        elif v is None:
            print(f"  {k}: (none)")
        else:
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    # Ensure DATABASE_URL is set before importing the app.
    if not os.environ.get("DATABASE_URL"):
        print(
            "ERROR: DATABASE_URL env var is not set.\n"
            "Example: DATABASE_URL='postgresql+asyncpg://user:pass@localhost:5432/outrena' "
            f"python {sys.argv[0]} ...",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(main())
