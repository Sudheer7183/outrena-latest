"""
Feature llm_config — thin re-export of shared models.

Re-exports the models classes used by this feature so feature code can
do `from .models import X` (migration doc §3.2 modular
monolith). The canonical definitions remain in `app.models/`.
"""
from app.models.global_llm_config import GlobalLlmConfig  # noqa: F401

