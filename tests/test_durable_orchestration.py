"""
Automated Test Suite for AURA-OS Durable Orchestration & Scheduling
tests/test_durable_orchestration.py - Verifies Task Persistence, Deduplication,
Restart Recovery, and Proactive Scheduling.
"""
import os
import sys
import tempfile
import pytest
from datetime import datetime, timezone, timedelta

# Ensure jarvis-core root is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.services.durable_task_manager import DurableTaskManager
from app.services.durable_scheduler import DurableScheduler
from app.orchestrator.central_orchestrator import CentralOrchestrator


@pytest.fixture
def temp_db():
    import gc
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def test_durable_task_lifecycle_and_restart_recovery(temp_db):
    """Verifies task creation, status updates, and that tasks survive restarts."""
    mgr1 = DurableTaskManager(db_path=temp_db)
    
    # 1. Create Task
    task = mgr1.create_task(
        raw_input="Remind me tomorrow morning to follow up with the supplier",
        user_id="mukil",
        channel="TELEGRAM",
        intent="SCHEDULE_REMINDER",
        priority="HIGH"
    )
    assert task["task_id"].startswith("tsk_")
    assert task["status"] == "CREATED"
    assert task["raw_input"] == "Remind me tomorrow morning to follow up with the supplier"
    
    # 2. Update Status
    mgr1.update_task_status(task["task_id"], status="COMPLETED", result_summary="Reminder set for 9 AM")
    
    # 3. Simulate Application Restart by instantiating new manager on same DB
    mgr2 = DurableTaskManager(db_path=temp_db)
    recovered = mgr2.get_task(task["task_id"])
    assert recovered is not None
    assert recovered["status"] == "COMPLETED"
    assert recovered["result_summary"] == "Reminder set for 9 AM"


def test_task_deduplication(temp_db):
    """Verifies that repeating the same request within deduplication window reuses active task."""
    mgr = DurableTaskManager(db_path=temp_db)
    
    t1 = mgr.create_task("Check SGC billing turnover", user_id="mukil", deduplicate_window_sec=60)
    t2 = mgr.create_task("Check SGC billing turnover", user_id="mukil", deduplicate_window_sec=60)
    
    # Should reuse the exact same task_id
    assert t1["task_id"] == t2["task_id"]


def test_durable_scheduler_timezone_and_missed_recovery(temp_db):
    """Verifies Asia/Kolkata scheduling and recovery of missed jobs after downtime."""
    sched1 = DurableScheduler(db_path=temp_db)
    
    # 1. Schedule a reminder in 10 minutes
    rem = sched1.schedule_reminder(
        time_expression="in 10 minutes",
        message="Follow up with Lakshmi Chemicals",
        user_id="mukil",
        chat_id=6233907249
    )
    assert rem["status"] == "SCHEDULED"
    assert "IST" in rem["trigger_time_ist"]
    
    # 2. Simulate a missed reminder (scheduled in the past)
    now_utc = datetime.now(timezone.utc)
    past_utc = now_utc - timedelta(minutes=5)
    
    with sched1._get_connection() as conn:
        conn.execute("""
            INSERT INTO durable_reminders (
                reminder_id, user_id, message, trigger_time_utc, trigger_time_ist, status, created_at
            ) VALUES ('rem_past_test', 'mukil', 'Missed payment call', ?, 'Past IST', 'SCHEDULED', ?)
        """, (past_utc.isoformat(), now_utc.isoformat()))
        conn.commit()
    
    # 3. Simulate Application Restart & Recovery
    sched2 = DurableScheduler(db_path=temp_db)
    missed = sched2.recover_missed_reminders()
    
    assert len(missed) >= 1
    assert any(m["reminder_id"] == "rem_past_test" for m in missed)
    assert any(m["status"] == "MISSED" for m in missed)


def test_central_orchestrator_end_to_end():
    """Tests Central Orchestrator natural language intent extraction and task dispatch."""
    orch = CentralOrchestrator()
    
    res = orch.process_request(
        raw_message="Remind me tomorrow at 6 PM to check Lakshmi Chemicals invoice",
        user_id="mukil",
        channel="TELEGRAM"
    )
    
    assert "task_id" in res
    assert res["task_id"].startswith("tsk_")
    assert res["intent"] in ["SCHEDULE_REMINDER", "BUSINESS_PAYABLES"]
    assert len(res["reply"]) > 10
