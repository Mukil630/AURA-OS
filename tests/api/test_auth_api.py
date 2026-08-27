"""Integration tests for Authentication API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_auth_token_generation_and_me(client: AsyncClient):
    # 1. Generate Token
    payload = {"user_id": "mukil_engineer", "role": "admin"}
    token_resp = await client.post("/api/v1/auth/token", json=payload)
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 2. Access /api/v1/auth/me with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["user_id"] == "mukil_engineer"
    assert me_data["role"] == "admin"
    assert me_data["auth_method"] == "bearer"
