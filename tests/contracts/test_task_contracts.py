"""Unit tests for Task Contracts."""
import pytest
from pydantic import ValidationError

from app.core.contracts.task import (
    TaskContract,
    TaskCreateRequestContract,
    TaskResponseContract,
)
from app.core.enums import ChannelType, PriorityLevel, RiskLevel, TaskStatus, TaskType


def test_task_contract_creation_defaults():
    task = TaskContract(
        user_id="user_123",
        raw_input="Check my GitHub builds"
    )
    assert task.schema_version == "v1"
    assert task.task_id.startswith("task_")
    assert task.user_id == "user_123"
    assert task.raw_input == "Check my GitHub builds"
    assert task.status == TaskStatus.CREATED
    assert task.task_type == TaskType.ACTION
    assert task.priority == PriorityLevel.NORMAL
    assert task.risk_level == RiskLevel.LOW
    assert task.channel == ChannelType.API


def test_task_contract_validation_error_empty_input():
    with pytest.raises(ValidationError):
        TaskContract(user_id="user_123", raw_input="")


def test_task_create_request_contract():
    req = TaskCreateRequestContract(
        user_id="user_456",
        raw_input="Deploy my Railway project",
        channel=ChannelType.VOICE,
        priority=PriorityLevel.HIGH,
    )
    assert req.user_id == "user_456"
    assert req.channel == ChannelType.VOICE
    assert req.priority == PriorityLevel.HIGH


def test_task_response_contract_serialization():
    task = TaskContract(user_id="user_789", raw_input="Search web for AI news")
    resp = TaskResponseContract(task=task, message="Task created")
    data = resp.model_dump()
    assert data["task"]["user_id"] == "user_789"
    assert data["message"] == "Task created"
    assert data["schema_version"] == "v1"
