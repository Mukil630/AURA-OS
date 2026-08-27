"""Integration tests for Task Planner API Endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_direct_plan_generation_endpoint(client: AsyncClient):
    payload = {
        "raw_input": "Check my GitHub CI builds and fix simple errors",
        "channel": "voice",
        "user_id": "mukil_voice",
    }
    resp = await client.post("/api/v1/planner/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "plan" in data
    assert "workflow" in data
    plan = data["plan"]
    assert len(plan["steps"]) == 5
    assert plan["steps"][0]["name"] == "read_ci_status"
    assert plan["steps"][4]["name"] == "run_verification_tests"


@pytest.mark.anyio
async def test_plan_and_persist_stored_task_endpoint(client: AsyncClient):
    # 1. Create a task via Phase 1 endpoint
    create_payload = {
        "user_id": "mukil_pipeline",
        "raw_input": "Upload master_resume.pdf to Google Drive vault",
        "channel": "web",
    }
    create_resp = await client.post("/api/v1/tasks", json=create_payload)
    assert create_resp.status_code == 201
    task_id = create_resp.json()["task"]["task_id"]

    # 2. Plan and persist via POST /api/v1/planner/tasks/{task_id}/plan
    plan_resp = await client.post(f"/api/v1/planner/tasks/{task_id}/plan")
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()

    workflow = plan_data["workflow"]
    workflow_id = workflow["workflow_id"]
    assert len(workflow["steps"]) == 3
    assert workflow["task_id"] == task_id

    # 3. Retrieve Planned Workflow via GET /api/v1/planner/tasks/{task_id}/workflow
    get_wf_resp = await client.get(f"/api/v1/planner/tasks/{task_id}/workflow")
    assert get_wf_resp.status_code == 200
    retrieved_wf = get_wf_resp.json()
    assert retrieved_wf["workflow_id"] == workflow_id
    assert len(retrieved_wf["steps"]) == 3

    # 4. Check audit event PLAN_GENERATED
    events_resp = await client.get(f"/api/v1/tasks/{task_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "plan_generated" in event_types
