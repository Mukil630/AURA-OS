"""Integration tests for Master Agent API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_understand_endpoint(client: AsyncClient):
    payload = {
        "raw_input": "Hey Jarvis, tomorrow 9 AM remind me to study Java",
        "channel": "voice",
        "user_id": "mukil_voice",
    }
    resp = await client.post("/api/v1/master/understand", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "parsed_intent" in data
    parsed = data["parsed_intent"]
    assert parsed["intent"] == "automation_schedule"
    assert parsed["task_type"] == "scheduled_task"
    assert "reminder.create" in parsed["required_capabilities"]
    assert parsed["extracted_entities"]["time"] == "09:00"
    assert parsed["extracted_entities"]["relative_day"] == "tomorrow"


@pytest.mark.anyio
async def test_parse_stored_task_endpoint(client: AsyncClient):
    # 1. Create a task via Phase 1 endpoint
    create_payload = {
        "user_id": "mukil_local",
        "raw_input": "Check my GitHub CI builds and fix simple errors",
        "channel": "web",
    }
    create_resp = await client.post("/api/v1/tasks", json=create_payload)
    assert create_resp.status_code == 201
    task_id = create_resp.json()["task"]["task_id"]

    # 2. Trigger Phase 2 parsing via POST /api/v1/master/tasks/{task_id}/parse
    parse_resp = await client.post(f"/api/v1/master/tasks/{task_id}/parse")
    assert parse_resp.status_code == 200
    parse_data = parse_resp.json()
    assert "task" in parse_data
    assert "understanding" in parse_data

    updated_task = parse_data["task"]["task"]
    assert updated_task["status"] == "planning"
    assert updated_task["intent"] == "code_assistance"
    assert updated_task["task_type"] == "coding"

    understanding = parse_data["understanding"]["parsed_intent"]
    assert "github.read_ci" in understanding["required_capabilities"]
    assert "coding.apply_fix" in understanding["required_capabilities"]

    # 3. Verify TASK_PARSED event was recorded in audit timeline
    events_resp = await client.get(f"/api/v1/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "task_created" in event_types
    assert "task_parsed" in event_types
