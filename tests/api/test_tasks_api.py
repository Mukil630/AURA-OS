"""Integration tests for Task API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_and_get_task_flow(client: AsyncClient):
    # 1. Create Task via POST /api/v1/tasks
    create_payload = {
        "user_id": "mukil_user_1",
        "raw_input": "Check my GitHub CI for failed workflows",
        "channel": "voice",
        "priority": "high",
        "tags": ["github", "ci", "automated"],
    }
    create_resp = await client.post("/api/v1/tasks", json=create_payload)
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    assert "task" in create_data
    task = create_data["task"]
    task_id = task["task_id"]
    assert task_id.startswith("task_")
    assert task["user_id"] == "mukil_user_1"
    assert task["raw_input"] == "Check my GitHub CI for failed workflows"
    assert task["status"] == "created"
    assert task["channel"] == "voice"
    assert task["priority"] == "high"

    # 2. Get Task via GET /api/v1/tasks/{task_id}
    get_resp = await client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["task"]["task_id"] == task_id
    assert get_data["task"]["raw_input"] == "Check my GitHub CI for failed workflows"

    # 3. Get Task Audit Events via GET /api/v1/tasks/{task_id}/events
    events_resp = await client.get(f"/api/v1/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "task_created"
    assert events[0]["task_id"] == task_id


@pytest.mark.anyio
async def test_get_nonexistent_task(client: AsyncClient):
    resp = await client.get("/api/v1/tasks/task_nonexistent_999")
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.anyio
async def test_list_tasks(client: AsyncClient):
    # Seed 2 tasks
    await client.post("/api/v1/tasks", json={"user_id": "user_a", "raw_input": "Task Alpha"})
    await client.post("/api/v1/tasks", json={"user_id": "user_b", "raw_input": "Task Beta"})

    # Query all
    list_resp = await client.get("/api/v1/tasks")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 2
    assert len(list_data["tasks"]) >= 2

    # Filter by user
    user_resp = await client.get("/api/v1/tasks?user_id=user_a")
    assert user_resp.status_code == 200
    user_data = user_resp.json()
    assert user_data["total"] == 1
    assert user_data["tasks"][0]["user_id"] == "user_a"


@pytest.mark.anyio
async def test_task_creation_validation_error(client: AsyncClient):
    # Empty raw_input should fail validation with 422
    resp = await client.post("/api/v1/tasks", json={"user_id": "user_a", "raw_input": ""})
    assert resp.status_code == 422
