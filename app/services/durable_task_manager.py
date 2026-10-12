"""
AURA-OS Durable Task Manager Service
app/services/durable_task_manager.py - Persistent, Deduplicating Task CRUD backed by SQLite.
Guarantees task recovery across application restarts and container rebuilds.
"""
import os
import sys
import json
import uuid
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.config import get_settings

logger = logging.getLogger("durable_task_manager")
IST_TZ = timezone(timedelta(hours=5, minutes=30))


class DurableTaskManager:
    """
    Manages task lifecycle with atomic SQLite persistence and anti-duplication deduplication.
    Directly compatible with data/master_agent.db.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            settings = get_settings()
            raw_url = settings.DATABASE_URL
            self.db_path = raw_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            if not os.path.isabs(self.db_path):
                self.db_path = os.path.join(BASE_DIR, self.db_path.lstrip("./"))
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """Ensures the tasks table exists with required indexes."""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                schema_version TEXT DEFAULT 'v1',
                user_id TEXT NOT NULL,
                session_id TEXT,
                channel TEXT DEFAULT 'API',
                raw_input TEXT NOT NULL,
                intent TEXT DEFAULT 'UNKNOWN',
                task_type TEXT DEFAULT 'ACTION',
                priority TEXT DEFAULT 'NORMAL',
                risk_level TEXT DEFAULT 'LOW',
                status TEXT DEFAULT 'CREATED',
                workflow_id TEXT,
                result_summary TEXT,
                result_data_json TEXT,
                error_message TEXT,
                tags_json TEXT DEFAULT '[]',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS ix_tasks_user_status ON tasks(user_id, status);")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_tasks_created_at ON tasks(created_at);")
            conn.commit()

    def create_task(
        self,
        raw_input: str,
        user_id: str = "mukil",
        channel: str = "TELEGRAM",
        intent: str = "UNKNOWN",
        priority: str = "NORMAL",
        risk_level: str = "LOW",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        deduplicate_window_sec: int = 300
    ) -> Dict[str, Any]:
        """
        Creates and persists a new task in SQLite.
        Deduplication: If an identical raw_input from the same user is still OPEN
        and was created within deduplicate_window_sec, reuses the existing task to prevent duplicates.
        """
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.isoformat()
        clean_input = raw_input.strip()

        with self._get_connection() as conn:
            # 1. Deduplication check
            if deduplicate_window_sec > 0:
                cutoff_time = (now_utc - timedelta(seconds=deduplicate_window_sec)).isoformat()
                cursor = conn.execute("""
                    SELECT * FROM tasks
                    WHERE user_id = ? AND raw_input = ? AND status IN ('CREATED', 'IN_PROGRESS', 'SCHEDULED')
                    AND created_at >= ?
                    ORDER BY created_at DESC LIMIT 1
                """, (user_id, clean_input, cutoff_time))
                row = cursor.fetchone()
                if row:
                    logger.info(f"🔄 Deduplication: Reusing active task {row['task_id']} for user {user_id}")
                    return dict(row)

            # 2. Insert new task
            task_id = f"tsk_{uuid.uuid4().hex[:12]}"
            tags_json = json.dumps(tags or [])
            meta_json = json.dumps(metadata or {})

            conn.execute("""
                INSERT INTO tasks (
                    task_id, schema_version, user_id, channel, raw_input,
                    intent, task_type, priority, risk_level, status,
                    tags_json, metadata_json, created_at, updated_at
                ) VALUES (?, 'v1', ?, ?, ?, ?, 'ACTION', ?, ?, 'CREATED', ?, ?, ?, ?)
            """, (
                task_id, user_id, channel, clean_input,
                intent, priority, risk_level,
                tags_json, meta_json, now_str, now_str
            ))
            conn.commit()

            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            created_row = dict(cursor.fetchone())
            logger.info(f"✅ Created durable task [{task_id}] (Intent: {intent}, User: {user_id})")
            return created_row

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_tasks(
        self,
        user_id: str = "mukil",
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if status:
                cursor = conn.execute("""
                    SELECT * FROM tasks
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (user_id, status.upper(), limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM tasks
                    WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result_summary: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        now_str = datetime.now(timezone.utc).isoformat()
        completed_at = now_str if status.upper() in ["COMPLETED", "FAILED", "CANCELLED"] else None
        res_json = json.dumps(result_data) if result_data else None

        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE tasks SET
                    status = ?,
                    result_summary = COALESCE(?, result_summary),
                    result_data_json = COALESCE(?, result_data_json),
                    error_message = COALESCE(?, error_message),
                    updated_at = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE task_id = ?
            """, (status.upper(), result_summary, res_json, error_message, now_str, completed_at, task_id))
            conn.commit()
            return cursor.rowcount > 0

    def cancel_task(self, task_id: str, reason: str = "User cancelled") -> bool:
        return self.update_task_status(task_id, status="CANCELLED", error_message=reason)


# Global Singleton Instance
durable_task_manager = DurableTaskManager()
