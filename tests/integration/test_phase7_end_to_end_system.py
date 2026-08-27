"""Comprehensive End-to-End System Integration & Multi-Turn Hardening Test Suite for Phase 7."""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.master.master_agent import MasterAgent
from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import (
    AgentType,
    ApprovalState,
    EventSeverity,
    EventType,
    ExecutionMode,
    MemoryType,
    RiskTier,
    StepStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.core.planner import TaskPlanner
from app.database.base import Base
from app.database.repositories.approval_repo import ApprovalRepository
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.memory.manager import MemoryManager
from app.tools.registry import MockTool, ToolExecutor, ToolRegistry


# ── Scenario 01: Complete P1 to P6 Full Lifecycle ─────────────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_01_full_lifecycle_p1_to_p6():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        mem_repo = MemoryRepository(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)

        # P1: Intake & Store
        task = TaskContract(user_id="mukil", raw_input="Check my GitHub CI builds and fix simple errors")
        saved_task = await task_repo.create_task(task)

        # P2: Understand
        _, context = agent.enrich_task_with_understanding(saved_task)

        # P3: Plan DAG
        plan, workflow = planner.plan(context)
        saved_wf = await wf_repo.create_workflow_with_steps(workflow)

        # P4 & P5: Execute & Verify
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert final_task.status == TaskStatus.COMPLETED

        # P6: Memory Distilled
        mems = await mem_repo.list_memories(user_id="mukil")
        assert len(mems) >= 1
        assert "completed" in mems[0].content.lower()

    await engine_db.dispose()


# ── Scenario 02: Multi-Turn Memory Reuse (Turn 1 Config -> Turn 2 Query) ─────────────
@pytest.mark.anyio
async def test_phase7_scenario_02_multi_turn_memory_reuse():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        agent = MasterAgent()
        planner = TaskPlanner()

        # Turn 1: User specifies preferred repo
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="My main GitHub repository is Mukil630/AURA-OS",
                tags=["github", "repository", "default"],
                importance_score=0.95,
            )
        )

        # Turn 2: User says "Check the CI of my main repository" without repeating repo name
        mem_context = await manager.build_context(user_id="mukil", raw_input="Check the CI of my main repository")
        context = agent.understand(
            raw_input="Check the CI of my main repository",
            user_id="mukil",
            memory_context=mem_context,
        )

        # Master Agent must have resolved target_repo from memory!
        assert context.parsed_intent.extracted_entities.target_repo == "Mukil630/AURA-OS"

        # Plan generated with resolved repository
        _, wf = planner.plan(context)
        assert wf.steps[0].input_payload["repository"] == "Mukil630/AURA-OS"

    await engine_db.dispose()


# ── Scenario 03: Memory Irrelevance Noise Filtering ───────────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_03_memory_irrelevance_noise_filtering():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        agent = MasterAgent()

        # Stored coding memory
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.SEMANTIC_FACT,
                content="Main project repository is Mukil630/AURA-OS",
                tags=["github", "repo"],
                importance_score=0.9,
            )
        )

        # Turn 2 is completely unrelated PC telemetry query
        mem_context = await manager.build_context(user_id="mukil", raw_input="Check battery and CPU status")
        assert len(mem_context) == 0  # Irrelevant memory discarded!

        context = agent.understand(
            raw_input="Check battery and CPU status",
            user_id="mukil",
            memory_context=mem_context,
        )
        assert context.parsed_intent.extracted_entities.target_repo is None

    await engine_db.dispose()


# ── Scenario 04: User Isolation Across Multi-Turn ─────────────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_04_user_isolation_across_multi_turn():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        agent = MasterAgent()

        # User Mukil sets repo
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="My repository is Mukil630/AURA-OS",
                tags=["github", "repo"],
                importance_score=0.9,
            )
        )

        # User Alice asks "Check my repo CI"
        alice_mem = await manager.build_context(user_id="alice", raw_input="Check my repo CI")
        assert len(alice_mem) == 0

        alice_context = agent.understand(
            raw_input="Check my repo CI",
            user_id="alice",
            memory_context=alice_mem,
        )
        # Alice does NOT receive Mukil's repo
        assert alice_context.parsed_intent.extracted_entities.target_repo is None

    await engine_db.dispose()


# ── Scenario 05: Idempotency Duplicate Request Handling ───────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_05_idempotent_duplicate_request_handling():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        engine = WorkflowEngine(db_session=session)

        task = TaskContract(user_id="mukil", raw_input="General task")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_idem", step_index=0, name="s1", agent_type=AgentType.MASTER, tool_name="system.general_action")
        wf = WorkflowContract(task_id=saved_task.task_id, name="idem_wf", steps=[s1])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        # Run 1
        wf1, _ = await engine.execute_workflow(saved_wf.workflow_id)
        assert wf1.status == WorkflowStatus.COMPLETED

        # Run 2 (duplicate request)
        wf2, _ = await engine.execute_workflow(saved_wf.workflow_id)
        assert wf2.status == WorkflowStatus.COMPLETED

    await engine_db.dispose()


# ── Scenario 06: Workflow Crash Recovery from Checkpoint ──────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_06_workflow_crash_recovery_from_checkpoint():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil", raw_input="Crash recovery task")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_crash", step_index=0, name="step_1", agent_type=AgentType.MASTER, tool_name="system.general_action")
        s2 = TaskStepContract(workflow_id="wf_crash", step_index=1, name="step_2", agent_type=AgentType.MASTER, tool_name="system.general_action", dependencies=[s1.step_id])
        wf = WorkflowContract(task_id=saved_task.task_id, name="crash_wf", steps=[s1, s2])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        # Simulate step 1 completed before crash
        await wf_repo.update_step_status(s1.step_id, StepStatus.COMPLETED, output_payload={"done": 1})
        await wf_repo.update_workflow_status(saved_wf.workflow_id, WorkflowStatus.PAUSED)

        # Engine recovers from checkpoint & finishes step 2
        engine = WorkflowEngine(db_session=session)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert final_task.status == TaskStatus.COMPLETED

    await engine_db.dispose()


# ── Scenario 07: Step Resume from Checkpoint Skips Completed ──────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_07_step_resume_from_checkpoint_skips_completed():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    step_1_runs = 0
    step_2_runs = 0

    def tool_handler(p):
        nonlocal step_1_runs, step_2_runs
        if p.get("step") == 1:
            step_1_runs += 1
        elif p.get("step") == 2:
            step_2_runs += 1
        return {"executed": True}

    registry = ToolRegistry()
    registry.register_tool(MockTool(name="counted.tool", handler=tool_handler))
    executor = ToolExecutor(registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil", raw_input="Skip test")
        saved_task = await task_repo.create_task(task)

        s1 = TaskStepContract(workflow_id="wf_skip", step_index=0, name="s1", agent_type=AgentType.MASTER, tool_name="counted.tool", input_payload={"step": 1})
        s2 = TaskStepContract(workflow_id="wf_skip", step_index=1, name="s2", agent_type=AgentType.MASTER, tool_name="counted.tool", input_payload={"step": 2}, dependencies=[s1.step_id])
        wf = WorkflowContract(task_id=saved_task.task_id, name="skip_wf", steps=[s1, s2])
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        # Pre-mark step 1 as COMPLETED
        await wf_repo.update_step_status(s1.step_id, StepStatus.COMPLETED, output_payload={"already_done": True})

        engine = WorkflowEngine(db_session=session, tool_executor=executor)
        await engine.execute_workflow(saved_wf.workflow_id)

        # Step 1 was skipped; Step 2 executed exactly once!
        assert step_1_runs == 0
        assert step_2_runs == 1

    await engine_db.dispose()


# ── Scenario 08: Concurrent Independent Tasks ─────────────────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_08_concurrent_independent_tasks_isolation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session1, session_factory() as session2:
        task_repo1 = TaskRepository(session1)
        task_repo2 = TaskRepository(session2)
        wf_repo1 = WorkflowRepository(session1)
        wf_repo2 = WorkflowRepository(session2)

        # Task A
        tA = await task_repo1.create_task(TaskContract(user_id="user_A", raw_input="Task A"))
        sA = TaskStepContract(workflow_id="wf_A", step_index=0, name="sA", agent_type=AgentType.MASTER, tool_name="system.general_action")
        wfA = await wf_repo1.create_workflow_with_steps(WorkflowContract(task_id=tA.task_id, name="wf_A", steps=[sA]))

        # Task B
        tB = await task_repo2.create_task(TaskContract(user_id="user_B", raw_input="Task B"))
        sB = TaskStepContract(workflow_id="wf_B", step_index=0, name="sB", agent_type=AgentType.MASTER, tool_name="system.general_action")
        wfB = await wf_repo2.create_workflow_with_steps(WorkflowContract(task_id=tB.task_id, name="wf_B", steps=[sB]))

        # Run concurrently
        engine1 = WorkflowEngine(db_session=session1)
        engine2 = WorkflowEngine(db_session=session2)

        resA, resB = await asyncio.gather(
            engine1.execute_workflow(wfA.workflow_id),
            engine2.execute_workflow(wfB.workflow_id),
        )

        assert resA[0].status == WorkflowStatus.COMPLETED
        assert resB[0].status == WorkflowStatus.COMPLETED

    await engine_db.dispose()


# ── Scenario 09: Failed Execution -> Recovery -> Memory Distillation ─────────────────
@pytest.mark.anyio
async def test_phase7_scenario_09_failed_execution_recovery_memory_distillation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    attempts = 0
    def flaky_tool(p):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionResetError("429 Too Many Requests: Rate limited")
        return {"status": "success", "resolved": True}

    registry = ToolRegistry()
    registry.register_tool(MockTool(name="flaky.tool", handler=flaky_tool))
    executor = ToolExecutor(registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        mem_repo = MemoryRepository(session)

        task = await task_repo.create_task(TaskContract(user_id="mukil", raw_input="Flaky task"))
        s1 = TaskStepContract(workflow_id="wf_flaky", step_index=0, name="s1", agent_type=AgentType.MASTER, tool_name="flaky.tool", max_retries=2)
        wf = await wf_repo.create_workflow_with_steps(WorkflowContract(task_id=task.task_id, name="flaky_wf", steps=[s1]))

        engine = WorkflowEngine(db_session=session, tool_executor=executor)
        final_wf, final_task = await engine.execute_workflow(wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert attempts == 2

        # Verify episodic memory was recorded
        mems = await mem_repo.list_memories(user_id="mukil")
        assert len(mems) >= 1
        assert "completed" in mems[0].content.lower()

    await engine_db.dispose()


# ── Scenario 10: High-Risk Approval Persistence Across Restart ────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_10_high_risk_approval_persistence_across_restart():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Session 1: Task pauses for approval
    async with session_factory() as session1:
        task_repo = TaskRepository(session1)
        wf_repo = WorkflowRepository(session1)
        approval_repo = ApprovalRepository(session1)

        task = await task_repo.create_task(TaskContract(user_id="mukil", raw_input="Dangerous action"))
        s1 = TaskStepContract(
            workflow_id="wf_auth_pers",
            step_index=0,
            name="dangerous_step",
            agent_type=AgentType.PC,
            tool_name="pc.system_info",
            risk_tier=RiskTier.TIER_4_CRITICAL,
            requires_approval=True,
        )
        wf = await wf_repo.create_workflow_with_steps(WorkflowContract(task_id=task.task_id, name="auth_pers_wf", steps=[s1]))

        engine1 = WorkflowEngine(db_session=session1)
        paused_wf, paused_task = await engine1.execute_workflow(wf.workflow_id)

        assert paused_wf.status == WorkflowStatus.PAUSED
        assert paused_task.status == TaskStatus.WAITING_FOR_APPROVAL

        # Human operator approves the pending ticket
        pending_tickets = await approval_repo.get_pending_approvals_for_task(task.task_id)
        assert len(pending_tickets) == 1
        await approval_repo.decide_approval(pending_tickets[0].approval_id, ApprovalState.APPROVED, approved_by="mukil_admin")
        await wf_repo.update_step_status(s1.step_id, StepStatus.PENDING)  # Ready to run upon approval
        await session1.commit()

    # Session 2 (Simulating Server Restart / Reconnect): Workflow resumes and finishes
    async with session_factory() as session2:
        engine2 = WorkflowEngine(db_session=session2)
        resumed_wf, resumed_task = await engine2.execute_workflow(wf.workflow_id)

        assert resumed_wf.status == WorkflowStatus.COMPLETED
        assert resumed_task.status == TaskStatus.COMPLETED

    await engine_db.dispose()


# ── Scenario 11: Complete Audit Trace Correlation Chain ───────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_11_complete_audit_trace_correlation_chain():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)

        # Full run
        task = await task_repo.create_task(TaskContract(user_id="mukil", raw_input="Audit correlation check"))
        _, ctx = agent.enrich_task_with_understanding(task)
        _, wf = planner.plan(ctx)
        saved_wf = await wf_repo.create_workflow_with_steps(wf)
        await engine.execute_workflow(saved_wf.workflow_id)

        # Trace correlation
        events = await event_repo.get_events_by_task(task.task_id)
        assert len(events) >= 4

        # Every event must correlate to the same task_id
        for e in events:
            assert e.task_id == task.task_id
            assert e.trace_id == f"tr_{task.task_id}"

    await engine_db.dispose()


# ── Scenario 12: THE KILLER THREE-TURN CONTINUITY TEST ────────────────────────────────
@pytest.mark.anyio
async def test_phase7_scenario_12_the_killer_three_turn_continuity_test():
    """
    Turn 1: 'My default repository is Mukil630/AURA-OS' -> Remembered
    Turn 2: 'Check its CI' -> Resolves 'its' -> Runs CI check -> Remembers result
    Turn 3: 'If it fails, fix the issue' -> Resolves 'it' -> Plans fix & verification -> Completes!
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        manager = MemoryManager(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)

        # ── TURN 1: Store User Preference / Fact ───────────────────────────────
        turn1_mem_id = await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="My default repository is Mukil630/AURA-OS for all CI checks",
                tags=["github", "repository", "default"],
                importance_score=0.98,
            )
        )
        assert turn1_mem_id.startswith("mem_")

        # ── TURN 2: 'Check its CI' (Resolves 'its' from Turn 1 Memory) ───────────
        t2_prompt = "Check its CI"
        t2_mem = await manager.build_context(user_id="mukil", raw_input=t2_prompt)
        t2_task = await task_repo.create_task(TaskContract(user_id="mukil", raw_input=t2_prompt))

        _, t2_ctx = agent.enrich_task_with_understanding(t2_task, memory_context=t2_mem)
        assert t2_ctx.parsed_intent.extracted_entities.target_repo == "Mukil630/AURA-OS"

        _, t2_wf = planner.plan(t2_ctx)
        saved_t2_wf = await wf_repo.create_workflow_with_steps(t2_wf)
        await engine.execute_workflow(saved_t2_wf.workflow_id)

        # ── TURN 3: 'If it fails, fix the issue' ──────────────────────────────
        t3_prompt = "If it fails, fix the issue"
        t3_mem = await manager.build_context(user_id="mukil", raw_input=t3_prompt)
        t3_task = await task_repo.create_task(TaskContract(user_id="mukil", raw_input=t3_prompt))

        _, t3_ctx = agent.enrich_task_with_understanding(t3_task, memory_context=t3_mem)
        # Context resolves 'it' to Mukil630/AURA-OS
        assert t3_ctx.parsed_intent.extracted_entities.target_repo == "Mukil630/AURA-OS"

        # Plan generated with full 5-step CI fix & verify pipeline
        _, t3_wf = planner.plan(t3_ctx)
        assert len(t3_wf.steps) == 5
        assert t3_wf.steps[3].name == "apply_code_fix"
        assert t3_wf.steps[4].name == "run_verification_tests"

        saved_t3_wf = await wf_repo.create_workflow_with_steps(t3_wf)
        final_wf, final_task = await engine.execute_workflow(saved_t3_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.COMPLETED
        assert final_task.status == TaskStatus.COMPLETED

        # Assert final distilled memory exists
        all_memories = await manager.query(MemoryQueryContract(query_text="AURA-OS fix", user_id="mukil"))
        assert len(all_memories) >= 1

    await engine_db.dispose()
