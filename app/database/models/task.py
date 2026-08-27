"""SQLAlchemy ORM Model for User Tasks."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.contracts.task import TaskContract
from app.core.enums import (
    ChannelType,
    IntentCategory,
    PriorityLevel,
    RiskLevel,
    TaskStatus,
    TaskType,
)
from app.database.base import Base, TimestampMixin, dump_json, load_json


class TaskModel(Base, TimestampMixin):
    """
    Persistent table storing all user-requested tasks and their execution outcomes.
    """
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default=ChannelType.API.value, nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(64), default=IntentCategory.UNKNOWN.value, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), default=TaskType.ACTION.value, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default=PriorityLevel.NORMAL.value, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default=RiskLevel.LOW.value, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.CREATED.value, nullable=False, index=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
    )

    def to_contract(self) -> TaskContract:
        """Convert ORM model to validated Version 1 TaskContract."""
        return TaskContract(
            schema_version=self.schema_version,
            task_id=self.task_id,
            user_id=self.user_id,
            session_id=self.session_id,
            channel=ChannelType(self.channel),
            raw_input=self.raw_input,
            intent=IntentCategory(self.intent) if self.intent else IntentCategory.UNKNOWN,
            task_type=TaskType(self.task_type) if self.task_type else TaskType.ACTION,
            priority=PriorityLevel(self.priority) if self.priority else PriorityLevel.NORMAL,
            risk_level=RiskLevel(self.risk_level) if self.risk_level else RiskLevel.LOW,
            status=TaskStatus(self.status),
            workflow_id=self.workflow_id,
            result_summary=self.result_summary,
            result_data=load_json(self.result_data_json) if self.result_data_json else None,
            error_message=self.error_message,
            tags=load_json(self.tags_json) if isinstance(load_json(self.tags_json), list) else [],
            metadata=load_json(self.metadata_json),
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )

    @classmethod
    def from_contract(cls, contract: TaskContract) -> "TaskModel":
        """Instantiate ORM model from validated TaskContract."""
        return cls(
            task_id=contract.task_id,
            schema_version=contract.schema_version,
            user_id=contract.user_id,
            session_id=contract.session_id,
            channel=contract.channel.value if hasattr(contract.channel, "value") else str(contract.channel),
            raw_input=contract.raw_input,
            intent=contract.intent.value if hasattr(contract.intent, "value") else str(contract.intent),
            task_type=contract.task_type.value if hasattr(contract.task_type, "value") else str(contract.task_type),
            priority=contract.priority.value if hasattr(contract.priority, "value") else str(contract.priority),
            risk_level=contract.risk_level.value if hasattr(contract.risk_level, "value") else str(contract.risk_level),
            status=contract.status.value if hasattr(contract.status, "value") else str(contract.status),
            workflow_id=contract.workflow_id,
            result_summary=contract.result_summary,
            result_data_json=dump_json(contract.result_data) if contract.result_data else None,
            error_message=contract.error_message,
            tags_json=dump_json(contract.tags),
            metadata_json=dump_json(contract.metadata),
            created_at=contract.created_at,
            updated_at=contract.updated_at,
            completed_at=contract.completed_at,
        )
