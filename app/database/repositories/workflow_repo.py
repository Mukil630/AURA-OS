"""Repository for Workflow, TaskStep, and Checkpoint persistence."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import (
    WorkflowContract,
    WorkflowStateContract,
)
from app.core.enums import StepStatus, WorkflowStatus
from app.database.base import dump_json
from app.database.models.task_step import TaskStepModel
from app.database.models.workflow import WorkflowModel, WorkflowStateModel


class WorkflowRepository:
    """Async repository for managing workflows, steps, and execution checkpoints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow_with_steps(self, workflow: WorkflowContract) -> WorkflowContract:
        """Persist a workflow and all its embedded TaskSteps in a single transaction."""
        wf_model = WorkflowModel.from_contract(workflow)
        self.session.add(wf_model)

        step_models = []
        for step in workflow.steps:
            step_model = TaskStepModel.from_contract(step)
            step_model.workflow_id = wf_model.workflow_id
            self.session.add(step_model)
            step_models.append(step_model)

        await self.session.flush()
        saved_steps = [s.to_contract() for s in step_models]
        return wf_model.to_contract(steps=saved_steps)

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowContract]:
        """Fetch full workflow with ordered steps."""
        wf_stmt = select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        wf_res = await self.session.execute(wf_stmt)
        wf_model = wf_res.scalar_one_or_none()
        if not wf_model:
            return None

        steps_stmt = select(TaskStepModel).where(TaskStepModel.workflow_id == workflow_id).order_by(TaskStepModel.step_index.asc())
        steps_res = await self.session.execute(steps_stmt)
        steps_models = steps_res.scalars().all()
        steps = [s.to_contract() for s in steps_models]
        return wf_model.to_contract(steps=steps)

    async def update_workflow_status(
        self,
        workflow_id: str,
        status: WorkflowStatus,
    ) -> Optional[WorkflowContract]:
        """Update workflow overall status and completion timestamp."""
        stmt = select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None

        model.status = status.value if hasattr(status, "value") else str(status)
        if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
            model.completed_at = datetime.now(timezone.utc)

        await self.session.flush()
        return await self.get_workflow(workflow_id)

    async def get_workflow_by_task_id(self, task_id: str) -> Optional[WorkflowContract]:
        """Fetch workflow associated with a task ID."""
        wf_stmt = select(WorkflowModel).where(WorkflowModel.task_id == task_id).order_by(WorkflowModel.created_at.desc())
        wf_res = await self.session.execute(wf_stmt)
        wf_model = wf_res.scalars().first()
        if not wf_model:
            return None
        return await self.get_workflow(wf_model.workflow_id)

    async def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        output_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TaskStepContract]:
        """Update step execution status, outputs, and timestamps."""
        stmt = select(TaskStepModel).where(TaskStepModel.step_id == step_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None

        model.status = status.value if hasattr(status, "value") else str(status)
        if output_payload is not None:
            model.output_payload_json = dump_json(output_payload)
        if error_message is not None:
            model.error_message = error_message
        if status == StepStatus.RUNNING and not model.started_at:
            model.started_at = datetime.now(timezone.utc)
        if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
            model.completed_at = datetime.now(timezone.utc)

        await self.session.flush()
        return model.to_contract()

    async def record_checkpoint(self, state: WorkflowStateContract) -> WorkflowStateContract:
        """Save a durable state checkpoint."""
        model = WorkflowStateModel.from_contract(state)
        self.session.add(model)
        await self.session.flush()
        return model.to_contract()

    async def get_latest_checkpoint(self, workflow_id: str) -> Optional[WorkflowStateContract]:
        """Retrieve the most recent checkpoint for a workflow."""
        stmt = (
            select(WorkflowStateModel)
            .where(WorkflowStateModel.workflow_id == workflow_id)
            .order_by(WorkflowStateModel.checkpoint_timestamp.desc())
        )
        res = await self.session.execute(stmt)
        model = res.scalars().first()
        return model.to_contract() if model else None
