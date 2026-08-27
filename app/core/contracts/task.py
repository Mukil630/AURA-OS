"""Version 1 Data Contracts for User Tasks."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    ChannelType,
    IntentCategory,
    PriorityLevel,
    RiskLevel,
    TaskStatus,
    TaskType,
)


class TaskContract(VersionedContractBase):
    """
    Core Task entity contract representing a user-requested goal.
    A Task defines WHAT the user wants to achieve.
    """
    task_id: str = Field(
        default_factory=lambda: f"task_{uuid4().hex[:12]}",
        description="Unique identifier for the task."
    )
    user_id: str = Field(
        ...,
        description="Identifier of the user who owns this task."
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional conversational session ID."
    )
    channel: ChannelType = Field(
        default=ChannelType.API,
        description="Input channel through which the request arrived."
    )
    raw_input: str = Field(
        ...,
        min_length=1,
        description="Original, unmodified user input text or voice transcript."
    )
    intent: Optional[IntentCategory] = Field(
        default=IntentCategory.UNKNOWN,
        description="Classified semantic intent category."
    )
    task_type: TaskType = Field(
        default=TaskType.ACTION,
        description="Functional classification of the task."
    )
    priority: PriorityLevel = Field(
        default=PriorityLevel.NORMAL,
        description="Execution priority level."
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Assessed overall risk level."
    )
    status: TaskStatus = Field(
        default=TaskStatus.CREATED,
        description="Current lifecycle status of the task."
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Associated execution workflow ID if planned and scheduled."
    )
    result_summary: Optional[str] = Field(
        default=None,
        description="Human-readable summary of the final execution result."
    )
    result_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured output data from task completion."
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error description if the task failed."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Organizational or contextual tags."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last status update."
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the task reached a terminal state."
    )


class TaskCreateRequestContract(VersionedContractBase):
    """Payload contract for creating a new Task."""
    user_id: Optional[str] = Field(default=None, description="Optional user ID (defaults to authenticated tenant).")
    raw_input: str = Field(..., min_length=1, description="Raw input command or query.")
    channel: ChannelType = Field(default=ChannelType.API, description="Source communication channel.")
    priority: PriorityLevel = Field(default=PriorityLevel.NORMAL, description="Desired execution priority.")
    session_id: Optional[str] = Field(default=None, description="Optional conversational session ID.")
    tags: List[str] = Field(default_factory=list, description="Optional tags for classification.")


class TaskResponseContract(VersionedContractBase):
    """API response contract returning Task information to clients."""
    task: TaskContract = Field(..., description="Full task domain contract.")
    message: str = Field(default="Task retrieved successfully.", description="Status message.")
