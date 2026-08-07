# Phase 1: no migrations yet. Phase 2 adds 0001_initial_public.py
# (public.tenants registry). Phase 3 adds 0002_initial_tenant.py (all 47
# tenant-scoped tables). `alembic current` should return 'base' at this phase.
