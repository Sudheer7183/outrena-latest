"""
Feature weekly_digest — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.campaign_models import ReplyDraft, Sequence  # noqa: F401
from app.models.enums import EmailStatus  # noqa: F401
from app.models.phase3_models import WeeklyDigest  # noqa: F401

