"""Comprehensive Unit and Integration Test Suite for Phase 8 Connector Framework & GitHub Connector."""
import asyncio
import pytest

from app.connectors.credential_manager import CredentialManager
from app.connectors.github.connector import GitHubConnector
from app.connectors.policy import ConnectorPolicyEngine
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import (
    ConnectorExecutionRequest,
)
from app.core.enums import ConnectorStatus, ConnectorType


# ── Scenario 1: Connector Registration & Capability Indexing ───────────────────────────
def test_scenario_1_connector_registration_and_capability_indexing():
    router = CapabilityRouter()
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # Verify Connector metadata
    connectors = router.list_connectors()
    assert len(connectors) == 1
    assert connectors[0].connector_id == "connector_github"
    assert connectors[0].connector_type == ConnectorType.GITHUB

    # Verify Capability indexing
    capabilities = router.list_capabilities()
    assert len(capabilities) == 5
    cap_ids = [c.capability_id for c in capabilities]
    assert "github.list_failed_workflows" in cap_ids
    assert "github.get_logs" in cap_ids
    assert "coding.analyze_patch" in cap_ids
    assert "coding.apply_fix" in cap_ids
    assert "coding.run_tests" in cap_ids


# ── Scenario 2: Credential Manager Token Isolation & Masking ─────────────────────────
def test_scenario_2_credential_manager_token_isolation_and_masking():
    cred_mgr = CredentialManager()
    raw_token = "ghp_superSecretToken9876543210abcd"

    # Store credential
    contract = cred_mgr.set_credential(
        provider=ConnectorType.GITHUB,
        token=raw_token,
        user_id="mukil",
    )

    # Safe masked value returned
    assert contract.masked_value == "ghp_****abcd"
    assert raw_token not in contract.masked_value

    # Internal resolution retrieves raw token securely
    resolved_token = cred_mgr.get_credential(ConnectorType.GITHUB, user_id="mukil")
    assert resolved_token == raw_token


# ── Scenario 3: Successful Capability Dispatch in Mock Mode ───────────────────────────
@pytest.mark.anyio
async def test_scenario_3_successful_capability_dispatch_mock_mode():
    router = CapabilityRouter()
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["repository"] == "Mukil630/AURA-OS"
    assert res.data["failed_count"] == 1
    assert len(res.data["workflow_runs"]) == 1


# ── Scenario 4: Emergency Kill-Switch Blocks Dispatch ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_4_emergency_kill_switch_blocks_dispatch():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # Trigger emergency stop on GitHub connector
    policy.disable_connector("connector_github")
    assert policy.is_connector_enabled("connector_github") is False

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 503
    assert "disabled by emergency kill-switch" in res.error_message.lower()

    # Re-enable connector
    policy.enable_connector("connector_github")
    res2 = await router.dispatch(req)
    assert res2.success is True


# ── Scenario 5: Capability Blocklist Security Policy ─────────────────────────────────
@pytest.mark.anyio
async def test_scenario_5_capability_blocklist_security_policy():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # Block write capability
    policy.block_capability("coding.apply_fix")

    req = ConnectorExecutionRequest(
        capability_id="coding.apply_fix",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 403
    assert "restricted by security policy" in res.error_message.lower()


# ── Scenario 6: Rate Limiting Enforcement (429) ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_6_rate_limiting_enforcement_429():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )

    # Configure and exhaust rate limit (allow max 2 calls)
    policy.set_rate_limit("github.list_failed_workflows", 2)
    assert policy.check_and_consume_rate_limit("github.list_failed_workflows") is True
    assert policy.check_and_consume_rate_limit("github.list_failed_workflows") is True

    # 3rd call should trigger 429 rate limit error
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 429
    assert "rate limit exceeded" in res.error_message.lower()


# ── Scenario 7: Authentication Failure Handling (401) ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_7_authentication_failure_handling_401():
    # Live mode without credentials triggers 401
    github_conn = GitHubConnector(is_mock=False)
    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await github_conn.execute_capability(req, credentials=None)

    assert res.success is False
    assert res.status_code == 401
    assert "authentication failure" in res.error_message.lower()


# ── Scenario 8: Connector Health Check Probes ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_8_connector_health_check_probes():
    github_conn = GitHubConnector(is_mock=True)
    health = await github_conn.health_check()

    assert health.connector_id == "connector_github"
    assert health.status == ConnectorStatus.CONNECTED
    assert health.latency_ms > 0
    assert "healthy" in health.message.lower()


# ── Scenario 9: Full 5-Step Coding Pipeline Connector Dispatch ────────────────────────
@pytest.mark.anyio
async def test_scenario_9_full_coding_pipeline_connector_dispatch():
    router = CapabilityRouter()
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # 1. Read failed workflows
    r1 = await router.dispatch(ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={"repository": "Mukil630/AURA-OS"}))
    assert r1.success is True
    run_id = r1.data["workflow_runs"][0]["id"]

    # 2. Get logs
    r2 = await router.dispatch(ConnectorExecutionRequest(capability_id="github.get_logs", parameters={"repository": "Mukil630/AURA-OS", "run_id": run_id}))
    assert r2.success is True
    assert "AssertionError" in r2.data["error_logs"]

    # 3. Analyze patch
    r3 = await router.dispatch(ConnectorExecutionRequest(capability_id="coding.analyze_patch", parameters={"repository": "Mukil630/AURA-OS"}))
    assert r3.success is True

    # 4. Apply fix
    r4 = await router.dispatch(ConnectorExecutionRequest(capability_id="coding.apply_fix", parameters={"repository": "Mukil630/AURA-OS"}))
    assert r4.success is True
    assert r4.data["applied"] is True

    # 5. Run tests
    r5 = await router.dispatch(ConnectorExecutionRequest(capability_id="coding.run_tests", parameters={"repository": "Mukil630/AURA-OS"}))
    assert r5.success is True
    assert r5.data["tests_failed"] == 0
    assert r5.data["status"] == "ALL_GREEN"


# ── Scenario 10: Unregistered Capability Handling ─────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_10_unregistered_capability_handling():
    router = CapabilityRouter()
    req = ConnectorExecutionRequest(
        capability_id="unknown.fake_tool",
        parameters={},
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 404
    assert "no connector registered" in res.error_message.lower()
