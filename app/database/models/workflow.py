"""SQLAlchemy ORM Models for Workflows and Durable State Checkpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import (
    WorkflowContract,
    WorkflowStateContract,
)
from app.core.enums import ExecutionMode, WorkflowStatus
from app.database.base import Base, TimestampMixin, dump_json, load_json
from app.database.models.task_step import TaskStepModel


class WorkflowModel(Base, TimestampMixin):
    """
    Persistent table storing orchestrated execution workflows.
    """
    __tablename__ = "workflows"

    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), default=ExecutionMode.SEQUENTIAL.value, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=WorkflowStatus.PENDING.value, nullable=False, index=True)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    context_variables_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    max_execution_time_seconds: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_contract(self, steps: Optional[List[TaskStepContract]] = None) -> WorkflowContract:
        """Convert ORM model to validated WorkflowContract."""
        return WorkflowContract(
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            name=self.name,
            description=self.description,
            execution_mode=ExecutionMode(self.execution_mode),
            status=WorkflowStatus(self.status),
            steps=steps or [],
            current_step_index=self.current_step_index,
            context_variables=load_json(self.context_variables_json),
            max_execution_time_seconds=self.max_execution_time_seconds,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )

    @classmethod
    def from_contract(cls, contract: WorkflowContract) -> "WorkflowModel":
        """Instantiate ORM model from validated WorkflowContract."""
        return cls(
            workflow_id=contract.workflow_id,
            task_id=contract.task_id,
            name=contract.name,
            description=contract.description,
            execution_mode=contract.execution_mode.value if hasattr(contract.execution_mode, "value") else str(contract.execution_mode),
            status=contract.status.value if hasattr(contract.status, "value") else str(contract.status),
            current_step_index=contract.current_step_index,
            context_variables_json=dump_json(contract.context_variables),
            max_execution_time_seconds=contract.max_execution_time_seconds,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
            completed_at=contract.completed_at,
        )


class WorkflowStateModel(Base):
    """
    Persistent table for durable state checkpoints.
    Enables workflow recovery across crashes, restarts, and approval pauses.
    """
    __tablename__ = "workflow_states"

    checkpoint_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_step_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    completed_step_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    failed_step_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    step_outputs_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    accumulated_context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    checkpoint_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def to_contract(self) -> WorkflowStateContract:
        """Convert ORM model to validated WorkflowStateContract."""
        return WorkflowStateContract(
            workflow_id=self.workflow_id,
            status=WorkflowStatus(self.status),
            active_step_id=self.active_step_id,
            completed_step_ids=load_json(self.completed_step_ids_json) if isinstance(load_json(self.completed_step_ids_json), list) else [],
            failed_step_ids=load_json(self.failed_step_ids_json) if isinstance(load_json(self.failed_step_ids_json), list) else [],
            step_outputs=load_json(self.step_outputs_json),
            accumulated_context=load_json(self.accumulated_context_json),
            checkpoint_timestamp=self.checkpoint_timestamp,
        )

    @classmethod
    def from_contract(cls, contract: WorkflowStateContract) -> "WorkflowStateModel":
        """Instantiate ORM model from validated WorkflowStateContract."""
        return cls(
            workflow_id=contract.workflow_id,
            status=contract.status.value if hasattr(contract.status, "value") else str(contract.status),
            active_step_id=contract.active_step_id,
            completed_step_ids_json=dump_json(contract.completed_step_ids),
            failed_step_ids_json=dump_json(contract.failed_step_ids),
            step_outputs_json=dump_json(contract.step_outputs),
            accumulated_context_json=dump_json(contract.accumulated_context),
            checkpoint_timestamp=contract.checkpoint_timestamp,
        )
