"""dns_service.py — DNS resolution helper for MX/TXT/SPF/DKIM/DMARC lookups.

Thin wrapper around ``dnspython.resolver`` that exposes the four operations
used by the Phase 3 domain + prospect validation flows:

  - resolve_mx(domain)            → list[str]   (MX record rdata, sorted by preference)
  - resolve_txt(domain)           → list[str]   (raw TXT record values)
  - verify_spf(domain)            → tuple[bool, str | None]
  - verify_dkim(domain, selector) → tuple[bool, str | None]
  - verify_dmarc(domain)          → tuple[bool, str | None]
  - has_mx_or_a(domain)           → bool        (RFC 5321 fallback for email validation)

All functions fail soft: on DNS errors, NXDOMAIN, timeouts, or dnspython not
being installed, they return an empty list / ``(False, None)`` rather than
raising. Callers (e.g. ``DomainService.dns_check``) translate the results
into ``DnsRecordResult`` payloads.

Why a dedicated module? The Phase 3 ``domain_service`` and
``prospect_service`` previously inlined ``dns.resolver`` calls with ad-hoc
try/except blocks. Centralising the lookups here gives one place to tune
timeouts, caching, and error semantics. (Migration audit Recommendation #1.)
"""
from __future__ import annotations

import socket
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Optional dnspython support. The package is now a hard dependency in
# pyproject.toml, but we still degrade gracefully if it is missing from the
# runtime environment (e.g. a stripped CI image) so that import-time failures
# don't cascade into app startup failures.
try:
    import dns.resolver  # type: ignore[import-untyped]
    import dns.exception  # type: ignore[import-untyped]

    _HAS_DNSPYTHON = True
except ImportError:  # pragma: no cover — defensive
    _HAS_DNSPYTHON = False
    dns = None  # type: ignore[assignment]

# Default per-query timeout (seconds). dnspython's lifetime covers the whole
# resolution including retries against multiple nameservers.
_DEFAULT_LIFETIME: float = 5.0


def _resolve(
    domain: str, rdtype: str, lifetime: float = _DEFAULT_LIFETIME
) -> list[Any]:
    """Return the raw dnspython answer list (empty on any failure)."""
    if not _HAS_DNSPYTHON:
        return []
    try:
        answers = dns.resolver.resolve(  # type: ignore[union-attr]
            domain, rdtype, lifetime=lifetime
        )
        return list(answers)
    except dns.exception.DNSException as exc:  # type: ignore[union-attr]
        logger.debug("dns.lookup.dns_exception", domain=domain, rdtype=rdtype, error=str(exc))
        return []
    except Exception as exc:  # noqa: BLE001 — network errors, timeouts, etc.
        logger.debug("dns.lookup.error", domain=domain, rdtype=rdtype, error=str(exc))
        return []


def resolve_mx(domain: str, lifetime: float = _DEFAULT_LIFETIME) -> list[str]:
    """Return MX record rdata as strings, sorted by preference (lowest first).

    Each returned string is the dnspython ``to_text()`` representation, e.g.
    ``"10 mail.example.com."``. Returns an empty list on any failure or when
    dnspython is unavailable.
    """
    answers = _resolve(domain, "MX", lifetime=lifetime)
    # Sort by preference (first integer field of the rdata text).
    def _pref(rec: Any) -> int:
        try:
            return int(str(rec).split()[0])
        except (ValueError, IndexError):
            return 1 << 30

    return sorted((str(r.to_text()) for r in answers), key=_pref)


def resolve_txt(domain: str, lifetime: float = _DEFAULT_LIFETIME) -> list[str]:
    """Return TXT record values as strings (one entry per TXT record)."""
    answers = _resolve(domain, "TXT", lifetime=lifetime)
    out: list[str] = []
    for r in answers:
        try:
            out.append(str(r.to_text()))
        except Exception:  # noqa: BLE001
            continue
    return out


def _first_matching_txt(domain: str, prefix: str) -> str | None:
    """Return the first TXT record at ``domain`` whose text starts with ``prefix``.

    TXT records are quoted in dnspython's ``to_text()`` output (e.g.
    ``"\"v=spf1 include:_spf.example.com ~all\""``). We strip surrounding
    quotes + whitespace before comparison so callers can match on the raw
    record value.
    """
    for raw in resolve_txt(domain):
        candidate = raw.strip().strip('"').strip()
        if candidate.lower().startswith(prefix.lower()):
            return candidate
    return None


def verify_spf(domain: str) -> tuple[bool, str | None]:
    """Return ``(found, record_text)`` for the SPF TXT record at ``domain``.

    SPF records live at the domain apex and start with ``v=spf1``. The
    returned record text is the unquoted TXT value (or ``None`` if not found).
    """
    record = _first_matching_txt(domain, "v=spf1")
    return (record is not None, record)


def verify_dkim(domain: str, selector: str = "default") -> tuple[bool, str | None]:
    """Return ``(found, record_text)`` for the DKIM TXT record.

    DKIM records live at ``{selector}._domainkey.{domain}`` and start with
    ``v=DKIM1``. The selector defaults to ``default`` (the most common
    convention) — callers should pass the actual selector configured by the
    sending MTA when known.
    """
    # if not selector:
    #     selector = "default"
    # name = f"{selector}._domainkey.{domain}"
    # record = _first_matching_txt(name, "v=dkim1")
    # if record is None:
    #     # Some providers omit the version tag; accept any p= key as a fallback.
    #     for raw in resolve_txt(name):
    #         candidate = raw.strip().strip('"').strip()
    #         if "p=" in candidate:
    #             record = candidate
    #             break
    # return (record is not None, record)
    COMMON_SELECTORS = ["default", "google", "zoho", "s1", "s2", "mail", "k1", "dkim"]
    selectors_to_try = [selector] if selector else []
    for s in COMMON_SELECTORS:
        if s not in selectors_to_try:
            selectors_to_try.append(s)

    for sel in selectors_to_try:
        name = f"{sel}._domainkey.{domain}"
        record = _first_matching_txt(name, "v=dkim1")
        if record is None:
            # Some providers omit the version tag; accept any p= key as a fallback.
            for raw in resolve_txt(name):
                candidate = raw.strip().strip('"').strip()
                if "p=" in candidate:
                    record = candidate
                    break
        if record is not None:
            return (True, record)

    return (False, None)


def verify_dmarc(domain: str) -> tuple[bool, str | None]:
    """Return ``(found, record_text)`` for the DMARC TXT record.

    DMARC records live at ``_dmarc.{domain}`` and start with ``v=DMARC1``.
    """
    name = f"_dmarc.{domain}"
    record = _first_matching_txt(name, "v=dmarc1")
    return (record is not None, record)


def has_mx_or_a(domain: str, lifetime: float = _DEFAULT_LIFETIME) -> bool:
    """RFC 5321 mailbox validation: True if the domain has MX OR A records.

    Email delivery falls back to the A record when no MX is present. Used by
    the prospect email-validation flow to decide whether a mailbox domain is
    deliverable. When dnspython is unavailable, falls back to a stdlib
    ``gethostbyname`` A-record check.
    """
    if _HAS_DNSPYTHON:
        if resolve_mx(domain, lifetime=lifetime):
            return True
        if _resolve(domain, "A", lifetime=lifetime):
            return True
        return False
    # Stdlib fallback (no native MX support) — A-record only.
    try:
        socket.gethostbyname(domain)
        return True
    except OSError:
        return False


__all__ = [
    "resolve_mx",
    "resolve_txt",
    "verify_spf",
    "verify_dkim",
    "verify_dmarc",
    "has_mx_or_a",
]
