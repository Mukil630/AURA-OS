"""Unit tests for Connector Contracts."""
from app.core.contracts.connector import (
    ConnectorContract,
    ConnectorHealthContract,
)
from app.core.enums import AuthType, ConnectorStatus, ConnectorType


def test_connector_contract():
    conn = ConnectorContract(
        connector_id="connector_github",
        name="GitHub Cloud API Connector",
        connector_type=ConnectorType.GITHUB,
        auth_type=AuthType.API_KEY,
        status=ConnectorStatus.CONNECTED,
        supported_tools=["github.list_workflows", "github.get_logs"],
        is_mcp=True,
    )
    assert conn.connector_id == "connector_github"
    assert conn.connector_type == ConnectorType.GITHUB
    assert conn.status == ConnectorStatus.CONNECTED
    assert conn.is_mcp is True


def test_connector_health_contract():
    health = ConnectorHealthContract(
        connector_id="connector_github",
        status=ConnectorStatus.CONNECTED,
        latency_ms=42.5,
        message="GitHub API ping OK",
    )
    assert health.connector_id == "connector_github"
    assert health.status == ConnectorStatus.CONNECTED
    assert health.latency_ms == 42.5
