"""Unit tests for TaskStep Contracts."""
import pytest
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import AgentType, ApprovalState, RiskTier, StepStatus


def test_task_step_contract_creation():
    step = TaskStepContract(
        workflow_id="wf_001",
        step_index=0,
        name="fetch_failed_runs",
        agent_type=AgentType.CODING,
        tool_name="github.list_failed_workflows",
        input_payload={"repository": "Mukil630/AURA-OS"},
        risk_tier=RiskTier.TIER_1_LOW,
    )
    assert step.step_id.startswith("step_")
    assert step.workflow_id == "wf_001"
    assert step.name == "fetch_failed_runs"
    assert step.agent_type == AgentType.CODING
    assert step.status == StepStatus.PENDING
    assert step.approval_state == ApprovalState.NOT_REQUIRED
    assert step.retry_count == 0
    assert step.max_retries == 2


def test_task_step_with_dependencies_and_approval():
    step = TaskStepContract(
        workflow_id="wf_001",
        step_index=1,
        name="delete_remote_branch",
        agent_type=AgentType.CODING,
        tool_name="github.delete_branch",
        input_payload={"branch": "old-feature"},
        risk_tier=RiskTier.TIER_3_HIGH,
        requires_approval=True,
        approval_state=ApprovalState.PENDING,
        dependencies=["step_001"],
    )
    assert step.requires_approval is True
    assert step.approval_state == ApprovalState.PENDING
    assert "step_001" in step.dependencies
