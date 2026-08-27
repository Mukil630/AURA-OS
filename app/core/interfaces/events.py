"""Abstract Interface definitions for Event Bus and Execution Auditing."""
from abc import ABC, abstractmethod
from typing import Callable, Coroutine, List, Optional

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.enums import EventType


class IEventBus(ABC):
    """
    Abstract interface for publishing and subscribing to system lifecycle events.
    """
    @abstractmethod
    async def publish(self, event: ExecutionEventContract) -> None:
        """Publish an execution event to the event stream."""
        pass

    @abstractmethod
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[ExecutionEventContract], Coroutine],
    ) -> None:
        """Subscribe an async handler to a specific event type."""
        pass


class IExecutionAuditor(ABC):
    """
    Abstract interface for persistent recording and querying of audit logs and traces.
    """
    @abstractmethod
    async def record_event(self, event: ExecutionEventContract) -> None:
        """Store an immutable audit event record."""
        pass

    @abstractmethod
    async def get_task_timeline(self, task_id: str) -> List[ExecutionEventContract]:
        """Fetch all chronological events associated with a Task ID."""
        pass

    @abstractmethod
    async def get_events_by_trace(self, trace_id: str) -> List[ExecutionEventContract]:
        """Fetch all chronological events belonging to a distributed Trace ID."""
        pass
