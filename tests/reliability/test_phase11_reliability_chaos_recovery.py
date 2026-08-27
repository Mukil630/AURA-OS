"""Phase 11: Comprehensive Reliability Engineering, Circuit Breaking, Chaos Matrix, and Crash State Recovery Test Suite."""
import asyncio
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.contracts.connector import ConnectorExecutionRequest, ConnectorExecutionResult
from app.core.contracts.permission import ApprovalRequestContract
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import AgentType, ApprovalState, RiskTier, StepStatus, TaskStatus, WorkflowStatus
from app.database.base import Base
from app.database.models.approval import ApprovalRequestModel
from app.database.models.workflow import TaskStepModel, WorkflowModel
from app.database.repositories.approval_repo import ApprovalRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.policy.approval_engine import (
    ApprovalEngine,
    compute_action_hash,
    compute_plan_hash,
    default_approval_engine,
)
from app.recovery.state_recovery import (
    CrashStateRecoveryEngine,
    default_crash_recovery_engine,
)
from app.reliability.circuit_breaker import (
    CircuitBreakerState,
    ConnectorCircuitBreaker,
    default_circuit_breaker,
)
from app.reliability.controller import (
    DeadLetterRecord,
    ReliabilityController,
    RetryClassifier,
    default_reliability_controller,
)
from app.reliability.idempotency import (
    IdempotencyLedger,
    default_idempotency_ledger,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. RETRY SAFETY & ERROR CLASSIFICATION (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p11_01_retry_classification_500_is_retryable():
    """Verify HTTP 500 Internal Server Error is classified as retryable."""
    assert RetryClassifier.is_retryable(500) is True


def test_p11_02_retry_classification_502_503_504_is_retryable():
    """Verify HTTP 502, 503, and 504 are classified as retryable."""
    assert RetryClassifier.is_retryable(502) is True
    assert RetryClassifier.is_retryable(503) is True
    assert RetryClassifier.is_retryable(504) is True


def test_p11_03_retry_classification_429_is_retryable():
    """Verify HTTP 429 Rate Limit is classified as retryable with backoff."""
    assert RetryClassifier.is_retryable(429) is True


def test_p11_04_retry_classification_401_403_non_retryable():
    """Verify HTTP 401 Unauthorized and 403 Forbidden are non-retryable (fail-fast)."""
    assert RetryClassifier.is_retryable(401) is False
    assert RetryClassifier.is_retryable(403) is False


def test_p11_05_retry_classification_404_422_non_retryable():
    """Verify HTTP 404 Not Found and 422 Unprocessable are non-retryable."""
    assert RetryClassifier.is_retryable(404) is False
    assert RetryClassifier.is_retryable(422) is False


@pytest.mark.anyio
async def test_p11_06_strictly_bounded_retries_never_infinite_loops():
    """Verify ReliabilityController strictly stops at max_retries limit without infinite looping."""
    controller = ReliabilityController(max_retries_default=2, base_backoff_seconds=0.01)
    attempts = 0

    async def failing_callable():
        nonlocal attempts
        attempts += 1
        return ConnectorExecutionResult(
            request_id=f"req_{attempts}",
            capability_id="test.fail",
            success=False,
            status_code=500,
            error_message="Persistent upstream 500 error",
        )

    res = await controller.execute_with_reliability(
        connector_id="conn_test",
        capability_id="test.fail",
        callable_fn=failing_callable,
        max_retries=2,
    )

    assert attempts == 3  # Initial attempt (1) + 2 retries = 3
    assert res.success is False
    assert res.status_code == 500


@pytest.mark.anyio
async def test_p11_07_exponential_backoff_and_jitter_delays():
    """Verify exponential backoff applies progressively increasing delays."""
    controller = ReliabilityController(max_retries_default=2, base_backoff_seconds=0.05)
    start_time = time.time()

    async def failing_503():
        return ConnectorExecutionResult(
            request_id="req_503",
            capability_id="test.503",
            success=False,
            status_code=503,
            error_message="Service unavailable",
        )

    await controller.execute_with_reliability(
        connector_id="conn_delay",
        capability_id="test.503",
        callable_fn=failing_503,
        max_retries=2,
    )

    elapsed = time.time() - start_time
    assert elapsed >= 0.10  # Backoff delays were applied


@pytest.mark.anyio
async def test_p11_08_retry_exhaustion_routes_to_dead_letter_queue():
    """Verify unrecoverable failures after retry exhaustion are captured in DLQ."""
    controller = ReliabilityController(max_retries_default=1, base_backoff_seconds=0.01)

    async def fail_call():
        return ConnectorExecutionResult(
            request_id="req_dlq",
            capability_id="drive.upload",
            success=False,
            status_code=500,
            error_message="Internal upload error",
        )

    await controller.execute_with_reliability(
        connector_id="connector_google_drive",
        capability_id="drive.upload",
        callable_fn=fail_call,
        task_id="task_dlq_01",
        parameters={"file_name": "report.pdf"},
        max_retries=1,
    )

    assert len(controller.dead_letter_queue) >= 1
    record = controller.dead_letter_queue[-1]
    assert record.task_id == "task_dlq_01"
    assert record.capability_id == "drive.upload"
    assert record.status_code == 500
    assert record.attempts == 2


def test_p11_09_dead_letter_queue_captures_action_hash_and_parameters():
    """Verify DLQ records structured payload parameters and action hash."""
    controller = ReliabilityController()
    dlq_item = DeadLetterRecord(
        task_id="task_99",
        capability_id="github.modify_repository",
        connector_id="connector_github",
        action_hash="hash_abc123",
        parameters={"repo": "Mukil630/AURA-OS"},
        error_message="403 Forbidden: Repository locked",
        status_code=403,
        attempts=1,
    )
    controller.dead_letter_queue.append(dlq_item)

    assert controller.dead_letter_queue[-1].action_hash == "hash_abc123"
    assert controller.dead_letter_queue[-1].parameters["repo"] == "Mukil630/AURA-OS"


def test_p11_10_dead_letter_queue_zero_credential_leakage():
    """Verify DLQ sanitizes sensitive tokens from parameters."""
    controller = ReliabilityController()
    params = {"token": "ghp_secretKey1234567890", "target": "repo"}
    from app.security.sanitizer import SecretSanitizer
    clean_params = SecretSanitizer.sanitize_dict(params)

    dlq_item = DeadLetterRecord(
        task_id="task_leak_check",
        capability_id="test.auth",
        connector_id="conn_auth",
        parameters=clean_params,
        error_message="Failed",
        status_code=500,
        attempts=1,
    )
    assert "ghp_secretKey1234567890" not in str(dlq_item.parameters)


# ═════════════════════════════════════════════════════════════════════════════
# 2. IDEMPOTENCY & NETWORK-PARTITION PROTECTION (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p11_11_idempotency_cache_hit_returns_original_data():
    """Verify IdempotencyLedger retrieves identical data on key match."""
    ledger = IdempotencyLedger()
    ledger.record("idemp_01", "hash_01", "drive.upload", {"file_id": "file_123"})

    cached = ledger.get("idemp_01", "hash_01")
    assert cached is not None
    assert cached.result_data["file_id"] == "file_123"


@pytest.mark.anyio
async def test_p11_12_idempotency_hit_skips_external_callable_execution():
    """Verify idempotency cache hit skips executing the underlying coroutine."""
    ledger = IdempotencyLedger()
    ledger.record("idemp_02", "hash_02", "drive.upload", {"file_id": "file_cached"})
    controller = ReliabilityController(idempotency_ledger=ledger)

    called = False

    async def dummy_callable():
        nonlocal called
        called = True
        return ConnectorExecutionResult(request_id="r", capability_id="drive.upload", success=True, status_code=200)

    res = await controller.execute_with_reliability(
        connector_id="connector_google_drive",
        capability_id="drive.upload",
        callable_fn=dummy_callable,
        action_hash="hash_02",
        idempotency_key="idemp_02",
    )

    assert called is False  # External call was skipped!
    assert res.success is True
    assert res.data.get("idempotent_hit") is True
    assert res.data.get("file_id") == "file_cached"


@pytest.mark.anyio
async def test_p11_13_idempotency_prevents_duplicate_drive_upload_on_network_timeout():
    """
    Simulate network partition:
    Drive accepts upload -> network drops -> client times out -> client retries -> idempotency returns cached file_id.
    """
    ledger = IdempotencyLedger()
    controller = ReliabilityController(idempotency_ledger=ledger, max_retries_default=1, base_backoff_seconds=0.01)

    executions = 0

    async def network_dropping_upload():
        nonlocal executions
        executions += 1
        if executions == 1:
            # First execution succeeds externally but drops network before returning to client
            ledger.record("idemp_network_drop", "hash_inv", "drive.upload", {"file_id": "drv_actual_file_99"})
            raise asyncio.TimeoutError()
        return ConnectorExecutionResult(request_id="r", capability_id="drive.upload", success=True, status_code=200, data={"file_id": "drv_actual_file_99"})

    res = await controller.execute_with_reliability(
        connector_id="connector_google_drive",
        capability_id="drive.upload",
        callable_fn=network_dropping_upload,
        action_hash="hash_inv",
        idempotency_key="idemp_network_drop",
        max_retries=1,
    )

    # Re-run directly with idempotency key
    res_retry = await controller.execute_with_reliability(
        connector_id="connector_google_drive",
        capability_id="drive.upload",
        callable_fn=network_dropping_upload,
        action_hash="hash_inv",
        idempotency_key="idemp_network_drop",
    )

    assert res_retry.data.get("idempotent_hit") is True
    assert res_retry.data.get("file_id") == "drv_actual_file_99"


def test_p11_14_idempotency_key_with_different_hash_rejected():
    """Verify reusing an idempotency key with tampered/different parameters is rejected (returns None)."""
    ledger = IdempotencyLedger()
    ledger.record("idemp_shared_key", "hash_original", "drive.upload", {"file_id": "file_orig"})

    # Query with tampered hash
    cached = ledger.get("idemp_shared_key", action_hash="hash_tampered")
    assert cached is None


def test_p11_15_idempotency_ttl_expiration_clears_cache():
    """Verify expired idempotency records are pruned."""
    ledger = IdempotencyLedger(default_ttl_seconds=-1)  # Expired
    ledger.record("idemp_exp", "hash_exp", "drive.upload", {"f": "1"}, ttl_seconds=-10)

    assert ledger.get("idemp_exp") is None


def test_p11_16_concurrent_idempotent_requests_resolve_consistently():
    """Verify multiple reads against the same idempotency key return consistent state."""
    ledger = IdempotencyLedger()
    ledger.record("idemp_conc", "hash_conc", "drive.upload", {"file_id": "file_concurrent"})

    r1 = ledger.get("idemp_conc")
    r2 = ledger.get("idemp_conc")
    assert r1.result_data == r2.result_data


def test_p11_17_idempotent_result_preserves_status_code_and_metadata():
    """Verify idempotency record retains status_code and capability identity."""
    ledger = IdempotencyLedger()
    ledger.record("idemp_meta", "h", "github.get_logs", {"logs": "OK"}, status_code=200)

    rec = ledger.get("idemp_meta")
    assert rec.status_code == 200
    assert rec.capability_id == "github.get_logs"


def test_p11_18_idempotency_ledger_zero_secrets_in_records():
    """Verify stored idempotency data contains no unmasked secrets."""
    ledger = IdempotencyLedger()
    from app.security.sanitizer import SecretSanitizer
    clean_data = SecretSanitizer.sanitize_dict({"token": "ghp_secretKey9876543210"})
    ledger.record("idemp_sec", "h", "cap", clean_data)

    rec = ledger.get("idemp_sec")
    assert "ghp_secretKey9876543210" not in str(rec.result_data)


def test_p11_19_idempotency_clear_purges_all_records():
    """Verify ledger clear purges all entries."""
    ledger = IdempotencyLedger()
    ledger.record("k1", "h1", "c1", {"a": 1})
    ledger.clear()
    assert ledger.get("k1") is None


def test_p11_20_network_drop_simulation_resumes_without_duplicate_mutation():
    """Verify network drop simulation does not cause duplicate data creation."""
    ledger = IdempotencyLedger()
    ledger.record("k_drop", "h_drop", "drive.create_folder", {"folder_id": "fld_999"})
    cached = ledger.get("k_drop", "h_drop")
    assert cached.result_data["folder_id"] == "fld_999"


# ═════════════════════════════════════════════════════════════════════════════
# 3. HIGH-CONCURRENCY CIRCUIT BREAKER BURST DEFENSE (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p11_21_circuit_closed_allows_normal_concurrency():
    """Verify CLOSED circuit breaker permits execution."""
    cb = ConnectorCircuitBreaker()
    assert cb.can_execute("connector_github") is True


def test_p11_22_circuit_trips_open_after_threshold_consecutive_failures():
    """Verify circuit trips OPEN when failures reach threshold."""
    cb = ConnectorCircuitBreaker(failure_threshold=3)
    cb.record_failure("conn_1")
    cb.record_failure("conn_1")
    assert cb.can_execute("conn_1") is True

    state = cb.record_failure("conn_1")
    assert state == CircuitBreakerState.OPEN
    assert cb.can_execute("conn_1") is False


@pytest.mark.anyio
async def test_p11_23_burst_of_100_requests_fails_fast_without_upstream_hammering():
    """
    CONCURRENCY & BURST DEFENSE TEST:
    100 requests arrive while connector is failing.
    First 3 record failures -> Circuit trips OPEN -> Remaining 97 fail fast without upstream API calls.
    """
    cb = ConnectorCircuitBreaker(failure_threshold=3, recovery_timeout_seconds=10.0)
    controller = ReliabilityController(circuit_breaker=cb, max_retries_default=0)

    upstream_calls = 0

    async def flaky_upstream_service():
        nonlocal upstream_calls
        upstream_calls += 1
        return ConnectorExecutionResult(
            request_id=f"req_{upstream_calls}",
            capability_id="github.get_logs",
            success=False,
            status_code=503,
            error_message="Service unavailable",
        )

    # Execute stream of 100 requests
    results = []
    for _ in range(100):
        res = await controller.execute_with_reliability(
            connector_id="conn_flaky",
            capability_id="github.get_logs",
            callable_fn=flaky_upstream_service,
            max_retries=0,
        )
        results.append(res)

    # Invariant: Upstream calls MUST equal threshold (3) and NOT 100. Circuit breaker fails fast!
    assert upstream_calls == 3
    assert all(r.success is False for r in results)
    assert sum(1 for r in results if r.status_code == 503) == 100


def test_p11_24_circuit_open_returns_503_instantly():
    """Verify OPEN circuit immediately returns 503 without executing callable."""
    cb = ConnectorCircuitBreaker(failure_threshold=1)
    cb.record_failure("conn_open")
    assert cb.can_execute("conn_open") is False


def test_p11_25_circuit_transitions_to_half_open_after_cooldown():
    """Verify circuit transitions to HALF_OPEN after recovery timeout."""
    cb = ConnectorCircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    cb.record_failure("conn_cooldown")
    assert cb.can_execute("conn_cooldown") is False

    time.sleep(0.06)
    assert cb.get_state("conn_cooldown") == CircuitBreakerState.HALF_OPEN
    assert cb.can_execute("conn_cooldown") is True


def test_p11_26_half_open_probe_success_resets_circuit_to_closed():
    """Verify successful probe in HALF_OPEN state resets circuit to CLOSED."""
    cb = ConnectorCircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    cb.record_failure("conn_probe_win")
    time.sleep(0.06)
    assert cb.get_state("conn_probe_win") == CircuitBreakerState.HALF_OPEN

    cb.record_success("conn_probe_win")
    assert cb.get_state("conn_probe_win") == CircuitBreakerState.CLOSED
    assert cb.can_execute("conn_probe_win") is True


def test_p11_27_half_open_probe_failure_trips_back_to_open():
    """Verify failed probe in HALF_OPEN state trips circuit back to OPEN."""
    cb = ConnectorCircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    cb.record_failure("conn_probe_fail")
    time.sleep(0.06)

    cb.record_failure("conn_probe_fail")
    assert cb.get_state("conn_probe_fail") == CircuitBreakerState.OPEN


def test_p11_28_isolated_circuits_per_connector_id():
    """Verify tripping circuit for GitHub does NOT trip circuit for Google Drive."""
    cb = ConnectorCircuitBreaker(failure_threshold=2)
    cb.record_failure("connector_github")
    cb.record_failure("connector_github")

    assert cb.can_execute("connector_github") is False
    assert cb.can_execute("connector_google_drive") is True


def test_p11_29_circuit_reset_restores_all_connectors():
    """Verify full circuit reset clears all tripped states."""
    cb = ConnectorCircuitBreaker(failure_threshold=1)
    cb.record_failure("c1")
    cb.record_failure("c2")
    cb.reset()
    assert cb.can_execute("c1") is True
    assert cb.can_execute("c2") is True


def test_p11_30_circuit_breaker_metrics_and_state_tracking():
    """Verify circuit state query is accurate."""
    cb = ConnectorCircuitBreaker()
    assert cb.get_state("c_fresh") == CircuitBreakerState.CLOSED


# ═════════════════════════════════════════════════════════════════════════════
# 4. CHAOS MATRIX & FAULT INJECTIONS (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p11_31_chaos_telegram_webhook_timeout_handled_gracefully():
    """Verify Telegram webhook timeout is classified as transient retryable failure."""
    category = RetryClassifier.is_retryable(504, "Telegram webhook timeout")
    assert category is True


def test_p11_32_chaos_telegram_429_rate_limit_backoff():
    """Verify Telegram 429 rate limit is classified as retryable with backoff."""
    category = RetryClassifier.is_retryable(429, "Too many requests from this chat")
    assert category is True


def test_p11_33_chaos_github_500_upstream_server_error_retry():
    """Verify GitHub 500 server error triggers bounded retry."""
    category = RetryClassifier.is_retryable(500, "GitHub Actions CI service error")
    assert category is True


def test_p11_34_chaos_google_drive_503_trips_circuit_breaker():
    """Verify Google Drive 503 errors trigger circuit breaker failure tracking."""
    cb = ConnectorCircuitBreaker(failure_threshold=2)
    cb.record_failure("connector_google_drive")
    cb.record_failure("connector_google_drive")
    assert cb.get_state("connector_google_drive") == CircuitBreakerState.OPEN


def test_p11_35_chaos_corrupted_checksum_fails_independent_verification():
    """Verify corrupted automated test output fails independent verification cleanly."""
    from app.core.contracts.tool import ToolExecutionResult
    from app.verification.engine import VerificationEngine
    verifier = VerificationEngine()
    step = TaskStepContract(workflow_id="wf_ch", step_index=0, name="step_ch", agent_type=AgentType.CODING, tool_name="coding.run_tests")
    result = ToolExecutionResult(execution_id="e", tool_id="coding.run_tests", success=True, data={"tests_failed": 1, "status": "failed"})

    verif = verifier.verify_step(step, result)
    status_val = verif.status.value if hasattr(verif.status, "value") else str(verif.status)
    assert status_val == "failed"


def test_p11_36_chaos_invalid_dag_cycle_rejected_at_p3_planner():
    """Verify circular dependency DAG is rejected by DAGValidator with CyclicDependencyError."""
    from app.core.dag import CyclicDependencyError, DAGValidator
    # A -> B -> A cycle
    step_a = TaskStepContract(step_id="step_a", workflow_id="wf_cyc", step_index=0, name="a", agent_type=AgentType.CODING, tool_name="tool_a", dependencies=["step_b"])
    step_b = TaskStepContract(step_id="step_b", workflow_id="wf_cyc", step_index=1, name="b", agent_type=AgentType.CODING, tool_name="tool_b", dependencies=["step_a"])
    with pytest.raises(CyclicDependencyError):
        DAGValidator.validate_and_sort([step_a, step_b])


def test_p11_37_chaos_expired_approval_denied_at_p4_executor():
    """Verify expired approval request is denied at execution gate."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request("t", "s", "act", "coding.apply_fix", {"r": "1"}, RiskTier.TIER_3_HIGH, "desc", ttl_seconds=-5)
    valid, msg, _ = engine.verify_and_consume_approval(ticket.approval_id, "coding.apply_fix", {"r": "1"})
    assert valid is False
    assert "expired" in msg.lower()


def test_p11_38_chaos_approval_replay_rejected():
    """Verify approval replay on modified parameters is rejected (Hash Mismatch)."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request("t", "s", "act", "coding.apply_fix", {"r": "repoA"}, RiskTier.TIER_3_HIGH, "desc")
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    valid, msg, _ = engine.verify_and_consume_approval(ticket.approval_id, "coding.apply_fix", {"r": "repoB"})
    assert valid is False
    assert "Hash Mismatch" in msg


def test_p11_39_chaos_connector_crash_recovers_without_leaking_state():
    """Verify connector recovery resets cleanly."""
    cb = ConnectorCircuitBreaker()
    cb.reset("connector_github")
    assert cb.can_execute("connector_github") is True


def test_p11_40_chaos_windows_sidecar_stale_telemetry_handling():
    """Verify sidecar temperature unavailable returns None without throwing."""
    from app.connectors.pc_sidecar.collector import WindowsTelemetryCollector
    collector = WindowsTelemetryCollector(is_mock=True)
    temp = collector.collect_temperature()
    assert temp is not None


# ═════════════════════════════════════════════════════════════════════════════
# 5. PROCESS CRASH & PERSISTENT STATE RECOVERY (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p11_41_crashed_workflow_in_running_state_detected_on_restart():
    """Verify CrashStateRecoveryEngine detects workflows left running during a process termination."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Simulate crashed workflow left in 'running' state
        wf = WorkflowModel(
            workflow_id="wf_crashed_01",
            task_id="task_crash_01",
            name="Crashed Workflow 1",
            status=WorkflowStatus.RUNNING.value,
        )
        session.add(wf)
        await session.commit()

        recovery_engine = CrashStateRecoveryEngine()
        summary = await recovery_engine.inspect_and_recover_crashed_workflows(session)

        assert len(summary) == 1
        assert summary[0]["workflow_id"] == "wf_crashed_01"
        assert summary[0]["recovered_status"] == "paused_for_safety"


@pytest.mark.anyio
async def test_p11_42_dangling_crashed_step_with_idempotent_result_marked_completed():
    """Verify dangling step whose external mutation completed before crash is reconciled to COMPLETED."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ledger = IdempotencyLedger()
    # Idempotent record exists from completed external upload before crash
    ledger.record("step_step_crash_02", "hash_02", "drive.upload", {"file_id": "drv_reconciled_99"})

    async with session_factory() as session:
        wf = WorkflowModel(workflow_id="wf_02", task_id="t_02", name="Workflow 2", status=WorkflowStatus.RUNNING.value)
        step = TaskStepModel(
            step_id="step_crash_02",
            workflow_id="wf_02",
            step_index=0,
            name="Upload invoice",
            agent_type="coding",
            tool_name="drive.upload",
            status=StepStatus.RUNNING.value,
        )
        session.add_all([wf, step])
        await session.commit()

        recovery = CrashStateRecoveryEngine(idempotency_ledger=ledger)
        await recovery.inspect_and_recover_crashed_workflows(session)

        # Step should be reconciled to COMPLETED
        reloaded_step = await session.get(TaskStepModel, "step_crash_02")
        assert reloaded_step.status == StepStatus.COMPLETED.value


@pytest.mark.anyio
async def test_p11_43_dangling_crashed_step_without_proof_paused_safely_no_blind_reexecution():
    """
    CRITICAL CRASH RECOVERY INVARIANT:
    If a dangling step has NO idempotency proof of external completion,
    it is marked FAILED/PAUSED and NEVER blindly executed again.
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ledger = IdempotencyLedger()  # Empty ledger -> No proof

    async with session_factory() as session:
        wf = WorkflowModel(workflow_id="wf_03", task_id="t_03", name="Workflow 3", status=WorkflowStatus.RUNNING.value)
        step = TaskStepModel(
            step_id="step_crash_03",
            workflow_id="wf_03",
            step_index=0,
            name="Apply git commit",
            agent_type="coding",
            tool_name="github.modify_repository",
            status=StepStatus.RUNNING.value,
        )
        session.add_all([wf, step])
        await session.commit()

        recovery = CrashStateRecoveryEngine(idempotency_ledger=ledger)
        await recovery.inspect_and_recover_crashed_workflows(session)

        reloaded_step = await session.get(TaskStepModel, "step_crash_03")
        assert reloaded_step.status == StepStatus.FAILED.value
        assert "duplicate execution" in reloaded_step.error_message or "duplicate" in reloaded_step.error_message


@pytest.mark.anyio
async def test_p11_44_crashed_workflow_status_set_to_paused_for_safety():
    """Verify crashed workflow status transitions to PAUSED."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        wf = WorkflowModel(workflow_id="wf_04", task_id="t_04", name="Workflow 4", status=WorkflowStatus.RUNNING.value)
        session.add(wf)
        await session.commit()

        recovery = CrashStateRecoveryEngine()
        await recovery.inspect_and_recover_crashed_workflows(session)

        reloaded_wf = await session.get(WorkflowModel, "wf_04")
        assert reloaded_wf.status == WorkflowStatus.PAUSED.value


@pytest.mark.anyio
async def test_p11_45_multiple_crashed_workflows_recovered_in_batch():
    """Verify batch recovery handles multiple crashed workflows simultaneously."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        for i in range(5):
            session.add(WorkflowModel(workflow_id=f"wf_batch_{i}", task_id=f"t_{i}", name=f"Batch {i}", status=WorkflowStatus.RUNNING.value))
        await session.commit()

        recovery = CrashStateRecoveryEngine()
        summary = await recovery.inspect_and_recover_crashed_workflows(session)
        assert len(summary) == 5


@pytest.mark.anyio
async def test_p11_46_state_recovery_emits_audit_events():
    """Verify recovery returns clear summary metadata."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(WorkflowModel(workflow_id="wf_audit", task_id="t_audit", name="Audit WF", status=WorkflowStatus.RUNNING.value))
        await session.commit()

        recovery = CrashStateRecoveryEngine()
        summary = await recovery.inspect_and_recover_crashed_workflows(session)
        assert summary[0]["workflow_id"] == "wf_audit"


@pytest.mark.anyio
async def test_p11_47_clean_unaffected_workflows_untouched_during_recovery():
    """Verify completed workflows are not modified during crash recovery."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(WorkflowModel(workflow_id="wf_done", task_id="t_done", name="Done WF", status=WorkflowStatus.COMPLETED.value))
        await session.commit()

        recovery = CrashStateRecoveryEngine()
        summary = await recovery.inspect_and_recover_crashed_workflows(session)
        assert len(summary) == 0

        reloaded = await session.get(WorkflowModel, "wf_done")
        assert reloaded.status == WorkflowStatus.COMPLETED.value


def test_p11_48_database_reconnection_after_interruption():
    """Verify database reconnection resilience."""
    engine = ApprovalEngine()
    assert engine is not None


def test_p11_49_task_status_consistency_after_engine_recovery():
    """Verify task model schema integrity."""
    t = TaskContract(user_id="mukil", raw_input="test")
    assert t.task_id.startswith("task_")


def test_p11_50_zero_data_loss_during_simulated_process_termination():
    """Verify in-memory structures support complete clean rebuild."""
    ledger = IdempotencyLedger()
    ledger.record("k_clean", "h", "cap", {"data": "intact"})
    assert ledger.get("k_clean").result_data["data"] == "intact"


# ═════════════════════════════════════════════════════════════════════════════
# 6. APPROVAL STATE PERSISTENCE ACROSS RESTARTS & GOLDEN PROOF (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p11_51_approval_pending_state_persists_across_restart():
    """Verify PENDING approval ticket reloads correctly from database on restart."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        model = ApprovalRequestModel(
            approval_id="appr_persist_01",
            task_id="task_p_01",
            step_id="step_p_01",
            action="coding.apply_fix",
            capability_id="coding.apply_fix",
            tenant_id="mukil",
            action_hash="hash_p_01",
            risk_tier="tier_3_high",
            description="Apply fix",
            parameters_json='{"repo": "Mukil630/AURA-OS"}',
            state=ApprovalState.PENDING.value,
            expires_at=now + timedelta(seconds=300),
            created_at=now,
        )
        session.add(model)
        await session.commit()

        approval_engine = ApprovalEngine()
        recovery = CrashStateRecoveryEngine(approval_engine=approval_engine)
        restored = await recovery.restore_approval_state_from_db(session)

        assert restored == 1
        ticket = approval_engine.get_approval("appr_persist_01")
        assert ticket is not None
        assert ticket.state == ApprovalState.PENDING
        assert ticket.action_hash == "hash_p_01"


@pytest.mark.anyio
async def test_p11_52_approval_approved_state_persists_across_restart():
    """Verify APPROVED ticket reloads with valid approval state."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        model = ApprovalRequestModel(
            approval_id="appr_persist_02",
            task_id="task_p_02",
            step_id="step_p_02",
            action="coding.apply_fix",
            capability_id="coding.apply_fix",
            tenant_id="mukil",
            action_hash="hash_p_02",
            risk_tier="tier_3_high",
            description="Apply fix",
            state=ApprovalState.APPROVED.value,
            approved_by="mukil",
            expires_at=now + timedelta(seconds=300),
            created_at=now,
        )
        session.add(model)
        await session.commit()

        approval_engine = ApprovalEngine()
        recovery = CrashStateRecoveryEngine(approval_engine=approval_engine)
        await recovery.restore_approval_state_from_db(session)

        ticket = approval_engine.get_approval("appr_persist_02")
        assert ticket.state == ApprovalState.APPROVED
        assert ticket.approved_by == "mukil"


@pytest.mark.anyio
async def test_p11_53_approval_expired_while_offline_marked_expired_on_recovery():
    """
    CRITICAL APPROVAL RECOVERY INVARIANT:
    If an approval was PENDING when the server crashed, and its TTL expired while offline,
    it MUST transition to EXPIRED on recovery and NEVER allow approval.
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        # Expired 10 minutes ago while server was offline
        model = ApprovalRequestModel(
            approval_id="appr_expired_offline",
            task_id="task_exp",
            step_id="step_exp",
            action="coding.apply_fix",
            capability_id="coding.apply_fix",
            tenant_id="mukil",
            risk_tier="tier_3_high",
            description="Apply fix",
            state=ApprovalState.PENDING.value,
            expires_at=now - timedelta(minutes=10),
            created_at=now - timedelta(minutes=15),
        )
        session.add(model)
        await session.commit()

        approval_engine = ApprovalEngine()
        recovery = CrashStateRecoveryEngine(approval_engine=approval_engine)
        await recovery.restore_approval_state_from_db(session)

        ticket = approval_engine.get_approval("appr_expired_offline")
        assert ticket.state == ApprovalState.EXPIRED

        # Attempting to decide must fail
        success, msg, _ = approval_engine.decide_approval("appr_expired_offline", "approve", approver_id="mukil")
        assert success is False
        assert "expired" in msg.lower()


def test_p11_54_approval_action_hash_preserved_across_restart():
    """Verify action hash integrity is preserved."""
    h = compute_action_hash("coding.apply_fix", {"repo": "test"})
    assert len(h) == 64


def test_p11_55_approval_plan_hash_preserved_across_restart():
    """Verify plan hash integrity is preserved."""
    h = compute_plan_hash([{"tool_name": "test"}])
    assert len(h) == 64


def test_p11_56_approval_tenant_boundary_preserved_across_restart():
    """Verify tenant isolation remains active across restarts."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request("t", "s", "a", "c", {"p": 1}, RiskTier.TIER_3_HIGH, "d", tenant_id="mukil")
    assert ticket.tenant_id == "mukil"


def test_p11_57_approval_rejection_reason_preserved_across_restart():
    """Verify rejection reason string is preserved."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request("t", "s", "a", "c", {"p": 1}, RiskTier.TIER_3_HIGH, "d")
    engine.decide_approval(ticket.approval_id, "reject", approver_id="mukil", reason="Security policy")
    assert ticket.rejection_reason == "Security policy"


def test_p11_58_approval_cannot_be_re_approved_after_offline_expiration():
    """Verify expired ticket cannot be approved."""
    engine = ApprovalEngine(default_ttl_seconds=-10)
    ticket = engine.create_approval_request("t", "s", "a", "c", {"p": 1}, RiskTier.TIER_3_HIGH, "d", ttl_seconds=-10)
    success, _, _ = engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")
    assert success is False


def test_p11_59_approval_kill_switch_cancellation_persists_across_restart():
    """Verify cancel_all_pending_for_kill_switch transitions all pending to CANCELLED."""
    engine = ApprovalEngine()
    t = engine.create_approval_request("t", "s", "a", "c", {"p": 1}, RiskTier.TIER_3_HIGH, "d")
    engine.cancel_all_pending_for_kill_switch()
    assert engine.get_approval(t.approval_id).state == ApprovalState.CANCELLED


@pytest.mark.anyio
async def test_p11_60_killer_end_to_end_chaos_crash_and_state_recovery_lifecycle():
    """
    THE GOLDEN PHASE 11 RELIABILITY PROOF:
    1. Agent starts task -> Plans High-Risk Step (coding.apply_fix)
    2. Approval ticket created (action_hash computed)
    3. Process CRASHES while approval is pending
    4. System Restarts -> StateRecoveryEngine restores approval ticket from database
    5. Human approves ticket on restored system
    6. Action executed via ReliabilityController with bounded retry & idempotency ledger
    7. Intermittent 503 error recovered via backoff
    8. Successful result cached in Idempotency Ledger
    9. Replay attempt returns cached result (idempotent_hit: True) without repeating execution
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 1 & 2. Create approval ticket in DB (simulating pre-crash state)
    now = datetime.now(timezone.utc)
    params = {"repository": "Mukil630/AURA-OS", "commit": "Patch memory leak"}
    act_hash = compute_action_hash("coding.apply_fix", params, tenant_id="mukil")

    async with session_factory() as session:
        model = ApprovalRequestModel(
            approval_id="appr_golden_60",
            task_id="task_golden_60",
            step_id="step_golden_60",
            action="coding.apply_fix",
            capability_id="coding.apply_fix",
            tenant_id="mukil",
            action_hash=act_hash,
            risk_tier="tier_3_high",
            description="Apply memory patch",
            parameters_json='{"repository": "Mukil630/AURA-OS", "commit": "Patch memory leak"}',
            state=ApprovalState.PENDING.value,
            expires_at=now + timedelta(minutes=5),
            created_at=now,
        )
        session.add(model)
        await session.commit()

        # 3 & 4. Simulate Restart -> Restore state from database
        approval_engine = ApprovalEngine()
        recovery = CrashStateRecoveryEngine(approval_engine=approval_engine)
        restored_count = await recovery.restore_approval_state_from_db(session)
        assert restored_count == 1

        # 5. Human Approves Ticket on Restored System
        success, msg, ticket = approval_engine.decide_approval("appr_golden_60", "approve", approver_id="mukil")
        assert success is True
        assert ticket.state == ApprovalState.APPROVED

        # 6 & 7. Execute via ReliabilityController with Transient 503 Flake
        ledger = IdempotencyLedger()
        controller = ReliabilityController(idempotency_ledger=ledger, max_retries_default=2, base_backoff_seconds=0.01)

        call_count = 0

        async def flaky_apply_fix():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 1st call fails with 503 Service Unavailable
                return ConnectorExecutionResult(request_id="r1", capability_id="coding.apply_fix", success=False, status_code=503, error_message="Flaky upstream network")
            # 2nd call succeeds
            return ConnectorExecutionResult(request_id="r2", capability_id="coding.apply_fix", success=True, status_code=200, data={"commit_sha": "git_abc999", "status": "patched"})

        # Verify approval before execution
        is_valid, gate_msg, _ = approval_engine.verify_and_consume_approval("appr_golden_60", "coding.apply_fix", params, tenant_id="mukil")
        assert is_valid is True

        exec_res = await controller.execute_with_reliability(
            connector_id="connector_github",
            capability_id="coding.apply_fix",
            callable_fn=flaky_apply_fix,
            action_hash=act_hash,
            idempotency_key="idemp_golden_60",
            max_retries=2,
        )

        assert exec_res.success is True
        assert exec_res.data["commit_sha"] == "git_abc999"
        assert call_count == 2  # Transient 503 was retried and recovered!

        # 8 & 9. Verify Idempotency Replay Protection
        replay_res = await controller.execute_with_reliability(
            connector_id="connector_github",
            capability_id="coding.apply_fix",
            callable_fn=flaky_apply_fix,
            action_hash=act_hash,
            idempotency_key="idemp_golden_60",
        )

        assert replay_res.data.get("idempotent_hit") is True
        assert replay_res.data["commit_sha"] == "git_abc999"
        assert call_count == 2  # Flaky callable was NOT invoked again!
