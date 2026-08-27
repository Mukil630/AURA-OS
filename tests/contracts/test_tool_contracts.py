"""Unit tests for Tool Contracts."""
from app.core.contracts.tool import (
    ToolContract,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from app.core.enums import RiskTier, ToolCategory, ToolExecutionMode, VerificationMethod


def test_tool_contract_creation():
    tool = ToolContract(
        tool_id="drive.upload_file",
        name="Upload File to Google Drive",
        category=ToolCategory.CLOUD_FILE,
        description="Uploads a local artifact to the target Google Drive vault folder.",
        execution_mode=ToolExecutionMode.REST_API,
        connector_id="connector_google_drive",
        risk_tier=RiskTier.TIER_2_MEDIUM,
        input_schema={"type": "object", "properties": {"local_path": {"type": "string"}}, "required": ["local_path"]},
        output_schema={"type": "object", "properties": {"file_id": {"type": "string"}, "drive_url": {"type": "string"}}},
        verification_method=VerificationMethod.API_LOOKUP,
    )
    assert tool.tool_id == "drive.upload_file"
    assert tool.category == ToolCategory.CLOUD_FILE
    assert tool.risk_tier == RiskTier.TIER_2_MEDIUM
    assert tool.verification_method == VerificationMethod.API_LOOKUP


def test_tool_execution_request_and_result():
    req = ToolExecutionRequest(
        tool_id="drive.upload_file",
        step_id="step_123",
        parameters={"local_path": "C:/reports/summary.pdf"},
    )
    assert req.execution_id.startswith("exec_")
    assert req.tool_id == "drive.upload_file"
    assert req.parameters["local_path"] == "C:/reports/summary.pdf"

    res = ToolExecutionResult(
        execution_id=req.execution_id,
        tool_id=req.tool_id,
        success=True,
        data={"file_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ", "size_bytes": 10240},
        latency_ms=145.2,
    )
    assert res.success is True
    assert res.data["file_id"] == "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ"
    assert res.latency_ms == 145.2
