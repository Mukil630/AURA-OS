import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

IST_TZ = timezone(timedelta(hours=5, minutes=30))

class CallSessionMemory:
    """Manages active conversation turns and logs sessions."""
    def __init__(self, max_history_turns: int = 10):
        self.max_history_turns = max_history_turns
        self.history: List[Dict[str, str]] = []
        self.call_start_time: Optional[datetime] = None

    def start_session(self) -> str:
        self.history = []
        self.call_start_time = datetime.now(IST_TZ)
        greeting = "Vanakkam Boss! JARVIS is on the line. Sollinga Mapla, enna plan?"
        self.history.append({"role": "assistant", "content": greeting})
        return greeting

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content.strip()})
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]

    def get_recent_turns(self, limit: int = 6) -> List[Dict[str, str]]:
        return self.history[-limit:]

    def format_history_for_prompt(self) -> str:
        if not self.history:
            return "No previous turns in this call."
        lines = []
        for turn in self.history[-8:]:
            speaker = "Mukil" if turn["role"] == "user" else "JARVIS"
            lines.append(f"{speaker}: {turn['content']}")
        return "\n".join(lines)

    def end_session(self) -> Dict[str, Any]:
        end_time = datetime.now(IST_TZ)
        duration_secs = 0
        if self.call_start_time:
            duration_secs = int((end_time - self.call_start_time).total_seconds())
        summary = {
            "start_time": self.call_start_time.isoformat() if self.call_start_time else "",
            "end_time": end_time.isoformat(),
            "duration_seconds": duration_secs,
            "turns_count": len(self.history)
        }
        return summary

session_memory = CallSessionMemory()
