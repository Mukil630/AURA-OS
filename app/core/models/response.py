"""Normalized agent response model for dispatch to client channels."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import ChannelType, TaskStatus


class NormalizedAgentResponse(VersionedContractBase):
    """
    Standardized response payload emitted back to clients.
    Formatted for both rich graphical/text UIs and audio TTS synthesis.
    """
    response_id: str = Field(
        default_factory=lambda: f"resp_{uuid4().hex[:12]}",
        description="Unique response ID."
    )
    request_id: str = Field(..., description="Correlated incoming request ID.")
    task_id: str = Field(..., description="Associated task ID.")
    channel: ChannelType = Field(..., description="Target dispatch channel.")
    status: TaskStatus = Field(..., description="Task execution outcome state.")
    text_content: str = Field(..., description="Markdown/text formatted response.")
    voice_content: Optional[str] = Field(
        default=None,
        description="Concise, phonetically friendly spoken audio script for TTS."
    )
    artifacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Generated files, download links, Drive URLs, or metrics."
    )
    suggested_actions: List[str] = Field(
        default_factory=list,
        description="Quick-reply action suggestions for the user."
    )
    latency_ms: float = Field(default=0.0, ge=0.0, description="Total pipeline latency in ms.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when response was formatted."
    )
