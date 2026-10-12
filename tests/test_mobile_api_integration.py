"""
Tests for Mobile Application & Backend API Integration.
Verifies Central Orchestrator, Live Vision, SGC Billing, and Call Triggering.
"""
import os
import sys
import base64
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import create_app

@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "healthy" or data.get("status") == "ok"

def test_orchestrator_sgc_query(client):
    res = client.post(
        "/api/v1/orchestrator/process",
        json={"message": "Check SGC billing total bills and turnover", "channel": "TEST"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["intent"] == "SGC_BILLING_QUERY"
    assert "Sri Ganapathi Colours" in data["reply"]
    assert "bills" in data["speech_reply"].lower()

def test_orchestrator_reminder_schedule(client):
    res = client.post(
        "/api/v1/orchestrator/process",
        json={"message": "Remind me in 10 minutes to verify dyeing recipes", "channel": "TEST"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["intent"] == "SCHEDULE_REMINDER"
    assert "DURABLE REMINDER SCHEDULED" in data["reply"]

def test_chat_hub_sgc_integration(client):
    res = client.post(
        "/api/v1/hub/chat",
        json={"message": "Check SGC billing turnover", "channel": "MOBILE_APP"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "speech_reply" in data
    assert data.get("intent") == "SGC_BILLING_QUERY"

def test_call_hub_trigger_offline_fallback(client):
    res = client.post(
        "/api/v1/call/trigger",
        json={"caller_name": "JARVIS", "reason": "test"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["success", "pending_or_offline"]

def test_vision_analyze_synthetic_image(client):
    # Create a simple red 100x100 test image in memory
    img = Image.new("RGB", (100, 100), color=(220, 20, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    res = client.post(
        "/api/v1/vision/analyze_base64",
        json={
            "image_base64": b64_str,
            "query": "Identify the primary color and describe this swatch",
            "channel": "TEST"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "analysis" in data
    assert "speech_reply" in data
    assert len(data["speech_reply"]) > 0
