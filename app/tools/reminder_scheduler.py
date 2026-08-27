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
        Parses complex natural, relative, absolute (IST), and Tanglish commands like:
        - "10.00 mani ku timer set pannu"
        - "10:00 pm study java"
        - "10m study python"
        - "in 1h 30m placement aptitude test"
        - "5 mins"
        - "22:30 meeting"
        """
        args = command_args.strip()
        if not args:
            raise ValueError("Usage: `/remind <time> <message>` (e.g. `/remind 10m Study Java` or `/remind 10.00`)")

        now_utc = datetime.now(timezone.utc)
        ist_offset = timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset
        target_time: Optional[datetime] = None
        message = ""

        # Normalize text
        clean = args.lower().strip()
        clean = re.sub(r"^(?:set\s+)?(?:a\s+)?(?:remind(?:er|ar)?|alarm|timer)\s+(?:for\s+|to\s+|in\s+|at\s+)?", "", clean)
        clean = re.sub(r"\s*(?:mani\s*ku|manikku|mani|ku|set\s*pannu)\s*", " ", clean).strip()

        # 1. First priority: Relative Duration (e.g. 10m, 5 mins, 1 hour 30 mins, 30s)
        rel_pattern = re.compile(r"(?:in\s+)?(\d+)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", re.IGNORECASE)
        rel_matches = rel_pattern.findall(args)

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
                target_time = now_utc + timedelta(seconds=total_seconds)
                cleaned_msg = rel_pattern.sub("", args).strip()
                cleaned_msg = re.sub(r"^(?:in|set|a|remind|reminder|timer|alarm|to|for)\b\s*", "", cleaned_msg, flags=re.IGNORECASE).strip()
                cleaned_msg = re.sub(r"\s*(?:mani\s*ku|manikku|mani|ku|set\s*pannu)\s*$", "", cleaned_msg, flags=re.IGNORECASE).strip()
                message = cleaned_msg

        # 2. Second priority: Absolute Clock Time (e.g. 10.00, 10:00, 10:00 PM, 10 pm, 22:00)
        if not target_time:
            clock_pattern = re.compile(r"\b(\d{1,2})(?:[:\.](\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
            clock_match = clock_pattern.search(args)
            if clock_match:
                hour = int(clock_match.group(1))
                minute = int(clock_match.group(2) or 0)
                ampm = (clock_match.group(3) or "").lower()

                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    if ampm == "pm" and hour < 12:
                        hour += 12
                    elif ampm == "am" and hour == 12:
                        hour = 0
                    elif not ampm and hour < 12 and now_ist.hour >= 12 and (hour + 12) > now_ist.hour:
                        hour += 12

                    target_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target_ist <= now_ist:
                        target_ist += timedelta(days=1)

                    target_time = target_ist - ist_offset
                    cleaned_msg = clock_pattern.sub("", args).strip()
                    cleaned_msg = re.sub(r"^(?:at|set|a|remind|reminder|timer|alarm|to|for)\b\s*", "", cleaned_msg, flags=re.IGNORECASE).strip()
                    cleaned_msg = re.sub(r"\s*(?:mani\s*ku|manikku|mani|ku|timer|alarm|set\s*pannu)\s*", " ", cleaned_msg, flags=re.IGNORECASE).strip()
                    message = cleaned_msg

        if not target_time:
            raise ValueError("Could not parse time. Examples: `10.00`, `10:00 PM`, `10m Study Java`, `1h Test`.")

        if not message:
            message = "Timer Alert"

        reminder_id = f"rem_{uuid4().hex[:8]}"
        reminder = {
            "reminder_id": reminder_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "message": message,
            "created_at": now_utc.isoformat(),
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
