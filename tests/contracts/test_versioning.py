"""Unit tests for Contract Versioning and Extensibility."""
import pytest
from pydantic import ValidationError

from app.core.contracts import (
    MemoryContract,
    TaskContract,
    TaskStepContract,
    ToolContract,
    WorkflowContract,
)
from app.core.enums import AgentType, MemoryType, ToolCategory


def test_schema_version_default_v1():
    task = TaskContract(user_id="u1", raw_input="test")
    step = TaskStepContract(workflow_id="wf1", name="s1", agent_type=AgentType.RESEARCH, tool_name="t1")
    wf = WorkflowContract(task_id="t1", name="wf1")
    tool = ToolContract(tool_id="t1", name="t1", category=ToolCategory.UTILITY, description="d")
    mem = MemoryContract(memory_type=MemoryType.WORKING, user_id="u1", content="c")

    for entity in [task, step, wf, tool, mem]:
        assert entity.schema_version == "v1"


def test_metadata_extensibility():
    task = TaskContract(
        user_id="u1",
        raw_input="test",
        metadata={"client_ip": "127.0.0.1", "custom_tag": "experimental", "version_note": "v1.1_candidate"},
    )
    assert task.metadata["client_ip"] == "127.0.0.1"
    assert task.metadata["custom_tag"] == "experimental"


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        # Trying to pass undeclared top-level field should fail to preserve schema purity
        TaskContract(
            user_id="u1",
            raw_input="test",
            unauthorized_field="should_fail",  # type: ignore
        )
