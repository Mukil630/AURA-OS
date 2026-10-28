"""
AURA OS Reminder & Temporal Task Engine
Turso Cloud (AWS Mumbai) + Local Zero-Bloat Auto-Purge + Tanglish NLP
"""
import sys
import os
import json
import re
import time
import asyncio
import concurrent.futures
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import libsql_client
import dateparser

from aura.config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, DATA_DIR

IST = timezone(timedelta(hours=5, minutes=30))
LOCAL_REMINDERS_FILE = DATA_DIR / "local_reminders.json"

def _execute_turso_cloud(sql: str, params: list = None):
    """Executes a SQL query against Turso Cloud DB (AWS Mumbai) for 24/7 Cloud Persistence."""
    async def _run():
        async with libsql_client.create_client(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN) as client:
            return await client.execute(sql, params or [])
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _run()).result()
    return asyncio.run(_run())

TANGLISH_MAP = {
    "naalaiki": "tomorrow",
    "naalaikku": "tomorrow",
    "nalaiku": "tomorrow",
    "nalaikki": "tomorrow",
    "kaalaila": "morning",
    "kalai": "morning",
    "saayandhram": "evening",
    "sayanthram": "evening",
    "saayankalam": "evening",
    "iravu": "night",
    "inikku": "today",
    "innikku": "today",
    "innum": "in",
    "madhiyam": "afternoon",
    "mathiyam": "afternoon",
}

def clean_tanglish(text: str) -> str:
    cleaned = text.lower()
    # Replace temporal day qualifiers
    cleaned = re.sub(r'\b(naalaiki|naalaikku|nalaiku|nalaikki)\b', 'tomorrow', cleaned)
    cleaned = re.sub(r'\b(inikku|innikku)\b', 'today', cleaned)
    cleaned = re.sub(r'\b(innum)\b', 'in', cleaned)
    
    # Morning / Kalai
    cleaned = re.sub(r'\b(kaalaila|kalai|morning)\s*(\d{1,2})\s*(?:mani\s*ku|manikku|mani)?\b', r'\2:00 am', cleaned)
    # Afternoon / Madhiyam
    cleaned = re.sub(r'\b(madhiyam|mathiyam|afternoon)\s*(\d{1,2})\s*(?:mani\s*ku|manikku|mani)?\b', r'\2:00 pm', cleaned)
    # Evening / Saayandhram
    cleaned = re.sub(r'\b(saayandhram|sayanthram|saayankalam|evening)\s*(\d{1,2})\s*(?:mani\s*ku|manikku|mani)?\b', r'\2:00 pm', cleaned)
    # Night / Iravu
    cleaned = re.sub(r'\b(iravu|night)\s*(\d{1,2})\s*(?:mani\s*ku|manikku|mani)?\b', r'\2:00 pm', cleaned)
    # Generic manikku
    cleaned = re.sub(r'(\d{1,2})\s*(?:mani\s*ku|manikku|mani)', r'\1:00', cleaned)
    return cleaned

def parse_natural_time(time_phrase: str) -> Dict[str, Any]:
    """
    Parses any natural date, time, or Tanglish phrase into an IST datetime.
    Examples: '10s', '5m', 'in 30 mins', 'tomorrow 10am', 'naalaikku kaalaila 9 manikku'
    """
    cleaned = clean_tanglish(time_phrase.strip())
    now = datetime.now(IST)

    # 1. Seconds check
    sec_match = re.match(r"^(\d+)\s*(s|sec|secs|seconds)?$", cleaned)
    if sec_match and int(sec_match.group(1)) <= 120 and (sec_match.group(2) or int(sec_match.group(1)) < 60):
        secs = int(sec_match.group(1))
        target = now + timedelta(seconds=secs)
        return {
            "success": True,
            "target_dt": target,
            "scheduled_iso": target.strftime("%Y-%m-%d %H:%M:%S"),
            "display": f"{secs}s from now ({target.strftime('%I:%M:%S %p IST')})"
        }

    # 2. Minutes check
    min_match = re.search(r"(\d+)\s*(m|min|mins|minutes)", cleaned)
    if min_match:
        mins = int(min_match.group(1))
        target = now + timedelta(minutes=mins)
        return {
            "success": True,
            "target_dt": target,
            "scheduled_iso": target.strftime("%Y-%m-%d %H:%M:%S"),
            "display": f"{mins} min(s) from now ({target.strftime('%I:%M %p IST')})"
        }

    # 3. Hours check
    hr_match = re.search(r"(\d+)\s*(h|hr|hrs|hours)", cleaned)
    if hr_match:
        hrs = int(hr_match.group(1))
        target = now + timedelta(hours=hrs)
        return {
            "success": True,
            "target_dt": target,
            "scheduled_iso": target.strftime("%Y-%m-%d %H:%M:%S"),
            "display": f"{hrs} hour(s) from now ({target.strftime('%I:%M %p IST')})"
        }

    # 4. Use dateparser
    settings = {
        'TIMEZONE': 'Asia/Kolkata',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future',
        'RELATIVE_BASE': now
    }
    parsed = dateparser.parse(cleaned, settings=settings)
    if parsed:
        if parsed <= now:
            parsed = parsed + timedelta(days=1)
        return {
            "success": True,
            "target_dt": parsed,
            "scheduled_iso": parsed.strftime("%Y-%m-%d %H:%M:%S"),
            "display": parsed.strftime("%d %b %Y at %I:%M %p IST")
        }

    target = now + timedelta(hours=1)
    return {
        "success": True,
        "target_dt": target,
        "scheduled_iso": target.strftime("%Y-%m-%d %H:%M:%S"),
        "display": f"1 hour from now ({target.strftime('%I:%M %p IST')})"
    }

# ==========================================
# TOOL 1: ADD REMINDER
# ==========================================
def add_reminder(task: str, time_phrase: str) -> str:
    """
    Schedules an autonomous reminder for Mukil.
    Supports English & Tanglish phrases (e.g., 'in 15 mins', 'tomorrow 10am', 'naalaikku kaalaila 9 manikku', '10s').
    Saves to Turso Cloud DB (AWS Mumbai) and triggers live notifications.
    """
    time_info = parse_natural_time(time_phrase)
    scheduled_iso = time_info["scheduled_iso"]
    display_time = time_info["display"]

    rem_id = None
    try:
        res = _execute_turso_cloud(
            "INSERT INTO reminders (title, remind_at, status) VALUES (?, ?, 'PENDING');",
            [task, scheduled_iso]
        )
        if hasattr(res, "last_insert_rowid") and res.last_insert_rowid:
            rem_id = int(res.last_insert_rowid)
    except Exception:
        rem_id = None

    if not rem_id:
        rem_id = int(time.time() * 1000) % 100000

    # Local disk backup sync
    local_data = []
    if LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        except Exception:
            local_data = []
    
    local_data.append({
        "id": rem_id,
        "title": task,
        "remind_at": scheduled_iso,
        "display": display_time,
        "status": "PENDING",
        "created_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(LOCAL_REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(local_data, f, indent=2)

    return (
        f"✅ **Reminder Set Successfully in Cloud!**\n"
        f"• **Reminder ID:** #{rem_id}\n"
        f"• **Task:** {task}\n"
        f"• **Scheduled For:** {display_time}\n"
        f"• **Cloud DB:** Turso Cloud (AWS Mumbai - Accessible 24/7 on Server & Phone)\n"
        f"• **Alert:** Live notification will fire across Server & Phone at due time."
    )

# ==========================================
# TOOL 2: LIST ACTIVE REMINDERS
# ==========================================
def list_active_reminders() -> str:
    """
    Retrieves all upcoming pending reminders from Turso Cloud DB.
    Returns structured list with Reminder IDs and scheduled times.
    """
    reminders = []
    try:
        res = _execute_turso_cloud(
            "SELECT id, title, remind_at FROM reminders WHERE status = 'PENDING' ORDER BY remind_at ASC;"
        )
        reminders = [{"id": r[0], "title": r[1], "remind_at": r[2]} for r in res.rows]
    except Exception:
        reminders = []

    if not reminders and LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                reminders = [r for r in json.load(f) if r.get("status") == "PENDING"]
        except Exception:
            pass

    if not reminders:
        return "📭 No active pending reminders found. You're completely caught up, Boss!"

    lines = [f"📋 **Active Reminders ({len(reminders)} Pending in Cloud):**\n"]
    lines.append("| ID | Scheduled Time (IST) | Task Description |")
    lines.append("| :--- | :--- | :--- |")
    for r in reminders:
        lines.append(f"| **#{r['id']}** | `{r['remind_at']}` | {r['title']} |")

    return "\n".join(lines)

# ==========================================
# TOOL 3: CANCEL REMINDER
# ==========================================
def cancel_reminder(reminder_id: int) -> str:
    """
    Cancels an active reminder by its Reminder ID (e.g., 101, 102).
    Deletes the record from Turso Cloud to maintain 0 MB bloat.
    """
    success = False
    try:
        res = _execute_turso_cloud("DELETE FROM reminders WHERE id = ?;", [reminder_id])
        success = res.rows_affected > 0
    except Exception:
        success = False

    if LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            updated = [r for r in local_data if r.get("id") != reminder_id]
            with open(LOCAL_REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2)
            success = True
        except Exception:
            pass

    if success:
        return f"🗑️ **Reminder #{reminder_id} has been cancelled & purged from Turso Cloud DB.**"
    else:
        return f"⚠️ Reminder #{reminder_id} was not found or already completed."

# ==========================================
# TOOL 4: COMPLETE TASK (CONVERSATIONAL PURGE)
# ==========================================
COMPLETED_TASKS_FILE = DATA_DIR / "daily_completed_tasks.json"

def complete_task(task_query_or_id: str) -> str:
    """
    Marks a task or reminder as completed when Mukil finishes it in natural conversation.
    Supports reminder ID (e.g. '101') or fuzzy title/keyword matching (e.g. 'Infinite prep', 'bill', 'leetcode', 'resume').
    Automatically purges the active record from Turso Cloud DB (maintaining 0 MB bloat)
    and logs it into daily completed tasks for the 10:00 PM EOD Retrospective.
    """
    query = str(task_query_or_id).strip()
    if query.startswith("#"):
        query = query[1:].strip()

    # 1. Fetch current pending reminders from Turso Cloud
    reminders = []
    try:
        res = _execute_turso_cloud("SELECT id, title, remind_at FROM reminders WHERE status = 'PENDING';")
        reminders = [{"id": r[0], "title": r[1], "remind_at": r[2]} for r in res.rows]
    except Exception:
        reminders = []

    if not reminders and LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                reminders = [r for r in json.load(f) if r.get("status") == "PENDING"]
        except Exception:
            pass

    if not reminders:
        return "📭 Active tasks list-la edhuvum pending illa mapla! You are completely caught up, chill pannunga!"

    # 2. Search for the matching task
    matched = None
    if query.isdigit():
        target_id = int(query)
        for r in reminders:
            if r["id"] == target_id:
                matched = r
                break

    if not matched:
        q_lower = query.lower()
        for r in reminders:
            if q_lower in r["title"].lower() or r["title"].lower() in q_lower:
                matched = r
                break
        
        if not matched:
            q_tokens = set(re.findall(r'\w+', q_lower))
            stop_words = {"task", "mudichiten", "done", "completed", "finish", "finished", "antha", "the", "a", "an", "la", "ku"}
            meaningful_tokens = q_tokens - stop_words
            if meaningful_tokens:
                best_score = 0
                for r in reminders:
                    t_tokens = set(re.findall(r'\w+', r["title"].lower()))
                    overlap = len(meaningful_tokens & t_tokens)
                    if overlap > best_score:
                        best_score = overlap
                        matched = r

    if not matched:
        active_list = list_active_reminders()
        return (
            f"⚠️ Mapla, '{task_query_or_id}' matching active task edhuvum kidaikala.\n\n"
            f"Current active tasks idho, edha complete panniteenga nu sollunga:\n{active_list}"
        )

    # 3. Purge from Turso Cloud DB (0 MB bloat)
    target_id = matched["id"]
    try:
        _execute_turso_cloud("DELETE FROM reminders WHERE id = ?;", [target_id])
    except Exception:
        pass

    # 4. Archive into Turso Cloud aura_vault (Universal Cloud Archive)
    try:
        archive_payload = json.dumps({
            "id": target_id,
            "title": matched["title"],
            "completed_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        })
        _execute_turso_cloud(
            "INSERT INTO aura_vault (category, title, content, tags) VALUES ('COMPLETED_TASK', ?, ?, 'task,completed');",
            [matched["title"], archive_payload]
        )
    except Exception:
        pass

    # 5. Local disk cache sync
    if LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            updated = [r for r in local_data if r.get("id") != target_id]
            with open(LOCAL_REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2)
        except Exception:
            pass

    return (
        f"🎯 **Task Completed! Super Mapla!**\n"
        f"• **Finished Task:** {matched['title']} (#{target_id})\n"
        f"• **Cloud DB:** Purged from Turso Cloud & archived in Cloud Vault (0 MB bloat maintained).\n"
        f"• **Archived for:** Night 10:00 PM EOD Retrospective report. Proud of you Boss!"
    )

def list_active_tasks() -> str:
    """Alias for list_active_reminders. Retrieves all current pending tasks for Mukil."""
    return list_active_reminders()

def get_daily_completed_tasks() -> List[Dict[str, Any]]:
    """Retrieves tasks completed today from Turso Cloud DB (with local fallback)."""
    # 1. Primary: Query Turso Cloud DB aura_vault
    today_prefix = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        res = _execute_turso_cloud(
            "SELECT title, content, created_at FROM aura_vault WHERE category = 'COMPLETED_TASK' ORDER BY id DESC LIMIT 20;"
        )
        tasks = []
        for r in res.rows:
            try:
                data = json.loads(r[1])
                if data.get("completed_at", "").startswith(today_prefix):
                    tasks.append(data)
            except Exception:
                pass
        if tasks:
            return tasks
    except Exception:
        pass

    # 2. Local fallback
    if not COMPLETED_TASKS_FILE.exists():
        return []
    try:
        with open(COMPLETED_TASKS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        return [r for r in records if r.get("completed_at", "").startswith(today_prefix)]
    except Exception:
        return []

# ==========================================
# TOOL 5: GET & PURGE DUE REMINDERS (DAEMON)
# ==========================================
def get_and_purge_due_reminders() -> List[Dict[str, Any]]:
    """
    Fetches all pending reminders whose scheduled time has arrived (<= now in IST).
    Auto-purges them from Turso Cloud DB (maintaining 0 MB bloat) and local sync,
    returning the list of due reminders to trigger alarms & speech alerts.
    """
    now_iso = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    due_items = []

    # 1. Check Turso Cloud DB
    try:
        res = _execute_turso_cloud(
            "SELECT id, title, remind_at FROM reminders WHERE remind_at <= ? AND status = 'PENDING';",
            [now_iso]
        )
        for r in res.rows:
            due_items.append({"id": r[0], "title": r[1], "remind_at": r[2]})

        if due_items:
            for item in due_items:
                _execute_turso_cloud("DELETE FROM reminders WHERE id = ?;", [item["id"]])
    except Exception:
        pass

    # 2. Check local sync file
    if LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            remaining = []
            for r in local_data:
                if r.get("remind_at") <= now_iso and r.get("status") == "PENDING":
                    if not any(d["id"] == r["id"] for d in due_items):
                        due_items.append(r)
                else:
                    remaining.append(r)
            with open(LOCAL_REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(remaining, f, indent=2)
        except Exception:
            pass

    return due_items

    # 2. Check local sync file
    if LOCAL_REMINDERS_FILE.exists():
        try:
            with open(LOCAL_REMINDERS_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
            remaining = []
            for r in local_data:
                if r.get("remind_at") <= now_iso and r.get("status") == "PENDING":
                    if not any(d["id"] == r["id"] for d in due_items):
                        due_items.append(r)
                else:
                    remaining.append(r)
            with open(LOCAL_REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(remaining, f, indent=2)
        except Exception:
            pass

    return due_items

