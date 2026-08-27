"""Agent identity, types, and operational states."""
from enum import Enum


class AgentType(str, Enum):
    """Specialized Agent role classifications."""
    MASTER = "master"
    RESEARCH = "research"
    CODING = "coding"
    CLOUD_FILE = "cloud_file"
    BROWSER = "browser"
    COMMUNICATION = "communication"
    PC = "pc"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Operational status of a Specialist Agent."""
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"
