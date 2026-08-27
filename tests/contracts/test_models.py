"""Unit tests for Normalized Request, Response, and Plan Models."""
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import AgentType, ChannelType, ExecutionMode, TaskStatus
from app.core.models.plan import ExecutionPlan, StepDependency
from app.core.models.request import NormalizedUserRequest
from app.core.models.response import NormalizedAgentResponse


def test_normalized_user_request():
    req = NormalizedUserRequest(
        user_id="mukil_001",
        channel=ChannelType.VOICE,
        raw_input="Check my GitHub CI and fix errors",
        language="en-ta",
    )
    assert req.request_id.startswith("req_")
    assert req.channel == ChannelType.VOICE
    assert req.language == "en-ta"


def test_normalized_agent_response():
    resp = NormalizedAgentResponse(
        request_id="req_123",
        task_id="task_456",
        channel=ChannelType.TELEGRAM,
        status=TaskStatus.COMPLETED,
        text_content="✅ All GitHub CI builds verified and passing.",
        voice_content="CI builds checked. All workflows passing on main branch.",
    )
    assert resp.response_id.startswith("resp_")
    assert resp.status == TaskStatus.COMPLETED
    assert resp.voice_content is not None


def test_execution_plan_and_dependencies():
    step1 = TaskStepContract(
        workflow_id="wf_1",
        step_index=0,
        name="list_runs",
        agent_type=AgentType.CODING,
        tool_name="github.list_runs",
    )
    step2 = TaskStepContract(
        workflow_id="wf_1",
        step_index=1,
        name="fix_error",
        agent_type=AgentType.CODING,
        tool_name="github.apply_fix",
    )
    dep = StepDependency(parent_step_id=step1.step_id, child_step_id=step2.step_id)
    plan = ExecutionPlan(
        task_id="task_123",
        goal="Fix CI",
        execution_mode=ExecutionMode.SEQUENTIAL,
        steps=[step1, step2],
        dependencies=[dep],
    )
    assert plan.plan_id.startswith("plan_")
    assert len(plan.steps) == 2
    assert len(plan.dependencies) == 1
    assert plan.dependencies[0].parent_step_id == step1.step_id
