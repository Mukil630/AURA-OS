"""Abstract Interface definitions for the Workflow Engine and State Machine."""
from abc import ABC, abstractmethod
from typing import Optional

from app.core.contracts.workflow import (
    WorkflowContract,
    WorkflowStateContract,
)


class IWorkflowEngine(ABC):
    """
    Abstract interface for orchestrating Workflows.
    Manages execution graphs, state checkpoints, pause/resume, human approval gating, and recovery.
    """
    @abstractmethod
    async def start_workflow(self, workflow: WorkflowContract) -> WorkflowStateContract:
        """Initialize and begin execution of a workflow."""
        pass

    @abstractmethod
    async def pause_workflow(self, workflow_id: str, reason: str = "") -> WorkflowStateContract:
        """Pause a running workflow and record checkpoint."""
        pass

    @abstractmethod
    async def resume_workflow(self, workflow_id: str) -> WorkflowStateContract:
        """Resume a paused or approval-gated workflow from its latest checkpoint."""
        pass

    @abstractmethod
    async def cancel_workflow(self, workflow_id: str, reason: str = "") -> WorkflowStateContract:
        """Cancel workflow execution gracefully."""
        pass

    @abstractmethod
    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowStateContract]:
        """Fetch the current state checkpoint of a workflow."""
        pass

    @abstractmethod
    async def record_checkpoint(self, state: WorkflowStateContract) -> bool:
        """Persist state checkpoint to durable storage."""
        pass
