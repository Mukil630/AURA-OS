"""Proactive Reminders & Alarm Scheduler Engine for JARVIS.
Handles timed alarms, study sprint notifications, and calendar alerts with persistent storage.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import re
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("ReminderScheduler")


class ReminderScheduler:
    """
    Manages active timed reminders and proactively triggers notification callbacks.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "reminders.json"
        )
        self._reminders: Dict[str, Dict[str, Any]] = {}
        self._callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._load_storage()

    def set_callback(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Sets the async callback invoked when a reminder triggers."""
        self._callback = callback

    def _load_storage(self) -> None:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._reminders = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load reminders storage: {e}")
                self._reminders = {}

    def _save_storage(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._reminders, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist reminders: {e}")

    def parse_and_create(self, chat_id: int, user_id: int, command_args: str) -> Dict[str, Any]:
        """
        Parses commands like:
        - "in 10m study java"
        - "in 2h 30m placement aptitude test"
        - "10m study python"
        - "22:30 meeting"
        """
        args = command_args.strip()
        if not args:
            raise ValueError("Usage: `/remind <time> <message>` (e.g. `/remind 10m Study Java`)")

        now = datetime.now(timezone.utc)
        target_time: Optional[datetime] = None
        message = ""

        # Check relative time (e.g. 10m, 2h, 1h 30m, in 15m)
        rel_match = re.match(r"^(?:in\s+)?(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*m(?:in(?:utes?)?)?)?\s*(?:(\d+)\s*s(?:ec(?:onds?)?)?)?\s+(.+)$", args, re.IGNORECASE)
        if rel_match and any([rel_match.group(1), rel_match.group(2), rel_match.group(3)]):
            hours = int(rel_match.group(1) or 0)
            minutes = int(rel_match.group(2) or 0)
            seconds = int(rel_match.group(3) or 0)
            message = rel_match.group(4).strip()
            total_seconds = hours * 3600 + minutes * 60 + seconds
            if total_seconds <= 0:
                raise ValueError("Reminder duration must be greater than 0.")
            target_time = now + timedelta(seconds=total_seconds)
        else:
            # Fallback simple split: first token as duration
            parts = args.split(maxsplit=1)
            if len(parts) >= 2:
                time_str = parts[0].lower()
                message = parts[1].strip()
                if time_str.endswith("m") and time_str[:-1].isdigit():
                    target_time = now + timedelta(minutes=int(time_str[:-1]))
                elif time_str.endswith("h") and time_str[:-1].isdigit():
                    target_time = now + timedelta(hours=int(time_str[:-1]))
                elif time_str.endswith("s") and time_str[:-1].isdigit():
                    target_time = now + timedelta(seconds=int(time_str[:-1]))

        if not target_time:
            raise ValueError("Could not parse reminder time. Examples: `10m Study Java`, `1h Placement Test`.")

        reminder_id = f"rem_{uuid4().hex[:8]}"
        reminder = {
            "reminder_id": reminder_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "message": message,
            "created_at": now.isoformat(),
            "target_time": target_time.isoformat(),
            "status": "pending",
        }

        self._reminders[reminder_id] = reminder
        self._save_storage()
        return reminder

    def list_reminders(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns all active pending reminders for user."""
        active = []
        for r in self._reminders.values():
            if r.get("status") == "pending":
                if user_id is None or r.get("user_id") == user_id:
                    active.append(r)
        return sorted(active, key=lambda x: x["target_time"])

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancels a reminder by ID."""
        if reminder_id in self._reminders:
            self._reminders[reminder_id]["status"] = "cancelled"
            self._save_storage()
            return True
        return False

    async def start(self) -> None:
        """Starts the periodic background evaluation loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._poll_loop())
        logger.info("ReminderScheduler background evaluation loop started.")

    async def stop(self) -> None:
        """Stops the evaluation loop."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        """Evaluates pending reminders every 2 seconds."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                due_reminders = []
                for rid, r in list(self._reminders.items()):
                    if r.get("status") == "pending":
                        target = datetime.fromisoformat(r["target_time"])
                        if target <= now:
                            r["status"] = "fired"
                            r["fired_at"] = now.isoformat()
                            due_reminders.append(r)

                if due_reminders:
                    self._save_storage()
                    for r in due_reminders:
                        if self._callback:
                            try:
                                await self._callback(r)
                            except Exception as ex:
                                logger.error(f"Error executing reminder callback for {r['reminder_id']}: {ex}")

            except Exception as e:
                logger.error(f"Error in reminder poll loop: {e}")

            await asyncio.sleep(2)
