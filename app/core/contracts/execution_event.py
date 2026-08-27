"""Version 1 Data Contracts for Execution Events and Audit Trail."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    EventSeverity,
    EventType,
)


class ExecutionEventContract(VersionedContractBase):
    """
    Contract representing an immutable audit and telemetry event.
    Provides complete observability, debugging traces, and execution timelines.
    """
    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid4().hex[:12]}",
        description="Unique event record ID."
    )
    trace_id: str = Field(
        ...,
        description="Distributed trace ID spanning the entire lifecycle of a task execution."
    )
    task_id: str = Field(
        ...,
        description="Associated parent Task ID."
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Associated Workflow ID if applicable."
    )
    step_id: Optional[str] = Field(
        default=None,
        description="Associated TaskStep ID if applicable."
    )
    event_type: EventType = Field(
        ...,
        description="Standardized classification of the event."
    )
    severity: EventSeverity = Field(
        default=EventSeverity.INFO,
        description="Log and alert severity level."
    )
    source_component: str = Field(
        ...,
        description="Subsystem emitting this event (e.g. 'MasterAgent', 'WorkflowEngine', 'Verifier')."
    )
    message: str = Field(
        ...,
        description="Human-readable description of the event occurrence."
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured contextual payload associated with this event."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the event occurred."
    )
