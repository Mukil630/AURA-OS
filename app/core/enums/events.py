"""Audit event and execution stream event enums."""
from enum import Enum


class EventType(str, Enum):
    """Types of system and lifecycle audit events."""
    # Task Lifecycle
    TASK_CREATED = "task_created"
    TASK_PARSED = "task_parsed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Planning & Graph
    PLAN_GENERATED = "plan_generated"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_CHECKPOINT = "workflow_checkpoint"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Steps
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"

    # Human-in-the-loop & Permissions
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_TIMEOUT = "approval_timeout"
    PERMISSION_DENIED = "permission_denied"

    # Tool Execution
    TOOL_CALLED = "tool_called"
    TOOL_EXECUTED = "tool_executed"
    TOOL_FAILED = "tool_failed"

    # Verification & Recovery
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    RECOVERY_SUCCEEDED = "recovery_succeeded"
    RECOVERY_FAILED = "recovery_failed"
    STEP_RETRIED = "step_retried"
    ESCALATED_TO_HUMAN = "escalated_to_human"

    # Memory
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_SAVED = "memory_saved"

    # Telegram Channel & Webhook
    TELEGRAM_UPDATE_RECEIVED = "telegram_update_received"
    TELEGRAM_AUTHENTICATED = "telegram_authenticated"
    TELEGRAM_REJECTED = "telegram_rejected"
    TELEGRAM_UPDATE_DUPLICATE = "telegram_update_duplicate"
    TELEGRAM_TASK_CREATED = "telegram_task_created"
    TELEGRAM_RESPONSE_SENT = "telegram_response_sent"
    TELEGRAM_RATE_LIMITED = "telegram_rate_limited"
    TELEGRAM_DISPATCH_FAILED = "telegram_dispatch_failed"

    # PC Sidecar Hardware & Telemetry
    PC_TELEMETRY_REQUESTED = "pc_telemetry_requested"
    PC_TELEMETRY_COLLECTED = "pc_telemetry_collected"
    PC_TELEMETRY_REJECTED = "pc_telemetry_rejected"
    PC_TELEMETRY_TIMEOUT = "pc_telemetry_timeout"
    PC_TELEMETRY_FAILED = "pc_telemetry_failed"


class EventSeverity(str, Enum):
    """Severity classification of audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
