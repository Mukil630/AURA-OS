"""Permission, approval states, and risk tier enums."""
from enum import Enum


class PermissionAction(str, Enum):
    """Granular action types evaluated by PermissionEngine."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    NETWORK_ACCESS = "network_access"
    HARDWARE_ACCESS = "hardware_access"
    ADMIN = "admin"


class ApprovalState(str, Enum):
    """Human-in-the-loop approval lifecycle state."""
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RiskTier(str, Enum):
    """Standardized 4-tier risk classification."""
    TIER_1_LOW = "tier_1_low"           # Read-only, safe queries, local info
    TIER_2_MEDIUM = "tier_2_medium"     # File creation, message sending, non-destructive edits
    TIER_3_HIGH = "tier_3_high"         # Deletions, shell execution, external pushes, deploy
    TIER_4_CRITICAL = "tier_4_critical" # OS format, credential modification, production database changes
