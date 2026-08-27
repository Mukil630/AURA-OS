"""Tool category and execution mode enums."""
from enum import Enum


class ToolCategory(str, Enum):
    """Categorization of discrete tool capabilities."""
    SYSTEM = "system"
    BROWSER = "browser"
    CODING = "coding"
    CLOUD_FILE = "cloud_file"
    COMMUNICATION = "communication"
    RESEARCH = "research"
    HARDWARE = "hardware"
    UTILITY = "utility"


class ToolExecutionMode(str, Enum):
    """How the tool action is dispatched and run."""
    LOCAL = "local"
    MCP = "mcp"
    REST_API = "rest_api"
    SANDBOX_SHELL = "sandbox_shell"
    ASYNC_JOB = "async_job"
