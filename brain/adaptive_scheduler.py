import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adaptive_scheduler")

SCHEDULE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "memory", "schedule_state.json")

class AdaptiveScheduler:
    """
    AURA Adaptive Sprints & Life Scheduler Engine.
    Handles Baseline Routine, Temporary Sprints (e.g. 7-day placement drive prep),
    and Autonomous Auto-Reversion State Machine.
    """
    def __init__(self):
        self.mem = MemoryManager()
        self._ensure_schedule_db()

    def _ensure_schedule_db(self):
        if not os.path.exists(SCHEDULE_DB_PATH):
            default_schedule = {
                "base_routine": {
                    "morning_08_00": {"task": "Placement & Gmail Radar Check + Morning Daily Brief", "category": "ROUTINE"},
                    "evening_19_00": {"task": "Java Collections & DSA Drill (Set, Subarrays, Trees)", "category": "STUDY"},
                    "evening_20_00": {"task": "Python & Problem Solving (Loops, Arrays, Matrix)", "category": "STUDY"},
                    "night_21_00": {"task": "Aptitude & Logical Reasoning (Time & Work, Percentages)", "category": "APTITUDE"},
                    "night_22_00": {"task": "Daily Review, GitHub Green Streak Sync & 5TB Drive Backup", "category": "REVIEW"}
                },
                "active_override": None,
                "completed_sprints": [],
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(SCHEDULE_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(default_schedule, f, indent=2)

    def load_schedule_state(self) -> Dict[str, Any]:
        with open(SCHEDULE_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_schedule_state(self, state: Dict[str, Any]):
        state["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(SCHEDULE_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def create_sprint_override(self, event_name: str, duration_days: int = 7, focus_topics: List[str] = None) -> Dict[str, Any]:
        """
        Creates a temporary high-intensity sprint (e.g. Capgemini Placement Drive Sprint)
        that overrides the baseline routine for `duration_days` and auto-reverts.
        """
        state = self.load_schedule_state()
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)

        focus_topics = focus_topics or ["Company-Specific Mock Tests", "Aptitude Fast-Track", "Technical Interview Prep"]

        override = {
            "sprint_name": event_name,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "expiry_date": end_date.strftime("%Y-%m-%d"),
            "duration_days": duration_days,
            "focus_topics": focus_topics,
            "sprint_schedule": {
                "morning_08_00": {"task": f"[{event_name}] Company Test Syllabus & Pattern Drill", "category": "SPRINT_PRIORITY"},
                "evening_19_00": {"task": f"[{event_name}] Mock Coding Assessment & Technical Round Prep", "category": "SPRINT_PRIORITY"},
                "night_21_00": {"task": f"[{event_name}] Company-Specific Aptitude & Core Concepts", "category": "SPRINT_PRIORITY"}
            },
            "status": "ACTIVE"
        }

        state["active_override"] = override
        self.save_schedule_state(state)
        self.mem.log_task("SPRINT_OVERRIDE_CREATED", f"Active Sprint: {event_name} for {duration_days} days until {override['expiry_date']}")
        logger.info(f"⚡ Created Sprint Override '{event_name}' expiring on {override['expiry_date']}")
        return override

    def check_and_auto_revert(self) -> Dict[str, Any]:
        """
        State Machine: Checks if the active sprint has reached its expiry date.
        If expired -> Automatically restores baseline routine and logs sprint completion.
        """
        state = self.load_schedule_state()
        override = state.get("active_override")

        if not override:
            return {"status": "BASELINE_ACTIVE", "message": "Baseline routine is active. No sprint override."}

        expiry_dt = datetime.strptime(override["expiry_date"], "%Y-%m-%d")
        now_dt = datetime.now()

        if now_dt >= expiry_dt:
            # Sprint has expired! Auto-revert state machine triggered!
            override["status"] = "COMPLETED"
            override["completed_at"] = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            state["completed_sprints"].append(override)
            state["active_override"] = None
            self.save_schedule_state(state)

            msg = f"🎉 7-Day Sprint '{override['sprint_name']}' completed! Auto-Reverted back to baseline Java/Python routine."
            self.mem.log_task("AUTO_REVERT_TRIGGERED", msg)
            logger.info(msg)
            return {"status": "AUTO_REVERTED", "message": msg, "completed_sprint": override["sprint_name"]}
        else:
            days_left = (expiry_dt - now_dt).days + 1
            return {
                "status": "SPRINT_IN_PROGRESS",
                "sprint_name": override["sprint_name"],
                "days_remaining": days_left,
                "expiry_date": override["expiry_date"]
            }

    def get_today_active_schedule(self) -> Dict[str, Any]:
        """Returns the effective live schedule for today (Sprint Override if active, else Baseline)."""
        revert_status = self.check_and_auto_revert()
        state = self.load_schedule_state()

        if state.get("active_override"):
            return {
                "mode": "SPRINT_OVERRIDE",
                "sprint_info": state["active_override"],
                "schedule": state["active_override"]["sprint_schedule"]
            }
        else:
            return {
                "mode": "BASELINE_ROUTINE",
                "schedule": state["base_routine"]
            }

if __name__ == "__main__":
    sched = AdaptiveScheduler()
    sched.create_sprint_override("Capgemini Placement Drive Sprint", duration_days=7)
    today = sched.get_today_active_schedule()
    print("Today's Active Schedule:\n" + json.dumps(today, indent=2))
