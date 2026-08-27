"""Data contracts for Telegram Updates, Users, Chats, and Outbound Responses."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from app.core.contracts.base import VersionedContractBase


class TelegramResponseState(str, Enum):
    """Standardized user-facing outbound status classifications."""
    TASK_ACCEPTED = "task_accepted"
    TASK_RUNNING = "task_running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RECOVERED = "task_recovered"


class TelegramUser(BaseModel):
    """Telegram sender user representation."""
    id: int = Field(..., description="Unique Telegram user ID.")
    is_bot: bool = Field(default=False, description="True if user is a bot.")
    first_name: str = Field(..., description="User's first name.")
    last_name: Optional[str] = Field(default=None, description="User's last name.")
    username: Optional[str] = Field(default=None, description="Telegram username handle.")
    language_code: Optional[str] = Field(default="en", description="IETF language tag.")


class TelegramChat(BaseModel):
    """Telegram chat or channel representation."""
    id: int = Field(..., description="Unique chat identifier.")
    type: str = Field(default="private", description="Chat type (private, group, supergroup, channel).")
    title: Optional[str] = Field(default=None, description="Group/channel title.")
    username: Optional[str] = Field(default=None, description="Chat username.")


class TelegramMessage(BaseModel):
    """Telegram message container."""
    model_config = {"populate_by_name": True}
    message_id: int = Field(..., description="Unique message ID within chat.")
    from_user: Optional[TelegramUser] = Field(default=None, alias="from", description="Sender.")
    chat: TelegramChat = Field(..., description="Conversation chat.")
    date: int = Field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp()), description="Unix timestamp.")
    text: Optional[str] = Field(default=None, description="Message text content.")


class TelegramUpdate(BaseModel):
    """Top-level inbound update delivered by Telegram Webhook or polling."""
    update_id: int = Field(..., description="Unique update identifier.")
    message: Optional[TelegramMessage] = Field(default=None, description="New incoming message.")
    edited_message: Optional[TelegramMessage] = Field(default=None, description="Edited message.")


class TelegramOutboundMessage(VersionedContractBase):
    """Outbound payload sent to Telegram Chat."""
    chat_id: int = Field(..., description="Target Telegram chat ID.")
    text: str = Field(..., description="Rendered text message.")
    parse_mode: Optional[str] = Field(default="Markdown", description="HTML or Markdown formatting.")
    reply_to_message_id: Optional[int] = Field(default=None, description="Message ID to reply to.")
    response_state: TelegramResponseState = Field(
        default=TelegramResponseState.TASK_ACCEPTED,
        description="Lifecycle status."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Context metadata.")
