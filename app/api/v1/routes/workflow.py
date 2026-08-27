"""Workflow Execution API Endpoints."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master.master_agent import MasterAgent
from app.core.contracts.task import TaskContract
from app.core.contracts.workflow import WorkflowContract, WorkflowStateContract
from app.core.enums import TaskStatus
from app.core.planner import TaskPlanner
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.database.session import get_db
from app.engine.workflow_engine import WorkflowEngine
from app.memory.manager import MemoryManager
from app.security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/workflows", tags=["Workflow Engine"])
_master_agent = MasterAgent()
_task_planner = TaskPlanner()


class ExecuteWorkflowResponse(BaseModel):
    """Response returned upon workflow execution."""
    workflow: WorkflowContract = Field(..., description="Final workflow state")
    task: Optional[TaskContract] = Field(default=None, description="Updated task state")
    message: str = Field(..., description="Execution status message")


@router.post(
    "/{workflow_id}/execute",
    response_model=ExecuteWorkflowResponse,
    summary="Execute a planned workflow",
    description="Runs the DAG state machine for the specified workflow ID until completion, pause, or failure.",
)
async def execute_workflow_by_id(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ExecuteWorkflowResponse:
    """Execute workflow by ID."""
    wf_repo = WorkflowRepository(db)
    workflow = await wf_repo.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    engine = WorkflowEngine(db_session=db)
    final_wf, final_task = await engine.execute_workflow(workflow_id)

    return ExecuteWorkflowResponse(
        workflow=final_wf,
        task=final_task,
        message=f"Workflow '{final_wf.name}' state: {final_wf.status.value if hasattr(final_wf.status, 'value') else final_wf.status}.",
    )


@router.post(
    "/tasks/{task_id}/execute",
    response_model=ExecuteWorkflowResponse,
    summary="Execute workflow for a task",
    description="If task has not yet been planned, automatically decomposes and generates DAG workflow first, then runs the Workflow Engine to completion.",
)
async def execute_task_workflow(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ExecuteWorkflowResponse:
    """Execute the entire pipeline for a task (Plan -> Execute)."""
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
            detail="Access denied: You do not have permission to execute this task.",
        )

    workflow_id = task.workflow_id
    if not workflow_id:
        # Auto-plan if not planned yet (with Phase 6 Multi-Turn Memory Context)
        memory_manager = MemoryManager(db)
        mem_context = await memory_manager.build_context(user_id=task.user_id, raw_input=task.raw_input)
        _, context = _master_agent.enrich_task_with_understanding(task, memory_context=mem_context)
        plan, workflow = _task_planner.plan(context)
        saved_wf = await wf_repo.create_workflow_with_steps(workflow)
        workflow_id = saved_wf.workflow_id
        await task_repo.update_task_status(task_id, TaskStatus.PLANNING, workflow_id=workflow_id)

    # Execute
    engine = WorkflowEngine(db_session=db)
    final_wf, final_task = await engine.execute_workflow(workflow_id)

    return ExecuteWorkflowResponse(
        workflow=final_wf,
        task=final_task,
        message=f"Task '{task_id}' execution completed with status: {final_task.status if final_task else final_wf.status}.",
    )


@router.get(
    "/{workflow_id}/state",
    response_model=Optional[WorkflowStateContract],
    summary="Get latest workflow checkpoint",
    description="Fetch the latest durable state snapshot/checkpoint for a workflow.",
)
async def get_workflow_state(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Optional[WorkflowStateContract]:
    """Get latest durable checkpoint."""
    engine = WorkflowEngine(db_session=db)
    checkpoint = await engine.get_state(workflow_id)
    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No checkpoints found for workflow '{workflow_id}'.",
        )
    return checkpoint


@router.post(
    "/{workflow_id}/pause",
    summary="Pause a running workflow",
)
async def pause_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Pause workflow."""
    engine = WorkflowEngine(db_session=db)
    success = await engine.pause_workflow(workflow_id)
    return {"status": "paused" if success else "error", "workflow_id": workflow_id}


@router.post(
    "/{workflow_id}/resume",
    response_model=ExecuteWorkflowResponse,
    summary="Resume a paused workflow",
)
async def resume_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ExecuteWorkflowResponse:
    """Resume workflow from checkpoint."""
    engine = WorkflowEngine(db_session=db)
    final_wf, final_task = await engine.execute_workflow(workflow_id)
    return ExecuteWorkflowResponse(
        workflow=final_wf,
        task=final_task,
        message="Workflow resumed and finished execution.",
    )


@router.post(
    "/{workflow_id}/cancel",
    summary="Cancel a workflow",
)
async def cancel_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel workflow."""
    engine = WorkflowEngine(db_session=db)
    success = await engine.cancel_workflow(workflow_id)
    return {"status": "cancelled" if success else "error", "workflow_id": workflow_id}
