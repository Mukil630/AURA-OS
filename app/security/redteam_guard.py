"""Adversarial Defense Engine, Prompt Injection Filter, and Multi-Tenant Security Guard."""
import re
from typing import Any, Dict, List, Optional, Set


# ── Adversarial Prompt Injection Signatures ──────────────────────────────────
INJECTION_SIGNATURES: List[re.Pattern] = [
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)\b"),
    re.compile(r"(?i)\bdisregard\s+(all\s+)?(security|system|safety)\s+(rules|guidelines|policies)\b"),
    re.compile(r"(?i)\bsystem\s+override\s*:\s*execute\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+in\s+(developer|god|dan|unrestricted)\s+mode\b"),
    re.compile(r"(?i)\b(print|reveal|show|send|exfiltrate|leak|give\s+me)\s+(the\s+|your\s+|me\s+)?(google\s+|github\s+|telegram\s+)?(oauth|pat|token|api_key|password|credential|bot_token|bot\s+token)\b"),
    re.compile(r"(?i)\b(dump|reveal|show|print)\s+(the\s+|your\s+)?(core\s+instructions|system\s+prompt|prompt|instructions)\b"),
    re.compile(r"(?i)\b__admin_bypass__\b"),
]


class PromptInjectionGuard:
    """
    Guards against direct and indirect prompt injection, jailbreaks, and persona hijacking.
    """

    @classmethod
    def contains_adversarial_injection(cls, text: Optional[str]) -> bool:
        """Return True if text contains detected prompt injection patterns."""
        if not text:
            return False
        clean = text.strip()
        for pattern in INJECTION_SIGNATURES:
            if pattern.search(clean):
                return True
        return False

    @classmethod
    def sanitize_user_input(cls, text: Optional[str]) -> str:
        """Strip dangerous delimiter breakout sequences."""
        if not text:
            return ""
        # Remove delimiter breakouts
        sanitized = re.sub(r"<\|im_start\|>|<\|im_end\|>|\[\[SYSTEM\]\]|\[\[ADMIN\]\]", "", text)
        return sanitized.strip()


class ToolOutputPoisoningGuard:
    """
    Guards against indirect prompt injection embedded in tool responses and external files.
    """

    @classmethod
    def sanitize_untrusted_output(cls, data: Any) -> Any:
        """Neutralize malicious injection instructions in tool responses."""
        if isinstance(data, str):
            for pattern in INJECTION_SIGNATURES:
                if pattern.search(data):
                    return "[FLAGGED: Untrusted tool output containing adversarial prompt injection stripped]"
            return data
        elif isinstance(data, dict):
            return {k: cls.sanitize_untrusted_output(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.sanitize_untrusted_output(item) for item in data]
        return data


class TenantSecurityGuard:
    """
    Enforces strict multi-tenant boundary isolation across tasks, files, and capabilities.
    """

    @classmethod
    def enforce_tenant_isolation(cls, requester_user_id: str, resource_owner_user_id: str) -> bool:
        """Return True if requester has permission to access resource owner."""
        if not requester_user_id or not resource_owner_user_id:
            return False
        # Strict equality matching
        return str(requester_user_id).strip().lower() == str(resource_owner_user_id).strip().lower()
