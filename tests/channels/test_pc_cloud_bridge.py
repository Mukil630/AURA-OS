"""Unit and Integration Tests for Cloud ⟷ Local PC WebSocket Bridge."""
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.connectors.bridge.pc_cloud_bridge import CloudPCBridgeServer
from app.main import app


def test_bridge_01_worker_auth_and_connection():
    """BRIDGE-01: Validates PC worker WebSocket handshake and auth token verification."""
    async def _run():
        server = CloudPCBridgeServer(secret_token="test_secret_123")
        assert not server.is_pc_online()

        mock_ws = AsyncMock()

        # Unauthorized attempt
        unauth = await server.connect_worker(mock_ws, worker_id="pc_1", auth_token="wrong_token")
        assert not unauth
        assert not server.is_pc_online()

        # Authorized attempt
        auth = await server.connect_worker(mock_ws, worker_id="pc_1", auth_token="test_secret_123")
        assert auth
        assert server.is_pc_online()

        # Disconnect
        server.disconnect_worker("pc_1")
        assert not server.is_pc_online()

    asyncio.run(_run())


def test_bridge_02_offline_task_queueing():
    """BRIDGE-02: Queues tasks when PC is offline and flushes upon worker connection."""
    async def _run():
        server = CloudPCBridgeServer(secret_token="test_secret_123")

        # Dispatch while offline
        res = await server.dispatch_task(command="Open Visual Studio Code")
        assert res["status"] == "QUEUED_OFFLINE"
        assert len(server.offline_queue) == 1

        # Connect worker
        mock_ws = AsyncMock()
        await server.connect_worker(mock_ws, worker_id="pc_1", auth_token="test_secret_123")

        # Queue should be flushed
        assert len(server.offline_queue) == 0
        mock_ws.send_json.assert_called_once()

    asyncio.run(_run())


def test_bridge_03_task_dispatch_and_response_handling():
    """BRIDGE-03: Successfully dispatches task to connected worker and resolves future."""
    async def _run():
        server = CloudPCBridgeServer(secret_token="test_secret_123")
        mock_ws = AsyncMock()
        await server.connect_worker(mock_ws, worker_id="pc_1", auth_token="test_secret_123")

        # Simulate worker responding in background
        async def simulate_worker_response():
            await asyncio.sleep(0.05)
            sent_task = mock_ws.send_json.call_args[0][0]
            task_id = sent_task["task_id"]
            server.handle_worker_response({
                "task_id": task_id,
                "status": "COMPLETED",
                "output_text": "Notepad opened successfully.",
                "photo_path": None,
            })

        asyncio.create_task(simulate_worker_response())

        result = await server.dispatch_task(command="Open Notepad", timeout_seconds=5.0)
        assert result["status"] == "COMPLETED"
        assert "Notepad opened" in result["output_text"]

    asyncio.run(_run())


def test_bridge_04_fastapi_rest_endpoints():
    """BRIDGE-04: Validates FastAPI /api/v1/bridge/status endpoint."""
    client = TestClient(app)
    response = client.get("/api/v1/bridge/status")
    assert response.status_code == 200
    data = response.json()
    assert "pc_online" in data
    assert "active_workers" in data
