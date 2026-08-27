"""Version 1 Data Contracts for Workflow TaskSteps."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    AgentType,
    ApprovalState,
    RiskTier,
    StepStatus,
)


class TaskStepContract(VersionedContractBase):
    """
    Contract representing one atomic, executable unit of work within a Workflow.
    A TaskStep defines HOW a specialist agent executes a specific action.
    """
    step_id: str = Field(
        default_factory=lambda: f"step_{uuid4().hex[:12]}",
        description="Unique identifier for this workflow step."
    )
    workflow_id: str = Field(
        ...,
        description="ID of the parent workflow owning this step."
    )
    step_index: int = Field(
        default=0,
        ge=0,
        description="Zero-indexed execution order position within workflow."
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Short, human-readable name of the step (e.g. 'fetch_ci_logs')."
    )
    description: str = Field(
        default="",
        description="Detailed description of what this step accomplishes."
    )
    agent_type: AgentType = Field(
        ...,
        description="Specialist agent type responsible for executing this step."
    )
    tool_name: str = Field(
        ...,
        description="Specific tool identifier invoked by this step."
    )
    input_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters passed to the tool."
    )
    output_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Result returned from successful tool execution."
    )
    status: StepStatus = Field(
        default=StepStatus.PENDING,
        description="Current execution state of this individual step."
    )
    risk_tier: RiskTier = Field(
        default=RiskTier.TIER_1_LOW,
        description="Safety and permission risk tier of this step."
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this step is gated on explicit human confirmation."
    )
    approval_state: ApprovalState = Field(
        default=ApprovalState.NOT_REQUIRED,
        description="Current status of human-in-the-loop approval."
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of prerequisite step_ids that must complete before this step runs."
    )
    timeout_seconds: int = Field(
        default=60,
        gt=0,
        description="Maximum allowed execution time in seconds before timing out."
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries attempted so far."
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum number of failure retries allowed."
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if this step failed."
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when step execution began."
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when step execution reached completion or failure."
    )
