"""
Feature mailbridge — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.campaign_models import Campaign, ReplyDraft, Sequence  # noqa: F401
from app.models.config_models import MailBridgeConfig  # noqa: F401
from app.models.enums import EmailStatus  # noqa: F401
from app.models.user_email import UserEmailQuota, UserSenderIdentity  # noqa: F401

