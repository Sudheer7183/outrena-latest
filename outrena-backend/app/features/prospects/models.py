"""
Feature prospects — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.enums import EnrichmentTier, IntentSource, SeniorityTier  # noqa: F401
from app.models.phase3_models import ProspectSource, SourceConfig  # noqa: F401
from app.models.prospect_models import IcpProfile, Prospect  # noqa: F401

