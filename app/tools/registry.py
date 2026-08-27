"""Tool Registry and Execution Subsystem with Mockable Stub Handlers."""
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from app.core.contracts.tool import (
    ToolContract,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from app.core.enums import RiskTier, ToolCategory, ToolExecutionMode
from app.core.interfaces.tool import ITool, IToolExecutor, IToolRegistry


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""
    pass


class MockTool(ITool):
    """Generic configurable tool implementation for local runtime and testing."""

    def __init__(
        self,
        name: str,
        category: ToolCategory = ToolCategory.SYSTEM,
        description: str = "",
        risk_tier: RiskTier = RiskTier.TIER_1_LOW,
        handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self._name = name
        self._category = category
        self._description = description
        self._risk_tier = risk_tier
        self._handler = handler

    @property
    def tool_id(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> ToolCategory:
        return self._category

    def get_contract(self) -> ToolContract:
        return ToolContract(
            tool_id=self.tool_id,
            name=self.name,
            category=self.category,
            description=self._description or f"Tool handler for {self.name}",
            execution_mode=ToolExecutionMode.LOCAL,
            risk_tier=self._risk_tier,
        )

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        payload = request.parameters
        t0 = time.perf_counter()

        try:
            if self._handler:
                if asyncio.iscoroutinefunction(self._handler):
                    res = await self._handler(payload)
                else:
                    res = self._handler(payload)
                output = res if isinstance(res, dict) else {"result": res}
            else:
                output = {
                    "status": "success",
                    "tool": self.name,
                    "received_payload": payload,
                    "message": f"Tool '{self.name}' executed successfully.",
                }
            latency = (time.perf_counter() - t0) * 1000.0
            return ToolExecutionResult(
                execution_id=request.execution_id,
                tool_id=self.name,
                success=True,
                data=output,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000.0
            return ToolExecutionResult(
                execution_id=request.execution_id,
                tool_id=self.name,
                success=False,
                error_message=str(exc),
                latency_ms=latency,
            )


class ToolRegistry(IToolRegistry):
    """In-memory tool registry with default handlers for all specialist capabilities."""

    def __init__(self):
        self._tools: Dict[str, ITool] = {}
        self._register_default_tools()

    def register_tool(self, tool: ITool) -> None:
        self._tools[tool.tool_id] = tool

    def get_tool(self, tool_id: str) -> Optional[ITool]:
        return self._tools.get(tool_id)

    def list_tools(self, category: Optional[str] = None) -> List[ToolContract]:
        contracts = [t.get_contract() for t in self._tools.values()]
        if category:
            return [c for c in contracts if c.category == category or (hasattr(c.category, "value") and c.category.value == category)]
        return contracts

    def validate_parameters(self, tool_id: str, parameters: Dict[str, Any]) -> bool:
        tool = self.get_tool(tool_id)
        return tool is not None

    def _register_default_tools(self) -> None:
        """Register built-in mock handlers for all system capabilities."""
        # 1. GitHub Tools
        self.register_tool(
            MockTool(
                name="github.list_failed_workflows",
                category=ToolCategory.CODING,
                description="List failed GitHub workflow runs for a repository",
                handler=lambda p: {"failed_runs": [{"id": 101, "name": "CI / build", "status": "failed", "conclusion": "failure"}]},
            )
        )
        self.register_tool(
            MockTool(
                name="github.get_logs",
                category=ToolCategory.CODING,
                description="Fetch logs for a failed run",
                handler=lambda p: {"run_id": 101, "error_trace": "AssertionError: test_login failed at line 42", "log_snippet": "FAILED tests/test_auth.py::test_login"},
            )
        )
        self.register_tool(
            MockTool(
                name="coding.analyze_patch",
                category=ToolCategory.CODING,
                description="Analyze error log to formulate patch",
                handler=lambda p: {"patch_strategy": "Fix token expiration boundary condition in auth.py", "files_to_modify": ["auth.py"]},
            )
        )
        self.register_tool(
            MockTool(
                name="coding.apply_fix",
                category=ToolCategory.CODING,
                risk_tier=RiskTier.TIER_2_MEDIUM,
                description="Apply code patch",
                handler=lambda p: {"modified_files": ["auth.py"], "diff": "+ if exp > now:", "status": "patch_applied"},
            )
        )
        self.register_tool(
            MockTool(
                name="coding.run_tests",
                category=ToolCategory.CODING,
                description="Run pytest suite",
                handler=lambda p: {"tests_passed": 52, "tests_failed": 0, "status": "all_green"},
            )
        )

        # 2. Cloud & Drive Tools
        self.register_tool(
            MockTool(
                name="filesystem.check_file",
                category=ToolCategory.CLOUD_FILE,
                description="Check if file exists on disk",
                handler=lambda p: {"exists": True, "file_path": p.get("file_path", "file.pdf"), "size_bytes": 1048576},
            )
        )
        self.register_tool(
            MockTool(
                name="drive.upload",
                category=ToolCategory.CLOUD_FILE,
                risk_tier=RiskTier.TIER_2_MEDIUM,
                description="Upload file to Google Drive",
                handler=lambda p: {"file_id": f"drive_{uuid4().hex[:8]}", "drive_folder": "JARVIS Master Vault", "status": "uploaded"},
            )
        )
        self.register_tool(
            MockTool(
                name="drive.search",
                category=ToolCategory.CLOUD_FILE,
                description="Search file in Google Drive",
                handler=lambda p: {"found": True, "file_id": f"drive_{uuid4().hex[:8]}", "file_name": p.get("file_name", "file.pdf")},
            )
        )

        # 3. Communication Tools
        self.register_tool(
            MockTool(
                name="telegram.send_message",
                category=ToolCategory.COMMUNICATION,
                description="Send message via Telegram",
                handler=lambda p: {"message_id": 9901, "delivered": True, "chat": p.get("recipient", "default")},
            )
        )
        self.register_tool(
            MockTool(
                name="scheduler.create_timer",
                category=ToolCategory.SYSTEM,
                description="Create timer reminder",
                handler=lambda p: {"timer_id": f"tmr_{uuid4().hex[:6]}", "scheduled_for": p.get("time", "09:00"), "status": "active"},
            )
        )

        # 4. PC & Hardware Telemetry Tools (Read-Only)
        self.register_tool(
            MockTool(
                name="pc.system_info",
                category=ToolCategory.SYSTEM,
                description="Query PC hardware telemetry",
                handler=lambda p: {"battery_percent": 88, "plugged_in": True, "cpu_usage": 12.4, "ram_free_gb": 18.2},
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_health_summary",
                category=ToolCategory.SYSTEM,
                description="Query consolidated PC health and sensor telemetry",
                handler=lambda p: {
                    "hostname": "MUKIL-WORKSTATION",
                    "cpu_utilization": 18.4,
                    "ram_utilization": 37.5,
                    "disk_utilization": 34.0,
                    "temperature_celsius": 46.5,
                    "overall_status": "healthy",
                },
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_cpu",
                category=ToolCategory.SYSTEM,
                description="Query CPU telemetry",
                handler=lambda p: {"logical_cores": 16, "utilization_percent": 18.4},
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_memory",
                category=ToolCategory.SYSTEM,
                description="Query RAM telemetry",
                handler=lambda p: {"total_bytes": 34359738368, "used_bytes": 12884901888, "utilization_percent": 37.5},
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_disk",
                category=ToolCategory.SYSTEM,
                description="Query storage telemetry",
                handler=lambda p: {"drive_letter": "C:", "utilization_percent": 34.0, "free_gb": 660},
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_network",
                category=ToolCategory.SYSTEM,
                description="Query network throughput telemetry",
                handler=lambda p: {"bytes_sent": 1420500120, "bytes_recv": 8940300240, "interface_count": 2},
            )
        )
        self.register_tool(
            MockTool(
                name="pc.get_temperature",
                category=ToolCategory.SYSTEM,
                description="Query hardware thermal sensors",
                handler=lambda p: {"sensor_available": True, "temperature_celsius": 46.5, "thermal_status": "normal"},
            )
        )

        # 5. Research Tools
        self.register_tool(
            MockTool(
                name="web.search",
                category=ToolCategory.RESEARCH,
                description="Search web sources",
                handler=lambda p: {"results": [{"title": "Documentation", "snippet": "Architecture and usage guide."}]},
            )
        )
        self.register_tool(
            MockTool(
                name="research.synthesize",
                category=ToolCategory.RESEARCH,
                description="Synthesize research results",
                handler=lambda p: {"summary": "Comprehensive overview based on verified sources."},
            )
        )
        self.register_tool(
            MockTool(
                name="system.general_action",
                category=ToolCategory.SYSTEM,
                description="General action executor",
                handler=lambda p: {"status": "completed", "action": p.get("instruction", "general")},
            )
        )


class ToolExecutor(IToolExecutor):
    """Executes tools with timeout enforcement and error interception."""

    def __init__(self, registry: Optional[IToolRegistry] = None):
        self._registry = registry or ToolRegistry()

    async def run(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Implements IToolExecutor.run."""
        return await self.execute(request)

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        tool = self._registry.get_tool(request.tool_id)
        if not tool:
            return ToolExecutionResult(
                execution_id=request.execution_id,
                tool_id=request.tool_id,
                success=False,
                error_message=f"Tool '{request.tool_id}' is not registered in ToolRegistry.",
            )

        timeout = float(request.timeout_seconds) if request.timeout_seconds else 30.0
        try:
            output = await asyncio.wait_for(
                tool.execute(request),
                timeout=timeout,
            )
            return output
        except asyncio.TimeoutError:
            return ToolExecutionResult(
                execution_id=request.execution_id,
                tool_id=request.tool_id,
                success=False,
                error_message=f"Tool '{request.tool_id}' timed out after {timeout}s.",
            )
        except Exception as exc:
            return ToolExecutionResult(
                execution_id=request.execution_id,
                tool_id=request.tool_id,
                success=False,
                error_message=str(exc),
            )
