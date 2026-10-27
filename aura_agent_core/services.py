import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from aura_agent_core.database import get_db_client
from aura_agent_core.config import IST

# ==========================================
# 1. REMINDER SERVICE (Limitless Auto-Clean)
# ==========================================


async def create_reminder(title: str, scheduled_iso: str) -> int:
    """Inserts a reminder into Turso Cloud with automatic retry."""
    for attempt in range(3):
        try:
            async with get_db_client() as client:
                res = await client.execute(
                    "INSERT INTO reminders (title, remind_at, status) VALUES (?, ?, 'PENDING');",
                    [title, scheduled_iso]
                )
                return int(res.last_insert_rowid)
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(1)
            else:
                raise e


async def cancel_reminder(reminder_id: int) -> bool:
    """Manually cancels a reminder before it triggers."""
    async with get_db_client() as client:
        res = await client.execute(
            "DELETE FROM reminders WHERE id = ?;",
            [reminder_id]
        )
        return res.rows_affected > 0


async def purge_completed_reminder(reminder_id: int) -> bool:
    """Auto-deletes triggered reminder from Turso to maintain 0 MB bloat."""
    async with get_db_client() as client:
        res = await client.execute(
            "DELETE FROM reminders WHERE id = ?;",
            [reminder_id]
        )
        return res.rows_affected > 0


async def get_due_reminders(current_time_iso: str) -> List[Dict[str, Any]]:
    """Fetches all reminders whose scheduled time has arrived and are pending."""
    async with get_db_client() as client:
        res = await client.execute(
            "SELECT id, title, remind_at FROM reminders WHERE remind_at <= ? AND status = 'PENDING';",
            [current_time_iso]
        )
        return [{"id": r[0], "title": r[1], "remind_at": r[2]} for r in res.rows]


async def list_active_reminders() -> List[Dict[str, Any]]:
    """Returns all pending reminders ordered by schedule time."""
    async with get_db_client() as client:
        res = await client.execute(
            "SELECT id, title, remind_at, created_at FROM reminders ORDER BY remind_at ASC;"
        )
        return [{"id": r[0], "title": r[1], "remind_at": r[2], "created_at": r[3]} for r in res.rows]


# ==========================================
# 2. UNIVERSAL VAULT SERVICE (Memory & Drive)
# ==========================================


async def save_to_vault(category: str, title: str, content: str, drive_link: str = "", tags: str = "") -> int:
    """
    Saves text, conversation notes, or Google Drive file references into Turso Cloud.
    Categories: 'IDEA', 'CONVO', 'PERSONAL', 'BILLS', 'JOB', 'CAREER', 'DOCS'
    """
    async with get_db_client() as client:
        res = await client.execute(
            "INSERT INTO aura_vault (category, title, content, drive_link, tags) VALUES (?, ?, ?, ?, ?);",
            [category.upper(), title, content, drive_link, tags]
        )
        return int(res.last_insert_rowid)


async def search_vault(keyword: str = "", category: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Searches memory vault by keyword, category, or tags."""
    async with get_db_client() as client:
        query = "SELECT id, category, title, content, drive_link, tags, created_at FROM aura_vault WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category.upper())
        if keyword:
            query += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            wildcard = f"%{keyword}%"
            params.extend([wildcard, wildcard, wildcard])
        query += f" ORDER BY created_at DESC LIMIT {limit};"
        res = await client.execute(query, params)

        return [
            {
                "id": r[0],
                "category": r[1],
                "title": r[2],
                "content": r[3],
                "drive_link": r[4],
                "tags": r[5],
                "created_at": r[6]
            }
            for r in res.rows
        ]


async def delete_vault_item(item_id: int) -> bool:
    """Deletes an item from the vault."""
    async with get_db_client() as client:
        res = await client.execute("DELETE FROM aura_vault WHERE id = ?;", [item_id])
        return res.rows_affected > 0


# ==========================================
# 3. CLOUD DAILY SCHEDULE & ROUTINE SERVICE
# ==========================================

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


async def get_or_init_blueprint(client=None) -> Dict[str, Any]:
    """Loads master daily schedule blueprint from Turso Cloud DB (aura_vault)."""
    if client:
        res = await client.execute(
            "SELECT content FROM aura_vault WHERE category = 'DAILY_SCHEDULE' AND title = 'master_blueprint' LIMIT 1;"
        )
        if res.rows and res.rows[0][0]:
            try:
                return json.loads(res.rows[0][0])
            except Exception:
                pass
        
        # Initialize in Cloud DB if missing
        await client.execute(
            "INSERT INTO aura_vault (category, title, content, tags) VALUES ('DAILY_SCHEDULE', 'master_blueprint', ?, 'lifestyle,schedule');",
            [json.dumps(DEFAULT_BLUEPRINT)]
        )
        return DEFAULT_BLUEPRINT
    else:
        for attempt in range(3):
            try:
                async with get_db_client() as c:
                    return await get_or_init_blueprint(c)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.5)
                else:
                    return DEFAULT_BLUEPRINT


async def save_blueprint(blueprint: Dict[str, Any]) -> bool:
    """Saves updated blueprint into Turso Cloud DB."""
    for attempt in range(3):
        try:
            async with get_db_client() as client:
                res = await client.execute(
                    "UPDATE aura_vault SET content = ? WHERE category = 'DAILY_SCHEDULE' AND title = 'master_blueprint';",
                    [json.dumps(blueprint)]
                )
                if res.rows_affected == 0:
                    await client.execute(
                        "INSERT INTO aura_vault (category, title, content, tags) VALUES ('DAILY_SCHEDULE', 'master_blueprint', ?, 'lifestyle,schedule');",
                        [json.dumps(blueprint)]
                    )
                return True
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5)
            else:
                return False


async def get_or_init_routine_logs(client=None) -> Dict[str, Any]:
    """Loads daily routine completion logs from Turso Cloud DB."""
    if client:
        res = await client.execute(
            "SELECT content FROM aura_vault WHERE category = 'ROUTINE_LOGS' AND title = 'daily_routine_logs' LIMIT 1;"
        )
        if res.rows and res.rows[0][0]:
            try:
                return json.loads(res.rows[0][0])
            except Exception:
                pass
        return {}
    else:
        for attempt in range(3):
            try:
                async with get_db_client() as c:
                    return await get_or_init_routine_logs(c)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.5)
                else:
                    return {}


async def save_routine_logs(logs: Dict[str, Any]) -> bool:
    """Saves daily routine completion logs to Turso Cloud DB."""
    for attempt in range(3):
        try:
            async with get_db_client() as client:
                res = await client.execute(
                    "UPDATE aura_vault SET content = ? WHERE category = 'ROUTINE_LOGS' AND title = 'daily_routine_logs';",
                    [json.dumps(logs)]
                )
                if res.rows_affected == 0:
                    await client.execute(
                        "INSERT INTO aura_vault (category, title, content, tags) VALUES ('ROUTINE_LOGS', 'daily_routine_logs', ?, 'logs,habits');",
                        [json.dumps(logs)]
                    )
                return True
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5)
            else:
                return False


async def get_daily_schedule_report(target_day: str = "today") -> Dict[str, Any]:
    """Generates structured daily schedule & workout split directly from Turso Cloud DB."""
    now = datetime.now(IST)
    blueprint = DEFAULT_BLUEPRINT
    logs = {}
    for attempt in range(3):
        try:
            async with get_db_client() as client:
                blueprint = await get_or_init_blueprint(client)
                logs = await get_or_init_routine_logs(client)
                break
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5)
            else:
                blueprint = DEFAULT_BLUEPRINT
                logs = {}
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

    workout_split = blueprint.get("workout_splits", {}).get(target_day_name, "Rest / Mobility")
    today_logs = logs.get(today_str, {})

    blocks_output = []
    lines = [
        f"📅 **AURA Cloud Master Daily Schedule — {target_day_name} ({date_display})**\n",
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
        blocks_output.append({
            "id": bid,
            "time": block["time"],
            "title": title,
            "tag": block.get("tag", "ROUTINE"),
            "completed": is_done
        })

    lines.append("\n💡 *Daily schedules are recurring lifestyle rhythms that reset fresh every day.*")
    lines.append("*For one-off ad-hoc action items (bills, interviews), ask for 'active tasks'.*")
    
    return {
        "success": True,
        "target_day": target_day_name,
        "date_display": date_display,
        "workout_target": workout_split,
        "blocks": blocks_output,
        "formatted_markdown": "\n".join(lines)
    }


async def modify_daily_schedule_cloud(block_query: str, new_time: str = "", new_activity: str = "") -> Dict[str, Any]:
    """Modifies lifestyle blueprint in Turso Cloud DB."""
    blueprint = await get_or_init_blueprint()
    q = block_query.lower().strip()

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days:
        if day in q and ("workout" in q or "split" in q or "target" in q):
            target_split = new_activity or new_time or "Custom Workout"
            blueprint["workout_splits"][day.title()] = target_split
            await save_blueprint(blueprint)
            return {
                "success": True,
                "message": f"⚡ Workout split for {day.title()} updated to '{target_split}' in Turso Cloud DB!"
            }

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
        if new_time:
            matched_block["time"] = new_time
        if new_activity:
            matched_block["title"] = new_activity

        await save_blueprint(blueprint)
        return {
            "success": True,
            "message": f"⚡ Flow block '{matched_block['title']}' updated to `{matched_block['time']}` in Turso Cloud DB! (Previous: `{old_time}`)"
        }

    if new_time and (new_activity or block_query):
        new_title = new_activity or block_query.title()
        new_id = f"b{len(blueprint.get('weekday_blocks', [])) + 1}"
        blueprint["weekday_blocks"].append({
            "id": new_id,
            "time": new_time,
            "title": new_title,
            "tag": "CUSTOM"
        })
        await save_blueprint(blueprint)
        return {
            "success": True,
            "message": f"⚡ New flow block '{new_title}' ({new_time}) added to Turso Cloud DB!"
        }

    return {"success": False, "message": f"⚠️ Mapla, '{block_query}' matching schedule block kidaikala."}


async def log_routine_completed_cloud(routine_query: str) -> Dict[str, Any]:
    """Marks a recurring routine/workout completed for today in Turso Cloud DB."""
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    blueprint = await get_or_init_blueprint()
    logs = await get_or_init_routine_logs()

    if today_str not in logs:
        logs[today_str] = {}

    q = routine_query.lower()
    matched_block = None

    if any(k in q for k in ["workout", "gym", "upper body", "lower body", "chest", "back", "legs", "shoulders"]):
        for b in blueprint.get("weekday_blocks", []):
            if b["tag"] == "WORKOUT":
                matched_block = b
                break

    if not matched_block:
        for b in blueprint.get("weekday_blocks", []):
            if any(token in b["title"].lower() for token in q.split()):
                matched_block = b
                break

    if not matched_block:
        return {"success": False, "message": f"⚠️ Mapla, '{routine_query}' matching routine block kidaikala."}

    bid = matched_block["id"]
    logs[today_str][bid] = True
    await save_routine_logs(logs)

    day_name = now.strftime("%A")
    workout_split = blueprint.get("workout_splits", {}).get(day_name, "Daily Workout")

    return {
        "success": True,
        "message": f"🔥 Routine '{matched_block['title']}' marked ✅ Completed for {now.strftime('%d %b %Y')} in Turso Cloud DB! (Workout: {workout_split})"
    }


async def complete_task_cloud(task_query_or_id: str) -> Dict[str, Any]:
    """
    Marks a one-off task as completed. Purges it from Turso reminders table (0 MB bloat)
    and archives into aura_vault under COMPLETED_TASK.
    """
    query = str(task_query_or_id).strip()
    if query.startswith("#"):
        query = query[1:].strip()

    active_reminders = await list_active_reminders()
    if not active_reminders:
        return {"success": False, "message": "📭 Active tasks list-la edhuvum pending illa mapla! You are completely caught up!"}

    matched = None
    if query.isdigit():
        target_id = int(query)
        for r in active_reminders:
            if r["id"] == target_id:
                matched = r
                break

    if not matched:
        q_lower = query.lower()
        for r in active_reminders:
            if q_lower in r["title"].lower() or r["title"].lower() in q_lower:
                matched = r
                break

    if not matched:
        q_tokens = set(re.findall(r'\w+', query.lower()))
        stop_words = {"task", "mudichiten", "done", "completed", "finish", "finished", "antha", "the", "a", "an", "la", "ku"}
        meaningful = q_tokens - stop_words
        if meaningful:
            best_score = 0
            for r in active_reminders:
                t_tokens = set(re.findall(r'\w+', r["title"].lower()))
                overlap = len(meaningful & t_tokens)
                if overlap > best_score:
                    best_score = overlap
                    matched = r

    if not matched:
        return {
            "success": False,
            "message": f"⚠️ Mapla, '{task_query_or_id}' matching active task kidaikala.",
            "active_tasks": active_reminders
        }

    target_id = matched["id"]
    # 1. Purge from reminders table
    await purge_completed_reminder(target_id)

    # 2. Archive into aura_vault
    archive_payload = json.dumps({
        "id": target_id,
        "title": matched["title"],
        "completed_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    })
    await save_to_vault(
        category="COMPLETED_TASK",
        title=matched["title"],
        content=archive_payload,
        tags="task,completed"
    )

    return {
        "success": True,
        "matched_task": matched,
        "message": f"🎯 Task '{matched['title']}' (#{target_id}) completed! Purged from Turso reminders table and archived in Cloud Vault."
    }

