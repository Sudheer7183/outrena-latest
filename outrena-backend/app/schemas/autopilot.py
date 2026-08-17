# """
# schemas/autopilot.py — Autopilot pipeline request / result / status contracts.

# FIXES vs original zip:
# - AutopilotStatusResponse: added currentStep and errorMessage fields (frontend
#   progress bar always showed 0% because run.currentStep was undefined)
# - AutopilotResult: kept as-is (prospect_count, sequence_count are correct)
# """
# from __future__ import annotations

# from datetime import datetime
# from typing import Any, Literal

# from pydantic import BaseModel, ConfigDict, Field, model_validator


# class AutopilotRequest(BaseModel):
#     """Body for POST /api/v1/autopilot."""

#     model_config = ConfigDict(extra="ignore")

#     campaign_name: str = Field(default="", min_length=0, max_length=200)
#     target_count: int = Field(default=10, ge=1, le=500)
#     icp_hint: str | None = Field(default=None)
#     sender_role: str | None = None
#     sender_company: str | None = None
#     sender_offer: str | None = None
#     proof_metric: str | None = None
#     sender_product: str | None = None
#     target_audience: str | None = None
#     framework: str | None = None
#     schema_name: str = Field(default="public")
#     metadata: dict[str, Any] | None = None

#     @model_validator(mode="before")
#     @classmethod
#     def _normalise_frontend_fields(cls, values: Any) -> Any:
#         """Accept camelCase frontend field names."""
#         if isinstance(values, dict):
#             if not values.get("campaign_name") and values.get("productName"):
#                 values["campaign_name"] = values["productName"]
#             if not values.get("icp_hint") and values.get("icpDescription"):
#                 values["icp_hint"] = values["icpDescription"]
#             if not values.get("campaign_name"):
#                 values["campaign_name"] = "Autopilot Run"
#         return values


# AutopilotCreateRequest = AutopilotRequest


# class AutopilotResult(BaseModel):
#     """Successful (or partially successful) pipeline run result."""

#     campaign_id: str
#     prospect_count: int
#     sequence_count: int
#     task_id: str
#     status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE", "PARTIAL"] = "SUCCESS"
#     error: str | None = None
#     started_at: datetime | None = None
#     completed_at: datetime | None = None

#     model_config = {"from_attributes": True}


# class AutopilotCreateResponse(BaseModel):
#     """202 Accepted response with the enqueued task_id."""

#     task_id: str
#     status: str = "PENDING"
#     message: str = "Task enqueued."


# class AutopilotStatusResponse(BaseModel):
#     """
#     GET /api/v1/autopilot/{task_id} polling response.

#     currentStep and errorMessage added — frontend reads run.currentStep
#     to compute step progress bar. Without this field progress was always 0%.
#     """

#     task_id: str
#     status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE"]
#     result: AutopilotResult | None = None
#     error: str | None = None
#     currentStep: int | None = Field(
#         default=None,
#         description="0-indexed current pipeline step (0-4). None = not started.",
#     )
#     errorMessage: str | None = Field(
#         default=None,
#         description="Step-level error detail.",
#     )


# __all__ = [
#     "AutopilotRequest",
#     "AutopilotCreateRequest",
#     "AutopilotResult",
#     "AutopilotCreateResponse",
#     "AutopilotStatusResponse",
# ]

"""
schemas/autopilot.py — Autopilot pipeline request / result / status contracts.

FIXES vs original zip:
- AutopilotStatusResponse: added currentStep and errorMessage fields (frontend
  progress bar always showed 0% because run.currentStep was undefined)
- AutopilotResult: kept as-is (prospect_count, sequence_count are correct)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutopilotRequest(BaseModel):
    """Body for POST /api/v1/autopilot."""

    model_config = ConfigDict(extra="ignore")

    campaign_name: str = Field(default="", min_length=0, max_length=200)
    target_count: int = Field(default=10, ge=1, le=500)
    icp_hint: str | None = Field(default=None)
    sender_role: str | None = None
    sender_company: str | None = None
    sender_offer: str | None = None
    proof_metric: str | None = None
    sender_product: str | None = None
    target_audience: str | None = None
    framework: str | None = None
    schema_name: str = Field(default="public")
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_frontend_fields(cls, values: Any) -> Any:
        """Accept camelCase frontend field names."""
        if isinstance(values, dict):
            if not values.get("campaign_name") and values.get("productName"):
                values["campaign_name"] = values["productName"]
            if not values.get("icp_hint") and values.get("icpDescription"):
                values["icp_hint"] = values["icpDescription"]
            if not values.get("campaign_name"):
                values["campaign_name"] = "Autopilot Run"
        return values


AutopilotCreateRequest = AutopilotRequest


class AutopilotResult(BaseModel):
    """Successful (or partially successful) pipeline run result."""

    campaign_id: str
    prospect_count: int
    sequence_count: int
    task_id: str
    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE", "PARTIAL"] = "SUCCESS"
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # RICH COMPLETION UI FIELDS — all optional/defaulted so this schema
    # stays backward-compatible with any already-stored result missing
    # these keys (e.g. from before this change shipped).
    campaign_name: str | None = None
    icp_profile_count: int = 0
    company_analysis: dict | None = None
    icp_personas: list[dict] = Field(default_factory=list)
    prospects_preview: list[dict] = Field(default_factory=list)
    step_timings: dict[str, float] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class AutopilotCreateResponse(BaseModel):
    """202 Accepted response with the enqueued task_id."""

    task_id: str
    status: str = "PENDING"
    message: str = "Task enqueued."


class AutopilotStatusResponse(BaseModel):
    """
    GET /api/v1/autopilot/{task_id} polling response.

    currentStep and errorMessage added — frontend reads run.currentStep
    to compute step progress bar. Without this field progress was always 0%.
    """

    task_id: str
    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE"]
    result: AutopilotResult | None = None
    error: str | None = None
    currentStep: int | None = Field(
        default=None,
        description="0-indexed current pipeline step (0-4). None = not started.",
    )
    errorMessage: str | None = Field(
        default=None,
        description="Step-level error detail.",
    )


__all__ = [
    "AutopilotRequest",
    "AutopilotCreateRequest",
    "AutopilotResult",
    "AutopilotCreateResponse",
    "AutopilotStatusResponse",
]
