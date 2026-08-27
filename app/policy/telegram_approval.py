"""Telegram Channel Human-In-The-Loop Approval Gateway."""
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.connectors.telegram.auth import TelegramAuthorizer
from app.connectors.telegram.contracts import TelegramOutboundMessage
from app.core.contracts.permission import ApprovalRequestContract
from app.policy.approval_engine import ApprovalEngine, default_approval_engine


class TelegramApprovalGateway:
    """
    Renders high-fidelity approval request cards for Telegram mobile interface
    and processes cryptographic operator decisions.
    """

    def __init__(
        self,
        approval_engine: Optional[ApprovalEngine] = None,
        authorizer: Optional[TelegramAuthorizer] = None,
    ):
        self.approval_engine = approval_engine or default_approval_engine
        self.authorizer = authorizer or TelegramAuthorizer()

    def build_approval_card(self, ticket: ApprovalRequestContract, chat_id: int = 987654321) -> TelegramOutboundMessage:
        """Construct structured markdown approval card for Telegram."""
        time_left = max(0, int((ticket.expires_at - datetime.now(timezone.utc)).total_seconds()))
        mins, secs = divmod(time_left, 60)

        param_summary = "\n".join(f"  • *{k}*: `{v}`" for k, v in ticket.parameters.items()) if ticket.parameters else "  • No extra arguments"
        risk_val = ticket.risk_tier.value if hasattr(ticket.risk_tier, "value") else str(ticket.risk_tier)
        text = (
            f"⚠️ *HUMAN APPROVAL REQUIRED*\n\n"
            f"📋 *Task*: `{ticket.task_id}`\n"
            f"🛡️ *Risk Level*: *{risk_val}*\n"
            f"⚡ *Action*: `{ticket.action}`\n"
            f"🎯 *Capability*: `{ticket.capability_id or ticket.action}`\n\n"
            f"📦 *Target Parameters*:\n{param_summary}\n\n"
            f"🔐 *Action Hash*: `{ticket.action_hash[:16] if ticket.action_hash else 'N/A'}...`\n"
            f"⏳ *Expires In*: {mins}m {secs}s\n\n"
            f"Reply with:\n"
            f"👉 `/approve {ticket.approval_id}` to authorize\n"
            f"👉 `/reject {ticket.approval_id}` to deny"
        )

        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )

    def process_telegram_decision(
        self,
        telegram_user_id: int,
        raw_command: str,
        username: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Parse and execute approval commands from authorized Telegram users.
        Commands: '/approve <approval_id>' or '/reject <approval_id> [reason]'.
        """
        # 1. Authorize sender identity to tenant
        tenant_id = self.authorizer.authorize_user(telegram_user_id, username)
        if not tenant_id:
            return False, "Access Denied: Telegram user is not authorized to decide approvals."

        parts = raw_command.strip().split()
        if not parts:
            return False, "Empty command."

        action = parts[0].lstrip("/").lower()
        if action not in ("approve", "reject"):
            return False, f"Unknown approval action '{action}'. Use /approve or /reject."

        if len(parts) < 2:
            return False, f"Missing approval ID. Usage: /{action} <approval_id>"

        approval_id = parts[1]
        reason = " ".join(parts[2:]) if len(parts) > 2 else None

        # 2. Record decision in ApprovalEngine
        success, message, ticket = self.approval_engine.decide_approval(
            approval_id=approval_id,
            decision=action,
            approver_id=f"tg_{telegram_user_id} (@{username or 'unknown'})",
            reason=reason,
        )
        return success, message


# Global Singleton Telegram Approval Gateway
default_telegram_approval = TelegramApprovalGateway()
