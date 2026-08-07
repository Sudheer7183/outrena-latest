"""
test_alembic_idempotency.py — Re-running alembic upgrade head is a no-op.

Reference model §7.2, migration doc §7.6.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.mark.usefixtures("test_engine")
async def test_alembic_upgrade_head_is_idempotent(
    test_db_url: str,
    db_public,
) -> None:
    """Running `alembic upgrade head` twice produces no errors and the
    schema state is unchanged."""
    env = {**os.environ, "ALEMBIC_TARGET_SCHEMA": "public", "DATABASE_URL": test_db_url}

    def _run() -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            cwd=".",
        )
        return proc.returncode, proc.stdout, proc.stderr

    # First run — may already be at head from the session fixture.
    rc1, _, err1 = _run()
    assert rc1 == 0, f"First alembic upgrade failed: {err1}"

    # Capture the alembic_version after first run.
    async with db_public.bind.connect() as conn:
        result = await conn.execute(
            text("SELECT version_num FROM public.alembic_version")
        )
        version_after_first = result.scalar()

    # Second run — must be a no-op.
    rc2, _, err2 = _run()
    assert rc2 == 0, f"Second alembic upgrade failed: {err2}"

    async with db_public.bind.connect() as conn:
        result = await conn.execute(
            text("SELECT version_num FROM public.alembic_version")
        )
        version_after_second = result.scalar()

    assert version_after_first == version_after_second, (
        f"Version changed between runs: {version_after_first} → {version_after_second}"
    )
