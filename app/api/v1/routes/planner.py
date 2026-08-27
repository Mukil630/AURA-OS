"""Task Planning and Execution Graph API Endpoints."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master.master_agent import MasterAgent
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import ChannelType, EventSeverity, EventType, TaskStatus
from app.core.models.plan import ExecutionPlan
from app.core.planner import TaskPlanner
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.database.session import get_db
from app.memory.manager import MemoryManager
from app.security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/planner", tags=["Task Planner"])
_master_agent = MasterAgent()
_task_planner = TaskPlanner()


class PlanDirectRequest(BaseModel):
    """Payload to test plan generation directly without stored task."""
    raw_input: str = Field(..., min_length=1, description="Raw user prompt")
    channel: ChannelType = Field(default=ChannelType.API, description="Source input channel")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")


class PlanResponse(BaseModel):
    """Response containing structured ExecutionPlan and WorkflowContract."""
    plan: ExecutionPlan = Field(..., description="Topologically ordered execution plan")
    workflow: WorkflowContract = Field(..., description="Persisted or generated workflow contract")


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate Execution Plan from Natural Language Prompt",
    description="Understands user request and decomposes it into a validated DAG ExecutionPlan without executing tools.",
)
async def generate_plan_direct(
    payload: PlanDirectRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PlanResponse:
    """Generate plan directly from prompt."""
    target_user = payload.user_id or current_user.user_id
    context = _master_agent.understand(
        raw_input=payload.raw_input,
        channel=payload.channel,
        user_id=target_user,
    )
    plan, workflow = _task_planner.plan(context)
    return PlanResponse(plan=plan, workflow=workflow)


@router.post(
    "/tasks/{task_id}/plan",
    response_model=PlanResponse,
    summary="Decompose stored task and persist workflow",
    description="Loads a stored Phase 1 task, executes Master Agent understanding and DAG decomposition, persists the Workflow and TaskSteps to the database, and records PLAN_GENERATED audit event.",
)
async def plan_and_persist_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PlanResponse:
    """Decompose stored task into a persisted Workflow in database."""
    task_repo = TaskRepository(db)
    wf_repo = WorkflowRepository(db)
    event_repo = EventRepository(db)

    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    # Tenant isolation check
    if current_user.role != "admin" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to plan this task.",
        )

    # Step 1: Understand task with multi-turn memory context
    mem_mgr = MemoryManager(db)
    mem_context = await mem_mgr.build_context(user_id=task.user_id, raw_input=task.raw_input)
    updated_task, context = _master_agent.enrich_task_with_understanding(task, memory_context=mem_context)

    # Step 2: Decompose into DAG Plan & Workflow
    plan, workflow = _task_planner.plan(context)

    # Step 3: Persist Workflow and Steps in DB
    saved_workflow = await wf_repo.create_workflow_with_steps(workflow)

    # Step 4: Update Task with workflow_id and PLANNING status
    await task_repo.update_task_status(
        task_id=task_id,
        status=TaskStatus.PLANNING,
        workflow_id=saved_workflow.workflow_id,
    )

    # Step 5: Record PLAN_GENERATED audit event
    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=f"tr_{task_id}",
            task_id=task_id,
            workflow_id=saved_workflow.workflow_id,
            event_type=EventType.PLAN_GENERATED,
            severity=EventSeverity.INFO,
            source_component="TaskPlanner",
            message=f"DAG Plan generated: {len(saved_workflow.steps)} steps, Mode={plan.execution_mode}, MaxRisk={plan.max_risk_tier}",
            payload={
                "workflow_id": saved_workflow.workflow_id,
                "step_count": len(saved_workflow.steps),
                "step_names": [s.name for s in saved_workflow.steps],
                "execution_mode": str(plan.execution_mode),
                "max_risk_tier": str(plan.max_risk_tier),
                "requires_approval": plan.requires_overall_approval,
            },
        )
    )

    return PlanResponse(plan=plan, workflow=saved_workflow)


@router.get(
    "/tasks/{task_id}/workflow",
    response_model=WorkflowContract,
    summary="Get planned workflow for task",
    description="Fetch the planned workflow and ordered TaskSteps associated with a task ID.",
)
async def get_task_workflow(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> WorkflowContract:
    """Fetch workflow associated with a task ID."""
    task_repo = TaskRepository(db)
    wf_repo = WorkflowRepository(db)

    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    # Tenant isolation check
    if current_user.role != "admin" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view workflow for this task.",
        )

    if not task.workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' has not been planned yet (no workflow assigned).",
        )

    wf = await wf_repo.get_workflow(task.workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{task.workflow_id}' not found in database.",
        )

    return wf
