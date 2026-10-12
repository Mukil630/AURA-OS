"""
AURA-OS Durable Reminder & Scheduler Engine
app/services/durable_scheduler.py - SQLite-backed, Asia/Kolkata timezone-locked,
Restart-Surviving Reminders with Missed-Deadline Catchup Recovery.
"""
import os
import sys
import re
import uuid
import sqlite3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Coroutine, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.config import get_settings

logger = logging.getLogger("durable_scheduler")
IST_TZ = timezone(timedelta(hours=5, minutes=30))


class DurableScheduler:
    """
    Timezone-aware (Asia/Kolkata), Restart-Resilient Reminder Scheduler.
    Guarantees that reminders survive container restarts by storing jobs in SQLite.
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
        self._callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """Creates durable_reminders table if not exists."""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS durable_reminders (
                reminder_id TEXT PRIMARY KEY,
                task_id TEXT,
                chat_id INTEGER,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                trigger_time_utc TEXT NOT NULL,
                trigger_time_ist TEXT NOT NULL,
                status TEXT DEFAULT 'SCHEDULED', -- SCHEDULED, TRIGGERED, MISSED, CANCELLED
                recurring_rule TEXT,              -- e.g. 'DAILY', 'WEEKLY', None
                delivery_attempts INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                executed_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS ix_reminders_status_time ON durable_reminders(status, trigger_time_utc);")
            conn.commit()

    def set_callback(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        self._callback = callback

    def parse_natural_time(self, time_expr: str) -> Tuple[datetime, str]:
        """
        Parses natural language relative, absolute, and Tanglish time into Asia/Kolkata datetime.
        Returns: (target_utc_datetime, remaining_message)
        """
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(IST_TZ)
        target_utc: Optional[datetime] = None
        message = ""

        clean = time_expr.strip()

        # 1. Relative Duration: "in 10m", "5 mins", "1 hour 30 mins", "30s"
        rel_pattern = re.compile(r"(?:in\s+)?(\d+)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", re.IGNORECASE)
        rel_matches = rel_pattern.findall(clean)

        if rel_matches:
            total_seconds = 0
            for val_str, unit in rel_matches:
                val = int(val_str)
                u = unit.lower()
                if u.startswith("h"):
                    total_seconds += val * 3600
                elif u.startswith("m") and not u.startswith("man"):
                    total_seconds += val * 60
                elif u.startswith("s"):
                    total_seconds += val

            if total_seconds > 0:
                target_utc = now_utc + timedelta(seconds=total_seconds)
                message = rel_pattern.sub("", clean).strip()

        # 2. Tomorrow / Today Specific Clock Time: "tomorrow 6 pm", "tomorrow morning", "tonight 9 pm"
        if not target_utc:
            tmrw_pattern = re.compile(r"\b(?:tomorrow|tmrw|naalaiki|nalaiki)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
            tmrw_match = tmrw_pattern.search(clean)
            if tmrw_match:
                hour = int(tmrw_match.group(1))
                minute = int(tmrw_match.group(2) or 0)
                meridiem = (tmrw_match.group(3) or "").lower()

                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

                target_ist = (now_ist + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                target_utc = target_ist.astimezone(timezone.utc)
                message = tmrw_pattern.sub("", clean).strip()

        # 3. Absolute 12h/24h Clock Time Today: "at 6:00 pm", "18:30", "10.00 am"
        if not target_utc:
            time_pat = re.compile(r"\b(?:at\s+)?(\d{1,2})[:.](\d{2})\s*(am|pm)?\b", re.IGNORECASE)
            time_match = time_pat.search(clean)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                meridiem = (time_match.group(3) or "").lower()

                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

                target_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target_ist <= now_ist:
                    target_ist += timedelta(days=1)  # Scheduled for next day
                target_utc = target_ist.astimezone(timezone.utc)
                message = time_pat.sub("", clean).strip()

        # Fallback: Default to 1 hour if unspecified
        if not target_utc:
            target_utc = now_utc + timedelta(hours=1)
            message = clean

        # Clean trailing fluff
        clean_msg = re.sub(r"^(?:remind\s+me|set\s+(?:a\s+)?reminder|alarm|timer|for|to)\s+", "", message, flags=re.IGNORECASE).strip()
        clean_msg = re.sub(r"\s*(?:mani\s*ku|manikku|set\s*pannu)$", "", clean_msg, flags=re.IGNORECASE).strip()

        return target_utc, clean_msg or "Reminder Alarm"

    def schedule_reminder(
        self,
        time_expression: str,
        message: str = "",
        user_id: str = "mukil",
        chat_id: Optional[int] = None,
        task_id: Optional[str] = None,
        recurring_rule: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses and schedules a reminder durably in SQLite.
        """
        target_utc, parsed_msg = self.parse_natural_time(time_expression)
        final_msg = message.strip() if message.strip() else parsed_msg
        target_ist = target_utc.astimezone(IST_TZ)

        reminder_id = f"rem_{uuid.uuid4().hex[:10]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO durable_reminders (
                reminder_id, task_id, chat_id, user_id, message,
                trigger_time_utc, trigger_time_ist, status, recurring_rule,
                delivery_attempts, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?, 0, ?)
            """, (
                reminder_id, task_id, chat_id, user_id, final_msg,
                target_utc.isoformat(), target_ist.strftime("%Y-%m-%d %I:%M %p IST"),
                recurring_rule, now_utc
            ))
            conn.commit()

        logger.info(f"⏰ Scheduled durable reminder [{reminder_id}]: '{final_msg}' at {target_ist.strftime('%I:%M %p (%d %b)')} IST")

        return {
            "reminder_id": reminder_id,
            "task_id": task_id,
            "message": final_msg,
            "trigger_time_ist": target_ist.strftime("%I:%M %p, %d %b %Y IST"),
            "trigger_time_utc": target_utc.isoformat(),
            "status": "SCHEDULED"
        }

    def recover_missed_reminders(self) -> List[Dict[str, Any]]:
        """
        Scans for reminders that were supposed to trigger while the application was offline/sleeping.
        Transitions them to MISSED and returns them for immediate catchup alerting.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        missed = []

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM durable_reminders
                WHERE status = 'SCHEDULED' AND trigger_time_utc <= ?
                ORDER BY trigger_time_utc ASC
            """, (now_utc,))
            rows = cursor.fetchall()

            for r in rows:
                item = dict(r)
                item["status"] = "MISSED"
                missed.append(item)
                conn.execute("""
                    UPDATE durable_reminders
                    SET status = 'MISSED', delivery_attempts = delivery_attempts + 1
                    WHERE reminder_id = ?
                """, (item["reminder_id"],))
            conn.commit()

        if missed:
            logger.warning(f"⚠️ Recovered {len(missed)} missed reminders from downtime. Dispatching catchup alerts...")
        return missed

    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM durable_reminders
                WHERE status = 'SCHEDULED'
                ORDER BY trigger_time_utc ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

    async def start(self):
        """Starts the background monitoring loop."""
        if self._running:
            return
        self._running = True

        # Catchup missed reminders on startup
        missed_list = self.recover_missed_reminders()
        for m in missed_list:
            if self._callback:
                try:
                    await self._callback(m)
                except Exception as e:
                    logger.error(f"Error firing catchup alert for {m['reminder_id']}: {e}")

        self._loop_task = asyncio.create_task(self._poll_loop())
        logger.info("🟢 DurableScheduler background loop running (locked to Asia/Kolkata).")

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 DurableScheduler loop stopped.")

    async def _poll_loop(self):
        """Polls every 5 seconds for due reminders."""
        while self._running:
            try:
                now_utc = datetime.now(timezone.utc).isoformat()
                due_items = []

                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT * FROM durable_reminders
                        WHERE status = 'SCHEDULED' AND trigger_time_utc <= ?
                    """, (now_utc,))
                    due_items = [dict(r) for r in cursor.fetchall()]

                    for d in due_items:
                        now_str = datetime.now(timezone.utc).isoformat()
                        conn.execute("""
                            UPDATE durable_reminders
                            SET status = 'TRIGGERED', executed_at = ?, delivery_attempts = delivery_attempts + 1
                            WHERE reminder_id = ?
                        """, (now_str, d["reminder_id"]))
                    conn.commit()

                for item in due_items:
                    logger.info(f"🔔 Firing due reminder [{item['reminder_id']}]: '{item['message']}'")
                    if self._callback:
                        try:
                            await self._callback(item)
                        except Exception as cb_err:
                            logger.error(f"Failed to execute reminder callback: {cb_err}")

            except Exception as e:
                logger.error(f"Scheduler poll loop error: {e}")

            await asyncio.sleep(5)


# Global Singleton Instance
durable_scheduler = DurableScheduler()
