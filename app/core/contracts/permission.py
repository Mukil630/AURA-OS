"""Version 1 Data Contracts for Permissions, Risk Tiers, and Human Approval."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    ApprovalState,
    PermissionAction,
    RiskTier,
)


class PermissionPolicyContract(VersionedContractBase):
    """
    Contract defining an access policy rule in the Permission Engine.
    Controls what actions and resources agents and tools are allowed to access.
    """
    policy_id: str = Field(..., description="Unique policy identifier.")
    name: str = Field(..., description="Human-readable policy name.")
    role: str = Field(default="default_user", description="Subject role governed by this policy.")
    action: PermissionAction = Field(..., description="Governed action type.")
    resource_pattern: str = Field(
        default="*",
        description="Glob/URI pattern matching target resources (e.g. 'github:*', 'drive:/backups/*')."
    )
    risk_tier: RiskTier = Field(
        default=RiskTier.TIER_1_LOW,
        description="Assigned risk tier."
    )
    requires_explicit_approval: bool = Field(
        default=False,
        description="Whether this policy mandates human confirmation regardless of role."
    )
    is_allowed: bool = Field(
        default=True,
        description="Whether the action matching this rule is permitted."
    )


class ApprovalRequestContract(VersionedContractBase):
    """
    Contract representing a Human-In-The-Loop approval ticket.
    Created whenever a task step matches a HIGH/CRITICAL risk tier or explicit approval rule.
    Cryptographically binds to the exact action parameters, plan hash, and tenant identity.
    """
    approval_id: str = Field(
        default_factory=lambda: f"appr_{uuid4().hex[:12]}",
        description="Unique identifier for the approval request."
    )
    task_id: str = Field(..., description="Parent task ID.")
    step_id: str = Field(..., description="Target TaskStep ID awaiting approval.")
    action: str = Field(..., description="Name of the high-risk action (e.g. 'coding.apply_fix').")
    capability_id: Optional[str] = Field(default=None, description="Specific capability identifier governed.")
    tenant_id: str = Field(default="mukil", description="Tenant ownership boundary.")
    action_hash: Optional[str] = Field(default=None, description="SHA-256 hash of canonical action parameters and tenant.")
    plan_hash: Optional[str] = Field(default=None, description="SHA-256 hash of entire planned DAG step structure.")
    risk_tier: RiskTier = Field(..., description="Risk tier of the requested action.")
    description: str = Field(..., description="Plain-language explanation of what will occur if approved.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters and side-effects summary.")
    state: ApprovalState = Field(default=ApprovalState.PENDING, description="Current approval decision state.")
    approved_by: Optional[str] = Field(default=None, description="Identifier of the user who approved or rejected.")
    rejection_reason: Optional[str] = Field(default=None, description="Explanation if rejected.")
    decided_at: Optional[datetime] = Field(default=None, description="UTC timestamp of the human decision.")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp after which pending request times out."
    )
