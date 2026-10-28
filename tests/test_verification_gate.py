"""
========================================================================================
JARVIS TEST SUITE — ZERO-HALLUCINATION VERIFICATION GATE (test_verification_gate.py)
----------------------------------------------------------------------------------------
Tests:
1. Real SGC Billing Database Physical Fact Verification.
2. Anti-Hallucination Gate (Catches and blocks wrong amounts).
3. Physical Device State Verification (Catches disconnected devices).
4. Self-Healing Reconnect Flow.
========================================================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain.verification_gate import VerificationGate


def test_sgc_real_record_verification():
    """Verify that a legitimate physical record (e.g. Gaia) passes verification."""
    is_valid, msg, record = VerificationGate.verify_sgc_ground_truth("gaia", claimed_amount=1575.0)
    assert is_valid is True
    assert "VERIFIED" in msg
    assert record.get("billNo") == "7" or "GAIA" in str(record.get("customer", "")).upper()


def test_sgc_anti_hallucination_blocks_wrong_amount():
    """Verify that if an AI hallucinates ₹9,999 for Gaia, the gate BLOCKS it."""
    is_valid, msg, record = VerificationGate.verify_sgc_ground_truth("gaia", claimed_amount=9999.0)
    assert is_valid is False
    assert "HALLUCINATION BLOCKED" in msg


def test_sgc_blocks_non_existent_customer():
    """Verify that fabricated customers are rejected with Ground-truth check failed."""
    is_valid, msg, record = VerificationGate.verify_sgc_ground_truth("NonExistentStarkIndustries123")
    assert is_valid is False
    assert "Ground-truth check failed" in msg


def test_device_physical_failure_detection():
    """Verify that an offline device or failed ADB returncode is flagged truthfully."""
    is_valid, msg = VerificationGate.verify_device_action("192.168.1.15", "power", 1, "error: device offline")
    assert is_valid is False
    assert "PHYSICAL FAILURE" in msg


def test_device_physical_success_verification():
    """Verify that a successful 0 exit code physically validates."""
    is_valid, msg = VerificationGate.verify_device_action("192.168.1.15", "power", 0, "Success")
    assert is_valid is True
    assert "VERIFIED" in msg
