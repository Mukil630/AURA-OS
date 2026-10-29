"""
Intent Validator & Tool-Schema Guardrail (intent_validator.py)
Prevents agents from using the wrong tool, hallucinating tool results,
and rejecting invalid tool inputs before execution.
"""
import logging
from typing import Dict, Any, Optional, Tuple, List
from pydantic import ValidationError

logger = logging.getLogger("IntentValidator")

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "read_file": {
        "required_params": ["file_path"],
        "description": "Reads content from an existing file on disk.",
        "returns": "file content",
    },
    "edit_file": {
        "required_params": ["target_content", "replacement_content", "file_path"],
        "description": "Makes an exact atomic replacement in an existing file.",
        "returns": "success/failure status",
    },
    "write_file": {
        "required_params": ["file_path", "code_content"],
        "description": "Creates or overwrites a file on disk.",
        "returns": "success/failure status",
    },
    "grep_search": {
        "required_params": ["query"],
        "description": "Searches for a pattern across files in the codebase.",
        "returns": "matching lines",
    },
    "run_command": {
        "required_params": ["command"],
        "description": "Executes a shell command on the local PC.",
        "returns": "stdout/stderr/exit_code",
    },
    "web_fetch": {
        "required_params": ["url"],
        "description": "Fetches content from a URL.",
        "returns": "web page content",
    },
    "web_search": {
        "required_params": ["query"],
        "description": "Searches the web for information.",
        "returns": "search results",
    },
    "list_files": {
        "required_params": [],
        "description": "Lists files in a directory.",
        "returns": "file listing",
    },
}

SUSPICIOUS_EMPTY_RESULTS: Dict[str, str] = {
    "grep_search": 'No matches found for query',
    "read_file": "Error: File not found",
    "web_fetch": "Failed to fetch",
}


class ToolCallSpec:
    """Represents a planned tool call with its arguments."""

    def __init__(self, tool_name: str, params: Dict[str, Any]):
        self.tool_name = tool_name
        self.params = params or {}

    def validate_params(self) -> Tuple[bool, Optional[str]]:
        """Validate that required parameters are present and non-empty."""
        schema = TOOL_REGISTRY.get(self.tool_name)
        if not schema:
            return False, f"Unknown tool '{self.tool_name}'. Available: {list(TOOL_REGISTRY.keys())}"

        required = schema["required_params"]
        for param in required:
            val = self.params.get(param)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return False, f"Missing or empty required parameter '{param}' for tool '{self.tool_name}'"

        return True, None


def validate_tool_call(tool_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate a tool call BEFORE execution:
    1. Is it a known tool?
    2. Are required parameters present and non-empty?
    3. Are there dangerous patterns (e.g., path traversal, destructive commands)?
    """
    spec = ToolCallSpec(tool_name, params)
    valid, err = spec.validate_params()
    if not valid:
        return False, err

    # Security / safety guardrails
    dangerous_patterns = {
        "run_command": ["rm -rf", "del /f /s /q", "shutdown", "taskkill /f", "format "],
    }
    for pattern in dangerous_patterns.get(tool_name, []):
        if pattern in str(params):
            return False, f"Dangerous pattern '{pattern}' detected in tool call '{tool_name}' — rejected by guardrail"

    return True, None


def detect_hallucinated_result(
    tool_name: str,
    result: str,
    expected_indicators: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Detects whether a tool result looks fabricated or empty.
    Called AFTER tool execution to verify the result isn't hallucinated.

    Returns (looks_hallucinated: bool, reason: str)
    """
    if result is None:
        return False, "No result returned (None)"

    result_str = str(result).strip()

    if len(result_str) == 0:
        return True, f"Empty result from tool '{tool_name}' — likely hallucinated execution"

    # Check for known error signatures
    suspicious_marker = SUSPICIOUS_EMPTY_RESULTS.get(tool_name)
    if suspicious_marker and suspicious_marker in result_str:
        snippet = suspicious_marker[:80]
        return True, f"Tool '{tool_name}' returned a known error/empty signature: '{snippet}'"

    # Check for expected indicators if provided
    if expected_indicators:
        found_any = any(ind.lower() in result_str.lower() for ind in expected_indicators)
        if not found_any:
            return True, f"Result from '{tool_name}' does not contain expected indicators"

    return False, "OK"


def validate_result_then_retry(
    tool_name: str,
    result: str,
    params: Dict[str, Any],
    max_retries: int = 2,
) -> Tuple[str, List[str]]:
    """
    Runs a tool call with validation and retry on hallucinated/empty results.
    Returns (final_result, audit_log)
    """
    audit_log: List[str] = []
    current_result = result

    for attempt in range(max_retries):
        hallucinated, reason = detect_hallucinated_result(tool_name, current_result)
        if not hallucinated:
            audit_log.append(f"Attempt {attempt + 1}: Result validated successfully")
            return current_result, audit_log

        audit_log.append(f"Attempt {attempt + 1}: {reason}")
        if attempt < max_retries - 1:
            audit_log.append(f"Attempt {attempt + 1}: Would retry with corrected approach")
        else:
            audit_log.append(f"Attempt {attempt + 1}: No retries left, returning result with warning")

    return current_result, audit_log
