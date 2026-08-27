"""Integration tests for Multi-Tenant Authorization and User Isolation."""
from datetime import timedelta
import pytest
from httpx import AsyncClient
from app.security.auth import create_access_token


@pytest.mark.anyio
async def test_tenant_task_isolation_and_authorization(client: AsyncClient):
    # 1. Generate Tokens for User A, User B, and Admin
    token_user_a = create_access_token(user_id="user_alice", role="authenticated_user")
    token_user_b = create_access_token(user_id="user_bob", role="authenticated_user")
    token_admin = create_access_token(user_id="mukil_admin", role="admin")

    headers_a = {"Authorization": f"Bearer {token_user_a}"}
    headers_b = {"Authorization": f"Bearer {token_user_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # 2. User A creates a task
    create_payload_a = {
        "user_id": "user_alice",
        "raw_input": "Alice's confidential project plan",
        "channel": "web",
    }
    resp_a = await client.post("/api/v1/tasks", json=create_payload_a, headers=headers_a)
    assert resp_a.status_code == 201
    task_a = resp_a.json()["task"]
    task_a_id = task_a["task_id"]

    # 3. User B creates a task
    create_payload_b = {
        "user_id": "user_bob",
        "raw_input": "Bob's public workflow task",
        "channel": "telegram",
    }
    resp_b = await client.post("/api/v1/tasks", json=create_payload_b, headers=headers_b)
    assert resp_b.status_code == 201
    task_b = resp_b.json()["task"]
    task_b_id = task_b["task_id"]

    # 4. User A can access User A's task
    get_a = await client.get(f"/api/v1/tasks/{task_a_id}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["task"]["user_id"] == "user_alice"

    # 5. User B CANNOT access User A's task (Forbidden)
    get_b_cross = await client.get(f"/api/v1/tasks/{task_a_id}", headers=headers_b)
    assert get_b_cross.status_code == 403
    assert "access denied" in get_b_cross.json()["detail"].lower()

    # 6. User B CANNOT access User A's task events (Forbidden)
    events_b_cross = await client.get(f"/api/v1/tasks/{task_a_id}/events", headers=headers_b)
    assert events_b_cross.status_code == 403

    # 7. Admin CAN access User A's task and events
    get_admin = await client.get(f"/api/v1/tasks/{task_a_id}", headers=headers_admin)
    assert get_admin.status_code == 200
    events_admin = await client.get(f"/api/v1/tasks/{task_a_id}/events", headers=headers_admin)
    assert events_admin.status_code == 200

    # 8. User A listing tasks ONLY returns User A's tasks (Tenant Isolation)
    list_a = await client.get("/api/v1/tasks", headers=headers_a)
    assert list_a.status_code == 200
    tasks_a = list_a.json()["tasks"]
    assert all(t["user_id"] == "user_alice" for t in tasks_a)
    assert not any(t["task_id"] == task_b_id for t in tasks_a)


@pytest.mark.anyio
async def test_invalid_and_expired_tokens(client: AsyncClient):
    # 1. Invalid Bearer Token
    bad_headers = {"Authorization": "Bearer invalid_gibberish_token"}
    resp = await client.get("/api/v1/tasks/task_123", headers=bad_headers)
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()

    # 2. Expired Token
    expired_token = create_access_token(user_id="user_alice", expires_delta=timedelta(seconds=-60))
    expired_headers = {"Authorization": f"Bearer {expired_token}"}
    resp_exp = await client.get("/api/v1/tasks/task_123", headers=expired_headers)
    assert resp_exp.status_code == 401
    assert "expired" in resp_exp.json()["detail"].lower()
