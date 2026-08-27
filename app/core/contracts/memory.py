"""Version 1 Data Contracts for Memory, Episodic Retrieval, and Context Storage."""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    MemoryScope,
    MemoryType,
)


class MemoryContract(VersionedContractBase):
    """
    Contract representing a persistent discrete unit of memory.
    Supports Working, Episodic, Semantic, User Preference, and Tool knowledge memory.
    """
    memory_id: str = Field(
        default_factory=lambda: f"mem_{uuid4().hex[:12]}",
        description="Unique identifier for the memory entry."
    )
    memory_type: MemoryType = Field(
        ...,
        description="Classification of the memory subsystem."
    )
    scope: MemoryScope = Field(
        default=MemoryScope.USER,
        description="Isolation scope boundary."
    )
    user_id: str = Field(
        ...,
        description="Owner user ID for this memory record."
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Optional project identifier associated with this memory."
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Primary textual content or structured fact payload."
    )
    summary: Optional[str] = Field(
        default=None,
        description="Condensed summary for fast prompt injection."
    )
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relevance and retention priority weight (0.0 to 1.0)."
    )
    source_task_id: Optional[str] = Field(
        default=None,
        description="Task ID from which this memory was distilled/learned."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Semantic tags for indexing and filtering."
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiration timestamp for ephemeral memory."
    )


class MemoryQueryContract(VersionedContractBase):
    """Query specification contract for context retrieval prior to planning."""
    query_text: str = Field(..., min_length=1, description="Semantic or keyword query text.")
    user_id: str = Field(..., description="Target user ID.")
    memory_types: List[MemoryType] = Field(
        default_factory=lambda: [MemoryType.SEMANTIC_FACT, MemoryType.EPISODIC_TASK, MemoryType.USER_PREFERENCE],
        description="Memory types to search."
    )
    scope: MemoryScope = Field(default=MemoryScope.USER, description="Scope boundary for retrieval.")
    project_id: Optional[str] = Field(default=None, description="Optional project context filter.")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of memory items to return.")
    min_importance: float = Field(default=0.2, ge=0.0, le=1.0, description="Minimum importance threshold.")
