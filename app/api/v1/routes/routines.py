"""
AURA-OS Cloud Routine & Morning Intel API Routes
app/api/v1/routes/routines.py
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from app.services.cloud_routine_engine import cloud_routine_engine

router = APIRouter(prefix="/routines", tags=["Cloud Routines & Daily Alarms"])

IST_TZ = timezone(timedelta(hours=5, minutes=30))
EXPECTED_SECRET = os.getenv("PC_BRIDGE_SECRET", "mukil-aura-pc-bridge-secret-2026")


def verify_secret(secret: Optional[str], header_secret: Optional[str]):
    token = secret or header_secret
    if not token or token.strip() != EXPECTED_SECRET.strip():
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid AURA Secret")


class UpdateScheduleRequest(BaseModel):
    routine_id: str
    target_time: str  # Format: "HH:MM" e.g. "06:00"
    enabled: Optional[bool] = None


@router.get("/status")
def get_routines_status():
    """Returns the live blueprint, execution timestamps, and current IST time."""
    bp = cloud_routine_engine.load_blueprint()
    now_ist = datetime.now(IST_TZ)
    return {
        "status": "RUNNING_24_7",
        "current_time_ist": now_ist.strftime("%Y-%m-%d %I:%M:%S %p IST"),
        "timezone": "Asia/Kolkata",
        "routines": bp.get("routines", [])
    }


@router.post("/trigger/{routine_id}")
def trigger_routine(
    routine_id: str,
    secret: Optional[str] = Query(None),
    x_aura_secret: Optional[str] = Header(None, alias="X-Aura-Secret"),
    dispatch_audio: bool = Query(True)
):
    """
    Webhook Trigger Endpoint for external Cloud Cron services (e.g. cron-job.org, GitHub Actions, UptimeRobot).
    Instantly wakes Render from sleep, synthesizes Gemini voice, and delivers to Telegram!
    """
    verify_secret(secret, x_aura_secret)
    res = cloud_routine_engine.execute_routine(routine_id, dispatch_audio=dispatch_audio, force_run=True)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to trigger routine"))
    return res


@router.post("/schedule")
def update_routine_schedule(
    req: UpdateScheduleRequest,
    secret: Optional[str] = Query(None),
    x_aura_secret: Optional[str] = Header(None, alias="X-Aura-Secret")
):
    """Dynamically updates any routine timing without redeploying code."""
    verify_secret(secret, x_aura_secret)
    res = cloud_routine_engine.update_schedule(req.routine_id, req.target_time, req.enabled)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res
