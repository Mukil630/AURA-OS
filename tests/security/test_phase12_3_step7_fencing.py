"""Phase 12.3 Step 7: Dedicated Unit, Adversarial & Fencing Token Defense Test Suite.
Verifies Monotonic Fencing Token Progression, Authoritative State Commit Guards,
Stale-Worker Write Rejection, Invalid/Future Token Defense, and Cross-Tenant Token Isolation.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest

from app.core.contracts.leasing import (
    LeaseNotFoundError,
    QueueMessageContract,
    StaleLeaseConflictError,
    UnauthorizedWorkerError,
)
from app.core.leasing.fencing_guard import FencedTaskExecutionGuard
from app.core.leasing.lease_manager import InMemoryLeaseManager
from app.core.leasing.reclaim_manager import StandbyReclaimManager
from app.core.leasing.task_queue import InMemoryTaskQueue


# ═════════════════════════════════════════════════════════════════════════════
# 1. MONOTONIC FENCING TOKEN PROGRESSION (Tests 1 - 3)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s7_01_first_lease_receives_initial_fencing_token_one():
    """S7-01: First lease acquisition initializes fencing_token = 1."""
    mgr = InMemoryLeaseManager()
    l1 = mgr.acquire("task_1", "tenant_A", "worker_1")
    assert l1.fencing_token == 1
    assert mgr.get_fencing_token("task_1") == 1


def test_p12_3_s7_02_reclaim_generates_newer_fencing_token():
    """S7-02: Reclaiming an expired task produces fencing_token = 2 > 1."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l1 = mgr.acquire("task_2", "tenant_A", "worker_1", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    l2 = reclaim_mgr.reclaim("task_2", "tenant_A", "worker_2")
    assert l2.fencing_token == 2
    assert l2.fencing_token > l1.fencing_token


def test_p12_3_s7_03_fencing_tokens_increase_monotonically():
    """S7-03: Repeated reclaim cycles produce strictly monotonic generation tokens (1 -> 2 -> 3 -> 4)."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    tokens = []
    l = mgr.acquire("task_mono", "tenant_A", "w0", lease_ttl_seconds=1)
    tokens.append(l.fencing_token)

    for i in range(1, 4):
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        l.acquired_at = past
        l.expires_at = past + timedelta(seconds=2)
        l = reclaim_mgr.reclaim("task_mono", "tenant_A", f"w{i}")
        tokens.append(l.fencing_token)

    assert tokens == [1, 2, 3, 4]


# ═════════════════════════════════════════════════════════════════════════════
# 2. WRITE AUTHORITY VALIDATION & STALE DEFENSE (Tests 4 - 7)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s7_04_current_worker_with_current_token_accepted():
    """S7-04: Current active worker holding current fencing token is authorized to write."""
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)

    lease = mgr.acquire("task_ok", "tenant_A", "worker_alpha", lease_ttl_seconds=30)

    val_lease = guard.validate_write_authority(
        task_id="task_ok",
        tenant_id="tenant_A",
        worker_id="worker_alpha",
        fencing_token=1,
        lease_id=lease.lease_id,
    )
    assert val_lease.lease_id == lease.lease_id


def test_p12_3_s7_05_old_worker_with_stale_token_rejected():
    """S7-05: Old worker presenting obsolete fencing token is rejected with StaleLeaseConflictError (409)."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l1 = mgr.acquire("task_stale", "tenant_A", "worker_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    # Standby worker reclaims and advances token to 2
    l2 = reclaim_mgr.reclaim("task_stale", "tenant_A", "worker_new", lease_ttl_seconds=30)
    assert l2.fencing_token == 2

    # Old worker wakes up and attempts validation with token = 1
    with pytest.raises(StaleLeaseConflictError) as exc_info:
        guard.validate_write_authority("task_stale", "tenant_A", "worker_old", fencing_token=1)
    assert exc_info.value.status_code == 409
    assert "superseded by active generation 2" in exc_info.value.detail


def test_p12_3_s7_06_stale_token_cannot_perform_authoritative_write():
    """S7-06: Stale worker cannot commit state outputs via execute_fenced_write()."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l1 = mgr.acquire("task_write_block", "tenant_A", "worker_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    reclaim_mgr.reclaim("task_write_block", "tenant_A", "worker_new")

    # Stale write rejected
    with pytest.raises(StaleLeaseConflictError):
        guard.execute_fenced_write(
            task_id="task_write_block",
            tenant_id="tenant_A",
            worker_id="worker_old",
            fencing_token=1,
            write_key="workflow_status",
            write_value="corrupted_by_zombie_worker",
        )


def test_p12_3_s7_07_new_worker_can_perform_authoritative_write():
    """S7-07: Valid new generation worker commits state cleanly."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l1 = mgr.acquire("task_write_ok", "tenant_A", "worker_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    l2 = reclaim_mgr.reclaim("task_write_ok", "tenant_A", "worker_new")

    state = guard.execute_fenced_write(
        task_id="task_write_ok",
        tenant_id="tenant_A",
        worker_id="worker_new",
        fencing_token=2,
        write_key="build_artifact",
        write_value="v1.2.0-clean",
    )
    assert state["fencing_token"] == 2
    assert state["data"]["build_artifact"] == "v1.2.0-clean"


# ═════════════════════════════════════════════════════════════════════════════
# 3. EDGE CASES & ADVERSARIAL TOKEN DEFENSE (Tests 8 - 11)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s7_08_multiple_reclaim_generations_strictly_increasing():
    """S7-08: Successive generations strictly enforce token monotonicity."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l = mgr.acquire("task_chain", "tenant_A", "w0", lease_ttl_seconds=1)
    for i in range(1, 5):
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        l.acquired_at = past
        l.expires_at = past + timedelta(seconds=2)
        l = reclaim_mgr.reclaim("task_chain", "tenant_A", f"w{i}")

    # Current token is 5
    assert mgr.get_fencing_token("task_chain") == 5

    # Any older token (1..4) is rejected
    for stale_token in range(1, 5):
        with pytest.raises(StaleLeaseConflictError):
            guard.validate_write_authority("task_chain", "tenant_A", f"w{stale_token - 1}", fencing_token=stale_token)


def test_p12_3_s7_09_equal_token_wrong_worker_rejected():
    """S7-09: Equal token presented by an unauthorized worker is rejected (403)."""
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)

    mgr.acquire("task_impersonate", "tenant_A", "worker_legit")

    with pytest.raises(UnauthorizedWorkerError):
        guard.validate_write_authority("task_impersonate", "tenant_A", "worker_impostor", fencing_token=1)


def test_p12_3_s7_10_invalid_future_token_rejected():
    """S7-10: Forged future token exceeding current generation is rejected."""
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)

    mgr.acquire("task_forged", "tenant_A", "worker_1")

    with pytest.raises(StaleLeaseConflictError) as exc_info:
        guard.validate_write_authority("task_forged", "tenant_A", "worker_1", fencing_token=999)
    assert "exceeds latest issued generation" in exc_info.value.detail


def test_p12_3_s7_11_cross_tenant_token_rejected():
    """S7-11: Token valid in Tenant A cannot authorize a write in Tenant B."""
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)

    mgr.acquire("task_tenant_isolated", "tenant_A", "worker_1")

    with pytest.raises(UnauthorizedWorkerError):
        guard.validate_write_authority("task_tenant_isolated", "tenant_B", "worker_1", fencing_token=1)


# ═════════════════════════════════════════════════════════════════════════════
# 4. CONCURRENCY & INTEGRATION (Tests 12 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s7_12_old_worker_after_reclaim_definitively_stale():
    """S7-12: Old worker is permanently marked stale after reclaim."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l1 = mgr.acquire("task_perm", "tenant_A", "w_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    reclaim_mgr.reclaim("task_perm", "tenant_A", "w_new")

    assert guard.get_task_state("task_perm", "tenant_A") is None


def test_p12_3_s7_13_concurrent_reclaims_produce_consistent_generations():
    """S7-13: Concurrent reclaim attempts do not corrupt fencing counter."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l1 = mgr.acquire("task_conc_fencing", "tenant_A", "w0", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    def attempt_reclaim(idx: int):
        try:
            return reclaim_mgr.reclaim("task_conc_fencing", "tenant_A", f"w_{idx}")
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(attempt_reclaim, range(5)))
        successful = [r for r in results if r is not None]

    assert len(successful) == 1
    assert successful[0].fencing_token == 2


def test_p12_3_s7_14_queue_and_fenced_write_consistency():
    """S7-14: Queue message ACK coordinates with fenced authoritative write."""
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)

    msg = QueueMessageContract(message_id="m_fence", task_id="t_fence", tenant_id="tenant_A")
    queue.enqueue(msg)

    consumed = queue.dequeue("tenant_A", worker_id="worker_fenced")
    lease = mgr.acquire(consumed.task_id, consumed.tenant_id, "worker_fenced")

    # Authoritative write
    guard.execute_fenced_write(
        task_id=consumed.task_id,
        tenant_id=consumed.tenant_id,
        worker_id="worker_fenced",
        fencing_token=lease.fencing_token,
        write_key="result",
        write_value="success_fenced",
    )

    # Release and ACK
    mgr.release(consumed.task_id, lease.lease_id, "worker_fenced", consumed.tenant_id)
    assert queue.ack(consumed.message_id, "tenant_A") is True


def test_p12_3_s7_15_critical_race_scenario_zombie_worker_rejected():
    """
    S7-15: CRITICAL RACE SCENARIO (Alpha vs Beta)
    Worker Alpha (token=1) executes -> Lease expires -> Standby Worker Beta reclaims (token=2)
    -> Beta writes output (SUCCESS) -> Worker Alpha wakes up & attempts write with token=1 -> REJECTED!
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    # 1. Worker Alpha starts task (token=1)
    l_alpha = mgr.acquire("task_critical_race", "tenant_mukil", "worker_alpha", lease_ttl_seconds=1)
    assert l_alpha.fencing_token == 1

    # 2. Worker Alpha suffers GC pause / network timeout; lease expires
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_alpha.acquired_at = past
    l_alpha.expires_at = past + timedelta(seconds=2)

    # 3. Standby Worker Beta reclaims task (token=2)
    l_beta = reclaim_mgr.reclaim("task_critical_race", "tenant_mukil", "worker_beta", lease_ttl_seconds=30)
    assert l_beta.fencing_token == 2

    # 4. Worker Beta commits authoritative result
    state_beta = guard.execute_fenced_write(
        task_id="task_critical_race",
        tenant_id="tenant_mukil",
        worker_id="worker_beta",
        fencing_token=l_beta.fencing_token,
        write_key="final_status",
        write_value="COMPLETED_BY_BETA",
    )
    assert state_beta["data"]["final_status"] == "COMPLETED_BY_BETA"

    # 5. Worker Alpha wakes up from freeze and attempts to commit stale write (token=1)
    with pytest.raises(StaleLeaseConflictError) as exc_info:
        guard.execute_fenced_write(
            task_id="task_critical_race",
            tenant_id="tenant_mukil",
            worker_id="worker_alpha",
            fencing_token=l_alpha.fencing_token,
            write_key="final_status",
            write_value="OVERWRITTEN_BY_ZOMBIE_ALPHA",
        )
    assert exc_info.value.status_code == 409

    # Verify Beta's committed state was NOT overwritten by zombie Alpha
    persisted_state = guard.get_task_state("task_critical_race", "tenant_mukil")
    assert persisted_state["data"]["final_status"] == "COMPLETED_BY_BETA"
    assert persisted_state["last_written_by"] == "worker_beta"
    assert persisted_state["fencing_token"] == 2
