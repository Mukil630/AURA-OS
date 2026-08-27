"""Unit tests for IntentClassifier."""
from app.core.enums import (
    IntentCategory,
    RiskLevel,
    TaskType,
)
from app.core.intent_classifier import IntentClassifier
from app.core.normalizer import RequestNormalizer


def test_reminder_schedule_intent_classification():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "Tomorrow 9 AM remind me to study Java"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.AUTOMATION_SCHEDULE
    assert parsed.task_type == TaskType.SCHEDULED_TASK
    assert parsed.risk_level == RiskLevel.LOW
    assert "reminder.create" in parsed.required_capabilities
    assert parsed.extracted_entities.time == "09:00"
    assert parsed.extracted_entities.relative_day == "tomorrow"
    assert "study Java" in parsed.extracted_entities.subject
    assert parsed.confidence_score >= 0.90


def test_coding_ci_fix_intent_classification():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "Check my GitHub CI builds on Mukil630/AURA-OS and fix simple errors"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.CODE_ASSISTANCE
    assert parsed.task_type == TaskType.CODING
    assert parsed.risk_level == RiskLevel.MEDIUM
    assert "github.read_ci" in parsed.required_capabilities
    assert "coding.apply_fix" in parsed.required_capabilities
    assert "coding.run_tests" in parsed.required_capabilities
    assert parsed.extracted_entities.target_repo == "Mukil630/AURA-OS"


def test_google_drive_file_sync_intent():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "Upload report.pdf to Google Drive vault"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.FILE_SYNC
    assert parsed.task_type == TaskType.FILE_OPERATION
    assert "drive.upload" in parsed.required_capabilities
    assert parsed.extracted_entities.file_path == "report.pdf"


def test_telegram_communication_intent():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "Send Telegram message to @mukil"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.COMMUNICATION_DISPATCH
    assert parsed.task_type == TaskType.COMMUNICATION
    assert "telegram.send_message" in parsed.required_capabilities
    assert parsed.extracted_entities.recipient == "mukil"


def test_pc_hardware_battery_intent():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "Check my PC battery percentage"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.PC_HARDWARE_CONTROL
    assert parsed.task_type == TaskType.SYSTEM_CONTROL
    assert "pc.system_info" in parsed.required_capabilities
    assert parsed.risk_level == RiskLevel.LOW


def test_research_query_intent():
    normalizer = RequestNormalizer()
    classifier = IntentClassifier()

    raw = "What is PostgreSQL database architecture?"
    payload = normalizer.normalize(raw)
    parsed = classifier.classify(payload)

    assert parsed.intent == IntentCategory.QUERY
    assert parsed.task_type == TaskType.RESEARCH
    assert "web.search" in parsed.required_capabilities
