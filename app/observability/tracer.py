"""Distributed Lifecycle Tracing and Decision Audit Subsystem."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from app.core.contracts.base import VersionedContractBase
from app.security.sanitizer import SecretSanitizer


class TraceSpanContract(BaseModel):
    """An individual execution span within a task lifecycle."""
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex[:8]}")
    parent_span_id: Optional[str] = None
    name: str = Field(..., description="Name of lifecycle stage (e.g. 'intent_classification', 'drive.upload').")
    component: str = Field(..., description="Originating module (e.g. 'MasterAgent', 'TaskPlanner', 'CapabilityRouter').")
    status: str = Field(default="ok", description="'ok', 'error', 'skipped', 'blocked'.")
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = Field(default=0.0)
    decision_rationale: Optional[str] = Field(default=None, description="Why this decision or path was chosen.")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    def finish(self, status: str = "ok", error_message: Optional[str] = None) -> None:
        """Mark span as finished and calculate duration in ms."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        if error_message:
            self.error_message = SecretSanitizer.sanitize_text(error_message)


class TaskTraceContract(VersionedContractBase):
    """Consolidated end-to-end distributed trace for an autonomous task."""
    trace_id: str = Field(default_factory=lambda: f"tr_{uuid4().hex[:12]}")
    task_id: str = Field(...)
    workflow_id: Optional[str] = None
    user_id: str = Field(...)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_ms: float = Field(default=0.0)
    spans: List[TraceSpanContract] = Field(default_factory=list)
    overall_status: str = Field(default="in_progress", description="'in_progress', 'completed', 'failed', 'rejected'.")
    decision_lineage: List[Dict[str, Any]] = Field(default_factory=list, description="Audit chain of architectural decisions.")

    def start_span(
        self,
        name: str,
        component: str,
        parent_span_id: Optional[str] = None,
        decision_rationale: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpanContract:
        """Create and append a new span to the trace."""
        clean_metadata = SecretSanitizer.sanitize_dict(metadata or {})
        clean_rationale = SecretSanitizer.sanitize_text(decision_rationale) if decision_rationale else None
        span = TraceSpanContract(
            parent_span_id=parent_span_id,
            name=name,
            component=component,
            decision_rationale=clean_rationale,
            metadata=clean_metadata,
        )
        self.spans.append(span)
        return span

    def record_decision(self, stage: str, chosen_option: str, why: str, constraints: Optional[Dict[str, Any]] = None) -> None:
        """Record structured decision lineage for why the agent took an action."""
        self.decision_lineage.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "decision": chosen_option,
            "rationale": SecretSanitizer.sanitize_text(why),
            "constraints": SecretSanitizer.sanitize_dict(constraints or {}),
        })

    def complete_trace(self, status: str = "completed") -> None:
        """Finalize the trace report."""
        self.completed_at = datetime.now(timezone.utc)
        if self.spans:
            first_start = self.spans[0].start_time
            last_end = max((s.end_time or time.time()) for s in self.spans)
            self.total_duration_ms = round((last_end - first_start) * 1000, 2)
        self.overall_status = status


class AgentTracer:
    """In-memory active trace collector and query manager."""

    def __init__(self):
        self._traces: Dict[str, TaskTraceContract] = {}

    def create_trace(self, task_id: str, user_id: str, workflow_id: Optional[str] = None) -> TaskTraceContract:
        """Instantiate and index a new task trace."""
        trace = TaskTraceContract(
            task_id=task_id,
            user_id=user_id,
            workflow_id=workflow_id,
        )
        self._traces[task_id] = trace
        return trace

    def get_trace(self, task_id: str) -> Optional[TaskTraceContract]:
        """Fetch trace for task."""
        return self._traces.get(task_id)

    def list_traces(self, limit: int = 50) -> List[TaskTraceContract]:
        """List recent traces."""
        return list(self._traces.values())[-limit:]


# Global Singleton Tracer Instance
default_tracer = AgentTracer()
