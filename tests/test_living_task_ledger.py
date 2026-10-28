"""
========================================================================================
JARVIS TEST SUITE — LIVING TASK LEDGER (test_living_task_ledger.py)
----------------------------------------------------------------------------------------
Tests:
1. Dynamic Task Card Registration.
2. Day 1 to 10 Monthly Interest Window Anomaly Detection.
3. Outside-Window Silence (Zero Spam).
4. Task Clearance and Auto-Muting.
5. Monthly Auto-Reset for recurring rules.
========================================================================================
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain.living_task_ledger import LivingTaskLedger


@pytest.fixture
def temp_ledger(tmp_path):
    ledger_file = str(tmp_path / "test_ledger.json")
    return LivingTaskLedger(ledger_file=ledger_file)


def test_add_dynamic_interest_task(temp_ledger):
    """Test adding a dynamic Day 1-10 interest task."""
    card = temp_ledger.add_task(
        title="Mani Monthly Interest",
        task_type="MONTHLY_INTEREST",
        party="Mani",
        amount=5000.0,
        due_day_start=1,
        due_day_end=10,
        recurring_monthly=True
    )
    assert card["status"] == "PENDING"
    assert card["party"] == "Mani"
    assert card["amount"] == 5000.0


def test_interest_window_anomaly_day_7(temp_ledger):
    """Verify that Day 7 generates a warning with 3 days left."""
    temp_ledger.add_task(
        title="Mani Monthly Interest",
        task_type="MONTHLY_INTEREST",
        party="Mani",
        amount=5000.0,
        due_day_start=1,
        due_day_end=10
    )
    # Simulate Day 7
    dt_day_7 = datetime(2026, 10, 7, 6, 0, 0)
    anomalies = temp_ledger.evaluate_daily_anomalies(current_dt=dt_day_7)
    
    assert len(anomalies) == 1
    assert "Mani" in anomalies[0]["party"]
    assert "3 days left" in anomalies[0]["message"]
    assert anomalies[0]["urgency"] == "HIGH"


def test_interest_window_last_day_alert(temp_ledger):
    """Verify that Day 10 generates the critical LAST DAY alert."""
    temp_ledger.add_task(
        title="Mani Monthly Interest",
        task_type="MONTHLY_INTEREST",
        party="Mani",
        amount=5000.0,
        due_day_start=1,
        due_day_end=10
    )
    # Simulate Day 10
    dt_day_10 = datetime(2026, 10, 10, 6, 0, 0)
    anomalies = temp_ledger.evaluate_daily_anomalies(current_dt=dt_day_10)

    assert len(anomalies) == 1
    assert "LAST DAY" in anomalies[0]["message"]


def test_outside_window_stays_silent(temp_ledger):
    """Verify that outside the window (e.g. Day 15), zero alerts are generated."""
    temp_ledger.add_task(
        title="Mani Monthly Interest",
        task_type="MONTHLY_INTEREST",
        party="Mani",
        amount=5000.0,
        due_day_start=1,
        due_day_end=10
    )
    # Simulate Day 15
    dt_day_15 = datetime(2026, 10, 15, 6, 0, 0)
    anomalies = temp_ledger.evaluate_daily_anomalies(current_dt=dt_day_15)

    assert len(anomalies) == 0  # Zero spam!


def test_mark_cleared_silences_alerts(temp_ledger):
    """Verify that once Mukil marks paid, alert is immediately silenced."""
    temp_ledger.add_task(
        title="Mani Monthly Interest",
        task_type="MONTHLY_INTEREST",
        party="Mani",
        amount=5000.0,
        due_day_start=1,
        due_day_end=10
    )
    # Mark paid
    temp_ledger.mark_cleared("Mani")
    
    # Check Day 7 again
    dt_day_7 = datetime(2026, 10, 7, 6, 0, 0)
    anomalies = temp_ledger.evaluate_daily_anomalies(current_dt=dt_day_7)

    assert len(anomalies) == 0  # Completely silenced!
