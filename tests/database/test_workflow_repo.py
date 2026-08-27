"""Database integration tests for WorkflowRepository."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import (
    WorkflowContract,
    WorkflowStateContract,
)
from app.core.enums import (
    AgentType,
    ExecutionMode,
    StepStatus,
    WorkflowStatus,
)
from app.database.repositories.workflow_repo import WorkflowRepository


@pytest.mark.anyio
async def test_workflow_and_steps_persistence(test_db_session: AsyncSession):
    repo = WorkflowRepository(test_db_session)

    # 1. Create Workflow with embedded Steps
    step1 = TaskStepContract(
        workflow_id="wf_001",
        step_index=0,
        name="fetch_logs",
        agent_type=AgentType.CODING,
        tool_name="github.get_logs",
        input_payload={"run_id": 123},
    )
    step2 = TaskStepContract(
        workflow_id="wf_001",
        step_index=1,
        name="fix_error",
        agent_type=AgentType.CODING,
        tool_name="github.apply_fix",
        dependencies=[step1.step_id],
    )

    wf = WorkflowContract(
        workflow_id="wf_001",
        task_id="task_001",
        name="ci_fix_pipeline",
        execution_mode=ExecutionMode.SEQUENTIAL,
        steps=[step1, step2],
        context_variables={"repository": "Mukil630/AURA-OS"},
    )

    saved_wf = await repo.create_workflow_with_steps(wf)
    assert saved_wf.workflow_id == "wf_001"
    assert len(saved_wf.steps) == 2
    assert saved_wf.steps[0].name == "fetch_logs"
    assert saved_wf.steps[1].name == "fix_error"

    # 2. Get Workflow by ID and Task ID
    fetched_wf = await repo.get_workflow("wf_001")
    assert fetched_wf is not None
    assert len(fetched_wf.steps) == 2
    assert fetched_wf.context_variables["repository"] == "Mukil630/AURA-OS"

    fetched_by_task = await repo.get_workflow_by_task_id("task_001")
    assert fetched_by_task is not None
    assert fetched_by_task.workflow_id == "wf_001"

    # 3. Update Step Status
    updated_step = await repo.update_step_status(
        step_id=step1.step_id,
        status=StepStatus.COMPLETED,
        output_payload={"log_content": "SyntaxError on line 12"},
    )
    assert updated_step is not None
    assert updated_step.status == StepStatus.COMPLETED
    assert updated_step.output_payload["log_content"] == "SyntaxError on line 12"

    # 4. Record and Retrieve Durable Checkpoint
    checkpoint = WorkflowStateContract(
        workflow_id="wf_001",
        status=WorkflowStatus.RUNNING,
        active_step_id=step2.step_id,
        completed_step_ids=[step1.step_id],
        step_outputs={step1.step_id: {"log_content": "SyntaxError on line 12"}},
        accumulated_context={"repo": "Mukil630/AURA-OS", "error_type": "SyntaxError"},
    )
    saved_cp = await repo.record_checkpoint(checkpoint)
    assert saved_cp.workflow_id == "wf_001"

    latest_cp = await repo.get_latest_checkpoint("wf_001")
    assert latest_cp is not None
    assert latest_cp.active_step_id == step2.step_id
    assert step1.step_id in latest_cp.completed_step_ids
    assert latest_cp.accumulated_context["error_type"] == "SyntaxError"
