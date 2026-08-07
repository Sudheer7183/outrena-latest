"""Phase 1 smoke test: /health endpoint is reachable and returns ok.

This is the ONLY test in Phase 1 — it just exercises the test runner and
proves the ASGI app boots. Phase 2+ adds the real test suites.
"""
from __future__ import annotations

from httpx import AsyncClient


async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "checks" in body
