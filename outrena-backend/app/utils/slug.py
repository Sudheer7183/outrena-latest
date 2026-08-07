"""
slug.py — Tenant slug (subdomain) validation.

Reference model Section 2.3. The slug is immutable after creation because
the schema name, identity-provider client registration, and every tenant
URL derive from it.
"""
from __future__ import annotations

import re
from typing import Final

SLUG_REGEX: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")

RESERVED_SLUGS: Final[frozenset[str]] = frozenset(
    {
        "www", "api", "app", "admin", "platform", "mail", "auth",
        "health", "docs", "redoc", "cdn", "assets", "static",
    }
)


class SlugValidationError(ValueError):
    """Raised when a proposed tenant slug violates the subdomain rules."""


def validate_slug(slug: str) -> str:
    """
    Validate a proposed tenant slug. Returns the slug on success,
    raises SlugValidationError with a human-readable reason otherwise.
    """
    if not 3 <= len(slug) <= 63:
        raise SlugValidationError("Slug must be between 3 and 63 characters.")
    if not SLUG_REGEX.match(slug):
        raise SlugValidationError(
            "Slug must be lowercase alphanumeric with optional inner hyphens."
        )
    if slug in RESERVED_SLUGS:
        raise SlugValidationError(f"Slug '{slug}' is reserved.")
    return slug


def schema_name_for(slug: str) -> str:
    """Derive the tenant schema name: hyphens become underscores."""
    return f"tenant_{slug.replace('-', '_')}"
