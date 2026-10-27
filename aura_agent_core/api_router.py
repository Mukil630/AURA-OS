from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from aura_agent_core.nlp_parser import parse_natural_time
from aura_agent_core.services import (
    create_reminder, cancel_reminder, list_active_reminders,
    save_to_vault, search_vault, delete_vault_item,
    get_daily_schedule_report, modify_daily_schedule_cloud,
    log_routine_completed_cloud, complete_task_cloud
)

router = APIRouter(prefix="/api", tags=["AURA-OS Core Engine"])


# ====================
# Pydantic Request Models
# ====================

class ReminderCreateRequest(BaseModel):
    task: str = Field(..., description="Reminder description or task")
    when: str = Field(..., description="Natural language date/time, e.g., '13th october 2026 at 10am', 'tomorrow 5pm', '10s'")


class VaultSaveRequest(BaseModel):
    category: str = Field(default="NOTE", description="Category: 'IDEA', 'CONVO', 'PERSONAL', 'BILLS', 'JOB'")
    title: str = Field(..., description="Short summary title")
    content: str = Field(..., description="Full text, memory details, or conversation")
    drive_link: Optional[str] = Field(default="", description="Google Drive URL for heavy files/PDFs")
    tags: Optional[str] = Field(default="", description="Comma-separated tags")


# ====================
# Reminder Endpoints
# ====================

@router.post("/reminders/add")
@router.post("/reminders/create")
async def add_reminder_endpoint(req: ReminderCreateRequest):
    """
    Parses NLP time input, saves to Turso Cloud, and schedules agent wakeup.
    """
    parsed = parse_natural_time(req.when)
    if not parsed["success"]:
        raise HTTPException(status_code=400, detail=parsed["error"])

    scheduled_iso = parsed["scheduled_iso"]
    rem_id = await create_reminder(req.task, scheduled_iso)

    return {
        "status": "success",
        "reminder_id": rem_id,
        "task": req.task,
        "scheduled_time": scheduled_iso + " IST",
        "display": parsed["display"],
        "message": "Saved to Turso Cloud DB. Will trigger and auto-delete when due!"
    }


@router.get("/reminders/list")
async def list_reminders_endpoint():
    """Returns all active reminders currently sitting in Turso Cloud"""
    reminders = await list_active_reminders()
    return {"count": len(reminders), "reminders": reminders}


@router.delete("/reminders/cancel/{reminder_id}")
async def cancel_reminder_endpoint(reminder_id: int):
    """Manually cancels and purges a reminder from Turso Cloud"""
    cancelled = await cancel_reminder(reminder_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Reminder ID not found")
    return {"status": "success", "message": f"Reminder #{reminder_id} cancelled & purged from DB"}


# ====================
# Vault Endpoints (Hybrid Memory)
# ====================

@router.post("/vault/save")
async def save_vault_endpoint(req: VaultSaveRequest):
    """
    Saves text, memories, or Google Drive file references into Turso Cloud.
    """
    vault_id = await save_to_vault(
        category=req.category,
        title=req.title,
        content=req.content,
        drive_link=req.drive_link or "",
        tags=req.tags or ""
    )
    return {
        "status": "success",
        "vault_id": vault_id,
        "category": req.category.upper(),
        "title": req.title,
        "drive_link": req.drive_link,
        "message": "Memory saved safely in Turso Cloud!"
    }


@router.get("/vault/search")
async def search_vault_endpoint(
    q: Optional[str] = Query(default="", description="Search keyword in title, content, or tags"),
    category: Optional[str] = Query(default="", description="Filter by category"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Searches memory vault across keywords, categories, and tags"""
    results = await search_vault(keyword=q, category=category, limit=limit)
    return {"count": len(results), "results": results}


@router.delete("/vault/delete/{item_id}")
async def delete_vault_endpoint(item_id: int):
    """Deletes an item from the vault"""
    deleted = await delete_vault_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return {"status": "success", "message": f"Vault item #{item_id} deleted"}


# ====================
# Request Models for Schedule & Tasks
# ====================

class ScheduleModifyRequest(BaseModel):
    block_query: str = Field(..., description="Schedule block or workout day to modify, e.g. 'gym', 'Tuesday workout'")
    new_time: Optional[str] = Field(default="", description="New timing, e.g. '08:00 PM - 09:30 PM'")
    new_activity: Optional[str] = Field(default="", description="New activity or workout split")


class RoutineLogRequest(BaseModel):
    routine_query: str = Field(..., description="Routine activity or workout completed today, e.g. 'upper body', 'gym', 'morning code'")


class TaskCompleteRequest(BaseModel):
    task_query_or_id: str = Field(..., description="Task ID or title keywords to mark as done and purge from active list")


# ====================
# Daily Schedule & Routine Endpoints (Turso Cloud DB)
# ====================

@router.get("/schedule/get")
async def get_schedule_endpoint(target_day: str = Query(default="today", description="'today', 'tomorrow', 'Monday', etc.")):
    """Retrieves 24/7 master daily schedule & workout split from Turso Cloud DB"""
    res = await get_daily_schedule_report(target_day=target_day)
    return res


@router.post("/schedule/modify")
async def modify_schedule_endpoint(req: ScheduleModifyRequest):
    """Dynamically updates daily schedule blueprint in Turso Cloud DB"""
    res = await modify_daily_schedule_cloud(
        block_query=req.block_query,
        new_time=req.new_time or "",
        new_activity=req.new_activity or ""
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@router.post("/schedule/log-routine")
async def log_routine_endpoint(req: RoutineLogRequest):
    """Marks a daily routine block or workout completed for today in Turso Cloud DB"""
    res = await log_routine_completed_cloud(req.routine_query)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


# ====================
# Task Lifecycle Endpoints (Auto-Purge & Cloud Archive)
# ====================

@router.get("/tasks/active")
async def get_active_tasks_endpoint():
    """Retrieves all pending one-off tasks from Turso Cloud DB"""
    reminders = await list_active_reminders()
    return {"count": len(reminders), "tasks": reminders}


@router.post("/tasks/complete")
async def complete_task_endpoint(req: TaskCompleteRequest):
    """Marks a one-off task as done: purges from active reminders table and archives in Cloud Vault"""
    res = await complete_task_cloud(req.task_query_or_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res

