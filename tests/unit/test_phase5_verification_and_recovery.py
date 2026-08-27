"""Comprehensive Unit & Integration Test Suite for Phase 5 Verification & Self-Healing."""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.tool import ToolExecutionRequest, ToolExecutionResult
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import (
    AgentType,
    EventSeverity,
    EventType,
    ExecutionMode,
    FailureCategory,
    RecoveryStrategy,
    RiskTier,
    StepStatus,
    TaskStatus,
    VerificationStatus,
    WorkflowStatus,
)
from app.database.base import Base
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.recovery.engine import SelfHealingEngine
from app.tools.registry import MockTool, ToolExecutor, ToolRegistry
from app.verification.engine import VerificationEngine


# ── Scenario 1: Successful execution -> Verification PASS ─────────────────────────────
@pytest.mark.anyio
async def test_scenario_1_successful_execution_and_verification_pass():
    verifier = VerificationEngine()
    step = TaskStepContract(workflow_id="wf_1", step_index=0, name="run_tests", agent_type=AgentType.CODING, tool_name="coding.run_tests")
    res = ToolExecutionResult(execution_id="exec_1", tool_id="coding.run_tests", success=True, data={"tests_passed": 52, "tests_failed": 0, "status": "all_green"})

    v_res = verifier.verify_step(step, res)
    assert v_res.status == VerificationStatus.VERIFIED
    assert "passed verification" in v_res.details


# ── Scenario 2: Tool transient failure -> Bounded Retry Success ───────────────────────
@pytest.mark.anyio
async def test_scenario_2_transient_failure_bounded_retry_success():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Flaky tool that fails on attempt 1, succeeds on attempt 2
    attempts = 0
    def flaky_handler(p):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionResetError("429 Too Many Requests: Rate limit exceeded (temporary lock)")
        return {"status": "success", "recovered_on_retry": True}

    registry = ToolRegistry()
    registry.register_tool(MockTool(name="flaky.api", handler=flaky_handler))
    executor = ToolExecutor(registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil_test", raw_input="Retry test")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_retry", step_index=0, name="flaky_step", agent_type=AgentType.CODING, tool_name="flaky.api", max_retries=3)
        wf = WorkflowContract(task_id=saved_task.task_id, name="retry_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session, tool_executor=executor)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert final_wf.steps[0].status == StepStatus.COMPLETED
        assert final_task.status == TaskStatus.COMPLETED
        assert attempts == 2

    await engine_db.dispose()


# ── Scenario 3: Tool permanent failure -> FAILED ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_3_permanent_failure_immediate_stop_and_fail():
    healer = SelfHealingEngine()
    step = TaskStepContract(workflow_id="wf_1", step_index=0, name="bad_step", agent_type=AgentType.CODING, tool_name="bad.tool")
    cat = healer.classify_failure(error_msg="404 Repository Not Found: git remote does not exist")
    assert cat == FailureCategory.PERMANENT
    strategy = healer.select_recovery_strategy(cat, step)
    assert strategy == RecoveryStrategy.ESCALATE_HUMAN


# ── Scenario 4: Timeout -> Handled Gracefully ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_4_timeout_failure_classification():
    healer = SelfHealingEngine()
    step = TaskStepContract(workflow_id="wf_1", step_index=0, name="timeout_step", agent_type=AgentType.CODING, tool_name="slow.tool", retry_count=0, max_retries=2)
    cat = healer.classify_failure(error_msg="Tool 'slow.tool' timed out after 30s deadline exceeded.")
    assert cat == FailureCategory.TIMEOUT
    strategy = healer.select_recovery_strategy(cat, step)
    assert strategy == RecoveryStrategy.RETRY


# ── Scenario 5: Verification mismatch -> Silent Failure Prevented ─────────────────────
@pytest.mark.anyio
async def test_scenario_5_verification_mismatch_silent_failure_prevented():
    """Tool runner returned success=True, but actual pytest reported 2 test failures."""
    verifier = VerificationEngine()
    step = TaskStepContract(workflow_id="wf_1", step_index=0, name="run_tests", agent_type=AgentType.CODING, tool_name="coding.run_tests")
    res = ToolExecutionResult(execution_id="exec_1", tool_id="coding.run_tests", success=True, data={"tests_passed": 10, "tests_failed": 2, "status": "failed"})

    v_res = verifier.verify_step(step, res)
    assert v_res.status == VerificationStatus.FAILED
    assert "reported 2 failures" in v_res.details


# ── Scenario 6: Self-healing repair succeeds ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_6_self_healing_repair_succeeds():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Tool fails initially due to bad cache, succeeds when auto_repair_applied is True
    def repairable_handler(p):
        if not p.get("auto_repair_applied"):
            return {"tests_passed": 0, "tests_failed": 3, "status": "failed"}
        return {"tests_passed": 52, "tests_failed": 0, "status": "all_green"}

    registry = ToolRegistry()
    registry.register_tool(MockTool(name="coding.run_tests", handler=repairable_handler))
    executor = ToolExecutor(registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil_test", raw_input="Repair test")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_repair", step_index=0, name="run_tests", agent_type=AgentType.CODING, tool_name="coding.run_tests", max_retries=2)
        wf = WorkflowContract(task_id=saved_task.task_id, name="repair_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session, tool_executor=executor)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert final_task.status == TaskStatus.COMPLETED

    await engine_db.dispose()


# ── Scenario 7: Recovery fails -> Escalates to Human ──────────────────────────────────
@pytest.mark.anyio
async def test_scenario_7_self_healing_recovery_failure_escalates_to_human():
    healer = SelfHealingEngine()
    step = TaskStepContract(workflow_id="wf_1", step_index=0, name="exhausted_step", agent_type=AgentType.CODING, tool_name="bad.tool", retry_count=3, max_retries=3)
    cat = healer.classify_failure(error_msg="Connection reset by peer")
    strategy = healer.select_recovery_strategy(cat, step)
    assert strategy == RecoveryStrategy.ESCALATE_HUMAN


# ── Scenario 8: Max Retries Exceeded -> Stop ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_8_max_retries_exceeded_stops():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Tool that always fails
    registry = ToolRegistry()
    registry.register_tool(MockTool(name="always.fail", handler=lambda p: (_ for _ in ()).throw(RuntimeError("Continuous Network Drop"))))
    executor = ToolExecutor(registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil_test", raw_input="Max retry test")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_stop", step_index=0, name="failing_step", agent_type=AgentType.CODING, tool_name="always.fail", retry_count=0, max_retries=1)
        wf = WorkflowContract(task_id=saved_task.task_id, name="stop_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session, tool_executor=executor)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.FAILED
        assert final_task.status == TaskStatus.FAILED

    await engine_db.dispose()


# ── Scenario 9: High Risk Operation -> WAITING_FOR_APPROVAL ───────────────────────────
@pytest.mark.anyio
async def test_scenario_9_high_risk_triggers_approval_gate():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil_test", raw_input="High risk action")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(
            workflow_id="wf_risk",
            step_index=0,
            name="delete_prod_table",
            agent_type=AgentType.PC,
            tool_name="pc.system_info",
            risk_tier=RiskTier.TIER_4_CRITICAL,
            requires_approval=True,
        )
        wf = WorkflowContract(task_id=saved_task.task_id, name="risk_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.PAUSED
        assert final_wf.steps[0].status == StepStatus.WAITING_FOR_APPROVAL
        assert final_task.status == TaskStatus.WAITING_FOR_APPROVAL

    await engine_db.dispose()


# ── Scenario 10: Complete Audit Trail Timeline ────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_10_complete_audit_trail_timeline():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)

        task = TaskContract(user_id="mukil_test", raw_input="Audit timeline test")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_audit", step_index=0, name="audit_step", agent_type=AgentType.CODING, tool_name="coding.run_tests")
        wf = WorkflowContract(task_id=saved_task.task_id, name="audit_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session)
        await engine.execute_workflow(saved_wf.workflow_id)

        events = await event_repo.get_events_by_task(saved_task.task_id)
        event_types = [e.event_type for e in events]

        assert EventType.WORKFLOW_STARTED in event_types
        assert EventType.STEP_STARTED in event_types
        assert EventType.VERIFICATION_PASSED in event_types
        assert EventType.STEP_COMPLETED in event_types
        assert EventType.WORKFLOW_COMPLETED in event_types
        assert EventType.TASK_COMPLETED in event_types

    await engine_db.dispose()
