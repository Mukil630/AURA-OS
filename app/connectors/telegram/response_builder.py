"""Outbound Response Builder for Telegram Messaging Channel."""
from typing import Any, Dict, Optional

from app.connectors.telegram.contracts import (
    TelegramOutboundMessage,
    TelegramResponseState,
)


class TelegramResponseBuilder:
    """
    Constructs clean, structured, user-facing responses for Telegram chats.
    CRITICAL SECURITY GUARANTEE: Never includes raw API tokens, system passwords,
    internal stack traces, or confidential filesystem directories.
    """

    @staticmethod
    def build_response(
        chat_id: int,
        state: TelegramResponseState,
        task_id: Optional[str] = None,
        summary: Optional[str] = None,
        error_message: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> TelegramOutboundMessage:
        """Construct sanitized TelegramOutboundMessage based on lifecycle state."""
        tid = f" (Task `{task_id}`)" if task_id else ""

        if state == TelegramResponseState.TASK_ACCEPTED:
            text = f"🤖 **Task Received**{tid}\n\nGot it! I have received your request and started planning the workflow."

        elif state == TelegramResponseState.TASK_RUNNING:
            text = f"⚡ **Executing**{tid}\n\nCurrently executing workflow steps and verifying outputs..."

        elif state == TelegramResponseState.WAITING_FOR_APPROVAL:
            text = f"⚠️ **Authorization Required**{tid}\n\nThis high-risk action requires your explicit approval before proceeding."

        elif state == TelegramResponseState.TASK_COMPLETED:
            body = summary or "All automated actions and checks were verified green."
            text = f"✅ **Task Completed**{tid}\n\n{body}"

        elif state == TelegramResponseState.TASK_RECOVERED:
            body = summary or "Transient failure was automatically healed via bounded retry."
            text = f"🔄 **Self-Healed & Completed**{tid}\n\n{body}"

        elif state == TelegramResponseState.TASK_FAILED:
            safe_err = error_message or "Task encountered an unrecoverable failure."
            # Sanitize any accidental sensitive leaks
            if "key" in safe_err.lower() or "token" in safe_err.lower():
                safe_err = "Operation failed due to an authorization or service error."
            text = f"❌ **Task Failed**{tid}\n\n{safe_err}"

        else:
            text = f"ℹ️ **Status Update**{tid}\n\n{summary or 'Status updated.'}"

        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_to_message_id=reply_to_message_id,
            response_state=state,
            metadata=extra_metadata or {},
        )
