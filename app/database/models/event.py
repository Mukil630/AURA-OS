"""SQLAlchemy ORM Model for Execution Events and Distributed Audit Trails."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.enums import EventSeverity, EventType
from app.database.base import Base, dump_json, load_json


class ExecutionEventModel(Base):
    """
    Immutable audit log table capturing telemetry, lifecycle transitions, and trace events.
    """
    __tablename__ = "execution_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    step_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), default=EventSeverity.INFO.value, nullable=False)
    source_component: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_events_task_time", "task_id", "timestamp"),
    )

    def to_contract(self) -> ExecutionEventContract:
        """Convert ORM model to validated ExecutionEventContract."""
        return ExecutionEventContract(
            event_id=self.event_id,
            trace_id=self.trace_id,
            task_id=self.task_id,
            workflow_id=self.workflow_id,
            step_id=self.step_id,
            event_type=EventType(self.event_type),
            severity=EventSeverity(self.severity),
            source_component=self.source_component,
            message=self.message,
            payload=load_json(self.payload_json),
            timestamp=self.timestamp,
        )

    @classmethod
    def from_contract(cls, contract: ExecutionEventContract) -> "ExecutionEventModel":
        """Instantiate ORM model from validated ExecutionEventContract."""
        return cls(
            event_id=contract.event_id,
            trace_id=contract.trace_id,
            task_id=contract.task_id,
            workflow_id=contract.workflow_id,
            step_id=contract.step_id,
            event_type=contract.event_type.value if hasattr(contract.event_type, "value") else str(contract.event_type),
            severity=contract.severity.value if hasattr(contract.severity, "value") else str(contract.severity),
            source_component=contract.source_component,
            message=contract.message,
            payload_json=dump_json(contract.payload),
            timestamp=contract.timestamp,
        )
