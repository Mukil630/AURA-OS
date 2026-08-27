"""API Tests for External Connectors and Capability Registry Endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security.auth import create_access_token


@pytest.mark.anyio
async def test_connectors_api_list_and_health():
    token = create_access_token(user_id="mukil", role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. List connectors
        res = await client.get("/api/v1/connectors", headers=headers)
        assert res.status_code == 200
        conns = res.json()
        assert len(conns) >= 1
        assert any(c["connector_id"] == "connector_github" for c in conns)

        # 2. List capabilities
        cap_res = await client.get("/api/v1/connectors/capabilities", headers=headers)
        assert cap_res.status_code == 200
        caps = cap_res.json()
        assert len(caps) >= 5

        # 3. Probe GitHub health
        health_res = await client.get("/api/v1/connectors/connector_github/health", headers=headers)
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "connected"

        # 4. Store credentials safely (returns masked value)
        cred_res = await client.post(
            "/api/v1/connectors/credentials",
            json={"provider": "github", "token": "ghp_mockSecretKey12345678"},
            headers=headers,
        )
        assert cred_res.status_code == 200
        assert cred_res.json()["masked_value"] == "ghp_****5678"

        # 5. Kill-Switch Toggle (Admin)
        ks_res = await client.post(
            "/api/v1/connectors/kill-switch",
            json={"connector_id": "connector_github", "enabled": False},
            headers=headers,
        )
        assert ks_res.status_code == 200
        assert ks_res.json()["is_enabled"] is False

        # Re-enable
        ks_res2 = await client.post(
            "/api/v1/connectors/kill-switch",
            json={"connector_id": "connector_github", "enabled": True},
            headers=headers,
        )
        assert ks_res2.status_code == 200
        assert ks_res2.json()["is_enabled"] is True
