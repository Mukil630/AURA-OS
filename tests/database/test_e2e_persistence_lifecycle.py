"""End-to-End Persistence Lifecycle and Session Restart Verification Test."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.contracts import (
    ExecutionEventContract,
    TaskContract,
    TaskStepContract,
    WorkflowContract,
    WorkflowStateContract,
)
from app.core.enums import (
    AgentType,
    ChannelType,
    EventSeverity,
    EventType,
    ExecutionMode,
    PriorityLevel,
    RiskLevel,
    RiskTier,
    StepStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.database.base import Base
from app.database.repositories import (
    EventRepository,
    TaskRepository,
    WorkflowRepository,
)


@pytest.mark.anyio
async def test_complete_persistence_lifecycle_across_session_restart():
    """
    Verifies that:
    1. A Task is created.
    2. A Workflow with TaskSteps is created.
    3. A WorkflowState checkpoint is saved.
    4. An ExecutionEvent is recorded.
    5. The DB session and engine are closed/disposed.
    6. A brand-new session is opened.
    7. All entities and their relational links are read back and verified 100%.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Initialize Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Phase 1 Session: Write Entities
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)

        # Create Task
        task = TaskContract(
            user_id="mukil_cloud",
            channel=ChannelType.VOICE,
            raw_input="Check GitHub CI and report to Telegram",
            priority=PriorityLevel.HIGH,
            risk_level=RiskLevel.MEDIUM,
            status=TaskStatus.PLANNING,
            tags=["github", "ci", "telegram"],
        )
        saved_task = await task_repo.create_task(task)
        task_id = saved_task.task_id

        # Create TaskSteps
        step1 = TaskStepContract(
            workflow_id="",
            step_index=0,
            name="fetch_ci_runs",
            agent_type=AgentType.CODING,
            tool_name="github.list_failed_workflows",
            input_payload={"repo": "Mukil630/AURA-OS"},
            risk_tier=RiskTier.TIER_1_LOW,
        )
        step2 = TaskStepContract(
            workflow_id="",
            step_index=1,
            name="send_telegram_notification",
            agent_type=AgentType.COMMUNICATION,
            tool_name="telegram.send_message",
            input_payload={"chat_id": "12345678", "message": "CI build passed"},
            risk_tier=RiskTier.TIER_2_MEDIUM,
            dependencies=[step1.step_id],
        )

        # Create Workflow
        workflow = WorkflowContract(
            task_id=task_id,
            name="github_ci_report_pipeline",
            execution_mode=ExecutionMode.SEQUENTIAL,
            status=WorkflowStatus.RUNNING,
            steps=[step1, step2],
            context_variables={"repo_owner": "Mukil630", "trigger": "voice"},
        )
        saved_wf = await wf_repo.create_workflow_with_steps(workflow)
        wf_id = saved_wf.workflow_id

        # Update Task with workflow_id
        await task_repo.update_task_status(task_id=task_id, status=TaskStatus.RUNNING, workflow_id=wf_id)

        # Record Step 1 Completion
        await wf_repo.update_step_status(
            step_id=step1.step_id,
            status=StepStatus.COMPLETED,
            output_payload={"failed_count": 0, "status": "all_green"},
        )

        # Save Checkpoint
        checkpoint = WorkflowStateContract(
            workflow_id=wf_id,
            status=WorkflowStatus.RUNNING,
            active_step_id=step2.step_id,
            completed_step_ids=[step1.step_id],
            step_outputs={step1.step_id: {"failed_count": 0}},
            accumulated_context={"repo_owner": "Mukil630", "status": "all_green"},
        )
        await wf_repo.record_checkpoint(checkpoint)

        # Record Audit Event
        event = ExecutionEventContract(
            trace_id=f"tr_{task_id}",
            task_id=task_id,
            workflow_id=wf_id,
            step_id=step1.step_id,
            event_type=EventType.STEP_COMPLETED,
            severity=EventSeverity.INFO,
            source_component="WorkflowEngine",
            message="Step 0 (fetch_ci_runs) completed successfully.",
            payload={"failed_count": 0},
        )
        await event_repo.record_event(event)
        await session.commit()

    # 3. Simulate Total App / Session Restart (Disposing session, opening new one)
    async with session_factory() as new_session:
        new_task_repo = TaskRepository(new_session)
        new_wf_repo = WorkflowRepository(new_session)
        new_event_repo = EventRepository(new_session)

        # Retrieve Task
        restored_task = await new_task_repo.get_task(task_id)
        assert restored_task is not None
        assert restored_task.task_id == task_id
        assert restored_task.user_id == "mukil_cloud"
        assert restored_task.status == TaskStatus.RUNNING
        assert restored_task.workflow_id == wf_id
        assert "github" in restored_task.tags

        # Retrieve Workflow and Steps
        restored_wf = await new_wf_repo.get_workflow(wf_id)
        assert restored_wf is not None
        assert restored_wf.task_id == task_id
        assert restored_wf.context_variables["repo_owner"] == "Mukil630"
        assert len(restored_wf.steps) == 2

        # Verify Step 1
        restored_step1 = restored_wf.steps[0]
        assert restored_step1.name == "fetch_ci_runs"
        assert restored_step1.status == StepStatus.COMPLETED
        assert restored_step1.output_payload["status"] == "all_green"

        # Verify Step 2
        restored_step2 = restored_wf.steps[1]
        assert restored_step2.name == "send_telegram_notification"
        assert restored_step2.dependencies == [step1.step_id]

        # Retrieve Latest Checkpoint
        restored_checkpoint = await new_wf_repo.get_latest_checkpoint(wf_id)
        assert restored_checkpoint is not None
        assert restored_checkpoint.workflow_id == wf_id
        assert restored_checkpoint.active_step_id == step2.step_id
        assert step1.step_id in restored_checkpoint.completed_step_ids
        assert restored_checkpoint.accumulated_context["status"] == "all_green"

        # Retrieve Audit Events
        restored_events = await new_event_repo.get_events_by_task(task_id)
        assert len(restored_events) == 1
        assert restored_events[0].trace_id == f"tr_{task_id}"
        assert restored_events[0].event_type == EventType.STEP_COMPLETED
        assert restored_events[0].payload["failed_count"] == 0

    await engine.dispose()
