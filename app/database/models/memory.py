"""SQLAlchemy ORM Model for Persistent Memory."""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.contracts.memory import MemoryContract
from app.core.enums import MemoryScope, MemoryType
from app.database.base import Base, TimestampMixin, dump_json, load_json


class MemoryModel(Base, TimestampMixin):
    """
    Persistent table for working, episodic, semantic, and preference memories.
    """
    __tablename__ = "memories"

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(32), default=MemoryScope.USER.value, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    source_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_memories_user_type", "user_id", "memory_type"),
    )

    def to_contract(self) -> MemoryContract:
        """Convert ORM model to MemoryContract."""
        return MemoryContract(
            memory_id=self.memory_id,
            memory_type=MemoryType(self.memory_type),
            scope=MemoryScope(self.scope),
            user_id=self.user_id,
            project_id=self.project_id,
            content=self.content,
            summary=self.summary,
            importance_score=self.importance_score,
            source_task_id=self.source_task_id,
            tags=load_json(self.tags_json) if isinstance(load_json(self.tags_json), list) else [],
            created_at=self.created_at,
            expires_at=self.expires_at,
        )

    @classmethod
    def from_contract(cls, contract: MemoryContract) -> "MemoryModel":
        """Instantiate ORM model from MemoryContract."""
        return cls(
            memory_id=contract.memory_id,
            memory_type=contract.memory_type.value if hasattr(contract.memory_type, "value") else str(contract.memory_type),
            scope=contract.scope.value if hasattr(contract.scope, "value") else str(contract.scope),
            user_id=contract.user_id,
            project_id=contract.project_id,
            content=contract.content,
            summary=contract.summary,
            importance_score=contract.importance_score,
            source_task_id=contract.source_task_id,
            tags_json=dump_json(contract.tags),
            created_at=contract.created_at,
            expires_at=contract.expires_at,
        )
