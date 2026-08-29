"""Unit & Integration Tests for SGC Automated Payment Reminders & Stark Protocol Guard."""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.agents.business.sgc_reminder_agent import SGCReminderAgent
from app.tools.agent_brain import AutonomousAgentBrain


def test_sgc_01_overdue_analysis():
    """Verify SGCReminderAgent accurately groups customer balances and calculates overdue ages."""
    agent = SGCReminderAgent()
    overdue = agent.get_overdue_analysis()
    assert len(overdue) >= 3

    # Check MSK Fabrics
    msk = next((c for c in overdue if c["customer_name"] == "M.S.K Fabrics"), None)
    assert msk is not None
    assert msk["total_pending_balance"] == 5488.0
    assert msk["party_gst"] == "33AAVFM9953BIZW"
    assert len(msk["bills"]) == 1


def test_sgc_02_bilingual_reminder_message_generation():
    """Verify respectful Tamil and English reminder pitches are generated with active Drive vault link."""
    agent = SGCReminderAgent()
    rem = agent.generate_reminder_message("M.S.K Fabrics", language="tamil")
    
    assert "M.S.K Fabrics" in rem["tamil_message"]
    assert "5,488" in rem["tamil_message"]
    assert "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9" in rem["tamil_message"]
    assert "https://wa.me/?text=" in rem["whatsapp_share_url"]

    rem_en = agent.generate_reminder_message("M.S.K Fabrics", language="english")
    assert "Dear M.S.K Fabrics" in rem_en["english_message"]
    assert "5,488" in rem_en["english_message"]


def test_sgc_03_all_reminders_summary():
    """Verify executive summary lists all pending customers with 1-click WhatsApp links."""
    agent = SGCReminderAgent()
    summary = agent.generate_all_reminders_summary()
    assert "SGC AUTOMATED CUSTOMER PAYMENT REMINDERS RADAR" in summary
    assert "M.S.K Fabrics" in summary
    assert "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9" in summary


def test_sgc_04_agent_brain_stark_security_confirmation_gate():
    """Verify Stark Protocol intercepts unauthorized dispatch and succeeds when confirmed."""
    brain = AutonomousAgentBrain(api_key="mock_key")

    # 1. Unconfirmed attempt -> Trigger Stark Security Guard
    res_guard, photo = brain.execute_tool("dispatch_sgc_reminder", {"customer_name": "M.S.K Fabrics", "confirmed": False})
    assert "STARK SECURITY PROTOCOL CONFIRMATION REQUIRED" in res_guard
    assert "M.S.K Fabrics" in res_guard
    assert "AURA Protocol Stark 55" in res_guard
    assert photo is None

    # 2. Confirmed attempt -> Execute and log
    with patch.object(brain.pc_pilot, "open_url") as mock_open, \
         patch.object(brain.pc_pilot, "capture_screen", return_value=("ok", "test_screen.png", None)):
        res_success, p_path = brain.execute_tool("dispatch_sgc_reminder", {"customer_name": "M.S.K Fabrics", "confirmed": True})
        assert "STARK PROTOCOL VERIFIED" in res_success
        assert "M.S.K Fabrics" in res_success
        assert "5,488" in res_success
        mock_open.assert_called_once()
