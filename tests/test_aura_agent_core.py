import asyncio
import pytest
from fastapi.testclient import TestClient
from aura_agent_core.database import init_database
from aura_agent_core.nlp_parser import parse_natural_time, clean_tanglish
from aura_agent_core.services import (
    create_reminder, list_active_reminders, cancel_reminder,
    save_to_vault, search_vault, delete_vault_item
)
from app.main import app


def test_turso_db_init():
    res = asyncio.run(init_database())
    assert res is True


def test_nlp_parser_variations():
    # Tanglish cleaning
    assert "tomorrow" in clean_tanglish("naalaiki kaalaila 9am")
    assert "evening" in clean_tanglish("sayanthram 6pm")

    # Time parsing
    res_sec = parse_natural_time("15s")
    assert res_sec["success"] is True
    assert res_sec["delay_seconds"] == 15

    res_tomorrow = parse_natural_time("tomorrow 10am")
    assert res_tomorrow["success"] is True
    assert "10:00:00" in res_tomorrow["scheduled_iso"]

    res_tanglish = parse_natural_time("naalaiki kaalaila 9am")
    assert res_tanglish["success"] is True
    assert "09:00:00" in res_tanglish["scheduled_iso"]


def test_turso_services_crud():
    async def run_crud():
        # 1. Reminder CRUD
        rem_id = await create_reminder("Test pytest reminder", "2099-01-01 10:00:00")
        assert rem_id > 0

        active = await list_active_reminders()
        assert any(r["id"] == rem_id for r in active)

        cancelled = await cancel_reminder(rem_id)
        assert cancelled is True

        # 2. Vault CRUD
        vault_id = await save_to_vault(
            category="TEST",
            title="Pytest Vault Item",
            content="Automated verification content",
            drive_link="https://drive.google.com/pytest_link",
            tags="test,pytest"
        )
        assert vault_id > 0

        found = await search_vault(keyword="Pytest Vault Item")
        assert len(found) >= 1
        assert found[0]["category"] == "TEST"

        deleted = await delete_vault_item(vault_id)
        assert deleted is True

    asyncio.run(run_crud())


def test_fastapi_core_endpoints():
    client = TestClient(app)

    # 1. POST reminder
    res_add = client.post("/api/reminders/add", json={
        "task": "Test reminder via API",
        "when": "tomorrow 4pm"
    })
    assert res_add.status_code == 200
    data_add = res_add.json()
    assert data_add["status"] == "success"
    rem_id = data_add["reminder_id"]

    # 2. GET reminders list
    res_list = client.get("/api/reminders/list")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert any(r["id"] == rem_id for r in data_list["reminders"])

    # 3. DELETE cancel reminder
    res_del = client.delete(f"/api/reminders/cancel/{rem_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

    # 4. POST vault save
    res_v_save = client.post("/api/vault/save", json={
        "category": "BILLS",
        "title": "API Test Bill Memory",
        "content": "Verify Turso API Vault storage",
        "drive_link": "https://drive.google.com/test_bill_api",
        "tags": "api,test"
    })
    assert res_v_save.status_code == 200
    v_id = res_v_save.json()["vault_id"]

    # 5. GET vault search
    res_v_search = client.get("/api/vault/search?q=API Test Bill")
    assert res_v_search.status_code == 200
    assert res_v_search.json()["count"] >= 1

    # 6. DELETE vault delete
    res_v_del = client.delete(f"/api/vault/delete/{v_id}")
    assert res_v_del.status_code == 200
    assert res_v_del.json()["status"] == "success"
