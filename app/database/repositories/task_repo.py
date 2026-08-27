"""Repository for Task data persistence and state transitions."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.task import TaskContract
from app.core.enums import TaskStatus
from app.database.base import dump_json
from app.database.models.task import TaskModel
from app.security.sanitizer import SecretSanitizer


class TaskRepository:
    """Async repository for managing TaskModel persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, contract: TaskContract) -> TaskContract:
        """Insert new task record from contract."""
        model = TaskModel.from_contract(contract)
        self.session.add(model)
        await self.session.flush()
        return model.to_contract()

    async def get_task(self, task_id: str, tenant_id: Optional[str] = None) -> Optional[TaskContract]:
        """Fetch task by ID with optional tenant isolation."""
        stmt = select(TaskModel).where(TaskModel.task_id == task_id)
        if tenant_id:
            stmt = stmt.where(TaskModel.user_id == tenant_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_contract() if model else None

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        tenant_id: Optional[str] = None,
        result_summary: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Optional[TaskContract]:
        """Update lifecycle status and output payloads of a task."""
        stmt = select(TaskModel).where(TaskModel.task_id == task_id)
        if tenant_id:
            stmt = stmt.where(TaskModel.user_id == tenant_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None

        model.status = status.value if hasattr(status, "value") else str(status)
        if result_summary is not None:
            model.result_summary = SecretSanitizer.sanitize_text(result_summary)
        if result_data is not None:
            model.result_data_json = dump_json(SecretSanitizer.sanitize_dict(result_data))
        if error_message is not None:
            model.error_message = SecretSanitizer.sanitize_text(error_message)
        if workflow_id is not None:
            model.workflow_id = workflow_id
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            model.completed_at = datetime.now(timezone.utc)

        model.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return model.to_contract()

    async def list_tasks(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        status: Optional[TaskStatus] = None,
        status_filter: Optional[TaskStatus] = None,
    ) -> List[TaskContract]:
        """Fetch paginated tasks strictly scoped to tenant/user."""
        stmt = select(TaskModel)
        target_tenant = tenant_id or user_id
        if target_tenant:
            stmt = stmt.where(TaskModel.user_id == target_tenant)
        target_status = status_filter or status
        if target_status:
            status_val = target_status.value if hasattr(target_status, "value") else str(target_status)
            stmt = stmt.where(TaskModel.status == status_val)

        stmt = stmt.order_by(TaskModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_contract() for m in models]

    async def count_tasks(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> int:
        """Count total matching tasks."""
        stmt = select(func.count()).select_from(TaskModel)
        target_tenant = tenant_id or user_id
        if target_tenant:
            stmt = stmt.where(TaskModel.user_id == target_tenant)
        if status:
            status_val = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(TaskModel.status == status_val)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
