"""
PC Remote Control & Heavyweight Project Execution API for AURA-OS.
Allows phone and cloud to trigger terminal commands, build projects, capture telemetry, and control hardware.
"""
import os
import sys
import json
import time
import subprocess
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/pc", tags=["PC Remote Hardware & Project Builder"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

class TerminalCommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout_sec: Optional[int] = 60

class HardwareActionRequest(BaseModel):
    action: str  # lock, screenshot, brightness, volume, battery, launch_app
    param: Optional[Any] = None

class ProjectBuildRequest(BaseModel):
    project_path: str
    build_command: Optional[str] = "npm run build"  # or "pytest", "python main.py"

@router.post("/execute_command")
async def execute_terminal_command(payload: TerminalCommandRequest) -> Dict[str, Any]:
    """Executes a terminal or PowerShell command on the PC and returns output logs."""
    target_cwd = payload.cwd or BASE_DIR
    if not os.path.exists(target_cwd):
        target_cwd = BASE_DIR

    logger_cmd = payload.command.strip()
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", payload.command],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=payload.timeout_sec or 60
        )
        return {
            "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
            "command": logger_cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "timestamp": time.strftime("%H:%M:%S")
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "command": logger_cmd,
            "error": f"Command timed out after {payload.timeout_sec} seconds."
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "command": logger_cmd,
            "error": str(e)
        }

@router.post("/control")
async def execute_hardware_action(payload: HardwareActionRequest) -> Dict[str, Any]:
    """Controls physical hardware: Screen lock, volume, brightness, screenshots, app launching."""
    from tools import pc_tools

    action = payload.action.lower()
    res = {}

    if action == "lock":
        msg = pc_tools.lock_workstation()
        res = {"action": "lock", "result": msg}
    elif action == "screenshot":
        msg = pc_tools.take_pc_screenshot()
        res = {"action": "screenshot", "result": msg}
    elif action == "battery":
        out = pc_tools.run_powershell("Get-CimInstance -ClassName Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json")
        res = {"action": "battery", "result": out}
    elif action == "brightness":
        level = int(payload.param) if payload.param is not None else 80
        msg = pc_tools.set_screen_brightness(level)
        res = {"action": "brightness", "level": level, "result": msg}
    elif action == "volume":
        level = int(payload.param) if payload.param is not None else 50
        msg = pc_tools.set_system_volume(level)
        res = {"action": "volume", "level": level, "result": msg}
    elif action == "launch_app":
        app_name = str(payload.param or "chrome")
        if "chrome" in app_name.lower():
            msg = pc_tools.open_browser_url("https://google.com")
        elif "youtube" in app_name.lower():
            msg = pc_tools.play_youtube_song("lofi beats")
        else:
            msg = pc_tools.run_powershell(f"Start-Process '{app_name}'")
        res = {"action": "launch_app", "app": app_name, "result": msg}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown hardware action: {action}")

    return {
        "status": "SUCCESS",
        "timestamp": time.strftime("%H:%M:%S"),
        **res
    }

@router.post("/build_project")
async def trigger_project_build(payload: ProjectBuildRequest) -> Dict[str, Any]:
    """Runs project build, test suites, and generates live compilation logs."""
    target_path = payload.project_path
    if not os.path.isabs(target_path):
        target_path = os.path.join(r"C:\Users\mukil", target_path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"Project path not found: {target_path}")

    build_cmd = payload.build_command or "npm run build"
    start_time = time.time()

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", build_cmd],
            cwd=target_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        elapsed = round(time.time() - start_time, 2)
        success = proc.returncode == 0
        return {
            "status": "BUILD_SUCCESS" if success else "BUILD_FAILED",
            "project_path": target_path,
            "command": build_cmd,
            "duration_sec": elapsed,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "summary": f"Project build {'completed successfully' if success else 'failed'} in {elapsed}s."
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "project_path": target_path,
            "error": str(e)
        }
