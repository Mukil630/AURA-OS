"""Version 1 Data Contracts for Tools, Execution Requests, and Execution Results."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    RiskTier,
    ToolCategory,
    ToolExecutionMode,
    VerificationMethod,
)


class ToolContract(VersionedContractBase):
    """
    Contract defining a discrete, executable Tool in the Tool Registry.
    A Tool is the actual executable action invoked by agents.
    """
    tool_id: str = Field(..., description="Unique tool identifier (e.g. 'github.list_failed_workflows').")
    name: str = Field(..., description="Display name of the tool.")
    category: ToolCategory = Field(..., description="Functional category of the tool.")
    description: str = Field(..., description="Clear explanation of the tool's behavior and side-effects.")
    version: str = Field(default="1.0.0", description="Semantic version of the tool definition.")
    execution_mode: ToolExecutionMode = Field(default=ToolExecutionMode.LOCAL, description="Execution transport mode.")
    connector_id: Optional[str] = Field(default=None, description="Associated connector ID if backed by external system.")
    risk_tier: RiskTier = Field(default=RiskTier.TIER_1_LOW, description="Safety and risk tier.")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema defining required and optional arguments.")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema defining structured return output.")
    timeout_seconds: int = Field(default=30, gt=0, description="Default execution timeout.")
    is_idempotent: bool = Field(default=True, description="True if calling repeatedly with same inputs produces same state.")
    requires_approval: bool = Field(default=False, description="Whether execution mandates human approval.")
    verification_method: VerificationMethod = Field(
        default=VerificationMethod.RETURN_CODE_CHECK,
        description="Standard verification method for this tool."
    )


class ToolExecutionRequest(VersionedContractBase):
    """Payload contract for invoking a tool through the ToolExecutor."""
    execution_id: str = Field(
        default_factory=lambda: f"exec_{uuid4().hex[:12]}",
        description="Unique identifier for this specific tool execution instance."
    )
    tool_id: str = Field(..., description="ID of the tool to execute.")
    step_id: Optional[str] = Field(default=None, description="Optional TaskStep ID triggering this execution.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Argument parameters conforming to tool input_schema.")
    timeout_seconds: Optional[int] = Field(default=None, description="Override timeout for this execution.")
    idempotency_key: Optional[str] = Field(default=None, description="Unique key to prevent duplicate execution side-effects.")


class ToolExecutionResult(VersionedContractBase):
    """Output contract produced by ToolExecutor upon action completion."""
    execution_id: str = Field(..., description="Execution ID corresponding to the request.")
    tool_id: str = Field(..., description="Tool ID executed.")
    success: bool = Field(..., description="True if execution succeeded without exception.")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Structured output payload from tool.")
    raw_output: Optional[str] = Field(default=None, description="Raw stdout or string output.")
    error_message: Optional[str] = Field(default=None, description="Error message if execution failed.")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Execution duration in milliseconds.")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of execution completion."
    )
