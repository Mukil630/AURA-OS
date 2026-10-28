"""
========================================================================================
AURA-OS — LIVING TASK LEDGER & DYNAMIC RULES ENGINE (living_task_ledger.py)
----------------------------------------------------------------------------------------
Dynamic, User-Defined Task & Financial Reminder Engine for Mukil:
1. Dynamic Rule Creation (Monthly Interest Day 1-10, Party Deadlines, Bill Follow-ups).
2. Daily Heartbeat Evaluator (Extracts ONLY actionable anomalies for Morning Briefing).
3. Zero-Spam Filter (Only alerts during urgency windows; stays silent otherwise).
4. Auto-Reset for monthly recurring financial rules.
========================================================================================
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional

logger = logging.getLogger("LivingTaskLedger")

LEDGER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "memory", "living_task_ledger.json")


class LivingTaskLedger:
    """
    Manages user-defined dynamic financial tasks, interest windows, and daily anomalies.
    """

    def __init__(self, ledger_file: Optional[str] = None):
        self.ledger_file = ledger_file or LEDGER_PATH

    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.ledger_file):
            return {"tasks": [], "last_evaluated_month": datetime.now().strftime("%Y-%m")}
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read ledger, starting fresh: {e}")
            return {"tasks": [], "last_evaluated_month": datetime.now().strftime("%Y-%m")}

    def _save_data(self, data: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.ledger_file), exist_ok=True)
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_task(
        self,
        title: str,
        task_type: str,  # "MONTHLY_INTEREST", "TARGET_DEADLINE", "CUSTOM_FOLLOWUP"
        party: str,
        amount: Optional[float] = None,
        due_day_start: Optional[int] = None,  # e.g. 1
        due_day_end: Optional[int] = None,    # e.g. 10
        target_date: Optional[str] = None,   # "YYYY-MM-DD"
        recurring_monthly: bool = False,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Creates a dynamic task card in Mukil's Living Task Ledger.
        """
        data = self._load_data()
        task_id = f"task_{len(data['tasks']) + 1}_{datetime.now().strftime('%d%H%M')}"
        
        card = {
            "task_id": task_id,
            "title": title,
            "task_type": task_type,
            "party": party,
            "amount": amount,
            "due_day_start": due_day_start,
            "due_day_end": due_day_end,
            "target_date": target_date,
            "recurring_monthly": recurring_monthly,
            "status": "PENDING",  # "PENDING", "CLEARED"
            "created_at": datetime.now().isoformat(),
            "last_cleared_at": None,
            "notes": notes
        }
        
        data["tasks"].append(card)
        self._save_data(data)
        logger.info(f"[Ledger] Registered new task card: {task_id} - '{title}'")
        return card

    def mark_cleared(self, identifier: str) -> bool:
        """
        Marks task as CLEARED by task_id or matching party name.
        """
        data = self._load_data()
        matched = False
        target = identifier.lower().strip()

        for t in data["tasks"]:
            if t["task_id"].lower() == target or target in t["party"].lower():
                t["status"] = "CLEARED"
                t["last_cleared_at"] = datetime.now().isoformat()
                matched = True

        if matched:
            self._save_data(data)
            logger.info(f"[Ledger] Task '{identifier}' marked CLEARED.")
        return matched

    def evaluate_daily_anomalies(self, current_dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Evaluates active tasks against current date.
        Returns ONLY actionable, high-priority anomalies for Mukil's morning briefing.
        """
        now = current_dt or datetime.now()
        current_day = now.day
        current_month_str = now.strftime("%Y-%m")
        today_iso = now.strftime("%Y-%m-%d")

        data = self._load_data()
        anomalies = []

        # Auto-reset recurring monthly tasks on 1st of each month
        if data.get("last_evaluated_month") != current_month_str:
            for t in data["tasks"]:
                if t.get("recurring_monthly") and t.get("status") == "CLEARED":
                    t["status"] = "PENDING"
            data["last_evaluated_month"] = current_month_str
            self._save_data(data)

        for t in data["tasks"]:
            if t.get("status") != "PENDING":
                continue

            ttype = t.get("task_type")
            party = t.get("party")
            amt = t.get("amount") or 0

            # 1. Monthly Interest Window (e.g. Day 1 to 10)
            if ttype == "MONTHLY_INTEREST":
                start = t.get("due_day_start", 1)
                end = t.get("due_day_end", 10)

                if start <= current_day <= end:
                    days_left = end - current_day
                    urgency = "HIGH" if days_left <= 3 else "MEDIUM"
                    msg = (
                        f"🚨 LAST DAY: {party} monthly interest ₹{amt:,.0f} due TODAY!"
                        if days_left == 0 else
                        f"⚠️ {party} monthly interest ₹{amt:,.0f} pending ({days_left} days left in Day {start}-{end} window)."
                    )
                    anomalies.append({
                        "task_id": t["task_id"],
                        "urgency": urgency,
                        "party": party,
                        "amount": amt,
                        "message": msg
                    })

            # 2. Specific Target Deadline
            elif ttype == "TARGET_DEADLINE":
                target = t.get("target_date")
                if target:
                    if target <= today_iso:
                        anomalies.append({
                            "task_id": t["task_id"],
                            "urgency": "HIGH",
                            "party": party,
                            "amount": amt,
                            "message": f"🚨 DEADLINE DUE: {party} task '{t['title']}' (Target: {target}) is pending action!"
                        })

        return anomalies
