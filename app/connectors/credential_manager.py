"""Secure Credential Manager with Token Isolation and Zero-LLM-Leakage Guarantee."""
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.contracts.connector import CredentialContract
from app.core.enums import ConnectorType


class CredentialManager:
    """
    Manages secure retrieval and isolation of API keys, tokens, and service credentials.
    CRITICAL SECURITY INVARIANT: Raw credentials NEVER leave this boundary into LLM prompts or audit logs.
    """

    def __init__(self, override_env: Optional[Dict[str, str]] = None):
        self._custom_store: Dict[str, str] = override_env or {}

    def mask_token(self, token: str) -> str:
        """Mask token leaving only the prefix and the last 4 characters visible."""
        if not token:
            return "none"
        if len(token) <= 8:
            return "********"
        prefix = token[:4]
        suffix = token[-4:]
        return f"{prefix}****{suffix}"

    def get_credential(self, provider: ConnectorType, user_id: str = "system") -> Optional[str]:
        """
        Securely resolve raw credential from internal vault or environment.
        Used strictly by internal Connector adapters at network dispatch time.
        """
        key = f"{provider.value.upper()}_TOKEN"
        # 1. Check custom in-memory store
        if key in self._custom_store:
            return self._custom_store[key]
        if f"{user_id.upper()}_{key}" in self._custom_store:
            return self._custom_store[f"{user_id.upper()}_{key}"]

        # 2. Check system environment
        env_val = os.getenv(key) or os.getenv(f"{provider.value.upper()}_API_KEY")
        if env_val:
            return env_val

        # 3. If in mock/test/local mode, provide safe dummy credentials
        if os.getenv("ENVIRONMENT", "local").lower() in ("mock", "test", "local"):
            return f"mock_{provider.value}_key_{user_id}"

        return None

    def set_credential(self, provider: ConnectorType, token: str, user_id: str = "system") -> CredentialContract:
        """Store credential securely and return sanitized, masked CredentialContract."""
        key = f"{provider.value.upper()}_TOKEN" if user_id == "system" else f"{user_id.upper()}_{provider.value.upper()}_TOKEN"
        self._custom_store[key] = token

        return CredentialContract(
            provider=provider,
            user_id=user_id,
            masked_value=self.mask_token(token),
            is_valid=True,
        )

    def get_credential_metadata(self, provider: ConnectorType, user_id: str = "system") -> CredentialContract:
        """Return safe, sanitized metadata representation of credential for inspectability."""
        raw = self.get_credential(provider, user_id)
        return CredentialContract(
            provider=provider,
            user_id=user_id,
            masked_value=self.mask_token(raw) if raw else "not_configured",
            is_valid=bool(raw),
        )
