"""Task Management API Endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.task import (
    TaskContract,
    TaskCreateRequestContract,
    TaskResponseContract,
)
from app.core.enums import EventSeverity, EventType, TaskStatus
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.session import get_db
from app.security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskListResponse(BaseModel):
    """Paginated task list response."""
    total: int = Field(..., description="Total matching tasks")
    limit: int = Field(..., description="Page limit")
    offset: int = Field(..., description="Page offset")
    tasks: List[TaskContract] = Field(..., description="List of task contracts")


@router.post(
    "",
    response_model=TaskResponseContract,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Accepts a normalized task request, persists it to the database, logs a TASK_CREATED audit event, and returns the TaskContract with assigned task_id.",
)
async def create_task(
    payload: TaskCreateRequestContract,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponseContract:
    """Create a new Task entity in the database."""
    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)

    # Construct validated TaskContract enforcing tenant boundary for non-admins
    if current_user.role == "admin":
        actual_user = payload.user_id or current_user.user_id
    else:
        actual_user = current_user.tenant_id if current_user.tenant_id != "mukil" else current_user.user_id

    task_contract = TaskContract(
        user_id=actual_user,
        session_id=payload.session_id,
        channel=payload.channel,
        raw_input=payload.raw_input,
        priority=payload.priority,
        status=TaskStatus.CREATED,
        tags=payload.tags,
    )

    # Persist in DB
    created_task = await task_repo.create_task(task_contract)

    # Record initial audit event
    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=f"tr_{created_task.task_id}",
            task_id=created_task.task_id,
            event_type=EventType.TASK_CREATED,
            severity=EventSeverity.INFO,
            source_component="TaskAPI",
            message=f"Task {created_task.task_id} registered successfully via {created_task.channel}.",
            payload={"raw_input": created_task.raw_input, "priority": str(created_task.priority)},
        )
    )

    return TaskResponseContract(
        task=created_task,
        message=f"Task {created_task.task_id} created successfully.",
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponseContract,
    summary="Get task by ID",
    description="Fetch a specific task and its current execution state with tenant isolation.",
)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponseContract:
    """Fetch task by ID with strict tenant isolation."""
    task_repo = TaskRepository(db)
    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    # Tenant Isolation: non-admins cannot access other users' tasks
    user_tenant = current_user.tenant_id or current_user.user_id
    if current_user.role != "admin" and task.user_id not in (user_tenant, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this task.",
        )

    return TaskResponseContract(
        task=task,
        message="Task retrieved successfully.",
    )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks",
    description="List tasks strictly scoped to tenant.",
)
async def list_tasks(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    task_status: Optional[TaskStatus] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TaskListResponse:
    """List tasks with strict tenant isolation."""
    task_repo = TaskRepository(db)
    if current_user.role != "admin":
        target_user = current_user.tenant_id if current_user.tenant_id != "mukil" else current_user.user_id
    else:
        target_user = user_id

    tasks = await task_repo.list_tasks(user_id=target_user, status=task_status, limit=limit, offset=offset)
    total = await task_repo.count_tasks(user_id=target_user, status=task_status)
    return TaskListResponse(
        total=total,
        limit=limit,
        offset=offset,
        tasks=tasks,
    )


@router.get(
    "/{task_id}/events",
    response_model=List[ExecutionEventContract],
    summary="Get task execution audit timeline",
    description="Fetch the complete chronological audit trail of execution events for a task.",
)
async def get_task_events(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[ExecutionEventContract]:
    """Fetch all audit events associated with a task ID with tenant isolation."""
    task_repo = TaskRepository(db)
    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    # Tenant Isolation: non-admins cannot access other users' task events
    if current_user.role != "admin" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view events for this task.",
        )

    event_repo = EventRepository(db)
    return await event_repo.get_events_by_task(task_id)
