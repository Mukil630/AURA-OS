"""API integration tests for Memory Subsystem endpoints."""
import pytest
from httpx import AsyncClient

from app.core.enums import MemoryScope, MemoryType


@pytest.mark.anyio
async def test_memory_api_store_and_retrieve(client: AsyncClient):
    # 1. Store memory
    store_payload = {
        "user_id": "mukil_api",
        "memory_type": MemoryType.SEMANTIC_FACT.value,
        "content": "Official Master Resume Link is 1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ",
        "summary": "Master Resume Link",
        "importance_score": 0.95,
        "tags": ["resume", "drive"],
    }
    resp = await client.post("/api/v1/memory/store", json=store_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["memory_id"].startswith("mem_")
    mem_id = data["memory_id"]

    # 2. Get memory by ID
    get_resp = await client.get(f"/api/v1/memory/{mem_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == store_payload["content"]

    # 3. Query memory
    query_payload = {
        "query_text": "resume link drive",
        "user_id": "mukil_api",
        "top_k": 3,
    }
    query_resp = await client.post("/api/v1/memory/query", json=query_payload)
    assert query_resp.status_code == 200
    results = query_resp.json()
    assert len(results) >= 1
    assert "1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ" in results[0]["content"]

    # 4. Delete memory
    del_resp = await client.delete(f"/api/v1/memory/{mem_id}")
    assert del_resp.status_code == 204

    # 5. Confirm 404 after deletion
    get_again = await client.get(f"/api/v1/memory/{mem_id}")
    assert get_again.status_code == 404
