"""
Feature signals — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.phase3_models import Signal, SignalMonitor  # noqa: F401
from app.models.prospect_models import Prospect  # noqa: F401

