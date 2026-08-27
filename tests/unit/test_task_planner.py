"""Unit tests for TaskPlanner decomposition engine."""
from app.agents.master.master_agent import MasterAgent
from app.core.enums import AgentType, ChannelType, RiskTier, WorkflowStatus
from app.core.planner import TaskPlanner


def test_plan_reminder_schedule_dag():
    agent = MasterAgent()
    planner = TaskPlanner()

    context = agent.understand("Tomorrow 9 AM remind me to study Java", channel=ChannelType.VOICE)
    plan, workflow = planner.plan(context)

    assert plan.task_id == context.task_id
    assert len(plan.steps) == 1
    assert plan.steps[0].agent_type == AgentType.COMMUNICATION
    assert plan.steps[0].tool_name == "scheduler.create_timer"
    assert plan.steps[0].input_payload["time"] == "09:00"
    assert workflow.status == WorkflowStatus.PENDING


def test_plan_coding_ci_dag_decomposition():
    agent = MasterAgent()
    planner = TaskPlanner()

    context = agent.understand("Check my GitHub CI builds on Mukil630/AURA-OS and fix simple errors")
    plan, workflow = planner.plan(context)

    assert len(plan.steps) == 5
    assert [s.agent_type for s in plan.steps] == [AgentType.CODING] * 5

    step_names = [s.name for s in plan.steps]
    assert step_names == [
        "read_ci_status",
        "inspect_error_logs",
        "determine_patch_strategy",
        "apply_code_fix",
        "run_verification_tests",
    ]

    # Verify DAG dependency chain
    s1, s2, s3, s4, s5 = plan.steps
    assert s2.dependencies == [s1.step_id]
    assert s3.dependencies == [s2.step_id]
    assert s4.dependencies == [s3.step_id]
    assert s5.dependencies == [s4.step_id]

    assert s4.risk_tier == RiskTier.TIER_2_MEDIUM
    assert plan.max_risk_tier == RiskTier.TIER_2_MEDIUM
    assert len(plan.dependencies) == 4


def test_plan_file_sync_dag():
    agent = MasterAgent()
    planner = TaskPlanner()

    context = agent.understand("Upload invoice_2026.pdf to Google Drive vault")
    plan, workflow = planner.plan(context)

    assert len(plan.steps) == 3
    assert plan.steps[0].name == "verify_local_artifact"
    assert plan.steps[1].name == "upload_to_drive_vault"
    assert plan.steps[2].name == "verify_drive_upload"
    assert plan.steps[1].dependencies == [plan.steps[0].step_id]
    assert plan.steps[2].dependencies == [plan.steps[1].step_id]


def test_unique_step_ids():
    agent = MasterAgent()
    planner = TaskPlanner()

    context = agent.understand("Check my GitHub CI builds and fix simple errors")
    plan, _ = planner.plan(context)

    step_ids = [s.step_id for s in plan.steps]
    assert len(step_ids) == len(set(step_ids)), "Every step must have a strictly unique step_id"
