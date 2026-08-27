"""Repository for Human-in-the-Loop Approval tickets."""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.permission import ApprovalRequestContract
from app.core.enums import ApprovalState
from app.database.models.approval import ApprovalRequestModel


class ApprovalRepository:
    """Async repository for managing Human-in-the-loop tickets."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_approval_request(self, contract: ApprovalRequestContract) -> ApprovalRequestContract:
        """Create a new pending approval ticket."""
        model = ApprovalRequestModel.from_contract(contract)
        self.session.add(model)
        await self.session.flush()
        return model.to_contract()

    async def get_approval_request(self, approval_id: str, tenant_id: Optional[str] = None) -> Optional[ApprovalRequestContract]:
        """Fetch approval request by ID with optional tenant isolation."""
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.approval_id == approval_id)
        if tenant_id:
            stmt = stmt.where(ApprovalRequestModel.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return model.to_contract() if model else None

    async def decide_approval(
        self,
        approval_id: str,
        state: ApprovalState,
        approved_by: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[ApprovalRequestContract]:
        """Record human decision on a pending ticket with tenant verification."""
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.approval_id == approval_id)
        if tenant_id:
            stmt = stmt.where(ApprovalRequestModel.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None

        model.state = state.value if hasattr(state, "value") else str(state)
        model.approved_by = approved_by
        model.decided_at = datetime.now(timezone.utc)
        await self.session.flush()
        return model.to_contract()

    async def list_pending_approvals(self, task_id: Optional[str] = None, tenant_id: Optional[str] = None) -> List[ApprovalRequestContract]:
        """List all pending approval tickets filtered by tenant."""
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.state == ApprovalState.PENDING.value)
        if task_id:
            stmt = stmt.where(ApprovalRequestModel.task_id == task_id)
        if tenant_id:
            stmt = stmt.where(ApprovalRequestModel.tenant_id == tenant_id)
        stmt = stmt.order_by(ApprovalRequestModel.created_at.asc())
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]

    async def get_pending_approvals_for_task(self, task_id: str) -> List[ApprovalRequestContract]:
        """Alias for list_pending_approvals filtered by task."""
        return await self.list_pending_approvals(task_id=task_id)

    async def get_approvals_for_task(self, task_id: str) -> List[ApprovalRequestContract]:
        """List all approval tickets for a task."""
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.task_id == task_id)
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]
