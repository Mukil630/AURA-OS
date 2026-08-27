"""API integration tests for Verification and Self-Healing endpoints."""
import pytest
from httpx import AsyncClient

from app.core.enums import FailureCategory, RecoveryStrategy, VerificationStatus


@pytest.mark.anyio
async def test_verification_api_verify_step_success(client: AsyncClient):
    payload = {
        "step": {
            "workflow_id": "wf_test",
            "step_index": 0,
            "name": "run_tests",
            "agent_type": "coding",
            "tool_name": "coding.run_tests",
        },
        "execution_result": {
            "execution_id": "exec_test",
            "tool_id": "coding.run_tests",
            "success": True,
            "data": {"tests_passed": 12, "tests_failed": 0, "status": "all_green"},
        },
    }
    response = await client.post("/api/v1/verification/verify-step", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == VerificationStatus.VERIFIED.value
    assert "passed verification" in data["details"]


@pytest.mark.anyio
async def test_verification_api_verify_step_mismatch_failure(client: AsyncClient):
    payload = {
        "step": {
            "workflow_id": "wf_test",
            "step_index": 0,
            "name": "run_tests",
            "agent_type": "coding",
            "tool_name": "coding.run_tests",
        },
        "execution_result": {
            "execution_id": "exec_test",
            "tool_id": "coding.run_tests",
            "success": True,
            "data": {"tests_passed": 10, "tests_failed": 2, "status": "failed"},
        },
    }
    response = await client.post("/api/v1/verification/verify-step", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == VerificationStatus.FAILED.value
    assert "reported 2 failures" in data["details"]


@pytest.mark.anyio
async def test_recovery_api_classify_transient_retry(client: AsyncClient):
    payload = {
        "error_message": "429 Too Many Requests: Rate limit exceeded (connection lock)",
    }
    response = await client.post("/api/v1/recovery/classify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["failure_category"] == FailureCategory.TRANSIENT.value
    assert data["recommended_strategy"] == RecoveryStrategy.RETRY.value
    assert data["is_retryable"] is True
