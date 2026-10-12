import asyncio
from typing import List, Dict, Any, Optional
from aura_agent_core.database import get_db_client

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
