"""Unit tests for Workflow and WorkflowState Contracts."""
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import (
    WorkflowContract,
    WorkflowStateContract,
)
from app.core.enums import AgentType, ExecutionMode, WorkflowStatus


def test_workflow_contract_creation():
    step1 = TaskStepContract(
        workflow_id="wf_test_1",
        step_index=0,
        name="step_one",
        agent_type=AgentType.RESEARCH,
        tool_name="web_search",
    )
    workflow = WorkflowContract(
        task_id="task_123",
        name="research_pipeline",
        execution_mode=ExecutionMode.SEQUENTIAL,
        steps=[step1],
    )
    assert workflow.workflow_id.startswith("wf_")
    assert workflow.task_id == "task_123"
    assert workflow.status == WorkflowStatus.PENDING
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "step_one"


def test_workflow_state_checkpoint_contract():
    state = WorkflowStateContract(
        workflow_id="wf_test_1",
        status=WorkflowStatus.RUNNING,
        active_step_id="step_123",
        completed_step_ids=["step_000"],
        step_outputs={"step_000": {"status": "ok"}},
        accumulated_context={"repo": "AURA-OS"},
    )
    assert state.workflow_id == "wf_test_1"
    assert state.status == WorkflowStatus.RUNNING
    assert state.active_step_id == "step_123"
    assert "step_000" in state.completed_step_ids
    assert state.accumulated_context["repo"] == "AURA-OS"
