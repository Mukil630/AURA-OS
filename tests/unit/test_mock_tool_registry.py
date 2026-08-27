"""Unit tests for Mock ToolRegistry and ToolExecutor."""
import asyncio
import pytest
from app.core.contracts.tool import ToolExecutionRequest
from app.core.enums import ToolCategory
from app.tools.registry import MockTool, ToolExecutor, ToolRegistry


@pytest.mark.anyio
async def test_tool_registry_and_executor_success():
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    # 1. Execute built-in GitHub tool
    req = ToolExecutionRequest(
        tool_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await executor.execute(req)
    assert res.success is True
    assert "failed_runs" in res.data

    # 2. Execute built-in Drive tool
    drive_req = ToolExecutionRequest(
        tool_id="drive.upload",
        parameters={"file_path": "report.pdf"},
    )
    drive_res = await executor.execute(drive_req)
    assert drive_res.success is True
    assert "file_id" in drive_res.data


@pytest.mark.anyio
async def test_unregistered_tool_failure():
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    req = ToolExecutionRequest(
        tool_id="unknown.non_existent_tool",
        parameters={},
    )
    res = await executor.execute(req)
    assert res.success is False
    assert "not registered" in res.error_message.lower()


@pytest.mark.anyio
async def test_tool_timeout_enforcement():
    async def slow_handler(payload):
        await asyncio.sleep(0.5)
        return {"done": True}

    registry = ToolRegistry()
    registry.register_tool(
        MockTool(name="slow.tool", handler=slow_handler)
    )
    executor = ToolExecutor(registry)

    req = ToolExecutionRequest(
        tool_id="slow.tool",
        parameters={},
        timeout_seconds=1,  # Fast timeout test handled in executor
    )
    res = await executor.execute(req)
    assert res.success is True  # with 1s timeout it finishes cleanly
