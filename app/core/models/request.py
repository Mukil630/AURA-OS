"""Normalized user request representation across all input channels."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import ChannelType, PriorityLevel


class NormalizedUserRequest(VersionedContractBase):
    """
    Standardized internal representation of an incoming user request,
    regardless of whether it originated from Voice, Telegram, Web, Mobile, or CLI.
    """
    request_id: str = Field(
        default_factory=lambda: f"req_{uuid4().hex[:12]}",
        description="Unique request transaction ID."
    )
    user_id: str = Field(..., description="Authenticated user ID.")
    session_id: Optional[str] = Field(default=None, description="Active session ID.")
    channel: ChannelType = Field(default=ChannelType.API, description="Source input channel.")
    raw_input: str = Field(..., min_length=1, description="Raw transcription or message text.")
    language: str = Field(default="en", description="Detected language code (e.g. 'en', 'ta', 'en-ta').")
    priority: PriorityLevel = Field(default=PriorityLevel.NORMAL, description="Inferred priority.")
    client_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Device/client information (e.g. location, battery, screen status)."
    )
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Attached files, audio URLs, or media objects."
    )
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when gateway accepted request."
    )
