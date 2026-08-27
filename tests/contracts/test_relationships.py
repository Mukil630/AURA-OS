"""Integration unit tests verifying end-to-end entity relationships across all contracts."""
from app.core.contracts import (
    AgentContract,
    ExecutionEventContract,
    MemoryContract,
    TaskContract,
    TaskStepContract,
    ToolContract,
    ToolExecutionRequest,
    ToolExecutionResult,
    VerificationResultContract,
    VerificationSpecContract,
    WorkflowContract,
)
from app.core.enums import (
    AgentType,
    ChannelType,
    EventType,
    ExecutionMode,
    MemoryType,
    RiskTier,
    StepStatus,
    TaskStatus,
    ToolCategory,
    VerificationMethod,
    VerificationStatus,
    WorkflowStatus,
)
from app.core.models import (
    ExecutionPlan,
    NormalizedAgentResponse,
    NormalizedUserRequest,
)


def test_complete_relational_lifecycle():
    # 1. User Voice Input
    user_req = NormalizedUserRequest(
        user_id="mukil_001",
        channel=ChannelType.VOICE,
        raw_input="Check GitHub CI and report",
    )

    # 2. Master Agent creates Task
    task = TaskContract(
        user_id=user_req.user_id,
        channel=user_req.channel,
        raw_input=user_req.raw_input,
        status=TaskStatus.PLANNING,
    )

    # 3. Agent & Tool definitions
    agent = AgentContract(
        agent_id="github_agent",
        name="GitHub Agent",
        agent_type=AgentType.CODING,
        description="GitHub specialist",
        allowed_tools=["github.check_ci"],
    )

    tool = ToolContract(
        tool_id="github.check_ci",
        name="Check CI",
        category=ToolCategory.CODING,
        description="Fetch CI status",
        risk_tier=RiskTier.TIER_1_LOW,
        verification_method=VerificationMethod.RETURN_CODE_CHECK,
    )

    # 4. Planner decomposes to Workflow & Steps
    step = TaskStepContract(
        workflow_id="",  # will link to workflow
        step_index=0,
        name="check_ci_step",
        agent_type=agent.agent_type,
        tool_name=tool.tool_id,
        input_payload={"repo": "Mukil630/AURA-OS"},
        risk_tier=tool.risk_tier,
    )

    workflow = WorkflowContract(
        task_id=task.task_id,
        name="ci_verification_wf",
        execution_mode=ExecutionMode.SEQUENTIAL,
        steps=[step],
        status=WorkflowStatus.RUNNING,
    )
    # Bind workflow_id
    step.workflow_id = workflow.workflow_id
    task.workflow_id = workflow.workflow_id

    # 5. Tool Execution
    exec_req = ToolExecutionRequest(
        tool_id=tool.tool_id,
        step_id=step.step_id,
        parameters=step.input_payload,
    )
    exec_res = ToolExecutionResult(
        execution_id=exec_req.execution_id,
        tool_id=tool.tool_id,
        success=True,
        data={"build_status": "passed", "commit": "f393550"},
    )
    step.status = StepStatus.COMPLETED
    step.output_payload = exec_res.data

    # 6. Verification
    vspec = VerificationSpecContract(
        method=VerificationMethod.RETURN_CODE_CHECK,
        target_resource="github:runs",
        expected_condition={"build_status": "passed"},
    )
    vres = VerificationResultContract(
        spec_id=vspec.spec_id,
        step_id=step.step_id,
        status=VerificationStatus.VERIFIED,
        details="GitHub API returned status 'passed'.",
        evidence=exec_res.data,
    )

    # 7. Memory & Event Logging
    mem = MemoryContract(
        memory_type=MemoryType.EPISODIC_TASK,
        user_id=task.user_id,
        source_task_id=task.task_id,
        content="CI check on Mukil630/AURA-OS passed for commit f393550.",
    )

    evt = ExecutionEventContract(
        trace_id=f"tr_{task.task_id}",
        task_id=task.task_id,
        workflow_id=workflow.workflow_id,
        step_id=step.step_id,
        event_type=EventType.TASK_COMPLETED,
        source_component="MasterAgent",
        message="Task completed successfully.",
    )

    # 8. Complete Task & Response
    task.status = TaskStatus.COMPLETED
    task.result_summary = "All CI checks on Mukil630/AURA-OS passed."
    workflow.status = WorkflowStatus.COMPLETED

    response = NormalizedAgentResponse(
        request_id=user_req.request_id,
        task_id=task.task_id,
        channel=user_req.channel,
        status=task.status,
        text_content=task.result_summary,
        voice_content="CI checks on AURA-OS passed successfully.",
    )

    # Relational Integrity Assertions
    assert task.workflow_id == workflow.workflow_id
    assert workflow.steps[0].workflow_id == workflow.workflow_id
    assert exec_res.execution_id == exec_req.execution_id
    assert vres.step_id == step.step_id
    assert mem.source_task_id == task.task_id
    assert evt.task_id == task.task_id
    assert response.task_id == task.task_id
    assert response.request_id == user_req.request_id
