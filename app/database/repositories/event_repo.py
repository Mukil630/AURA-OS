"""Repository for ExecutionEvent audit logs and telemetry persistence."""
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.execution_event import ExecutionEventContract
from app.database.models.event import ExecutionEventModel
from app.security.sanitizer import SecretSanitizer


class EventRepository:
    """Async repository for recording and querying execution events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(self, event: ExecutionEventContract) -> ExecutionEventContract:
        """Insert immutable audit event with guaranteed secret redaction."""
        clean_msg = SecretSanitizer.sanitize_text(event.message)
        clean_payload = SecretSanitizer.sanitize_dict(event.payload) if event.payload else None

        clean_contract = event.model_copy(
            update={
                "message": clean_msg,
                "payload": clean_payload,
            }
        )

        model = ExecutionEventModel.from_contract(clean_contract)
        self.session.add(model)
        await self.session.flush()
        return model.to_contract()

    async def get_events_by_task(self, task_id: str) -> List[ExecutionEventContract]:
        """Fetch all events belonging to a task in chronological order."""
        stmt = (
            select(ExecutionEventModel)
            .where(ExecutionEventModel.task_id == task_id)
            .order_by(ExecutionEventModel.timestamp.asc())
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]

    async def get_events_by_trace(self, trace_id: str) -> List[ExecutionEventContract]:
        """Fetch all events spanning a distributed trace."""
        stmt = (
            select(ExecutionEventModel)
            .where(ExecutionEventModel.trace_id == trace_id)
            .order_by(ExecutionEventModel.timestamp.asc())
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]

    async def list_events(self, limit: int = 50) -> List[ExecutionEventContract]:
        """Fetch recent execution events."""
        stmt = (
            select(ExecutionEventModel)
            .order_by(ExecutionEventModel.timestamp.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]
