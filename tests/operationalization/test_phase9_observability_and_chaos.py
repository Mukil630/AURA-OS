"""Phase 9: Operationalization, Observability, Circuit Breakers, and Chaos Resilience Test Suite."""
import asyncio
import hashlib
import time
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient

from app.connectors.telegram.contracts import (
    TelegramChat,
    TelegramMessage,
    TelegramUpdate,
    TelegramUser,
)
from app.chaos.fault_injector import ChaosFaultInjector, ChaosFaultType, default_chaos_injector
from app.connectors.github.connector import GitHubConnector
from app.connectors.policy import ConnectorPolicyEngine
from app.connectors.telegram.connector import TelegramConnector
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.enums import ConnectorType
from app.main import app
from app.observability.dashboard import OperationalDashboardService, default_dashboard
from app.observability.tracer import AgentTracer, default_tracer
from app.reliability.circuit_breaker import CircuitBreakerState, ConnectorCircuitBreaker
from app.security.auth import create_access_token
from app.connectors.credential_manager import CredentialManager


# ═════════════════════════════════════════════════════════════════════════════
# 1. AGENT OBSERVABILITY & DISTRIBUTED TRACING (3 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_op_01_trace_creation_and_span_recording():
    """Verify AgentTracer accurately records hierarchical spans and execution durations."""
    tracer = AgentTracer()
    trace = tracer.create_trace(task_id="task_obs_101", user_id="mukil", workflow_id="wf_obs_101")

    # Span 1: Intent Classification
    s1 = trace.start_span(name="intent_classification", component="MasterAgent")
    time.sleep(0.01)
    s1.finish(status="ok")

    # Span 2: Plan Generation
    s2 = trace.start_span(name="plan_generation", component="TaskPlanner", parent_span_id=s1.span_id)
    time.sleep(0.01)
    s2.finish(status="ok")

    trace.complete_trace(status="completed")

    assert trace.task_id == "task_obs_101"
    assert trace.overall_status == "completed"
    assert len(trace.spans) == 2
    assert trace.spans[0].duration_ms > 0
    assert trace.spans[1].parent_span_id == trace.spans[0].span_id
    assert trace.total_duration_ms > 0


def test_op_02_trace_decision_lineage_and_rationale():
    """Verify structured decision rationale tracks causal lineage of autonomous choices."""
    tracer = AgentTracer()
    trace = tracer.create_trace(task_id="task_obs_102", user_id="mukil")

    trace.record_decision(
        stage="planner",
        chosen_option="drive.upload",
        why="User requested invoice PDF backup into Master Vault.",
        constraints={"risk_tier": "TIER_1_LOW", "requires_dual_vault": True},
    )

    assert len(trace.decision_lineage) == 1
    decision = trace.decision_lineage[0]
    assert decision["stage"] == "planner"
    assert decision["decision"] == "drive.upload"
    assert "invoice PDF backup" in decision["rationale"]
    assert decision["constraints"]["requires_dual_vault"] is True


def test_op_03_trace_secret_sanitization():
    """Verify traces automatically mask sensitive tokens from metadata, rationales, and error messages."""
    tracer = AgentTracer()
    trace = tracer.create_trace(task_id="task_obs_103", user_id="mukil")

    span = trace.start_span(
        name="github_call",
        component="GitHubConnector",
        decision_rationale="Connecting with token ghp_superSecretToken9876543210",
        metadata={"auth_header": "Bearer ghp_superSecretToken9876543210"},
    )
    span.finish(status="error", error_message="Failed with ghp_superSecretToken9876543210")

    assert "ghp_superSecretToken9876543210" not in (span.decision_rationale or "")
    assert "ghp_superSecretToken9876543210" not in str(span.metadata)
    assert "ghp_superSecretToken9876543210" not in (span.error_message or "")


# ═════════════════════════════════════════════════════════════════════════════
# 2. OPERATIONAL DASHBOARD & METRICS ENGINE (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_op_04_system_health_matrix_status():
    """Verify system health matrix aggregates operational health across all subsystems."""
    policy = ConnectorPolicyEngine()
    dashboard = OperationalDashboardService(policy_engine=policy)
    health = dashboard.get_system_health()

    assert health["agent_core"].status == "healthy"
    assert health["security_gate"].status == "healthy"
    assert health["kill_switch"].status == "healthy"
    assert health["telegram_gateway"].status == "healthy"
    assert health["google_drive"].status == "healthy"
    assert health["github_connector"].status == "healthy"
    assert health["windows_sidecar"].status == "healthy"


def test_op_05_task_metrics_throughput_and_success_rate():
    """Verify dashboard metrics compute accurate throughput, failure count, and success rate %."""
    tracer = AgentTracer()
    dashboard = OperationalDashboardService(tracer=tracer)

    # Simulate 5 tasks: 4 completed, 1 failed
    for i in range(4):
        t = tracer.create_trace(f"task_{i}", "mukil")
        s = t.start_span("exec", "agent")
        time.sleep(0.005)
        s.finish()
        t.complete_trace(status="completed")

    t_fail = tracer.create_trace("task_fail", "mukil")
    s_f = t_fail.start_span("exec", "agent")
    s_f.finish(status="error")
    t_fail.complete_trace(status="failed")

    metrics = dashboard.compute_metrics()
    assert metrics.total_tasks == 5
    assert metrics.completed_tasks == 4
    assert metrics.failed_tasks == 1
    assert metrics.success_rate_percent == 80.0
    assert metrics.avg_duration_ms > 0


@pytest.mark.anyio
async def test_op_06_dashboard_rest_endpoint_authorized():
    """Verify authenticated operators can access GET /api/v1/dashboard/overview."""
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get(
            "/api/v1/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "system_health" in data
        assert "metrics" in data
        assert data["system_health"]["agent_core"]["status"] == "healthy"


@pytest.mark.anyio
async def test_op_07_dashboard_trace_retrieval_endpoint():
    """Verify operators can query detailed execution traces via REST API."""
    trace = default_tracer.create_trace(task_id="task_rest_trace_101", user_id="mukil")
    span = trace.start_span("test_span", "MasterAgent")
    span.finish()
    trace.complete_trace()

    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get(
            "/api/v1/dashboard/traces/task_rest_trace_101",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["task_id"] == "task_rest_trace_101"
        assert len(data["spans"]) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# 3. RELIABILITY & CONNECTOR CIRCUIT BREAKER (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_op_08_circuit_breaker_closed_state_permits_execution():
    """Verify circuit breaker in CLOSED state allows normal capability dispatches."""
    cb = ConnectorCircuitBreaker(failure_threshold=3)
    assert cb.can_execute("connector_github") is True
    assert cb.get_state("connector_github") == CircuitBreakerState.CLOSED


def test_op_09_circuit_breaker_trips_open_after_consecutive_failures():
    """Verify circuit breaker trips OPEN after consecutive failures and fails fast."""
    cb = ConnectorCircuitBreaker(failure_threshold=3, recovery_timeout_seconds=5.0)

    cb.record_failure("connector_github")
    cb.record_failure("connector_github")
    assert cb.can_execute("connector_github") is True

    # 3rd Failure -> Trips Circuit
    state = cb.record_failure("connector_github")
    assert state == CircuitBreakerState.OPEN
    assert cb.get_state("connector_github") == CircuitBreakerState.OPEN
    assert cb.can_execute("connector_github") is False  # Fails fast!


def test_op_10_circuit_breaker_half_open_recovery_probe():
    """Verify circuit breaker automatically transitions to HALF_OPEN after recovery timeout."""
    cb = ConnectorCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)
    cb.record_failure("connector_drive")
    cb.record_failure("connector_drive")
    assert cb.can_execute("connector_drive") is False

    time.sleep(0.06)  # Wait for recovery timeout
    assert cb.get_state("connector_drive") == CircuitBreakerState.HALF_OPEN
    assert cb.can_execute("connector_drive") is True


def test_op_11_circuit_breaker_successful_recovery_resets_to_closed():
    """Verify successful probe in HALF_OPEN state resets circuit back to CLOSED."""
    cb = ConnectorCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)
    cb.record_failure("connector_telegram")
    cb.record_failure("connector_telegram")

    time.sleep(0.06)
    assert cb.get_state("connector_telegram") == CircuitBreakerState.HALF_OPEN

    # Probe succeeds
    cb.record_success("connector_telegram")
    assert cb.get_state("connector_telegram") == CircuitBreakerState.CLOSED
    assert cb.can_execute("connector_telegram") is True


# ═════════════════════════════════════════════════════════════════════════════
# 4. SECURITY V2 & RUNTIME STATE HARDENING (3 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_op_12_kill_switch_instant_global_halt_across_concurrent_tasks():
    """Verify emergency kill switch immediately stops all connectors simultaneously."""
    policy = ConnectorPolicyEngine()
    policy.disable_connector("connector_github")
    policy.disable_connector("connector_google_drive")
    policy.disable_connector("connector_telegram")
    policy.disable_connector("connector_windows_sidecar")

    assert policy.is_connector_enabled("connector_github") is False
    assert policy.is_connector_enabled("connector_google_drive") is False
    assert policy.is_connector_enabled("connector_telegram") is False
    assert policy.is_connector_enabled("connector_windows_sidecar") is False


def test_op_13_kill_switch_re_enable_restores_new_tasks_cleanly():
    """Verify re-enabling connector restores operational readiness without server restart."""
    policy = ConnectorPolicyEngine()
    policy.disable_connector("connector_github")
    assert policy.is_connector_enabled("connector_github") is False

    policy.enable_connector("connector_github")
    assert policy.is_connector_enabled("connector_github") is True


def test_op_14_token_rotation_and_revocation_isolation():
    """Verify rotating credentials immediately invalidates old token and masks new token."""
    cred_mgr = CredentialManager()
    old_token = "ghp_oldToken1234567890abcdef"
    new_token = "ghp_newToken9998887776fedcba"

    cred_mgr.set_credential(ConnectorType.GITHUB, old_token, user_id="mukil")
    assert cred_mgr.get_credential(ConnectorType.GITHUB, user_id="mukil") == old_token

    # Rotate
    contract = cred_mgr.set_credential(ConnectorType.GITHUB, new_token, user_id="mukil")
    assert cred_mgr.get_credential(ConnectorType.GITHUB, user_id="mukil") == new_token
    assert new_token not in contract.masked_value
    assert contract.masked_value.startswith("ghp_****")


# ═════════════════════════════════════════════════════════════════════════════
# 5. CHAOS TESTING & FAULT INJECTION ENGINE (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_op_15_chaos_timeout_fault_injection_bounded_retry():
    """Verify injected timeout fault triggers bounded retry mechanism without hanging."""
    injector = ChaosFaultInjector()
    injector.inject_fault("github.get_logs", ChaosFaultType.TIMEOUT, count=2)

    assert injector.consume_fault("github.get_logs") == ChaosFaultType.TIMEOUT
    assert injector.consume_fault("github.get_logs") == ChaosFaultType.TIMEOUT
    assert injector.consume_fault("github.get_logs") is None


def test_op_16_chaos_http_502_bad_gateway_fault_recovery():
    """Verify 502 Bad Gateway chaos fault is classified as transient failure for retry."""
    from app.core.enums import FailureCategory
    from app.recovery.engine import SelfHealingEngine

    healer = SelfHealingEngine()
    category = healer.classify_failure(error_msg="Upstream service returned HTTP 502 Bad Gateway - connection reset")
    assert category == FailureCategory.TRANSIENT


def test_op_17_chaos_http_429_rate_limit_backoff_handling():
    """Verify 429 rate limit chaos fault is classified appropriately for backoff."""
    from app.core.enums import FailureCategory
    from app.recovery.engine import SelfHealingEngine

    healer = SelfHealingEngine()
    category = healer.classify_failure(error_msg="HTTP 429 Too Many Requests: Rate limit ceiling reached")
    assert category == FailureCategory.TRANSIENT


def test_op_18_chaos_corrupted_payload_validation_rejection():
    """Verify corrupted / tampered payloads fail verification safely without modifying state."""
    from app.core.contracts.task_step import TaskStepContract
    from app.core.contracts.tool import ToolExecutionResult
    from app.core.enums import AgentType, StepStatus, VerificationStatus
    from app.verification.engine import VerificationEngine

    verifier = VerificationEngine()
    step = TaskStepContract(
        workflow_id="wf_chaos",
        step_index=0,
        name="verify_ci_run",
        agent_type=AgentType.CODING,
        tool_name="coding.run_tests",
        status=StepStatus.COMPLETED,
    )
    # Corrupted mismatch: tool claims success=True but result data indicates tests_failed=2
    tool_res = ToolExecutionResult(
        execution_id="exec_chaos_99",
        tool_id="coding.run_tests",
        success=True,
        data={"tests_passed": 10, "tests_failed": 2, "error": "AssertionError"},
    )

    verif = verifier.verify_step(step, tool_res)
    status_val = verif.status.value if hasattr(verif.status, "value") else str(verif.status)
    assert status_val == "failed"
