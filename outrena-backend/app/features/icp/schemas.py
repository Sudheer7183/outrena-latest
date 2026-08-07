"""
Feature icp — thin re-export of shared schemas.

Re-exports the schemas classes used by this feature so feature code can
do `from .schemas import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.schemas/`.
"""
from app.schemas.auth import Role, TokenPayload  # noqa: F401

