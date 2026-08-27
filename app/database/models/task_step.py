"""SQLAlchemy ORM Model for Workflow TaskSteps."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.contracts.task_step import TaskStepContract
from app.core.enums import (
    AgentType,
    ApprovalState,
    RiskTier,
    StepStatus,
)
from app.database.base import Base, TimestampMixin, dump_json, load_json


class TaskStepModel(Base, TimestampMixin):
    """
    Persistent table storing individual atomic steps within an orchestrated workflow.
    """
    __tablename__ = "task_steps"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    output_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=StepStatus.PENDING.value, nullable=False, index=True)
    risk_tier: Mapped[str] = mapped_column(String(32), default=RiskTier.TIER_1_LOW.value, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_state: Mapped[str] = mapped_column(String(32), default=ApprovalState.NOT_REQUIRED.value, nullable=False)
    dependencies_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_steps_wf_index", "workflow_id", "step_index"),
    )

    def to_contract(self) -> TaskStepContract:
        """Convert ORM model to validated TaskStepContract."""
        return TaskStepContract(
            step_id=self.step_id,
            workflow_id=self.workflow_id,
            step_index=self.step_index,
            name=self.name,
            description=self.description,
            agent_type=AgentType(self.agent_type),
            tool_name=self.tool_name,
            input_payload=load_json(self.input_payload_json),
            output_payload=load_json(self.output_payload_json) if self.output_payload_json else None,
            status=StepStatus(self.status),
            risk_tier=RiskTier(self.risk_tier),
            requires_approval=self.requires_approval,
            approval_state=ApprovalState(self.approval_state),
            dependencies=load_json(self.dependencies_json) if isinstance(load_json(self.dependencies_json), list) else [],
            timeout_seconds=self.timeout_seconds,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            error_message=self.error_message,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )

    @classmethod
    def from_contract(cls, contract: TaskStepContract) -> "TaskStepModel":
        """Instantiate ORM model from validated TaskStepContract."""
        return cls(
            step_id=contract.step_id,
            workflow_id=contract.workflow_id,
            step_index=contract.step_index,
            name=contract.name,
            description=contract.description,
            agent_type=contract.agent_type.value if hasattr(contract.agent_type, "value") else str(contract.agent_type),
            tool_name=contract.tool_name,
            input_payload_json=dump_json(contract.input_payload),
            output_payload_json=dump_json(contract.output_payload) if contract.output_payload else None,
            status=contract.status.value if hasattr(contract.status, "value") else str(contract.status),
            risk_tier=contract.risk_tier.value if hasattr(contract.risk_tier, "value") else str(contract.risk_tier),
            requires_approval=contract.requires_approval,
            approval_state=contract.approval_state.value if hasattr(contract.approval_state, "value") else str(contract.approval_state),
            dependencies_json=dump_json(contract.dependencies),
            timeout_seconds=contract.timeout_seconds,
            retry_count=contract.retry_count,
            max_retries=contract.max_retries,
            error_message=contract.error_message,
            created_at=contract.created_at,
            started_at=contract.started_at,
            completed_at=contract.completed_at,
        )
