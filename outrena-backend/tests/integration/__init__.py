"""Integration tests for Phase 2 (multitenancy substrate).

These tests require PostgreSQL 16 + Redis 7 + a mock Keycloak. They use
testcontainers-style fixtures (defined in conftest.py). When run in an
environment without Docker, they are skipped with a clear message.
"""
