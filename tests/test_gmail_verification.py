"""Unit and Integration Tests for Gmail Verification and Placement Radar System."""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.connectors.gmail.connector import GoogleGmailConnector
from tools.gmail_verifier import GmailVerifier
from app.core.contracts.connector import ConnectorExecutionRequest


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def gmail_verifier():
    """GmailVerifier fixture."""
    return GmailVerifier(target_email="mukilarasu55@gmail.com")


@pytest.fixture
def gmail_connector():
    """GoogleGmailConnector fixture."""
    return GoogleGmailConnector(is_mock=True, target_email="mukilarasu55@gmail.com")


# ── 1. Tool-level Verification Tests ──────────────────────────────────────────

def test_gmail_verifier_mock_verification(gmail_verifier):
    """Assert mock/simulation verification produces verified telemetry."""
    res = gmail_verifier.verify_mock_connection()
    assert res["is_verified"] is True
    assert res["api_verified"] is True
    assert res["imap_verified"] is True
    assert res["smtp_verified"] is True
    assert res["email_address"] == "mukilarasu55@gmail.com"
    assert res["unread_messages"] >= 0


def test_gmail_verifier_comprehensive_verification(gmail_verifier):
    """Assert comprehensive multi-tier check returns valid payload."""
    res = gmail_verifier.run_comprehensive_verification(allow_mock=True)
    assert res["is_verified"] is True
    assert "email_address" in res
    assert "latency_ms" in res
    assert res["latency_ms"] >= 0


def test_gmail_verifier_placement_radar_scan(gmail_verifier):
    """Assert placement radar detects assessments and test links."""
    radar = gmail_verifier.scan_placement_radar(max_results=10)
    assert radar["total_scanned"] > 0
    assert radar["placement_alerts_count"] >= 3
    assert len(radar["assessments"]) >= 3

    # Validate Zoho assessment fixture
    zoho = next((a for a in radar["assessments"] if "zoho" in a["company"].lower()), None)
    assert zoho is not None
    assert "assessment_link" in zoho
    assert "deadline" in zoho
    assert zoho["priority"] == "URGENT"

    # Validate Capgemini assessment fixture
    capgemini = next((a for a in radar["assessments"] if "capgemini" in a["company"].lower()), None)
    assert capgemini is not None
    assert "teams.microsoft.com" in capgemini["assessment_link"]


def test_gmail_verifier_send_email_simulation(gmail_verifier):
    """Assert simulated email dispatch succeeds."""
    res = gmail_verifier.send_email(
        to_email="recruiter@zoho.com",
        subject="Application for AI Engineer - Mukilarasu S",
        body="Dear Recruiter,\nPlease find attached my master resume.\nBest regards,\nMukil",
    )
    assert res["success"] is True
    assert res["recipient"] == "recruiter@zoho.com"
    assert "message_id" in res


import asyncio

# ── 2. Connector Interface Tests ──────────────────────────────────────────────

def test_gmail_connector_contract(gmail_connector):
    """Assert connector contract metadata matches AURA-OS enterprise schema."""
    contract = gmail_connector.get_contract()
    assert contract.connector_id == "connector_google_gmail"
    assert contract.connector_type == "email"
    assert "gmail.verify_connection" in contract.supported_capabilities
    assert "gmail.scan_placement_radar" in contract.supported_capabilities
    assert "gmail.send_email" in contract.supported_capabilities


def test_gmail_connector_health_check(gmail_connector):
    """Assert connector health check returns healthy status."""
    health = asyncio.run(gmail_connector.health_check())
    assert health.connector_id == "connector_google_gmail"
    assert str(health.status) in ("connected", "auth_required", "ConnectorStatus.CONNECTED", "ConnectorStatus.AUTH_REQUIRED")
    assert health.latency_ms >= 0


def test_gmail_connector_execute_verify(gmail_connector):
    """Assert executing verify_connection capability returns success."""
    req = ConnectorExecutionRequest(
        capability_id="gmail.verify_connection",
        parameters={},
    )
    res = asyncio.run(gmail_connector.execute_capability(req))
    assert res.success is True
    assert res.status_code == 200
    assert res.data["is_verified"] is True


def test_gmail_connector_execute_radar(gmail_connector):
    """Assert executing scan_placement_radar capability returns assessments."""
    req = ConnectorExecutionRequest(
        capability_id="gmail.scan_placement_radar",
        parameters={"max_results": 5},
    )
    res = asyncio.run(gmail_connector.execute_capability(req))
    assert res.success is True
    assert res.status_code == 200
    assert res.data["placement_alerts_count"] >= 3


# ── 3. FastAPI REST Endpoints Tests ───────────────────────────────────────────

def test_api_gmail_status(client):
    """Assert GET /api/v1/gmail/status returns profile telemetry."""
    response = client.get("/api/v1/gmail/status")
    assert response.status_code == 200
    data = response.json()
    assert data["email_address"] == "mukilarasu55@gmail.com"
    assert data["is_verified"] is True
    assert data["unread_messages"] >= 0


def test_api_gmail_verify(client):
    """Assert POST /api/v1/gmail/verify executes live handshake."""
    response = client.post("/api/v1/gmail/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["is_verified"] is True
    assert "latency_ms" in data


def test_api_gmail_radar(client):
    """Assert GET /api/v1/gmail/radar returns parsed assessments."""
    response = client.get("/api/v1/gmail/radar?max_results=5")
    assert response.status_code == 200
    data = response.json()
    assert data["placement_alerts_count"] >= 3
    assert len(data["assessments"]) >= 3
    assert data["assessments"][0]["company"] != ""


def test_api_gmail_configure(client):
    """Assert POST /api/v1/gmail/configure updates settings."""
    payload = {
        "email_address": "mukil.career@gmail.com",
        "app_password": "testapppassword1234"
    }
    response = client.post("/api/v1/gmail/configure", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["email_address"] == "mukil.career@gmail.com"


def test_api_gmail_send(client):
    """Assert POST /api/v1/gmail/send dispatches email."""
    payload = {
        "to_email": "careers@zoho.com",
        "subject": "Interview Confirmation - Mukilarasu S",
        "body": "I confirm my availability for the interview round.\nThank you.",
        "is_html": False
    }
    response = client.post("/api/v1/gmail/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["recipient"] == "careers@zoho.com"


def test_api_connectors_includes_gmail(client):
    """Assert Gmail connector is registered in the master connectors catalog."""
    response = client.get("/api/v1/connectors")
    assert response.status_code == 200
    connectors = response.json()
    gmail_entry = next((c for c in connectors if c["connector_id"] == "connector_google_gmail"), None)
    assert gmail_entry is not None
    assert gmail_entry["connector_type"] == "email"
