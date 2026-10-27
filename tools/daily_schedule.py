"""
AURA Cloud Daily Schedule & Habit Tools for jarvis-core
File: tools/daily_schedule.py
Synchronous wrappers around aura_agent_core.services for agent & tool execution.
Backed 100% by Turso Cloud DB (AWS Mumbai) for 24/7 cloud persistence.
"""

import asyncio
import concurrent.futures
from typing import Dict, Any, Optional

from tools.registry import aura_tool
from aura_agent_core.services import (
    get_daily_schedule_report,
    modify_daily_schedule_cloud,
    log_routine_completed_cloud,
    complete_task_cloud,
    list_active_reminders
)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@aura_tool(name="get_daily_schedule", category="schedule", description="Retrieves Mukil's master daily schedule, workout split, and completion status from Turso Cloud DB.")
def get_daily_schedule(target_day: str = "today") -> str:
    """
    Retrieves the complete Daily Schedule Routine & Time Blocks for Mukil from Turso Cloud DB.
    target_day: 'today', 'tomorrow', 'Monday', 'Tuesday', etc. (Defaults to 'today').
    """
    res = _run_async(get_daily_schedule_report(target_day=target_day))
    return res.get("formatted_markdown", "Unable to load schedule from cloud.")


@aura_tool(name="log_routine_completed", category="schedule", description="Marks a daily recurring routine or workout (e.g. 'gym', 'upper body') as completed for today in Turso Cloud DB.")
def log_routine_completed(routine_query: str) -> str:
    """
    Marks a recurring daily schedule block or workout as COMPLETED for today in Turso Cloud DB.
    Does NOT delete the routine from future days!
    """
    res = _run_async(log_routine_completed_cloud(routine_query=routine_query))
    return res.get("message", "Routine logged.")


@aura_tool(name="modify_daily_schedule", category="schedule", description="Dynamically modifies Mukil's daily schedule blueprint or workout split in Turso Cloud DB.")
def modify_daily_schedule(block_query: str, new_time: str = "", new_activity: str = "") -> str:
    """
    Modifies schedule timing or activities in Turso Cloud DB.
    Examples:
    - modify_daily_schedule(block_query="gym", new_time="08:00 PM - 09:30 PM")
    - modify_daily_schedule(block_query="Tuesday workout", new_activity="Chest & Triceps")
    """
    res = _run_async(modify_daily_schedule_cloud(block_query=block_query, new_time=new_time, new_activity=new_activity))
    return res.get("message", "Schedule updated.")


@aura_tool(name="complete_task", category="tasks", description="Marks a one-off task as done. Purges it from Turso Cloud active reminders table and archives in Cloud Vault.")
def complete_task(task_query_or_id: str) -> str:
    """
    Marks a one-off action task as completed by task ID or keywords.
    Purges from active reminders (0 MB bloat) and archives in Turso Cloud Vault.
    """
    res = _run_async(complete_task_cloud(task_query_or_id=task_query_or_id))
    return res.get("message", "Task completed.")


@aura_tool(name="list_active_tasks", category="tasks", description="Lists all pending one-off action tasks and reminders from Turso Cloud DB.")
def list_active_tasks() -> str:
    """Retrieves all pending one-off tasks from Turso Cloud DB."""
    reminders = _run_async(list_active_reminders())
    if not reminders:
        return "📭 No active pending tasks in Turso Cloud DB. You're all caught up, Boss!"
    lines = [f"📋 **Active Tasks ({len(reminders)} Pending in Cloud DB):**\n"]
    lines.append("| ID | Scheduled Time (IST) | Task Description |")
    lines.append("| :--- | :--- | :--- |")
    for r in reminders:
        lines.append(f"| **#{r['id']}** | `{r['remind_at']}` | {r['title']} |")
    return "\n".join(lines)
