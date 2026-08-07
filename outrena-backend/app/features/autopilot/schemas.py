"""
Feature autopilot — thin re-export of shared schemas.

Re-exports the schemas classes used by this feature so feature code can
do `from .schemas import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.schemas/`.
"""
from app.schemas.auth import Role, TokenPayload  # noqa: F401
from app.schemas.autopilot import AutopilotRequest, AutopilotResult  # noqa: F401
from app.schemas.sequences import SEVEN_TOUCH_CADENCE  # noqa: F401

