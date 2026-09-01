"""
timezone_utils.py — Derive an IANA timezone from a prospect's email domain.

Strategy (in priority order):
  1. Country-code TLD (.in, .uk, .de, .fr, .au, etc.)
       → unambiguous single-country TLD → direct timezone
  2. Known company domain patterns (generic TLDs like .com, .org, .io)
       → no derivation possible from TLD alone → return None

  Result: a best-effort IANA timezone string (e.g. "Asia/Kolkata") or None.
  None means "unknown — skip business hours gate" per scheduler logic.

Why NOT .com:
  .com is used globally. microsoft.com could be US, UK, India, or anywhere.
  Guessing New_York for .com is wrong for 60%+ of global B2B prospects.
  We return None for .com/.org/.io/.net/.co — scheduler sends immediately.

Coverage:
  - 60+ country-code TLDs covering all major B2B markets
  - Second-level ccTLDs (.co.uk, .co.in, .com.au, .co.jp, etc.)
  - Most common single-timezone countries (1 tz per country)
  - Multi-timezone countries return the primary commercial hub timezone:
      US (.us) → None (too ambiguous, don't guess)
      AU (.au) → Australia/Sydney (east coast = most B2B)
      BR (.br) → America/Sao_Paulo
      CA (.ca) → America/Toronto
      RU (.ru) → Europe/Moscow
      CN (.cn) → Asia/Shanghai

Usage:
  from app.features.prospects.timezone_utils import derive_timezone_from_email

  tz = derive_timezone_from_email("sudheer@vanigamsoftware.com")  # → None (.com)
  tz = derive_timezone_from_email("john@company.co.uk")           # → "Europe/London"
  tz = derive_timezone_from_email("hans@firma.de")                # → "Europe/Berlin"
  tz = derive_timezone_from_email("raj@startup.in")               # → "Asia/Kolkata"
"""
from __future__ import annotations

import re

# ── Country-code TLD → IANA timezone ───────────────────────────────────────
# Single-timezone countries only. Multi-timezone countries: use primary
# commercial hub or return None (see module docstring).
_TLD_TO_TIMEZONE: dict[str, str] = {
    # South Asia
    "in":   "Asia/Kolkata",       # India (single tz)
    "lk":   "Asia/Colombo",       # Sri Lanka
    "bd":   "Asia/Dhaka",         # Bangladesh
    "np":   "Asia/Kathmandu",     # Nepal
    "pk":   "Asia/Karachi",       # Pakistan
    "af":   "Asia/Kabul",         # Afghanistan

    # Southeast Asia
    "sg":   "Asia/Singapore",     # Singapore
    "my":   "Asia/Kuala_Lumpur",  # Malaysia
    "th":   "Asia/Bangkok",       # Thailand
    "vn":   "Asia/Ho_Chi_Minh",   # Vietnam
    "ph":   "Asia/Manila",        # Philippines
    "id":   "Asia/Jakarta",       # Indonesia (primary hub)
    "mm":   "Asia/Rangoon",       # Myanmar
    "kh":   "Asia/Phnom_Penh",    # Cambodia
    "la":   "Asia/Vientiane",     # Laos

    # East Asia
    "jp":   "Asia/Tokyo",         # Japan
    "kr":   "Asia/Seoul",         # South Korea
    "tw":   "Asia/Taipei",        # Taiwan
    "hk":   "Asia/Hong_Kong",     # Hong Kong
    "cn":   "Asia/Shanghai",      # China (primary hub)
    "mn":   "Asia/Ulaanbaatar",   # Mongolia

    # Middle East
    "ae":   "Asia/Dubai",         # UAE
    "sa":   "Asia/Riyadh",        # Saudi Arabia
    "il":   "Asia/Jerusalem",     # Israel
    "tr":   "Europe/Istanbul",    # Turkey
    "ir":   "Asia/Tehran",        # Iran
    "iq":   "Asia/Baghdad",       # Iraq
    "kw":   "Asia/Kuwait",        # Kuwait
    "qa":   "Asia/Qatar",         # Qatar
    "bh":   "Asia/Bahrain",       # Bahrain
    "om":   "Asia/Muscat",        # Oman
    "jo":   "Asia/Amman",         # Jordan
    "lb":   "Asia/Beirut",        # Lebanon
    "sy":   "Asia/Damascus",      # Syria
    "ye":   "Asia/Aden",          # Yemen

    # Central Asia
    "kz":   "Asia/Almaty",        # Kazakhstan
    "uz":   "Asia/Tashkent",      # Uzbekistan
    "az":   "Asia/Baku",          # Azerbaijan
    "ge":   "Asia/Tbilisi",       # Georgia
    "am":   "Asia/Yerevan",       # Armenia

    # Europe — Western
    "uk":   "Europe/London",      # UK (alias)
    "gb":   "Europe/London",      # Great Britain
    "ie":   "Europe/Dublin",      # Ireland
    "de":   "Europe/Berlin",      # Germany
    "fr":   "Europe/Paris",       # France
    "es":   "Europe/Madrid",      # Spain
    "it":   "Europe/Rome",        # Italy
    "nl":   "Europe/Amsterdam",   # Netherlands
    "be":   "Europe/Brussels",    # Belgium
    "ch":   "Europe/Zurich",      # Switzerland
    "at":   "Europe/Vienna",      # Austria
    "pt":   "Europe/Lisbon",      # Portugal
    "se":   "Europe/Stockholm",   # Sweden
    "no":   "Europe/Oslo",        # Norway
    "dk":   "Europe/Copenhagen",  # Denmark
    "fi":   "Europe/Helsinki",    # Finland
    "lu":   "Europe/Luxembourg",  # Luxembourg

    # Europe — Eastern
    "pl":   "Europe/Warsaw",      # Poland
    "cz":   "Europe/Prague",      # Czech Republic
    "sk":   "Europe/Bratislava",  # Slovakia
    "hu":   "Europe/Budapest",    # Hungary
    "ro":   "Europe/Bucharest",   # Romania
    "bg":   "Europe/Sofia",       # Bulgaria
    "hr":   "Europe/Zagreb",      # Croatia
    "rs":   "Europe/Belgrade",    # Serbia
    "si":   "Europe/Ljubljana",   # Slovenia
    "ua":   "Europe/Kiev",        # Ukraine
    "by":   "Europe/Minsk",       # Belarus
    "lt":   "Europe/Vilnius",     # Lithuania
    "lv":   "Europe/Riga",        # Latvia
    "ee":   "Europe/Tallinn",     # Estonia
    "ru":   "Europe/Moscow",      # Russia (primary hub)
    "gr":   "Europe/Athens",      # Greece

    # Americas
    "br":   "America/Sao_Paulo",  # Brazil (primary hub)
    "mx":   "America/Mexico_City",# Mexico
    "ar":   "America/Argentina/Buenos_Aires",
    "cl":   "America/Santiago",   # Chile
    "co":   "America/Bogota",     # Colombia
    "pe":   "America/Lima",       # Peru
    "ve":   "America/Caracas",    # Venezuela
    "ec":   "America/Guayaquil",  # Ecuador
    "uy":   "America/Montevideo", # Uruguay
    "bo":   "America/La_Paz",     # Bolivia
    "py":   "America/Asuncion",   # Paraguay
    "cr":   "America/Costa_Rica", # Costa Rica
    "pa":   "America/Panama",     # Panama
    "gt":   "America/Guatemala",  # Guatemala
    "cu":   "America/Havana",     # Cuba
    "ca":   "America/Toronto",    # Canada (primary hub — Eastern)

    # Africa
    "za":   "Africa/Johannesburg",# South Africa
    "ng":   "Africa/Lagos",       # Nigeria
    "ke":   "Africa/Nairobi",     # Kenya
    "eg":   "Africa/Cairo",       # Egypt
    "ma":   "Africa/Casablanca",  # Morocco
    "gh":   "Africa/Accra",       # Ghana
    "et":   "Africa/Addis_Ababa", # Ethiopia
    "tz":   "Africa/Dar_es_Salaam",# Tanzania
    "ug":   "Africa/Kampala",     # Uganda
    "sn":   "Africa/Dakar",       # Senegal

    # Oceania
    "au":   "Australia/Sydney",   # Australia (primary hub — east coast)
    "nz":   "Pacific/Auckland",   # New Zealand

    # Second-level ccTLDs (handled separately below)
    # .co.uk → Europe/London (detected via domain suffix check)
}

# Generic TLDs where timezone is unknowable — return None
_GENERIC_TLDS: frozenset[str] = frozenset({
    "com", "org", "net", "io", "co", "app", "dev", "ai", "tech",
    "info", "biz", "xyz", "online", "site", "web", "cloud", "agency",
    "solutions", "group", "global", "world", "inc", "ltd", "llc",
    "email", "mail", "business", "company", "services", "consulting",
})

# Second-level ccTLD suffixes → timezone
# These match the END of the domain (after the last dot + second-to-last dot)
_SECOND_LEVEL_CCLTD: dict[str, str] = {
    "co.uk":   "Europe/London",
    "org.uk":  "Europe/London",
    "me.uk":   "Europe/London",
    "ltd.uk":  "Europe/London",
    "plc.uk":  "Europe/London",
    "co.in":   "Asia/Kolkata",
    "net.in":  "Asia/Kolkata",
    "org.in":  "Asia/Kolkata",
    "co.jp":   "Asia/Tokyo",
    "ne.jp":   "Asia/Tokyo",
    "or.jp":   "Asia/Tokyo",
    "com.au":  "Australia/Sydney",
    "net.au":  "Australia/Sydney",
    "org.au":  "Australia/Sydney",
    "co.nz":   "Pacific/Auckland",
    "net.nz":  "Pacific/Auckland",
    "com.br":  "America/Sao_Paulo",
    "net.br":  "America/Sao_Paulo",
    "com.mx":  "America/Mexico_City",
    "com.ar":  "America/Argentina/Buenos_Aires",
    "com.co":  "America/Bogota",
    "com.sg":  "Asia/Singapore",
    "com.my":  "Asia/Kuala_Lumpur",
    "com.hk":  "Asia/Hong_Kong",
    "com.tw":  "Asia/Taipei",
    "com.cn":  "Asia/Shanghai",
    "co.za":   "Africa/Johannesburg",
    "co.ke":   "Africa/Nairobi",
    "com.ng":  "Africa/Lagos",
    "com.gh":  "Africa/Accra",
    "com.eg":  "Africa/Cairo",
    "co.il":   "Asia/Jerusalem",
    "co.ae":   "Asia/Dubai",
    "com.sa":  "Asia/Riyadh",
    "com.tr":  "Europe/Istanbul",
    "co.kr":   "Asia/Seoul",
    "com.ph":  "Asia/Manila",
    "com.vn":  "Asia/Ho_Chi_Minh",
    "com.pk":  "Asia/Karachi",
}

# Strip www. and any subdomains to get the registrable domain
_SUBDOMAIN_STRIP = re.compile(r"^(?:www\d*\.|mail\.|smtp\.|mx\d*\.)+", re.IGNORECASE)


def _extract_domain(email_or_domain: str) -> str:
    """Extract the bare domain from an email address or domain string."""
    s = email_or_domain.strip().lower()
    if "@" in s:
        s = s.split("@", 1)[1]
    # Strip leading subdomains
    s = _SUBDOMAIN_STRIP.sub("", s)
    return s


def derive_timezone_from_domain(domain: str) -> str | None:
    """Return an IANA timezone string for the given domain, or None.

    None means timezone is unknown — caller should NOT apply any business
    hours restriction (send immediately).

    Examples:
      vanigamsoftware.com → None       (.com = ambiguous)
      acme.co.uk          → Europe/London
      firma.de            → Europe/Berlin
      startup.in          → Asia/Kolkata
      company.com.au      → Australia/Sydney
    """
    if not domain:
        return None

    d = _extract_domain(domain)
    if not d or "." not in d:
        return None

    # Check second-level ccTLD first (longer match wins)
    for suffix, tz in _SECOND_LEVEL_CCLTD.items():
        if d.endswith("." + suffix):
            return tz

    # Extract the rightmost TLD
    tld = d.rsplit(".", 1)[-1]

    # Generic TLD — unknowable
    if tld in _GENERIC_TLDS:
        return None

    # Country-code TLD lookup
    return _TLD_TO_TIMEZONE.get(tld)


def derive_timezone_from_email(email: str) -> str | None:
    """Return an IANA timezone string derived from the email's domain, or None."""
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    return derive_timezone_from_domain(domain)


__all__ = [
    "derive_timezone_from_email",
    "derive_timezone_from_domain",
]
