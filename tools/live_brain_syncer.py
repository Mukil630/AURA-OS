"""
Live Brain Syncer for JARVIS Prime / Antigravity <-> AURA OS Bridge.
Extracts live working context from Antigravity session transcript, memory files,
and system vitals, compiling an actionable synchronized cognitive payload.
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("LiveBrainSyncer")

BASE_DIR = Path("C:/Users/mukil")
BRAIN_LOGS_DIR = BASE_DIR / ".gemini" / "antigravity-cli" / "brain"
JARVIS_MEMORY = BASE_DIR / "jarvis-core" / "storage" / "memory"
AURA_MEMORY = BASE_DIR / "aura-os" / "storage" / "memory"


def get_latest_conversation_dir() -> Path | None:
    """Finds the most recently modified conversation directory in brain folder."""
    if not BRAIN_LOGS_DIR.exists():
        return None
    try:
        dirs = [d for d in BRAIN_LOGS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not dirs:
            return None
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return dirs[0]
    except Exception as e:
        logger.warning(f"Error finding latest brain directory: {e}")
        return None


def extract_recent_antigravity_dialogue(limit: int = 4) -> Dict[str, Any]:
    """Reads tail of transcript.jsonl from active Antigravity session."""
    conv_dir = get_latest_conversation_dir()
    if not conv_dir:
        return {"user_prompts": [], "summary": "No active conversation transcript found."}

    transcript_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if not transcript_file.exists():
        return {"user_prompts": [], "summary": "Transcript file not created yet."}

    user_prompts = []
    actions = []

    try:
        with open(transcript_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        tail_lines = lines[-80:] if len(lines) > 80 else lines
        for line in tail_lines:
            try:
                obj = json.loads(line)
                step_type = obj.get("type")
                if step_type == "USER_INPUT":
                    content = obj.get("content", "").strip()
                    if content and not content.startswith("<CONTEXT_SUMMARY>"):
                        user_prompts.append(content[:250])
                elif step_type == "PLANNER_RESPONSE":
                    calls = obj.get("tool_calls", [])
                    if calls:
                        for c in calls:
                            name = c.get("name", "")
                            summary = c.get("args", {}).get("toolSummary", name)
                            actions.append(summary)
            except Exception:
                continue

        recent_users = user_prompts[-limit:] if len(user_prompts) > limit else user_prompts
        recent_actions = actions[-limit:] if len(actions) > limit else actions

        summary = (
            f"Latest User Requests: {', '.join(recent_users) if recent_users else 'Standby'}. "
            f"Recent AGY Actions: {', '.join(recent_actions) if recent_actions else 'Idle'}."
        )

        return {
            "conversation_id": conv_dir.name,
            "user_prompts": recent_users,
            "recent_actions": recent_actions,
            "summary": summary
        }
    except Exception as e:
        logger.warning(f"Error reading transcript: {e}")
        return {"user_prompts": [], "summary": f"Transcript read error: {e}"}


def compile_live_brain_context() -> Dict[str, Any]:
    """Compiles the full synchronized live brain context."""
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    now_iso = now_ist.strftime("%Y-%m-%d %I:%M:%S %p IST")

    # 1. System hardware vitals
    vitals = {"cpu": "N/A", "ram": "N/A", "battery": "N/A", "status": "ONLINE"}
    try:
        import psutil
        batt = psutil.sensors_battery()
        batt_str = f"{batt.percent:.0f}%" if batt else "N/A"
        batt_plug = "Charging" if (batt and batt.power_plugged) else "On Battery"
        vitals = {
            "cpu": f"{psutil.cpu_percent(interval=None):.1f}%",
            "ram": f"{psutil.virtual_memory().percent:.1f}%",
            "battery": f"{batt_str} ({batt_plug})",
            "status": "ONLINE_ACTIVE"
        }
    except Exception:
        pass

    # 2. Antigravity live transcript extraction
    convo = extract_recent_antigravity_dialogue()

    # 3. Voice config
    locked_voice = "STARK (Tony Stark Brotherly Tanglish Slang)"
    voice_cfg = JARVIS_MEMORY / "voice_config.json"
    if voice_cfg.exists():
        try:
            with open(voice_cfg, "r", encoding="utf-8") as f:
                vdata = json.load(f)
                locked_voice = vdata.get("active_voice", locked_voice)
        except Exception:
            pass

    # 4. Living task ledger
    open_tasks = []
    ledger_file = JARVIS_MEMORY / "living_task_ledger.json"
    if ledger_file.exists():
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                ldata = json.load(f)
                open_tasks = [t.get("title", "") for t in ldata.get("tasks", []) if t.get("status") != "COMPLETED"][:5]
        except Exception:
            pass

    # 5. Active context focus
    recent_focus = "Dual-Brain Synchronization & Multi-Angle Autonomous Self-Healing"
    ctx_file = JARVIS_MEMORY / "context.json"
    if ctx_file.exists():
        try:
            with open(ctx_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                recent_focus = cdata.get("recent_focus", recent_focus)
        except Exception:
            pass

    payload = {
        "timestamp": now_iso,
        "source": "ANTIGRAVITY_PRIME_PC",
        "active_mission": recent_focus,
        "locked_voice_persona": locked_voice,
        "recent_user_prompts": convo.get("user_prompts", []),
        "recent_actions": convo.get("recent_actions", []),
        "recent_dialogue_summary": convo.get("summary", ""),
        "last_decisions": (
            "1. Three Gemini native voices locked permanently: STARK (default), CHARON, FENRIR.\n"
            "2. Render Cloud <-> PC Worker inter-process loopback active via HTTP 127.0.0.1:PORT.\n"
            "3. Live Brain Context synchronization streams AGY session state to Cloud AURA every 15s."
        ),
        "open_tasks": open_tasks,
        "hardware_vitals": vitals
    }

    # Persist locally to jarvis-core and aura-os
    for mem_dir in [JARVIS_MEMORY, AURA_MEMORY]:
        try:
            mem_dir.mkdir(parents=True, exist_ok=True)
            out_file = mem_dir / "agy_live_context.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as pe:
            logger.warning(f"Could not write agy_live_context to {mem_dir}: {pe}")

    return payload


if __name__ == "__main__":
    ctx = compile_live_brain_context()
    print("LIVE BRAIN CONTEXT COMPILED:")
    print(json.dumps(ctx, indent=2))
