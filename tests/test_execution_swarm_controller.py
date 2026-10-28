"""
========================================================================================
JARVIS TEST SUITE — EXECUTION SWARM CONTROLLER (test_execution_swarm_controller.py)
----------------------------------------------------------------------------------------
Tests Mukil's Execution-First Mandates:
1. Action-Before-Speech (Tools execute before speech synthesis).
2. Honest failure disclosure if primary agent breaks.
3. Automatic handover to backup agent with retry.
4. Double failure truthfulness (Zero fake success).
========================================================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain.execution_swarm_controller import ExecutionSwarmController


def test_action_before_speech_primary_success():
    """Verify tool runs first and successful output forms the speech reply."""
    controller = ExecutionSwarmController(
        primary_agent_name="XstreamAdbPilot",
        backup_agent_name="SmartIRBlaster"
    )
    
    execution_order = []

    def mock_primary_tool():
        execution_order.append("TOOL_EXECUTED")
        return True, "TV Volume Muted (Code 164)"

    res = controller.execute_with_fallback(
        task_name="Mute TV",
        primary_tool_fn=mock_primary_tool
    )

    assert execution_order == ["TOOL_EXECUTED"]
    assert res["success"] is True
    assert res["agent_used"] == "XstreamAdbPilot"
    assert "TV Volume Muted" in res["final_reply"]


def test_primary_failure_triggers_honest_disclosure_and_backup_retry():
    """Verify primary failure is disclosed, backup agent is engaged, and retry succeeds."""
    controller = ExecutionSwarmController(
        primary_agent_name="XstreamAdbPilot",
        backup_agent_name="SmartIRBlaster"
    )

    execution_order = []

    def mock_primary_fail():
        execution_order.append("PRIMARY_TRIED")
        return False, "ADB Connection refused: 192.168.1.15:5555 offline"

    def mock_backup_success():
        execution_order.append("BACKUP_TRIED")
        return True, "IR Signal broadcast: Mute sent to TV"

    res = controller.execute_with_fallback(
        task_name="Mute TV",
        primary_tool_fn=mock_primary_fail,
        backup_tool_fn=mock_backup_success
    )

    # Verify execution order: Primary tried -> Backup tried
    assert execution_order == ["PRIMARY_TRIED", "BACKUP_TRIED"]
    assert res["success"] is True
    assert res["agent_used"] == "SmartIRBlaster"
    assert res["retried"] is True
    # Verify honest disclosure is in the reply
    assert "XstreamAdbPilot" in res["final_reply"]
    assert "Switched to Backup Agent (SmartIRBlaster)" in res["final_reply"]


def test_double_failure_truthful_admission_zero_hallucination():
    """Verify that if both primary and backup fail, agent admits failure truthfully."""
    controller = ExecutionSwarmController(
        primary_agent_name="XstreamAdbPilot",
        backup_agent_name="SmartIRBlaster"
    )

    def mock_primary_fail():
        return False, "Device unreachable"

    def mock_backup_fail():
        return False, "IR Blaster USB unplugged"

    res = controller.execute_with_fallback(
        task_name="Turn on AC",
        primary_tool_fn=mock_primary_fail,
        backup_tool_fn=mock_backup_fail
    )

    assert res["success"] is False
    assert res["all_failed"] is True
    # Must NOT hallucinate success!
    assert "Task execution failed" in res["final_reply"]
    assert "Physical action could not be completed" in res["final_reply"]
