"""
AURA Chatbot Hub & Multi-Modal Mobile Companion API Endpoints.
Handles chat processing, file/video/document uploads, voice synthesis, hardware telemetry, and auto-apply triggers.
"""
import os
import sys
import json
import time
import shutil
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/hub", tags=["AURA Chatbot & Mobile Hub"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
UPLOADS_DIR = os.path.join(BASE_DIR, "storage", "uploads")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "storage", "screenshots")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

class ChatMessageRequest(BaseModel):
    message: str
    user_name: Optional[str] = "Mukil"
    channel: Optional[str] = "WebHub"

class AutoApplyRequest(BaseModel):
    company: str
    role: Optional[str] = "AI Engineer"
    url: Optional[str] = None

@router.get("/status")
async def get_system_telemetry() -> Dict[str, Any]:
    """Retrieves live PC hardware status, battery, memory, and active placement state."""
    battery_level = 78
    battery_status = "Discharging"
    try:
        from tools.pc_tools import run_powershell
        ps_out = run_powershell("(Get-CimInstance -ClassName Win32_Battery).EstimatedChargeRemaining")
        if ps_out and ps_out.strip().isdigit():
            battery_level = int(ps_out.strip())
    except Exception:
        pass

    ctx_path = os.path.join(BASE_DIR, "storage", "memory", "context.json")
    ctx = {}
    if os.path.exists(ctx_path):
        try:
            with open(ctx_path, "r", encoding="utf-8") as f:
                ctx = json.load(f)
        except Exception:
            pass

    return {
        "status": "ONLINE",
        "user": "Mukil",
        "agent": "JARVIS / AURA-OS",
        "battery": {
            "percentage": battery_level,
            "status": battery_status
        },
        "drive_vault": {
            "name": "5TB Google Drive Master Vault",
            "url": "https://drive.google.com/drive/folders/1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1?usp=sharing"
        },
        "resume": {
            "filename": "MK.PDF.RESUME.pdf",
            "url": "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link"
        },
        "active_phase": ctx.get("active_phase", "Placement & Operating Plane Active"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@router.post("/chat")
async def send_chat_message(payload: ChatMessageRequest) -> Dict[str, Any]:
    """Processes user chat, voice transcript, or quick action through AgentBrain."""
    try:
        from brain.agent_brain import AgentBrain
        brain = AgentBrain()
        reply = brain.process_message(payload.message, user_name=payload.user_name)

        # Extract screenshot if present
        screenshot_url = None
        import re
        patterns = [
            r'(?:Proof Screenshot|Screenshot saved successfully at|Screenshot):\s*`?([^\s`\n\r]+\.png)`?',
            r'([A-Za-z]:\\[^\s\n\r]+\.png)',
            r'(storage[\\/]screenshots[\\/][^\s`\n\r]+\.png)',
            r'([^\s`\n\r]+apply_[^\s`\n\r]*\.png)'
        ]
        for pat in patterns:
            m = re.search(pat, reply, re.IGNORECASE)
            if m:
                cand = m.group(1).strip().strip('`')
                if os.path.exists(cand):
                    screenshot_url = f"/api/v1/hub/screenshots/{os.path.basename(cand)}"
                    break
                elif os.path.exists(os.path.join(BASE_DIR, cand)):
                    screenshot_url = f"/api/v1/hub/screenshots/{os.path.basename(cand)}"
                    break

        return {
            "reply": reply,
            "sender": "JARVIS",
            "screenshot_url": screenshot_url,
            "timestamp": time.strftime("%H:%M")
        }
    except Exception as e:
        return {
            "reply": f"Maapla, error: {str(e)}",
            "sender": "JARVIS",
            "screenshot_url": None,
            "timestamp": time.strftime("%H:%M")
        }

@router.post("/apply")
async def trigger_auto_apply(payload: AutoApplyRequest) -> Dict[str, Any]:
    """Triggers autonomous Playwright job apply, captures screenshot, and logs record."""
    try:
        from tools.career_auto_apply import CareerAutoApplyEngine
        engine = CareerAutoApplyEngine()
        res = engine.execute_auto_apply(
            company=payload.company,
            role=payload.role or "AI Engineer",
            portal_url=payload.url,
            headless=True
        )
        screenshot_filename = os.path.basename(res.get("screenshot_path", ""))
        return {
            "status": "SUCCESS",
            "company": res.get("company"),
            "role": res.get("role"),
            "summary": res.get("summary"),
            "screenshot_url": f"/api/v1/hub/screenshots/{screenshot_filename}" if screenshot_filename else None,
            "resume_attached": res.get("resume_attached"),
            "timestamp": time.strftime("%H:%M")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_multi_modal_file(
    file: UploadFile = File(...),
    file_type: str = Form("document"),
    note: Optional[str] = Form("")
) -> Dict[str, Any]:
    """Handles multi-modal file uploads: Documents, Resumes, Videos, Photos, and Audio."""
    try:
        safe_name = f"{int(time.time())}_{file.filename}"
        dest_path = os.path.join(UPLOADS_DIR, safe_name)
        with open(dest_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        size_kb = round(os.path.getsize(dest_path) / 1024, 2)
        return {
            "status": "UPLOADED",
            "filename": file.filename,
            "stored_filename": safe_name,
            "file_type": file_type,
            "size_kb": size_kb,
            "download_url": f"/api/v1/hub/uploads/{safe_name}",
            "note": note,
            "summary": f"✅ File '{file.filename}' ({size_kb} KB, {file_type}) uploaded safely to JARVIS Vault!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/screenshots/{filename}")
async def get_screenshot_file(filename: str):
    """Serves application proof screenshot images."""
    fpath = os.path.join(SCREENSHOTS_DIR, filename)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/png")
    raise HTTPException(status_code=404, detail="Screenshot not found")

@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Serves uploaded user documents, videos, and images."""
    fpath = os.path.join(UPLOADS_DIR, filename)
    if os.path.exists(fpath):
        return FileResponse(fpath)
    raise HTTPException(status_code=404, detail="File not found")
