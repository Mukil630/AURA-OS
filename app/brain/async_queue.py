"""Async Task Queue & Background Worker for Long-Running Operations."""
import asyncio
import enum
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger("AsyncTaskQueue")


class TaskState(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AsyncTaskItem(BaseModel):
    task_id: str = Field(default_factory=lambda: f"async_{uuid4().hex[:8]}")
    name: str
    state: TaskState = TaskState.QUEUED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None


class AsyncTaskQueue:
    """Non-blocking in-memory task queue that executes heavy jobs in the background."""

    def __init__(self):
        self._tasks: Dict[str, AsyncTaskItem] = {}

    def submit_task(
        self,
        name: str,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        on_complete_callback: Optional[Callable[[AsyncTaskItem], Coroutine[Any, Any, None]]] = None,
    ) -> AsyncTaskItem:
        """Submits a coroutine to run in the background without blocking caller."""
        item = AsyncTaskItem(name=name, state=TaskState.QUEUED)
        self._tasks[item.task_id] = item

        asyncio.create_task(self._worker(item, coro_func, on_complete_callback))
        logger.info(f"⏳ Async Task [{item.task_id}] '{name}' submitted to background queue.")
        return item

    async def _worker(
        self,
        item: AsyncTaskItem,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        on_complete_callback: Optional[Callable[[AsyncTaskItem], Coroutine[Any, Any, None]]],
    ) -> None:
        item.state = TaskState.RUNNING
        try:
            res = await coro_func()
            item.state = TaskState.COMPLETED
            item.result = res
            item.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"✅ Async Task [{item.task_id}] '{item.name}' finished successfully.")
        except Exception as e:
            item.state = TaskState.FAILED
            item.error = str(e)
            item.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"❌ Async Task [{item.task_id}] '{item.name}' failed: {e}")

        if on_complete_callback:
            try:
                await on_complete_callback(item)
            except Exception as cb_err:
                logger.error(f"Error in on_complete_callback for {item.task_id}: {cb_err}")

    def get_task(self, task_id: str) -> Optional[AsyncTaskItem]:
        return self._tasks.get(task_id)

    def list_active_tasks(self) -> List[AsyncTaskItem]:
        return [t for t in self._tasks.values() if t.state in [TaskState.QUEUED, TaskState.RUNNING]]
