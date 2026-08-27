"""Unit tests for MasterAgent reasoning orchestrator."""
import pytest
from app.agents.master.master_agent import MasterAgent
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, IntentCategory, TaskStatus, TaskType


def test_master_agent_understand_flow():
    agent = MasterAgent()
    context = agent.understand(
        raw_input="Hey Jarvis, tomorrow 9 AM remind me to study Java",
        channel=ChannelType.VOICE,
        user_id="mukil_test",
    )
    assert context.task_id.startswith("task_")
    assert context.user_id == "mukil_test"
    assert context.channel == ChannelType.VOICE
    assert context.parsed_intent.intent == IntentCategory.AUTOMATION_SCHEDULE
    assert context.parsed_intent.task_type == TaskType.SCHEDULED_TASK
    assert "reminder.create" in context.parsed_intent.required_capabilities
    assert context.parsed_intent.extracted_entities.time == "09:00"


def test_master_agent_enrich_task():
    agent = MasterAgent()
    task = TaskContract(
        user_id="mukil_test",
        raw_input="Check my GitHub CI builds and fix simple errors",
        channel=ChannelType.WEB,
        status=TaskStatus.CREATED,
    )
    updated_task, context = agent.enrich_task_with_understanding(task)

    assert updated_task.status == TaskStatus.PLANNING
    assert updated_task.intent == IntentCategory.CODE_ASSISTANCE
    assert updated_task.task_type == TaskType.CODING
    assert len(context.parsed_intent.required_capabilities) >= 2


@pytest.mark.anyio
async def test_master_agent_contract_and_health():
    agent = MasterAgent()
    contract = await agent.get_contract()
    assert contract.agent_id == "master_agent"
    assert len(contract.capabilities) >= 1
    assert await agent.health_check() is True
