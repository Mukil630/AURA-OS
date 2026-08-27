"""Failure Category and Recovery Strategy Enums."""
from enum import Enum


class FailureCategory(str, Enum):
    """Categorization of execution faults."""
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    """Actionable mitigation strategies selected by SelfHealingEngine."""
    RETRY = "retry"
    REPAIR_INPUT = "repair_input"
    FALLBACK_TOOL = "fallback_tool"
    REPLAN_DAG = "replan_dag"
    ESCALATE_HUMAN = "escalate_human"
