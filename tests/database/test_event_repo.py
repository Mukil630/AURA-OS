"""Database integration tests for EventRepository."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.enums import EventSeverity, EventType
from app.database.repositories.event_repo import EventRepository


@pytest.mark.anyio
async def test_execution_event_audit_trail(test_db_session: AsyncSession):
    repo = EventRepository(test_db_session)

    evt1 = ExecutionEventContract(
        trace_id="tr_100",
        task_id="task_100",
        event_type=EventType.TASK_CREATED,
        severity=EventSeverity.INFO,
        source_component="Gateway",
        message="Task received from voice input.",
    )
    evt2 = ExecutionEventContract(
        trace_id="tr_100",
        task_id="task_100",
        event_type=EventType.STEP_COMPLETED,
        severity=EventSeverity.INFO,
        source_component="CodingAgent",
        message="CI logs fetched.",
    )

    await repo.record_event(evt1)
    await repo.record_event(evt2)

    # Query events by Task
    task_events = await repo.get_events_by_task("task_100")
    assert len(task_events) == 2
    assert task_events[0].event_type == EventType.TASK_CREATED
    assert task_events[1].event_type == EventType.STEP_COMPLETED

    # Query events by Trace
    trace_events = await repo.get_events_by_trace("tr_100")
    assert len(trace_events) == 2
