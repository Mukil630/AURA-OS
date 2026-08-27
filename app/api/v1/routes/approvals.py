"""FastAPI REST Endpoints for Human-In-The-Loop Approval Decisions."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.contracts.permission import ApprovalRequestContract
from app.policy.approval_engine import (
    ApprovalEngine,
    default_approval_engine,
)
from app.security.auth import AuthenticatedUser, get_current_user


router = APIRouter(prefix="/approvals", tags=["Human-In-The-Loop Approval Gates"])


class ApprovalDecisionRequest(BaseModel):
    """Payload to decide an approval request."""
    decision: str = Field(..., description="'approve' or 'reject'.")
    reason: Optional[str] = Field(default=None, description="Optional justification for decision.")


class ApprovalDecisionResponse(BaseModel):
    """Response returned after human decision."""
    success: bool
    message: str
    ticket: Optional[ApprovalRequestContract] = None


@router.get(
    "/pending",
    response_model=List[ApprovalRequestContract],
    summary="List Pending Approval Requests",
    description="Retrieve all active approval tickets awaiting human decision.",
)
async def list_pending_approvals(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[ApprovalRequestContract]:
    """List pending tickets for the current tenant."""
    return default_approval_engine.list_pending_approvals(tenant_id=current_user.user_id)


@router.get(
    "/{approval_id}",
    response_model=ApprovalRequestContract,
    summary="Get Approval Ticket Details",
    description="Inspect action hash, plan hash, risk level, and parameters for a specific approval ticket.",
)
async def get_approval_ticket(
    approval_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ApprovalRequestContract:
    """Retrieve specific approval ticket with tenant isolation (returns 404 on mismatch)."""
    ticket = default_approval_engine.get_approval(approval_id)
    tenant = current_user.tenant_id or current_user.user_id
    if not ticket or (current_user.role != "admin" and ticket.tenant_id != tenant):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval ticket '{approval_id}' not found.",
        )
    return ticket


@router.post(
    "/{approval_id}/decide",
    response_model=ApprovalDecisionResponse,
    summary="Authorize or Reject Approval Ticket",
    description="Submit human operator decision (approve or reject) for high-risk action.",
)
async def decide_approval_ticket(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ApprovalDecisionResponse:
    """Record operator decision with strict tenant boundary check."""
    ticket = default_approval_engine.get_approval(approval_id)
    tenant = current_user.tenant_id or current_user.user_id
    if not ticket or (current_user.role != "admin" and ticket.tenant_id != tenant):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval ticket '{approval_id}' not found.",
        )

    success, message, decided_ticket = default_approval_engine.decide_approval(
        approval_id=approval_id,
        decision=payload.decision,
        approver_id=current_user.user_id,
        reason=payload.reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return ApprovalDecisionResponse(
        success=True,
        message=message,
        ticket=decided_ticket,
    )
