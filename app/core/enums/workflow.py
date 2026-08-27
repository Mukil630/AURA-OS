"""Workflow and TaskStep lifecycle enums."""
from enum import Enum


class WorkflowStatus(str, Enum):
    """Lifecycle state of an orchestrated Workflow execution graph."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RETRYING = "retrying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class StepStatus(str, Enum):
    """Execution status of an individual atomic TaskStep."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    """Workflow step execution dependency model."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    GRAPH_DIRECTED = "graph_directed"
    CONDITIONAL = "conditional"
