"""
AURA Reactive Background Task Manager
File: aura/kernel/task_manager.py
Reverse-engineered from Google Antigravity (AGY) Background Task Engine:
- Runs long-running jobs (scrapers, exports, cloud sync) asynchronously.
- Assigns unique Task IDs.
- Provides non-blocking execution with reactive completion events.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Callable


class AsyncTaskRecord:
    def __init__(self, task_id: str, name: str, description: str):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.status = "RUNNING"
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.result: Any = None
        self.error: Optional[str] = None

    def complete(self, result: Any):
        self.status = "COMPLETED"
        self.end_time = time.time()
        self.result = result

    def fail(self, error: str):
        self.status = "FAILED"
        self.end_time = time.time()
        self.error = error

    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)


class BackgroundTaskManager:
    def __init__(self):
        self.tasks: Dict[str, AsyncTaskRecord] = {}
        self.notification_queue: List[str] = []

    def spawn_task(self, name: str, description: str, coro_fn: Callable[..., Any], *args, **kwargs) -> str:
        """Spawns an async task in the background and returns its Task ID."""
        task_id = f"TASK-{uuid.uuid4().hex[:6].upper()}"
        record = AsyncTaskRecord(task_id, name, description)
        self.tasks[task_id] = record

        async def _runner():
            try:
                res = await coro_fn(*args, **kwargs)
                record.complete(res)
                self.notification_queue.append(
                    f"🔔 [Background Event] Task #{task_id} ('{name}') COMPLETED in {record.duration_seconds()}s!"
                )
            except Exception as e:
                record.fail(str(e))
                self.notification_queue.append(
                    f"⚠️ [Background Event] Task #{task_id} ('{name}') FAILED: {str(e)}"
                )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_runner())
            else:
                loop.run_until_complete(_runner())
        except RuntimeError:
            asyncio.run(_runner())

        return task_id

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Returns status of all active and completed background tasks."""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "status": t.status,
                "duration": f"{t.duration_seconds()}s",
                "has_error": bool(t.error)
            }
            for t in self.tasks.values()
        ]

    def pop_notifications(self) -> List[str]:
        """Pops and returns all pending background completion notifications."""
        notes = list(self.notification_queue)
        self.notification_queue.clear()
        return notes


# Global Task Manager Singleton
task_manager = BackgroundTaskManager()
