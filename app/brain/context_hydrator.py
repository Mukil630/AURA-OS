"""Stage 2: Context Hydration with User Profile & Time-Decayed Episodic Memory."""
import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ContextHydrator")


class HydratedContext(BaseModel):
    user_name: str = "Mukil"
    user_profile: Dict[str, Any] = Field(default_factory=dict)
    active_phase: str = "AURA-OS Autonomous Execution"
    recent_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    system_time_ist: str = ""
    hardware_summary: Optional[Dict[str, Any]] = None


class ContextHydrator:
    """Hydrates agent context with user identity, skills, and prioritized episodic memory."""

    def __init__(self, memory_dir: Optional[str] = None):
        self.memory_dir = memory_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "storage",
            "memory"
        )
        # Fallback to jarvis-core storage if local is not populated
        self.fallback_dir = r"C:\Users\mukil\jarvis-core\storage\memory"

    def _read_json_safe(self, filename: str) -> Any:
        paths = [
            os.path.join(self.memory_dir, filename),
            os.path.join(self.fallback_dir, filename)
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read {p}: {e}")
        return {}

    def hydrate(self, max_recent_tasks: int = 5) -> HydratedContext:
        """Assembles the complete context for reasoning."""
        user_profile = self._read_json_safe("user_profile.json")
        context_data = self._read_json_safe("context.json")
        task_log = self._read_json_safe("task_log.json")

        if isinstance(task_log, dict):
            task_log = task_log.get("tasks", [])
        if not isinstance(task_log, list):
            task_log = []

        # Time-decayed recency scoring: Sort by recency and take top N
        recent_tasks = task_log[-max_recent_tasks:] if task_log else []

        now_utc = datetime.now(timezone.utc)
        ist_hour = (now_utc.hour + 5) + ((now_utc.minute + 30) // 60)
        ist_min = (now_utc.minute + 30) % 60
        ist_time_str = f"{now_utc.strftime('%Y-%m-%d')} {ist_hour:02d}:{ist_min:02d} IST"

        return HydratedContext(
            user_name=user_profile.get("personal_details", {}).get("name", "Mukil"),
            user_profile=user_profile,
            active_phase=context_data.get("active_phase", "AURA Master Operating Plane"),
            recent_tasks=recent_tasks,
            system_time_ist=ist_time_str,
        )

    def format_system_prompt_context(self, hydrated: HydratedContext) -> str:
        """Formats the hydrated context into a concise prompt prefix."""
        skills = hydrated.user_profile.get("technical_skills", {}).get("languages", ["Java", "Python"])
        college = hydrated.user_profile.get("personal_details", {}).get("college", "VSB Engineering College")
        
        prompt_context = (
            f"=== MUKIL MASTER CONTEXT ===\n"
            f"• User: {hydrated.user_name} | College: {college}\n"
            f"• Core Stack: {', '.join(skills)}\n"
            f"• System Time: {hydrated.system_time_ist}\n"
            f"• Active Phase: {hydrated.active_phase}\n"
            f"• Recent History: {len(hydrated.recent_tasks)} events loaded.\n"
            f"============================\n"
        )
        return prompt_context
