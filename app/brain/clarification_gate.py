"""Stage 3: Risk-Tiered Clarification & Human-in-the-Loop Gate."""
import enum
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ClarificationGate")


class RiskTier(str, enum.Enum):
    TIER_1_READ_ONLY = "TIER_1_READ_ONLY"          # Zero risk: read, search, status, telemetry
    TIER_2_IDEMPOTENT_WRITE = "TIER_2_IDEMPOTENT_WRITE"  # Safe write: temp files, reminders, local tests
    TIER_3_HIGH_RISK = "TIER_3_HIGH_RISK"          # High risk: delete, wipe, payment, external message


class ClarificationDecision(BaseModel):
    requires_clarification: bool
    risk_tier: RiskTier
    clarification_prompt: Optional[str] = None
    reason: str


class ClarificationGate:
    """Evaluates proposed actions against risk policies to prevent over-questioning while blocking dangerous ops."""

    DESTRUCTIVE_KEYWORDS = [
        "delete", "remove", "drop", "wipe", "clean disk", "format",
        "rm -rf", "del /f", "kill -9", "transfer money", "pay", "send email to all"
    ]

    READ_ONLY_KEYWORDS = [
        "get", "read", "fetch", "check", "status", "list", "show",
        "battery", "ram", "cpu", "screen", "screenshot", "search", "view", "find"
    ]

    def evaluate_intent(self, raw_query: str, target_action: Optional[str] = None) -> ClarificationDecision:
        """Determines if the action requires user confirmation before proceeding."""
        query_lower = (raw_query or "").lower()

        # Check for Tier 3: High Risk / Destructive
        for kw in self.DESTRUCTIVE_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
                return ClarificationDecision(
                    requires_clarification=True,
                    risk_tier=RiskTier.TIER_3_HIGH_RISK,
                    clarification_prompt=f"⚠️ Boss, indha command high-risk operation ({kw}). Confirm panna proceed pannatuma?",
                    reason=f"Matched high-risk keyword: '{kw}'",
                )

        # Check for Tier 1: Zero Risk / Read Only
        for kw in self.READ_ONLY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
                return ClarificationDecision(
                    requires_clarification=False,
                    risk_tier=RiskTier.TIER_1_READ_ONLY,
                    reason=f"Safe read-only operation: '{kw}'",
                )

        # Default to Tier 2: Safe Execution with logging
        return ClarificationDecision(
            requires_clarification=False,
            risk_tier=RiskTier.TIER_2_IDEMPOTENT_WRITE,
            reason="Standard idempotent execution",
        )
