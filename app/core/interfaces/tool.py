"""Abstract Interface definitions for Tools, Tool Registry, and Tool Executors."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.contracts.tool import (
    ToolContract,
    ToolExecutionRequest,
    ToolExecutionResult,
)


class ITool(ABC):
    """
    Abstract interface for discrete executable tools.
    Every tool provides machine-readable schemas and an asynchronous execute method.
    """
    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Unique tool identifier."""
        pass

    @abstractmethod
    def get_contract(self) -> ToolContract:
        """Return full definition and input/output schemas."""
        pass

    @abstractmethod
    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Execute the tool action with validated parameters."""
        pass


class IToolRegistry(ABC):
    """
    Central registry interface for managing and discovering available tools.
    """
    @abstractmethod
    def register_tool(self, tool: ITool) -> None:
        """Register a tool instance into the registry."""
        pass

    @abstractmethod
    def get_tool(self, tool_id: str) -> Optional[ITool]:
        """Retrieve a registered tool by its ID."""
        pass

    @abstractmethod
    def list_tools(self, category: Optional[str] = None) -> List[ToolContract]:
        """List all registered tools, optionally filtered by category."""
        pass

    @abstractmethod
    def validate_parameters(self, tool_id: str, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters against the tool's input_schema."""
        pass


class IToolExecutor(ABC):
    """
    Interface for executing tools with timeouts, retries, sandbox enforcement, and metrics.
    """
    @abstractmethod
    async def run(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Run tool execution request with observability and safety sandboxing."""
        pass
