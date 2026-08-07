"""
support.py — Tenant support ticket router.

Endpoints (verify_tenant, any authenticated):
  GET   /support/tickets                  → list caller-visible tickets
  POST  /support/tickets                  → create ticket (201)
  GET   /support/tickets/{id}             → ticket + threaded messages
  POST  /support/tickets/{id}/messages    → append a message (201)
  POST  /support/tickets/{id}/close       → close ticket (204)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_tenant
from app.schemas.auth import TokenPayload
from app.features.support.service import SupportService

router = APIRouter(prefix="/support", tags=["Support"])
_service = SupportService()

_TICKET_CATEGORIES = {"BUG", "QUESTION", "FEATURE_REQUEST", "BILLING", "ACCOUNT"}
_TICKET_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}


class TicketCreateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    category: str = Field(default="QUESTION")
    priority: str = Field(default="MEDIUM")
    description: str = Field(..., min_length=1, max_length=10000)


class MessageCreateRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    is_internal_note: bool = False


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int | None = None
    author_user_id: str
    author_role: str
    body: str
    is_internal_note: bool
    created_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject: str
    category: str
    priority: str
    status: str
    created_by_user_id: str
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    messages: list[MessageResponse] | None = None


def _validate_enums(body: TicketCreateRequest) -> None:
    if body.category not in _TICKET_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"category must be one of {sorted(_TICKET_CATEGORIES)}",
        )
    if body.priority not in _TICKET_PRIORITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"priority must be one of {sorted(_TICKET_PRIORITIES)}",
        )


@router.get("/tickets", response_model=list[TicketResponse])
async def list_tickets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[TicketResponse]:
    verify_tenant(request, token)
    rows = await _service.list_tickets(db, token.sub, token.role.value)
    return [TicketResponse(**r) for r in rows]


@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> TicketResponse:
    verify_tenant(request, token)
    _validate_enums(body)
    # FR-101: contextual diagnostics auto-attached as an internal note.
    tenant = getattr(request.state, "tenant", None)
    diagnostics = {
        "tenant_slug": getattr(tenant, "slug", None),
        "user_id": token.sub,
        "user_email": token.email,
        "role": token.role.value,
        "user_agent": request.headers.get("user-agent"),
        "referer": request.headers.get("referer"),
        "request_id": request.headers.get("x-request-id"),
        "client_ip": request.headers.get(
            "x-forwarded-for", request.client.host if request.client else None
        ),
    }
    result = await _service.create_ticket(
        db,
        subject=body.subject,
        category=body.category,
        priority=body.priority,
        description=body.description,
        created_by_user_id=token.sub,
        author_role=token.role.value,
        diagnostics=diagnostics,
    )
    return TicketResponse(**result)


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> TicketResponse:
    verify_tenant(request, token)
    result = await _service.get_ticket_with_messages(
        db, ticket_id, token.sub, token.role.value
    )
    return TicketResponse(**result)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    ticket_id: int,
    body: MessageCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> MessageResponse:
    verify_tenant(request, token)
    result = await _service.add_message(
        db,
        ticket_id=ticket_id,
        body=body.body,
        author_user_id=token.sub,
        author_role=token.role.value,
        is_internal_note=body.is_internal_note,
        user_id_for_acl=token.sub,
        role_for_acl=token.role.value,
    )
    return MessageResponse(**result)


@router.post(
    "/tickets/{ticket_id}/close",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def close_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> Response:
    verify_tenant(request, token)
    await _service.close_ticket(db, ticket_id, token.sub, token.role.value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
