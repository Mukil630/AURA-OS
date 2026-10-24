from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from aura_agent_core.nlp_parser import parse_natural_time
from aura_agent_core.services import (
    create_reminder, cancel_reminder, list_active_reminders,
    save_to_vault, search_vault, delete_vault_item
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
