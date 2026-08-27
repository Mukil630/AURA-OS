"""Integration tests for Workflow API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_full_pipeline_task_execution(client: AsyncClient):
    # 1. Create a task via Phase 1 endpoint
    create_payload = {
        "user_id": "mukil_e2e",
        "raw_input": "Check my GitHub CI builds and fix simple errors",
        "channel": "web",
    }
    create_resp = await client.post("/api/v1/tasks", json=create_payload)
    assert create_resp.status_code == 201
    task_id = create_resp.json()["task"]["task_id"]

    # 2. Execute Task Workflow via POST /api/v1/workflows/tasks/{task_id}/execute
    exec_resp = await client.post(f"/api/v1/workflows/tasks/{task_id}/execute")
    assert exec_resp.status_code == 200
    data = exec_resp.json()

    workflow = data["workflow"]
    task = data["task"]

    assert workflow["status"] == "completed"
    assert len(workflow["steps"]) == 5
    assert all(s["status"] == "completed" for s in workflow["steps"])

    assert task["status"] == "completed"
    assert "all 5 steps" in task["result_summary"].lower()

    # 3. Check State Checkpoint via GET /api/v1/workflows/{workflow_id}/state
    wf_id = workflow["workflow_id"]
    state_resp = await client.get(f"/api/v1/workflows/{wf_id}/state")
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["status"] == "completed"
    assert len(state["completed_step_ids"]) == 5

    # 4. Check Audit Timeline
    events_resp = await client.get(f"/api/v1/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "task_created" in event_types
    assert "workflow_started" in event_types
    assert "step_started" in event_types
    assert "step_completed" in event_types
    assert "workflow_completed" in event_types
    assert "task_completed" in event_types
