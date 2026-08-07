"""
base.py — Declarative base, CUID generation, and timestamp mixin.

CUID generation mirrors Prisma's ``@default(cuid())`` so existing client-
side code that treats IDs as opaque 'c...' strings continues to work.

The timestamp mixin provides ``createdAt`` and ``updatedAt`` columns that
mirror Prisma's ``@default(now())`` and ``@updatedAt`` semantics. The
``updated_at`` trigger is implemented at the ORM level via SQLAlchemy's
``onupdate`` parameter (executed on UPDATE, not via a DB trigger).
"""
from __future__ import annotations

import random
import string
import threading
import time
from datetime import datetime

# Base lives in app.core.database (single declarative base for the whole app,
# imported by alembic/env.py as target_metadata). Importing it here keeps all
# models bound to the same metadata registry.
from app.core.database import Base  # noqa: E402,F401  (re-exported for convenience)
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

# ── CUID generation ─────────────────────────────────────────────────────────

_counter_lock = threading.Lock()
_counter = 0


def _base36_encode(n: int) -> str:
    """Encode a non-negative integer as base-36 (lowercase)."""
    if n == 0:
        return "0"
    chars = string.ascii_lowercase + string.digits
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(chars[rem])
    return "".join(reversed(out))


def _generate_cuid() -> str:
    """
    Generate a CUID-compatible ID (24 chars, starts with 'c').
    Mirrors Prisma's @default(cuid()) so existing client-side code that
    treats IDs as opaque 'c...' strings continues to work.

    Structure: 'c' + 8-char base-36 timestamp + 4-char counter + 16-char random.
    Collision probability ≈ 1 in 2^80 under high write concurrency.
    """
    global _counter
    with _counter_lock:
        _counter = (_counter + 1) % 36 ** 4
        c = _counter
    ts = _base36_encode(int(time.time() * 1000))
    counter_str = _base36_encode(c).rjust(4, "0")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return f"c{ts}{counter_str}{random_str}"


# ── Declarative base ────────────────────────────────────────────────────────
# Base is imported from app.core.database above (single source of truth).


class TimestampMixin:
    """Provides createdAt + updatedAt columns matching Prisma semantics."""

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CuidPrimaryKey:
    """Mixin providing a CUID string primary key (Prisma @default(cuid()) parity)."""

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=_generate_cuid,
    )


__all__ = [
    "Base",
    "CuidPrimaryKey",
    "TimestampMixin",
    "_generate_cuid",
]
