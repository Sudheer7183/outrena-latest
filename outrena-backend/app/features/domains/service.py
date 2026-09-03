"""domain_service.py — Domain CRUD + DNS check (MX/SPF/DKIM/DMARC).

DNS lookups use dnspython if installed; otherwise fall back to stdlib
socket-based resolution for MX/A records (best-effort — SPF/DKIM/DMARC
TXT lookups will report found=False without dnspython).
"""
from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_models import Domain
from app.schemas.domains import (
    DnsCheckRequest,
    DnsCheckResult,
    DnsRecordResult,
    DomainCreate,
    DomainUpdate,
)

logger = structlog.get_logger(__name__)

# Optional dnspython support.
try:
    import dns.resolver  # type: ignore
    import dns.exception  # type: ignore

    _HAS_DNSPYTHON = True
except ImportError:  # pragma: no cover — defensive
    _HAS_DNSPYTHON = False


class DomainService:
    """CRUD + DNS check for Domain rows."""

    async def list_domains(
        self, db: AsyncSession, *, limit: int = 50, offset: int = 0
    ) -> list[Domain]:
        result = await db.execute(select(Domain).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, domain_id: str) -> Domain | None:
        result = await db.execute(select(Domain).where(Domain.id == domain_id))
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, body: DomainCreate
    ) -> Domain:
        item = Domain(**body.model_dump())
        db.add(item)
        await db.commit()
        item = await db.get(Domain, item.id)
        return item

    async def update(
        self, db: AsyncSession, domain_id: str, body: DomainUpdate
    ) -> Domain | None:
        item = await self.get(db, domain_id)
        if item is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await db.commit()
        item = await db.get(Domain, item.id)
        return item

    async def delete(self, db: AsyncSession, domain_id: str) -> bool:
        item = await self.get(db, domain_id)
        if item is None:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def dns_check(self, body: DnsCheckRequest) -> DnsCheckResult:
        """Run MX/SPF/DKIM/DMARC DNS lookups for a domain."""
        domain = body.domain.strip().lower()

        mx = self._lookup_mx(domain)
        spf = self._lookup_txt(domain, "v=spf1")
        dkim = self._lookup_dkim(domain, body.selector)
        dmarc = self._lookup_txt(f"_dmarc.{domain}", "v=DMARC1")

        all_passed = mx.found and spf.found and dkim.found and dmarc.found
        return DnsCheckResult(
            domain=domain,
            mx=mx,
            spf=spf,
            dkim=dkim,
            dmarc=dmarc,
            allPassed=all_passed,
        )

    async def refresh_domain_status(
        self, db: AsyncSession, domain_id: str
    ) -> Domain | None:
        """Re-run DNS checks and update the Domain row's status flags."""
        item = await self.get(db, domain_id)
        if item is None:
            return None
        result = await self.dns_check(
            DnsCheckRequest(domain=item.domainName)
        )
        item.spfStatus = result.spf.found
        item.dkimStatus = result.dkim.found
        item.dmarcStatus = result.dmarc.found
        item.lastChecked = datetime.now(timezone.utc)
        await db.commit()
        item = await db.get(Domain, item.id)
        return item

    # ── DNS helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _lookup_mx(domain: str) -> DnsRecordResult:
        if _HAS_DNSPYTHON:
            try:
                answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)  # type: ignore[union-attr]
                records = [str(r.to_text()) for r in answers]
                return DnsRecordResult(
                    name="MX",
                    found=bool(records),
                    records=records,
                    detail=f"{len(records)} MX record(s).",
                )
            except Exception as exc:  # noqa: BLE001
                return DnsRecordResult(
                    name="MX", found=False, records=[], detail=str(exc)
                )
        # Stdlib fallback — no native MX support; resolve A record only.
        try:
            socket.gethostbyname(domain)
            return DnsRecordResult(
                name="MX",
                found=True,
                records=[],
                detail="A record resolves (MX lookup requires dnspython).",
            )
        except OSError as exc:
            return DnsRecordResult(
                name="MX", found=False, records=[], detail=str(exc)
            )

    @staticmethod
    def _lookup_txt(domain: str, prefix: str | None = None) -> DnsRecordResult:
        if not _HAS_DNSPYTHON:
            return DnsRecordResult(
                name="TXT",
                found=False,
                records=[],
                detail="TXT lookup requires dnspython (not installed).",
            )
        try:
            answers = dns.resolver.resolve(domain, "TXT", lifetime=5.0)  # type: ignore[union-attr]
            records = [str(r.to_text()) for r in answers]
            if prefix:
                records = [r for r in records if prefix in r]
            return DnsRecordResult(
                name="TXT",
                found=bool(records),
                records=records,
                detail=f"{len(records)} record(s).",
            )
        except Exception as exc:  # noqa: BLE001
            return DnsRecordResult(
                name="TXT", found=False, records=[], detail=str(exc)
            )

    @staticmethod
    def _lookup_dkim(domain: str, selector: str) -> DnsRecordResult:
        from app.features.domains.dns_service import verify_dkim
        found, record = verify_dkim(domain, selector)
        return DnsRecordResult(
            name="DKIM",
            found=found,
            records=[record] if record else [],
            detail=record if record else "No DKIM record found for common selectors.",
        )


__all__ = ["DomainService"]
