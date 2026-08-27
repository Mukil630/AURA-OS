"""Task-specific lifecycle and intent enums."""
from enum import Enum


class TaskStatus(str, Enum):
    """Lifecycle state of a user-requested Task."""
    CREATED = "created"
    PARSING = "parsing"
    RETRIEVING_CONTEXT = "retrieving_context"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    PAUSED = "paused"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """High-level functional category of a task."""
    INFORMATIONAL = "informational"
    ACTION = "action"
    AUTOMATION = "automation"
    RESEARCH = "research"
    CODING = "coding"
    FILE_OPERATION = "file_operation"
    COMMUNICATION = "communication"
    SYSTEM_CONTROL = "system_control"
    SCHEDULED_TASK = "scheduled_task"
    MULTI_AGENT_WORKFLOW = "multi_agent_workflow"


class IntentCategory(str, Enum):
    """Understood user intent categories."""
    QUERY = "query"
    WORKFLOW_EXECUTION = "workflow_execution"
    SYSTEM_CONFIGURATION = "system_configuration"
    AUTOMATION_SCHEDULE = "automation_schedule"
    FILE_SYNC = "file_sync"
    CODE_ASSISTANCE = "code_assistance"
    COMMUNICATION_DISPATCH = "communication_dispatch"
    PC_HARDWARE_CONTROL = "pc_hardware_control"
    UNKNOWN = "unknown"
