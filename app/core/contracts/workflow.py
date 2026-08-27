"""Version 1 Data Contracts for Workflows and Execution Graphs."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import (
    ExecutionMode,
    WorkflowStatus,
)


class WorkflowContract(VersionedContractBase):
    """
    Contract representing the full orchestrated execution graph for a Task.
    A Workflow defines the structured plan, dependencies, and state machine transitions.
    """
    workflow_id: str = Field(
        default_factory=lambda: f"wf_{uuid4().hex[:12]}",
        description="Unique identifier for the workflow execution instance."
    )
    task_id: str = Field(
        ...,
        description="ID of the parent user Task being satisfied by this workflow."
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Descriptive name of the workflow plan (e.g. 'github_ci_repair_pipeline')."
    )
    description: str = Field(
        default="",
        description="Detailed description of the workflow execution strategy."
    )
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEQUENTIAL,
        description="Execution graph orchestration mode."
    )
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING,
        description="Current state of the workflow state machine."
    )
    steps: List[TaskStepContract] = Field(
        default_factory=list,
        description="Ordered list of TaskSteps comprising this workflow."
    )
    current_step_index: int = Field(
        default=0,
        ge=0,
        description="Index of currently active step."
    )
    context_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared execution context passed across steps in the graph."
    )
    max_execution_time_seconds: int = Field(
        default=600,
        gt=0,
        description="Global timeout for the entire workflow execution."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last workflow update."
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the workflow reached a terminal state."
    )


class WorkflowStateContract(VersionedContractBase):
    """
    Durable checkpoint snapshot of a running Workflow.
    Used for pause, resume, crash recovery, and replay.
    """
    workflow_id: str = Field(..., description="ID of the workflow being checkpointed.")
    status: WorkflowStatus = Field(..., description="Workflow status at checkpoint time.")
    active_step_id: Optional[str] = Field(default=None, description="Currently executing step ID.")
    completed_step_ids: List[str] = Field(default_factory=list, description="List of successfully completed step IDs.")
    failed_step_ids: List[str] = Field(default_factory=list, description="List of failed step IDs.")
    step_outputs: Dict[str, Any] = Field(default_factory=dict, description="Map of step_id -> output data.")
    accumulated_context: Dict[str, Any] = Field(default_factory=dict, description="Accumulated execution context.")
    checkpoint_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this checkpoint was recorded."
    )
