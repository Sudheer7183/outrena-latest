"""
csv_export_service.py — RFC-4180-compliant CSV export (UTF-8 with BOM).

Phase 3 deliverable: CSV export on prospects + sequences. The BOM is required
so Excel auto-detects UTF-8 encoding (Prisma/Next.js parity: the original
implementation prepended \ufeff).
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Mapping

# UTF-8 BOM — Excel needs this to honour UTF-8 without a config tweak.
_BOM = "\ufeff"


def rows_to_csv(rows: Iterable[Mapping[str, Any]], columns: list[str]) -> str:
    """
    Serialize an iterable of row dicts to a CSV string.

    - RFC-4180 quoting: every field with a comma, quote, or newline is quoted.
    - Empty iterable produces a header-only document.
    - Missing keys render as empty strings (not "None").
    """
    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.DictWriter(
        buf,
        fieldnames=columns,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",  # RFC-4180 mandates CRLF
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _safe_cell(row.get(col)) for col in columns})
    return buf.getvalue()


def _safe_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        import json

        return json.dumps(value, default=str)
    return str(value)


__all__ = ["rows_to_csv"]
