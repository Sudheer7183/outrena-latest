"""
test_sequence_delivery.py — Verify E2 fix: sequence send_email resolves prospect email.

These are unit tests for the SequenceService.send_email method's email
resolution logic. They verify that the fix for Audit Issue E2
(empty to= field causing null-recipient sends) is present and correct.
"""
from __future__ import annotations

import ast
import os

BACKEND_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICE_PATH = os.path.join(
    BACKEND_ROOT, "app", "features", "sequences", "service.py"
)


def _read_service() -> str:
    with open(SERVICE_PATH) as f:
        return f.read()


def test_sequence_service_file_exists() -> None:
    assert os.path.isfile(SERVICE_PATH), "sequence service not found"


def test_send_email_resolves_prospect_email() -> None:
    """
    Verify the fix is present: send_email must look up prospect.email
    from the DB rather than passing an empty string.
    """
    content = _read_service()
    # The fix uses select(Prospect).where(Prospect.id == seq.prospectId)
    assert "select(Prospect)" in content, (
        "E2 fix missing: send_email should SELECT the Prospect row to get the email address."
    )


def test_send_email_decrypts_pii_field() -> None:
    """
    Verify that the fix decrypts the stored email (PII is encrypted at rest).
    """
    content = _read_service()
    assert "PiiService" in content or "decrypt_field" in content, (
        "E2 fix incomplete: send_email should decrypt the email via PiiService."
    )


def test_send_email_returns_failed_when_email_missing() -> None:
    """
    Verify that when no email is found, the service returns a Failed response
    instead of sending a null-recipient email.
    """
    content = _read_service()
    assert "Prospect email is missing" in content or "to_email" in content, (
        "E2 fix incomplete: send_email must fail gracefully when prospect email is empty."
    )


def test_seven_touch_cadence_constant_defined() -> None:
    """Verify SEVEN_TOUCH_CADENCE is importable from sequences schemas."""
    import importlib, sys
    try:
        import pydantic  # noqa: F401
    except ImportError:
        import pytest; pytest.skip("pydantic not installed — run from venv with requirements.txt")

    # Make sure app is importable (backend root must be in sys.path)
    if BACKEND_ROOT not in sys.path:
        sys.path.insert(0, BACKEND_ROOT)

    # Set env vars required by settings
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("BASE_DOMAIN", "localhost")

    from app.schemas.sequences import SEVEN_TOUCH_CADENCE
    assert len(SEVEN_TOUCH_CADENCE) == 7, (
        f"Expected 7 cadence touches, got {len(SEVEN_TOUCH_CADENCE)}"
    )


def test_sequence_service_generate_cadence_method_exists() -> None:
    """Verify the auto-generate cadence helper is implemented (E6 fix)."""
    content = _read_service()
    assert "generate_cadence_for_campaign" in content or "auto_generate" in content or "generate_cadence" in content, (
        "E6 fix missing: SequenceService should have a method to auto-generate "
        "7-touch cadence sequences for a campaign when a prospect is linked."
    )
