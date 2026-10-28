"""
AURA OS Daily Schedule & Routine Engine
File: aura/tools/daily_schedule.py

Crucial Architectural Separation:
1. DAILY SCHEDULE / ROUTINE (Recurring Habit Rhythm & Time Blocks - Workout split, Sleep/Wake, Study blocks).
   - Never permanently deleted! Logged as completed for today, resets fresh tomorrow.
2. DYNAMIC ACTION TASKS (One-off Ad-hoc To-Dos - SGC Bills, Interviews, Errands).
   - Purged from database upon completion (0 MB bloat).
"""

import sys
import os
import json
import asyncio
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

import libsql_client
from aura.config import DATA_DIR, TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

IST = timezone(timedelta(hours=5, minutes=30))
ROUTINE_FILE = DATA_DIR / "daily_routine_blueprint.json"
ROUTINE_LOG_FILE = DATA_DIR / "daily_routine_logs.json"

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

DEFAULT_BLUEPRINT = {
    "version": "1.0",
    "weekday_blocks": [
        {"id": "b1", "time": "06:00 AM - 07:00 AM", "title": "Wakeup, Morning Hydration & AURA Briefing", "tag": "ROUTINE"},
        {"id": "b2", "time": "09:00 AM - 04:30 PM", "title": "College Core / Engineering & Lab Block", "tag": "CAREER"},
        {"id": "b3", "time": "04:30 PM - 06:00 PM", "title": "SGC Business Operations & Mill Collections", "tag": "SGC"},
        {"id": "b4", "time": "06:00 PM - 07:30 PM", "title": "Gym & Fitness Workout", "tag": "WORKOUT"},
        {"id": "b5", "time": "08:30 PM - 10:30 PM", "title": "Placement DSA / LeetCode & AI Engineering", "tag": "CAREER"},
        {"id": "b6", "time": "10:30 PM - 11:00 PM", "title": "AURA EOD Retrospective & Wind Down", "tag": "ROUTINE"}
    ],
    "workout_splits": {
        "Monday": "Upper Body (Chest & Triceps)",
        "Tuesday": "Upper Body (Back & Biceps)",
        "Wednesday": "Lower Body (Legs, Calves & Abs)",
        "Thursday": "Upper Body (Shoulders & Arms)",
        "Friday": "Functional Core & High-Intensity Cardio",
        "Saturday": "Full Body Compound / Sports",
        "Sunday": "Active Recovery & Mobility Stretch"
    }
}

def _load_blueprint() -> Dict[str, Any]:
    # 1. Primary: Load from Turso Cloud DB (Universal 24/7 Truth across PC & Cloud Server)
    try:
        res = _execute_turso_cloud(
            "SELECT content FROM aura_vault WHERE category = 'DAILY_SCHEDULE' AND title = 'master_blueprint' LIMIT 1;"
        )
        if res.rows and res.rows[0][0]:
            cloud_blueprint = json.loads(res.rows[0][0])
            with open(ROUTINE_FILE, "w", encoding="utf-8") as f:
                json.dump(cloud_blueprint, f, indent=2)
            return cloud_blueprint
    except Exception:
        pass

    # 2. Fallback to local file or default
    if not ROUTINE_FILE.exists():
        with open(ROUTINE_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_BLUEPRINT, f, indent=2)
        blueprint = DEFAULT_BLUEPRINT
    else:
        try:
            with open(ROUTINE_FILE, "r", encoding="utf-8") as f:
                blueprint = json.load(f)
        except Exception:
            blueprint = DEFAULT_BLUEPRINT

    # Seed into Turso Cloud DB
    try:
        _execute_turso_cloud(
            "INSERT INTO aura_vault (category, title, content, tags) VALUES ('DAILY_SCHEDULE', 'master_blueprint', ?, 'lifestyle,schedule');",
            [json.dumps(blueprint)]
        )
    except Exception:
        pass

    return blueprint

def _save_blueprint(blueprint: Dict[str, Any]):
    # 1. Update Turso Cloud DB (AWS Mumbai)
    try:
        res = _execute_turso_cloud(
            "UPDATE aura_vault SET content = ? WHERE category = 'DAILY_SCHEDULE' AND title = 'master_blueprint';",
            [json.dumps(blueprint)]
        )
        if res.rows_affected == 0:
            _execute_turso_cloud(
                "INSERT INTO aura_vault (category, title, content, tags) VALUES ('DAILY_SCHEDULE', 'master_blueprint', ?, 'lifestyle,schedule');",
                [json.dumps(blueprint)]
            )
    except Exception:
        pass

    # 2. Local disk cache
    try:
        with open(ROUTINE_FILE, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, indent=2)
    except Exception:
        pass

def _load_routine_logs() -> Dict[str, Any]:
    # 1. Primary: Load from Turso Cloud DB
    try:
        res = _execute_turso_cloud(
            "SELECT content FROM aura_vault WHERE category = 'ROUTINE_LOGS' AND title = 'daily_routine_logs' LIMIT 1;"
        )
        if res.rows and res.rows[0][0]:
            cloud_logs = json.loads(res.rows[0][0])
            with open(ROUTINE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(cloud_logs, f, indent=2)
            return cloud_logs
    except Exception:
        pass

    # 2. Fallback to local file
    if ROUTINE_LOG_FILE.exists():
        try:
            with open(ROUTINE_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_routine_logs(logs: Dict[str, Any]):
    # 1. Update Turso Cloud DB (AWS Mumbai)
    try:
        res = _execute_turso_cloud(
            "UPDATE aura_vault SET content = ? WHERE category = 'ROUTINE_LOGS' AND title = 'daily_routine_logs';",
            [json.dumps(logs)]
        )
        if res.rows_affected == 0:
            _execute_turso_cloud(
                "INSERT INTO aura_vault (category, title, content, tags) VALUES ('ROUTINE_LOGS', 'daily_routine_logs', ?, 'logs,habits');",
                [json.dumps(logs)]
            )
    except Exception:
        pass

    # 2. Local disk cache
    try:
        with open(ROUTINE_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception:
        pass


def get_daily_schedule(target_day: str = "today") -> str:
    """
    Retrieves the complete Daily Schedule Routine & Time Blocks for Mukil.
    target_day: Target day to inspect ('today', 'tomorrow', 'Monday', 'Tuesday', etc. Defaults to 'today').
    Includes the day's fixed blocks, target workout split (e.g. Upper Body/Lower Body),
    and shows which routines are already completed for today.
    """
    now = datetime.now(IST)
    blueprint = _load_blueprint()
    logs = _load_routine_logs()
    today_str = now.strftime("%Y-%m-%d")

    clean_target = str(target_day or "today").strip().lower()
    if clean_target in ["tomorrow", "naalaiki", "naalaikku"]:
        target_dt = now + timedelta(days=1)
        target_day_name = target_dt.strftime("%A")
        date_display = target_dt.strftime("%d %b %Y")
    elif clean_target in ["today", "inikku", "innikku", "null", "none"]:
        target_day_name = now.strftime("%A")
        date_display = now.strftime("%d %b %Y")
    else:
        target_day_name = clean_target.title()
        date_display = target_day_name

    workout_split = blueprint.get("workout_splits", {}).get(target_day_name, "Rest / Flexibility")
    today_logs = logs.get(today_str, {})

    lines = [
        f"📅 **AURA Master Daily Schedule — {target_day_name} ({date_display})**\n",
        f"🏋️ **Workout Target for {target_day_name}:** `{workout_split}`\n",
        "| Time Block | Routine Activity | Status |",
        "| :--- | :--- | :--- |"
    ]

    for block in blueprint.get("weekday_blocks", []):
        bid = block["id"]
        title = block["title"]
        if block["tag"] == "WORKOUT":
            title = f"{block['title']} ➡️ **{workout_split}**"
        
        is_done = today_logs.get(bid, False)
        status = "✅ Completed" if is_done else "⏳ Scheduled"
        lines.append(f"| `{block['time']}` | {title} | {status} |")

    lines.append("\n💡 *Note: Daily schedules are recurring lifestyle rhythms that reset fresh every day.*")
    lines.append("*For one-off ad-hoc action items (bills, interviews), ask for 'active tasks'.*")
    return "\n".join(lines)


def log_routine_completed(routine_query: str) -> str:
    """
    Marks a recurring daily schedule block or workout as COMPLETED for today.
    Does NOT delete the routine from future days! Increments daily consistency streak.
    Examples: 'workout', 'upper body', 'morning code', 'gym'.
    """
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    blueprint = _load_blueprint()
    logs = _load_routine_logs()

    if today_str not in logs:
        logs[today_str] = {}

    q = routine_query.lower()
    matched_block = None

    # Check if workout
    if any(k in q for k in ["workout", "gym", "upper body", "lower body", "chest", "back", "legs", "shoulders"]):
        for b in blueprint.get("weekday_blocks", []):
            if b["tag"] == "WORKOUT":
                matched_block = b
                break

    # Otherwise fuzzy match block title
    if not matched_block:
        for b in blueprint.get("weekday_blocks", []):
            if any(token in b["title"].lower() for token in q.split()):
                matched_block = b
                break

    if not matched_block:
        return f"⚠️ Mapla, '{routine_query}' matching daily routine block kidaikala. Use 'get_daily_schedule' to view all blocks."

    bid = matched_block["id"]
    logs[today_str][bid] = True
    _save_routine_logs(logs)

    day_name = now.strftime("%A")
    workout_split = blueprint.get("workout_splits", {}).get(day_name, "Daily Workout")

    return (
        f"🔥 **Routine Block Logged! Beast Mode, Boss!**\n"
        f"• **Routine:** {matched_block['title']} ({workout_split if matched_block['tag'] == 'WORKOUT' else ''})\n"
        f"• **Today's Status:** Marked as ✅ Completed for {now.strftime('%d %b %Y')}.\n"
        f"• **Persistence:** Kept safe in your permanent daily blueprint (resets tomorrow automatically)."
    )


def modify_daily_schedule(block_query: str, new_time: str = "", new_activity: str = "") -> str:
    """
    Dynamically modifies Mukil's daily schedule blueprint when his real-life flow changes.
    Can shift block timings (e.g. shift gym to 8:00 PM), update activities, or change workout splits.
    Examples:
    - modify_daily_schedule(block_query="gym", new_time="08:00 PM - 09:30 PM")
    - modify_daily_schedule(block_query="Tuesday workout", new_activity="Chest & Triceps")
    - modify_daily_schedule(block_query="college", new_time="10:00 AM - 03:00 PM")
    """
    blueprint = _load_blueprint()
    q = block_query.lower().strip()

    # 1. Check if modifying workout split for a specific day
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days:
        if day in q and ("workout" in q or "split" in q or "target" in q):
            target_split = new_activity or new_time or "Custom Workout"
            blueprint["workout_splits"][day.title()] = target_split
            _save_blueprint(blueprint)
            return (
                f"⚡ **Workout Split Updated!**\n"
                f"• **Day:** {day.title()}\n"
                f"• **New Target:** `{target_split}`\n"
                f"• Saved directly to your lifestyle blueprint."
            )

    # 2. Match existing weekday blocks
    matched_block = None
    if "gym" in q or "workout" in q:
        for b in blueprint.get("weekday_blocks", []):
            if b["tag"] == "WORKOUT":
                matched_block = b
                break

    if not matched_block:
        for b in blueprint.get("weekday_blocks", []):
            if any(token in b["title"].lower() for token in q.split()):
                matched_block = b
                break

    if matched_block:
        old_time = matched_block["time"]
        old_title = matched_block["title"]
        if new_time:
            matched_block["time"] = new_time
        if new_activity:
            matched_block["title"] = new_activity

        _save_blueprint(blueprint)

        return (
            f"⚡ **Daily Schedule Flow Updated Successfully!**\n"
            f"• **Block:** {matched_block['title']}\n"
            f"• **New Timing:** `{matched_block['time']}` (Previously: `{old_time}`)\n"
            f"• **Updated in:** Permanent Lifestyle Blueprint."
        )

    # 3. If not found, add a new block if details provided
    if new_time and (new_activity or block_query):
        new_title = new_activity or block_query.title()
        new_id = f"b{len(blueprint.get('weekday_blocks', [])) + 1}"
        blueprint["weekday_blocks"].append({
            "id": new_id,
            "time": new_time,
            "title": new_title,
            "tag": "CUSTOM"
        })
        _save_blueprint(blueprint)

        return (
            f"⚡ **New Flow Block Added to Daily Schedule!**\n"
            f"• **Block:** {new_title}\n"
            f"• **Timing:** `{new_time}`\n"
            f"• Saved to your lifestyle blueprint."
        )

    return f"⚠️ Mapla, '{block_query}' matching schedule block kidaikala. Please specify the block and new time."

