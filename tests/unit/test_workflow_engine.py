"""Unit tests for WorkflowEngine DAG state machine execution."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.master.master_agent import MasterAgent
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import (
    AgentType,
    ExecutionMode,
    RiskTier,
    StepStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.core.planner import TaskPlanner
from app.database.base import Base
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.tools.registry import MockTool, ToolExecutor, ToolRegistry


@pytest.mark.anyio
async def test_workflow_engine_full_dag_success():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)

    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        agent = MasterAgent()
        planner = TaskPlanner()

        # 1. Create Task
        task = TaskContract(
            user_id="mukil_dev",
            raw_input="Check my GitHub CI builds and fix simple errors",
            status=TaskStatus.CREATED,
        )
        saved_task = await task_repo.create_task(task)

        # 2. Understand and Plan
        _, context = agent.enrich_task_with_understanding(saved_task)
        plan, workflow = planner.plan(context)
        saved_wf = await wf_repo.create_workflow_with_steps(workflow)
        await task_repo.update_task_status(saved_task.task_id, TaskStatus.PLANNING, workflow_id=saved_wf.workflow_id)

        # 3. Execute via WorkflowEngine
        engine = WorkflowEngine(db_session=session)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        # 4. Verify Final State
        assert final_wf.status == WorkflowStatus.COMPLETED
        assert len(final_wf.steps) == 5
        assert all(s.status == StepStatus.COMPLETED for s in final_wf.steps)

        assert final_task.status == TaskStatus.COMPLETED
        assert "all 5 steps" in final_task.result_summary.lower()
        assert len(final_task.result_data) == 5

    await engine_db.dispose()


@pytest.mark.anyio
async def test_workflow_engine_failure_propagation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)

    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Custom registry with a failing tool at step 1
    custom_registry = ToolRegistry()
    custom_registry.register_tool(
        MockTool(name="failing.tool", handler=lambda p: (_ for _ in ()).throw(RuntimeError("API Gateway Timeout")))
    )
    custom_executor = ToolExecutor(custom_registry)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        # Task
        task = TaskContract(user_id="mukil_dev", raw_input="Failing task")
        saved_task = await task_repo.create_task(task)

        # 2 Steps: Step 1 fails, Step 2 depends on Step 1
        s1 = TaskStepContract(workflow_id="wf_fail", step_index=0, name="step_1", agent_type=AgentType.CODING, tool_name="failing.tool")
        s2 = TaskStepContract(workflow_id="wf_fail", step_index=1, name="step_2", agent_type=AgentType.CODING, tool_name="system.general_action", dependencies=[s1.step_id])

        wf = WorkflowContract(
            task_id=saved_task.task_id,
            name="failing_workflow",
            execution_mode=ExecutionMode.SEQUENTIAL,
            status=WorkflowStatus.PENDING,
            steps=[s1, s2],
        )
        saved_wf = await wf_repo.create_workflow_with_steps(wf)
        await task_repo.update_task_status(saved_task.task_id, TaskStatus.PLANNING, workflow_id=saved_wf.workflow_id)

        engine = WorkflowEngine(db_session=session, tool_executor=custom_executor)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        assert final_wf.status == WorkflowStatus.FAILED
        assert final_wf.steps[0].status == StepStatus.FAILED
        assert final_wf.steps[1].status == StepStatus.CANCELLED
        assert final_task.status == TaskStatus.FAILED
        assert "API Gateway Timeout" in final_task.error_message

    await engine_db.dispose()


@pytest.mark.anyio
async def test_workflow_engine_approval_pause():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)

    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)

        task = TaskContract(user_id="mukil_dev", raw_input="High risk task")
        saved_task = await task_repo.create_task(task)

        # High risk step requiring approval
        s1 = TaskStepContract(
            workflow_id="wf_auth",
            step_index=0,
            name="destructive_action",
            agent_type=AgentType.PC,
            tool_name="pc.system_info",
            risk_tier=RiskTier.TIER_3_HIGH,
            requires_approval=True,
        )
        wf = WorkflowContract(
            task_id=saved_task.task_id,
            name="auth_workflow",
            steps=[s1],
        )
        saved_wf = await wf_repo.create_workflow_with_steps(wf)

        engine = WorkflowEngine(db_session=session)
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        # Verify paused state
        assert final_wf.status == WorkflowStatus.PAUSED
        assert final_wf.steps[0].status == StepStatus.WAITING_FOR_APPROVAL
        assert final_task.status == TaskStatus.WAITING_FOR_APPROVAL

    await engine_db.dispose()
