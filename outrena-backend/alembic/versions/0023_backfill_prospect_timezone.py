"""
0023_backfill_prospect_timezone.py — Backfill Prospect.timezone from email domain.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-31

What this migration does
------------------------
For every Prospect row where timezone IS NULL and email IS NOT NULL,
derives the timezone from the email's country-code TLD and writes it back.

Examples:
  sudheer@vanigamsoftware.com  → NULL      (.com = ambiguous, leave NULL)
  john@company.co.uk           → Europe/London
  hans@firma.de                → Europe/Berlin
  raj@startup.in               → Asia/Kolkata
  yuki@corp.co.jp              → Asia/Tokyo

Generic TLDs (.com, .org, .io, .net, .co, .app, .ai, etc.) are LEFT AS NULL
intentionally — the scheduler treats NULL as "send anytime" rather than
guessing a wrong timezone.

This migration runs per-tenant schema (same pattern as 0019/0022).
It is safe to re-run — only touches rows where timezone IS NULL.

After applying:
  docker exec -it outrena-backend bash -c "cd /app && alembic upgrade head"
"""
from __future__ import annotations

import re
from typing import Union

from alembic import context, op
from sqlalchemy import text

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels = None
depends_on = None

# ── Inline timezone map (no app imports — migrations must be self-contained) ─

_TLD_TO_TIMEZONE: dict[str, str] = {
    # South Asia
    "in": "Asia/Kolkata", "lk": "Asia/Colombo", "bd": "Asia/Dhaka",
    "np": "Asia/Kathmandu", "pk": "Asia/Karachi", "af": "Asia/Kabul",
    # Southeast Asia
    "sg": "Asia/Singapore", "my": "Asia/Kuala_Lumpur", "th": "Asia/Bangkok",
    "vn": "Asia/Ho_Chi_Minh", "ph": "Asia/Manila", "id": "Asia/Jakarta",
    "mm": "Asia/Rangoon", "kh": "Asia/Phnom_Penh",
    # East Asia
    "jp": "Asia/Tokyo", "kr": "Asia/Seoul", "tw": "Asia/Taipei",
    "hk": "Asia/Hong_Kong", "cn": "Asia/Shanghai",
    # Middle East
    "ae": "Asia/Dubai", "sa": "Asia/Riyadh", "il": "Asia/Jerusalem",
    "tr": "Europe/Istanbul", "ir": "Asia/Tehran", "iq": "Asia/Baghdad",
    "kw": "Asia/Kuwait", "qa": "Asia/Qatar", "bh": "Asia/Bahrain",
    "om": "Asia/Muscat", "jo": "Asia/Amman", "lb": "Asia/Beirut",
    # Central Asia
    "kz": "Asia/Almaty", "uz": "Asia/Tashkent", "az": "Asia/Baku",
    "ge": "Asia/Tbilisi", "am": "Asia/Yerevan",
    # Europe — Western
    "uk": "Europe/London", "gb": "Europe/London", "ie": "Europe/Dublin",
    "de": "Europe/Berlin", "fr": "Europe/Paris", "es": "Europe/Madrid",
    "it": "Europe/Rome", "nl": "Europe/Amsterdam", "be": "Europe/Brussels",
    "ch": "Europe/Zurich", "at": "Europe/Vienna", "pt": "Europe/Lisbon",
    "se": "Europe/Stockholm", "no": "Europe/Oslo", "dk": "Europe/Copenhagen",
    "fi": "Europe/Helsinki", "lu": "Europe/Luxembourg",
    # Europe — Eastern
    "pl": "Europe/Warsaw", "cz": "Europe/Prague", "sk": "Europe/Bratislava",
    "hu": "Europe/Budapest", "ro": "Europe/Bucharest", "bg": "Europe/Sofia",
    "hr": "Europe/Zagreb", "rs": "Europe/Belgrade", "ua": "Europe/Kiev",
    "by": "Europe/Minsk", "lt": "Europe/Vilnius", "lv": "Europe/Riga",
    "ee": "Europe/Tallinn", "ru": "Europe/Moscow", "gr": "Europe/Athens",
    # Americas
    "br": "America/Sao_Paulo", "mx": "America/Mexico_City",
    "ar": "America/Argentina/Buenos_Aires", "cl": "America/Santiago",
    "co": "America/Bogota", "pe": "America/Lima", "ve": "America/Caracas",
    "ec": "America/Guayaquil", "uy": "America/Montevideo",
    "bo": "America/La_Paz", "py": "America/Asuncion",
    "cr": "America/Costa_Rica", "pa": "America/Panama",
    "gt": "America/Guatemala", "cu": "America/Havana",
    "ca": "America/Toronto",
    # Africa
    "za": "Africa/Johannesburg", "ng": "Africa/Lagos", "ke": "Africa/Nairobi",
    "eg": "Africa/Cairo", "ma": "Africa/Casablanca", "gh": "Africa/Accra",
    "et": "Africa/Addis_Ababa", "tz": "Africa/Dar_es_Salaam",
    "ug": "Africa/Kampala", "sn": "Africa/Dakar",
    # Oceania
    "au": "Australia/Sydney", "nz": "Pacific/Auckland",
}

_SECOND_LEVEL: dict[str, str] = {
    "co.uk": "Europe/London", "org.uk": "Europe/London",
    "co.in": "Asia/Kolkata", "net.in": "Asia/Kolkata", "org.in": "Asia/Kolkata",
    "co.jp": "Asia/Tokyo", "ne.jp": "Asia/Tokyo",
    "com.au": "Australia/Sydney", "net.au": "Australia/Sydney",
    "co.nz": "Pacific/Auckland",
    "com.br": "America/Sao_Paulo",
    "com.mx": "America/Mexico_City",
    "com.ar": "America/Argentina/Buenos_Aires",
    "com.co": "America/Bogota",
    "com.sg": "Asia/Singapore",
    "com.my": "Asia/Kuala_Lumpur",
    "com.hk": "Asia/Hong_Kong",
    "com.tw": "Asia/Taipei",
    "com.cn": "Asia/Shanghai",
    "co.za": "Africa/Johannesburg",
    "co.ke": "Africa/Nairobi",
    "com.ng": "Africa/Lagos",
    "com.eg": "Africa/Cairo",
    "co.il": "Asia/Jerusalem",
    "co.ae": "Asia/Dubai",
    "com.sa": "Asia/Riyadh",
    "com.tr": "Europe/Istanbul",
    "co.kr": "Asia/Seoul",
    "com.ph": "Asia/Manila",
    "com.vn": "Asia/Ho_Chi_Minh",
    "com.pk": "Asia/Karachi",
}

_GENERIC_TLDS = frozenset({
    "com", "org", "net", "io", "co", "app", "dev", "ai", "tech",
    "info", "biz", "xyz", "online", "site", "web", "cloud",
})

_STRIP = re.compile(r"^(?:www\d*\.|mail\.|smtp\.|mx\d*\.)+", re.IGNORECASE)


def _tz_from_email(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    domain = _STRIP.sub("", domain)
    if not domain or "." not in domain:
        return None
    # Second-level ccTLD
    for suffix, tz in _SECOND_LEVEL.items():
        if domain.endswith("." + suffix):
            return tz
    # Single TLD
    tld = domain.rsplit(".", 1)[-1]
    if tld in _GENERIC_TLDS:
        return None
    return _TLD_TO_TIMEZONE.get(tld)


def _s() -> str:
    ctx = context.get_context()
    return (ctx.version_table_schema or "public") if ctx else "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = :n LIMIT 1"
        ),
        {"s": schema, "n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    schema = _s()
    bind = op.get_bind()

    if not _table_exists(bind, schema, "Prospect"):
        return  # Schema not provisioned yet — skip silently

    # Fetch all prospects with NULL timezone and a non-null email
    rows = bind.execute(
        text(
            f'SELECT id, email FROM "{schema}"."Prospect" '
            'WHERE timezone IS NULL AND email IS NOT NULL AND email != \'\''
        )
    ).fetchall()

    updated = 0
    for row in rows:
        prospect_id, email = row[0], row[1]
        tz = _tz_from_email(email)
        if tz:
            bind.execute(
                text(
                    f'UPDATE "{schema}"."Prospect" '
                    'SET timezone = :tz WHERE id = :id'
                ),
                {"tz": tz, "id": prospect_id},
            )
            updated += 1

    if updated:
        print(f"  [0023] Backfilled timezone for {updated} prospects in schema '{schema}'")


def downgrade() -> None:
    """Downgrade: clear derived timezones.

    This is intentionally a no-op — we cannot safely distinguish
    user-provided timezones from auto-derived ones without an extra
    column. If you need to revert, set timezone = NULL on specific rows.
    """
    pass
