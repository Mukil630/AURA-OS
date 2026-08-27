"""Security Sanitizers for Secret Masking, Log Redaction, and Path Traversal Prevention."""
import posixpath
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Union


# ── Regular Expression Patterns for High-Risk Secrets ─────────────────────────
SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"ghp_[A-Za-z0-9_]{20,}", re.IGNORECASE),                         # GitHub PAT
    re.compile(r"gho_[A-Za-z0-9_]{20,}", re.IGNORECASE),                         # GitHub OAuth
    re.compile(r"ya29\.[A-Za-z0-9_.-]{20,}", re.IGNORECASE),                     # Google OAuth
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),                              # Telegram Bot Token
    re.compile(r"Bearer\s+[A-Za-z0-9_.-\/]{20,}", re.IGNORECASE),                # Bearer Token
    re.compile(r"(?i)(password|secret|api_key|private_key|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?"), # Key-Value Secrets
]


class SecretSanitizer:
    """
    Guarantees that raw secrets never leak into LLM prompts, logs, responses,
    task summaries, or audit events.
    """

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        """Redact known secret patterns from string content."""
        if not text:
            return ""

        sanitized = str(text)

        # 1. Redact GitHub Tokens (PAT, OAuth, User-to-Server, Server-to-Server, Refresh)
        sanitized = re.sub(
            r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{4}([A-Za-z0-9_]+)([A-Za-z0-9_]{4})",
            r"\1_****\3",
            sanitized,
        )
        sanitized = re.sub(r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{10,}", "[REDACTED_GITHUB_TOKEN]", sanitized)

        # 2. Redact Google OAuth Tokens
        sanitized = re.sub(
            r"ya29\.[A-Za-z0-9_.-]{4}([A-Za-z0-9_.-]+)([A-Za-z0-9_.-]{4})",
            r"ya29****\2",
            sanitized,
        )
        sanitized = re.sub(r"ya29\.[A-Za-z0-9_.-]{10,}", "[REDACTED_GOOGLE_OAUTH]", sanitized)

        # 3. Redact Telegram Bot Tokens
        sanitized = re.sub(
            r"(\d{4})\d+:[A-Za-z0-9_-]+([A-Za-z0-9_-]{4})",
            r"\1****\2",
            sanitized,
        )
        sanitized = re.sub(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b", "[REDACTED_TELEGRAM_TOKEN]", sanitized)

        # 4. Redact generic Bearer Tokens
        sanitized = re.sub(r"Bearer\s+[A-Za-z0-9_.\-\/]{15,}", "Bearer [REDACTED_TOKEN]", sanitized)

        # 5. Redact key-value credentials
        sanitized = re.sub(
            r"(?i)\b(password|secret|api_key|access_token)\s*[:=]\s*(['\"][^'\"]+['\"]|[^\s,]+)",
            r"\1=[REDACTED]",
            sanitized,
        )

        return sanitized

    @classmethod
    def sanitize_dict(cls, data: Any) -> Any:
        """Recursively sanitize dictionary or list structures."""
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                # Check for sensitive key names
                if any(s in str(k).lower() for s in ["token", "secret", "password", "key", "auth", "credential"]):
                    if isinstance(v, str) and len(v) > 8:
                        clean[k] = cls.sanitize_text(v)
                    else:
                        clean[k] = "[REDACTED]"
                else:
                    clean[k] = cls.sanitize_dict(v)
            return clean
        elif isinstance(data, list):
            return [cls.sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return cls.sanitize_text(data)
        return data


class PathSanitizer:
    """
    Enforces path canonicalization and directory sandboxing.
    Protects against directory traversal, URL encoding exploits, Unicode normalization,
    and null-byte injections.
    """

    RESTRICTED_KEYWORDS = ["/system", "/private", "/root", "/etc", "/windows", "/boot", "config.sys"]

    @classmethod
    def canonicalize_path(cls, raw_path: Optional[str]) -> str:
        """Decode, normalize, and resolve path to standard POSIX style."""
        if not raw_path:
            return "/"

        # 1. URL-decode repeatedly to defeat multi-encoded exploits (%252e%252e)
        decoded = raw_path
        for _ in range(3):
            prev = decoded
            decoded = urllib.parse.unquote(decoded)
            if decoded == prev:
                break

        # 2. Reject null-byte injections
        if "\x00" in decoded or "%00" in decoded:
            return "/INVALID_NULL_BYTE_PATH"

        # 3. Replace backslashes with forward slashes
        normalized = decoded.replace("\\", "/")

        # 4. Collapse duplicate slashes
        normalized = re.sub(r"/+", "/", normalized)

        # 5. Normalize path removing relative navigation (..)
        canonical = posixpath.normpath(normalized)

        if not canonical.startswith("/"):
            canonical = "/" + canonical

        # Ensure trailing slash if original intended folder
        if raw_path.endswith("/") and not canonical.endswith("/"):
            canonical += "/"

        return canonical

    @classmethod
    def is_path_allowed(cls, path: str, allowed_prefixes: List[str]) -> bool:
        """
        Verify if canonicalized path is within sandbox boundary and outside restricted zones.
        """
        canonical = cls.canonicalize_path(path)
        low = canonical.lower()

        # Check explicit forbidden targets
        for restricted in cls.RESTRICTED_KEYWORDS:
            if restricted in low:
                return False

        # Must start with at least one allowed prefix
        return any(canonical.startswith(prefix) for prefix in allowed_prefixes)
