"""Common enumerated values across the MUKIL MASTER AGENT OS."""
from enum import Enum


class ChannelType(str, Enum):
    """Input/Output communication channels."""
    VOICE = "voice"
    TELEGRAM = "telegram"
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    API = "api"
    CLI = "cli"
    SYSTEM = "system"


class PriorityLevel(str, Enum):
    """Task execution priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Risk tiers for permission and safety evaluation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Environment(str, Enum):
    """Execution environment."""
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
