"""Execution plan and dependency graph helper models."""
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import ExecutionMode, RiskTier


class StepDependency(VersionedContractBase):
    """Explicit Directed Acyclic Graph (DAG) edge between TaskSteps."""
    parent_step_id: str = Field(..., description="Step ID that must complete first.")
    child_step_id: str = Field(..., description="Step ID that is blocked until parent completes.")
    condition: Optional[str] = Field(
        default=None,
        description="Optional expression evaluated on parent step output (e.g. 'output.status == true')."
    )


class ExecutionPlan(VersionedContractBase):
    """
    Structured decomposition produced by Task Planner before execution.
    Transforms user intent into a validated, dependency-ordered graph of steps.
    """
    plan_id: str = Field(
        default_factory=lambda: f"plan_{uuid4().hex[:12]}",
        description="Unique execution plan ID."
    )
    task_id: str = Field(..., description="Associated parent Task ID.")
    goal: str = Field(..., description="Clear statement of intended goal.")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL, description="Step orchestration mode.")
    steps: List[TaskStepContract] = Field(default_factory=list, description="Ordered steps in the plan.")
    dependencies: List[StepDependency] = Field(default_factory=list, description="DAG dependencies between steps.")
    estimated_duration_seconds: int = Field(default=60, gt=0, description="Estimated completion time.")
    max_risk_tier: RiskTier = Field(default=RiskTier.TIER_1_LOW, description="Highest risk tier in the plan.")
    requires_overall_approval: bool = Field(default=False, description="Whether plan requires approval before start.")
    plan_metadata: Dict[str, Any] = Field(default_factory=dict, description="Planner reasoning and retrieval context.")
