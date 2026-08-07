"""
Feature sequences — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.campaign_models import Campaign, Sequence, SubjectLine  # noqa: F401
from app.models.enums import EmailStatus  # noqa: F401
from app.models.prospect_models import Prospect  # noqa: F401

