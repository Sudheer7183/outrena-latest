"""
test_seed_data.py — Validate seed data CSV files for completeness.

These are pure-Python tests (no DB/network needed). They verify that the
seed data directory contains well-formed CSVs for all expected tables and
that no required columns are empty in every row.
"""
from __future__ import annotations

import csv
import os

SEED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "seed", "outrena-seed-data", "02-tenant-schema")
)

# Tables that must be present in the seed data
REQUIRED_TABLES = [
    "Prospect",
    "Campaign",
    "Sequence",
    "IcpProfile",
    "Domain",
    "EmailTemplate",
    "Deal",
    "Signal",
    "Meeting",
    "MailBridgeConfig",
]

# Non-nullable columns that must not be empty for each table
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "Prospect": ["id", "firstName", "lastName", "email"],
    "Campaign": ["id", "name", "status"],
    "Sequence": ["id", "campaignId", "prospectId"],
    "IcpProfile": ["id", "name"],
    "Domain": ["id", "domainName"],
    "Deal": ["id", "prospectId", "stage"],
}


def _csv_rows(table: str) -> list[dict]:
    path = os.path.join(SEED_DIR, f"{table}.csv")
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_seed_directory_exists() -> None:
    assert os.path.isdir(SEED_DIR), (
        f"Seed data directory not found at {SEED_DIR}. "
        "Make sure OUTRENA-Seed-Data-Dev.zip was extracted."
    )


def test_required_table_csvs_present() -> None:
    missing = []
    for table in REQUIRED_TABLES:
        path = os.path.join(SEED_DIR, f"{table}.csv")
        if not os.path.isfile(path):
            missing.append(table)
    assert not missing, f"Missing seed CSV files for tables: {missing}"


def test_prospect_csv_has_rows() -> None:
    rows = _csv_rows("Prospect")
    assert len(rows) > 0, "Prospect.csv is empty — seed data should include ≥1 prospect"


def test_campaign_csv_has_rows() -> None:
    rows = _csv_rows("Campaign")
    assert len(rows) > 0, "Campaign.csv is empty"


def test_required_columns_not_empty() -> None:
    errors = []
    for table, cols in REQUIRED_COLUMNS.items():
        rows = _csv_rows(table)
        if not rows:
            continue  # table-present check already covers emptiness
        for col in cols:
            if col not in rows[0]:
                errors.append(f"{table}.{col}: column not found in CSV header")
                continue
            empty_rows = [i for i, r in enumerate(rows) if not r.get(col, "").strip()]
            if empty_rows:
                errors.append(
                    f"{table}.{col}: empty in rows {empty_rows[:5]}"
                )
    assert not errors, "Required columns have empty values:\n" + "\n".join(errors)


def test_icp_profile_csv_has_rows() -> None:
    rows = _csv_rows("IcpProfile")
    assert len(rows) > 0, "IcpProfile.csv is empty — seed data needs ≥1 ICP profile"


def test_meeting_csv_present() -> None:
    path = os.path.join(SEED_DIR, "Meeting.csv")
    assert os.path.isfile(path), "Meeting.csv missing from seed data"
