"""Operational Dashboard and Distributed Tracing API Endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.observability.dashboard import (
    OperationalDashboardService,
    SystemDashboardOverview,
    default_dashboard,
)
from app.observability.tracer import (
    AgentTracer,
    TaskTraceContract,
    default_tracer,
)
from app.security.auth import AuthenticatedUser, get_current_user


router = APIRouter(prefix="/dashboard", tags=["Operational Dashboard & Tracing"])


@router.get(
    "/overview",
    response_model=SystemDashboardOverview,
    summary="Get System Operational Health and Metrics Overview",
    description="Returns consolidated status of Agent Core, Security Gate, Connectors, Task Metrics, and Active Traces.",
)
async def get_dashboard_overview(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SystemDashboardOverview:
    """Retrieve aggregate system metrics and health."""
    return default_dashboard.get_dashboard_overview()


@router.get(
    "/traces",
    response_model=List[TaskTraceContract],
    summary="List Recent Distributed Task Traces",
    description="Query chronological execution traces for recent autonomous tasks.",
)
async def list_task_traces(
    limit: int = 50,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[TaskTraceContract]:
    """Retrieve trace summaries."""
    return default_tracer.list_traces(limit=limit)


@router.get(
    "/traces/{task_id}",
    response_model=TaskTraceContract,
    summary="Get Detailed Task Lifecycle Trace and Decision Lineage",
    description="Inspect chronological spans, execution latencies, and decision reasoning for a specific task.",
)
async def get_task_trace(
    task_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TaskTraceContract:
    """Retrieve specific task trace."""
    trace = default_tracer.get_trace(task_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distributed trace for task '{task_id}' not found.",
        )
    return trace
