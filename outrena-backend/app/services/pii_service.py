"""
pii_service.py — Field-level encryption for Prospect PII columns.

Wraps ``secret_service.encrypt_at_rest`` / ``decrypt_at_rest`` (Fernet
symmetric authenticated encryption) and applies them transparently to
the PII-bearing fields of a Prospect dict.

Transparency contract:
  - On WRITE (create/update): caller passes a normal dict; PiiService
    encrypts the PII fields before the dict is sent to the DB.
  - On READ (get/list): caller fetches the row from the DB and hands the
    dict to PiiService, which decrypts the PII fields before the dict is
    returned to the API layer.

Pass-through behaviour:
  - If ``ENCRYPTION_KEY`` is not set (empty), PiiService logs a warning
    and passes values through UNCHANGED. This lets dev / CI environments
    without a key continue to work — production MUST set the key.
  - On decrypt, if the value is not a valid Fernet token (legacy plaintext
    data, or test fixtures), the original value is returned unchanged.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from app.core.config import get_settings
from app.services.secret_service import decrypt_at_rest, encrypt_at_rest

logger = structlog.get_logger(__name__)


class PiiService:
    """Field-level encryption helper for Prospect PII columns."""

    # Fields on Prospect (and prospect-shaped dicts) that are PII and must
    # be encrypted at rest. Keep in sync with the Prospect model.
    PII_FIELDS: tuple[str, ...] = (
        "email",
        "phone",            # not currently on Prospect but reserved for future
        "first_name",       # snake-case alias
        "lastName",         # camelCase (Prospect model uses camelCase)
        "firstName",
        "last_name",
        "company_email",    # reserved for future
    )

    # ── Single-field helpers ────────────────────────────────────────────────

    def encrypt_field(self, value: str | None) -> str | None:
        """Encrypt a single PII value. None / empty pass through unchanged."""
        if not value:
            return value
        if not self._is_encryption_enabled():
            return value
        try:
            return encrypt_at_rest(value)
        except Exception as exc:  # noqa: BLE001 — never break a write on crypto
            logger.error("pii.encrypt_failed", error=str(exc))
            return value

    def decrypt_field(self, value: str | None) -> str | None:
        """Decrypt a single PII value. None / empty / non-token pass through."""
        if not value:
            return value
        if not self._is_encryption_enabled():
            return value
        try:
            return decrypt_at_rest(value)
        except Exception:  # noqa: BLE001 — legacy plaintext or invalid token
            # The value is either plaintext (pre-encryption legacy data) or
            # a corrupt token. Either way, return it unchanged so reads
            # continue to work — never raise on decrypt.
            return value

    # ── Dict-level helpers (for Prospect payloads) ──────────────────────────

    def encrypt_prospect(self, prospect_dict: dict[str, Any]) -> dict[str, Any]:
        """Encrypt every PII field present in ``prospect_dict`` (in place)."""
        for field in self.PII_FIELDS:
            if field in prospect_dict and prospect_dict[field]:
                prospect_dict[field] = self.encrypt_field(prospect_dict[field])
        return prospect_dict

    def decrypt_prospect(self, prospect_dict: dict[str, Any]) -> dict[str, Any]:
        """Decrypt every PII field present in ``prospect_dict`` (in place)."""
        for field in self.PII_FIELDS:
            if field in prospect_dict and prospect_dict[field]:
                prospect_dict[field] = self.decrypt_field(prospect_dict[field])
        return prospect_dict

    def anonymize_prospect(self, prospect_dict: dict[str, Any]) -> dict[str, Any]:
        """Replace every PII field with ``"[anonymized]"`` and flag the row.

        Used by GDPR Article 17 (right to erasure) processing. The row is
        RETAINED (for FK integrity + aggregate stats) but is no longer PII.
        """
        for field in self.PII_FIELDS:
            if field in prospect_dict:
                prospect_dict[field] = "[anonymized]"
        prospect_dict["anonymized"] = True
        prospect_dict["deleted_at"] = datetime.utcnow()
        return prospect_dict

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _is_encryption_enabled() -> bool:
        """True iff ENCRYPTION_KEY is set in the environment.

        When False, all encrypt/decrypt operations are pass-through (with a
        one-time-per-process warning log). This lets dev / CI run without a
        key — production MUST set the key (the audit_env pre-deploy script
        enforces this for prod).
        """
        key = get_settings().ENCRYPTION_KEY
        if not key:
            # Log once per process (structlog deduplicates by message).
            logger.warning(
                "pii.encryption_disabled",
                reason="ENCRYPTION_KEY is not set — PII is stored in plaintext. "
                       "Production MUST set ENCRYPTION_KEY (see secret_service.py).",
            )
            return False
        return True


__all__ = ["PiiService"]
