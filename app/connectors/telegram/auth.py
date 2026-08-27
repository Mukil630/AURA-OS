"""Telegram Webhook Secret Verification and Tenant Authorization Engine."""
import os
from typing import Dict, Optional


class TelegramAuthorizer:
    """
    Validates Telegram Webhook integrity and authorizes chat/user identities.
    Prevents unauthorized strangers from executing tasks or accessing tenant memory.
    """

    def __init__(
        self,
        default_secret: Optional[str] = None,
        user_mappings: Optional[Dict[str, str]] = None,
    ):
        self._secret = default_secret or os.getenv("TELEGRAM_WEBHOOK_SECRET", "mukil_jarvis_secret_webhook_2026")
        # Map Telegram IDs/Usernames to internal tenant user_ids
        self._authorized_users: Dict[str, str] = user_mappings or {
            "987654321": "mukil",
            "mukil630": "mukil",
            "mukil_admin": "mukil",
            "123456789": "mukil",
        }

    def verify_webhook_secret(self, provided_secret: Optional[str]) -> bool:
        """Verify the X-Telegram-Bot-Api-Secret-Token header."""
        if not provided_secret or not self._secret:
            return False
        return provided_secret.strip() == self._secret.strip()

    def authorize_user(self, telegram_user_id: int, username: Optional[str] = None) -> Optional[str]:
        """
        Authorize Telegram identity and resolve corresponding application tenant user_id.
        Returns internal user_id if authorized, None if forbidden.
        """
        # 1. Check numeric user ID mapping
        str_id = str(telegram_user_id)
        if str_id in self._authorized_users:
            return self._authorized_users[str_id]

        # 2. Check username mapping
        if username and username.lower() in self._authorized_users:
            return self._authorized_users[username.lower()]

        # 3. Unauthorized
        return None

    def register_authorized_user(self, telegram_identity: str, tenant_user_id: str) -> None:
        """Add authorized user mapping."""
        self._authorized_users[str(telegram_identity).lower()] = tenant_user_id

    def revoke_user(self, telegram_identity: str) -> None:
        """Revoke authorized user."""
        self._authorized_users.pop(str(telegram_identity).lower(), None)
