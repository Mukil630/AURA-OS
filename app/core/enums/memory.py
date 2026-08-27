"""Memory classification and scope enums."""
from enum import Enum


class MemoryType(str, Enum):
    """Subsystems of memory storage."""
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC_TASK = "episodic_task"
    SEMANTIC_FACT = "semantic_fact"
    USER_PREFERENCE = "user_preference"
    PROJECT_CONTEXT = "project_context"
    TOOL_KNOWLEDGE = "tool_knowledge"


class MemoryScope(str, Enum):
    """Visibility and lifecycle boundary for stored memory."""
    SESSION = "session"
    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"
