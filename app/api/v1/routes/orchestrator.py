"""
AURA-OS Central Cognitive Orchestrator API Router.
app/api/v1/routes/orchestrator.py
Direct REST interface to the Gemini-powered Central Orchestrator & Durable Task Lifecycle.
"""
import os
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.orchestrator.central_orchestrator import central_orchestrator
from app.services.durable_task_manager import durable_task_manager

router = APIRouter(prefix="/orchestrator", tags=["AURA-OS Central Cognitive Orchestrator"])


class ProcessRequestPayload(BaseModel):
    message: str
    user_id: Optional[str] = "mukil"
    channel: Optional[str] = "MOBILE_APP"
    chat_id: Optional[int] = None


class TaskStatusUpdatePayload(BaseModel):
    status: str
    result_summary: Optional[str] = None


@router.post("/process")
async def process_orchestrator_request(payload: ProcessRequestPayload) -> Dict[str, Any]:
    """Processes user voice transcript or text command through Central Cognitive Orchestrator."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        result = central_orchestrator.process_request(
            raw_message=payload.message,
            user_id=payload.user_id or "mukil",
            channel=payload.channel or "MOBILE_APP",
            chat_id=payload.chat_id
        )
        # Generate neural audio voice file for mobile playback
        audio_url = None
        try:
            from tools.tts_generator import generate_voice_audio
            speech = result.get("speech_reply") or result.get("reply") or ""
            if speech:
                voice_file = await generate_voice_audio(speech)
                if voice_file and os.path.exists(voice_file):
                    fname = os.path.basename(voice_file)
                    audio_url = f"/api/voice/stream/{fname}"
        except Exception as ve:
            pass

        return {
            "status": "success",
            "task_id": result.get("task_id"),
            "intent": result.get("intent"),
            "task_status": result.get("status"),
            "reply": result.get("reply"),
            "speech_reply": result.get("speech_reply"),
            "audio_url": audio_url,
            "duration_ms": result.get("duration_ms"),
            "execution_result": result.get("execution_result"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failure: {str(e)}")


@router.get("/tasks")
async def list_orchestrator_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100)
) -> List[Dict[str, Any]]:
    """Lists persistent tasks from SQLite Durable Task Manager."""
    tasks = durable_task_manager.list_tasks(status=status_filter, limit=limit)
    return tasks


@router.get("/tasks/{task_id}")
async def get_orchestrator_task(task_id: str) -> Dict[str, Any]:
    """Retrieves a single task record by task ID."""
    task = durable_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/complete")
async def mark_task_complete(task_id: str, payload: TaskStatusUpdatePayload) -> Dict[str, Any]:
    """Marks a task as completed or updates its status."""
    updated = durable_task_manager.update_task_status(
        task_id=task_id,
        status=payload.status,
        result_summary=payload.result_summary
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found or could not be updated")
    return {"status": "success", "task_id": task_id, "new_status": payload.status}
