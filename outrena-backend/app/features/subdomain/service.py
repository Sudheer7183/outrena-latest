"""
subdomain_allocation.py — Subdomain (slug) allocation for new tenants.

The slug IS the subdomain: on creation the tenant is allocated a clean URL
    https://{slug}.{BASE_DOMAIN}
No per-tenant DNS or TLS work is required — a wildcard DNS record
(*.example.com → the reverse proxy) and a wildcard certificate cover every
tenant. Allocation is therefore purely logical:

  1. validate_slug()      — format, length, reserved words (utils/slug.py)
  2. is_slug_available()  — no ACTIVE/PROVISIONING tenant already holds it
  3. provisioning         — registry row + Keycloak redirect-URI registration
                            (Step 5b) make the subdomain live end to end

Availability is checked BEFORE provisioning starts so a taken slug is a
clean 409 up front — never a mid-flight unique-constraint failure that
triggers the compensating rollback.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.utils.slug import SlugValidationError, validate_slug


async def is_slug_available(slug: str, db: AsyncSession) -> tuple[bool, str | None]:
    """
    Check whether a proposed slug can be allocated.

    Returns (available, reason). reason is None when available, otherwise a
    human-readable explanation suitable for direct display in the UI.
    Deleted tenants still block reuse (see module docstring).
    """
    try:
        validate_slug(slug)
    except SlugValidationError as exc:
        return False, str(exc)

    result = await db.execute(
        text("SELECT 1 FROM public.tenants WHERE slug = :slug"),
        {"slug": slug},
    )
    if result.fetchone() is not None:
        return False, f"Subdomain '{slug}' is already allocated."
    return True, None


def tenant_url_for(slug: str) -> str:
    """
    The clean URL allocated to a tenant. Returned from provisioning and
    shown in the platform-admin UI / welcome email.
    """
    settings = get_settings()
    scheme = "http" if settings.BASE_DOMAIN in ("localhost", "127.0.0.1") else "https"
    return f"{scheme}://{slug}.{settings.BASE_DOMAIN}"
