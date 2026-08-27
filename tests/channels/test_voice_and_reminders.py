"""Unit and Integration Tests for JARVIS Neural Voice Engine and Reminder Scheduler."""
import asyncio
from datetime import datetime, timedelta, timezone
import os
import tempfile
import pytest

from app.tools.reminder_scheduler import ReminderScheduler
from app.tools.tts_engine import JARVISVoiceEngine, TAMIL_VOICE, ENGLISH_VOICE


def test_vr_01_tts_script_detection():
    """VR-01: Voice engine automatically detects Tamil script vs English."""
    engine = JARVISVoiceEngine()
    assert engine._detect_script("வணக்கம் மாப்ள!") == TAMIL_VOICE
    assert engine._detect_script("Hello Maapla, how are you?") == ENGLISH_VOICE
    assert engine._detect_script("Java study session 10 PM") == ENGLISH_VOICE
    assert engine._detect_script("நினைவூட்டல் பதிவு செய்யப்பட்டது") == TAMIL_VOICE


def test_vr_02_tts_empty_input_validation():
    """VR-02: Voice engine raises ValueError on empty text."""
    engine = JARVISVoiceEngine()
    with pytest.raises(ValueError):
        asyncio.run(engine.generate_voice_bytes(""))
    with pytest.raises(ValueError):
        asyncio.run(engine.generate_voice_bytes("   "))


def test_vr_03_reminder_parsing_relative_minutes():
    """VR-03: Reminder parser correctly calculates future target timestamp for minutes."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        scheduler = ReminderScheduler(storage_path=tmp_path)
        rem = scheduler.parse_and_create(chat_id=12345, user_id=67890, command_args="10m Study Java")
        assert rem["message"] == "Study Java"
        assert rem["chat_id"] == 12345
        assert rem["user_id"] == 67890
        assert rem["status"] == "pending"

        target = datetime.fromisoformat(rem["target_time"])
        now = datetime.now(timezone.utc)
        diff = (target - now).total_seconds()
        assert 590 <= diff <= 610
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_vr_04_reminder_parsing_hours_and_minutes():
    """VR-04: Reminder parser correctly parses 'in 1h 30m Placement Aptitude'."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        scheduler = ReminderScheduler(storage_path=tmp_path)
        rem = scheduler.parse_and_create(chat_id=12345, user_id=67890, command_args="in 1h 30m Placement Aptitude")
        assert rem["message"] == "Placement Aptitude"
        target = datetime.fromisoformat(rem["target_time"])
        now = datetime.now(timezone.utc)
        diff = (target - now).total_seconds()
        assert 5390 <= diff <= 5410
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_vr_05_reminder_list_and_cancellation():
    """VR-05: List reminders filters active ones and cancellation works."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        scheduler = ReminderScheduler(storage_path=tmp_path)
        rem1 = scheduler.parse_and_create(chat_id=100, user_id=200, command_args="5m Task 1")
        rem2 = scheduler.parse_and_create(chat_id=100, user_id=200, command_args="15m Task 2")

        active = scheduler.list_reminders(user_id=200)
        assert len(active) == 2

        assert scheduler.cancel_reminder(rem1["reminder_id"]) is True
        active_after = scheduler.list_reminders(user_id=200)
        assert len(active_after) == 1
        assert active_after[0]["reminder_id"] == rem2["reminder_id"]

        assert scheduler.cancel_reminder("non_existent_id") is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_vr_06_reminder_poll_loop_trigger():
    """VR-06: Reminder scheduler background loop fires due callback."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    async def _runner():
        scheduler = ReminderScheduler(storage_path=tmp_path)
        fired_reminders = []

        async def mock_callback(rem):
            fired_reminders.append(rem)

        scheduler.set_callback(mock_callback)

        # Manually create a reminder that is already due
        now = datetime.now(timezone.utc)
        past_target = now - timedelta(seconds=2)
        scheduler._reminders["test_due"] = {
            "reminder_id": "test_due",
            "chat_id": 111,
            "user_id": 222,
            "message": "Due now",
            "created_at": now.isoformat(),
            "target_time": past_target.isoformat(),
            "status": "pending",
        }

        await scheduler.start()
        await asyncio.sleep(2.5)
        await scheduler.stop()

        assert len(fired_reminders) == 1
        assert fired_reminders[0]["reminder_id"] == "test_due"
        assert scheduler._reminders["test_due"]["status"] == "fired"

    try:
        asyncio.run(_runner())
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
