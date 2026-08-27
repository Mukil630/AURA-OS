"""Phase 12.3 Step 6: Dedicated Unit, Adversarial & Multi-Worker Race Tests for Standby Reclaim Manager.
Verifies Lease Expiration Detection, Reclaim Eligibility Evaluation, Cross-Tenant Isolation,
Completed Task Protection, Standby Ownership Transfer, and High-Concurrency Standby Reclaim Races.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseNotFoundError,
    LeaseStatus,
    QueueMessageContract,
    UnauthorizedWorkerError,
)
from app.core.leasing.heartbeat_daemon import (
    HeartbeatDaemonConfig,
    HeartbeatRenewalDaemon,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager
from app.core.leasing.reclaim_manager import StandbyReclaimManager
from app.core.leasing.task_queue import InMemoryTaskQueue


# ═════════════════════════════════════════════════════════════════════════════
# 1. EXPIRATION DETECTION & RECLAIM ELIGIBILITY (Tests 1 - 3)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_01_active_lease_not_reclaimable():
    """S6-01: An actively held unexpired lease is not reclaimable (raises 409)."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    mgr.acquire("task_active", "tenant_A", "worker_alpha", lease_ttl_seconds=30)

    is_elig, reason = reclaim_mgr.is_eligible_for_reclaim("task_active", "tenant_A")
    assert is_elig is False
    assert "currently held" in reason

    with pytest.raises(LeaseConflictError) as exc_info:
        reclaim_mgr.reclaim("task_active", "tenant_A", "worker_standby")
    assert exc_info.value.status_code == 409


def test_p12_3_s6_02_expired_lease_is_detectable():
    """S6-02: detect_expired_leases() returns timed-out leases across the tenant."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l1 = mgr.acquire("task_1", "tenant_A", "worker_1", lease_ttl_seconds=1)
    l2 = mgr.acquire("task_2", "tenant_A", "worker_2", lease_ttl_seconds=30)

    # Backdate l1 to simulate expiration
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    expired = reclaim_mgr.detect_expired_leases("tenant_A")
    assert len(expired) == 1
    assert expired[0].task_id == "task_1"


def test_p12_3_s6_03_expired_lease_becomes_eligible_for_reclaim():
    """S6-03: An expired lease is reported eligible for reclaim by is_eligible_for_reclaim()."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    lease = mgr.acquire("task_exp", "tenant_A", "worker_1", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    lease.acquired_at = past
    lease.expires_at = past + timedelta(seconds=2)

    is_elig, reason = reclaim_mgr.is_eligible_for_reclaim("task_exp", "tenant_A")
    assert is_elig is True
    assert "eligible for reclaim" in reason


# ═════════════════════════════════════════════════════════════════════════════
# 2. STANDBY RECLAIM & OWNERSHIP TRANSFER (Tests 4 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_04_standby_worker_can_reclaim_expired_lease():
    """S6-04: Standby worker successfully reclaims an expired task lease."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_old = mgr.acquire("task_reclaim", "tenant_A", "worker_crashed", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    new_lease = reclaim_mgr.reclaim("task_reclaim", "tenant_A", "worker_standby", lease_ttl_seconds=30)
    assert new_lease.task_id == "task_reclaim"
    assert new_lease.worker_id == "worker_standby"
    assert new_lease.status == LeaseStatus.ACQUIRED
    assert new_lease.metadata["reclaimed_from_worker"] == "worker_crashed"


def test_p12_3_s6_05_reclaim_transfers_task_ownership_correctly():
    """S6-05: Reclaim assigns new worker as the sole registered owner."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_old = mgr.acquire("task_owner", "tenant_A", "worker_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    reclaim_mgr.reclaim("task_owner", "tenant_A", "worker_new")

    current_lease = mgr.get_lease("task_owner", "tenant_A")
    assert current_lease.worker_id == "worker_new"

    # Old worker cannot release the new lease (403)
    with pytest.raises(UnauthorizedWorkerError):
        mgr.release("task_owner", current_lease.lease_id, "worker_old", "tenant_A")


# ═════════════════════════════════════════════════════════════════════════════
# 3. TENANT ISOLATION & ACCESS CONTROL (Tests 6 - 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_06_tenant_a_cannot_reclaim_tenant_b_task():
    """S6-06: Tenant B worker cannot reclaim Tenant A expired task (403)."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_a = mgr.acquire("task_tenant_a", "tenant_A", "worker_a", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_a.acquired_at = past
    l_a.expires_at = past + timedelta(seconds=2)

    with pytest.raises(UnauthorizedWorkerError) as exc_info:
        reclaim_mgr.reclaim("task_tenant_a", "tenant_B", "worker_b")
    assert exc_info.value.status_code == 403


def test_p12_3_s6_07_missing_lease_cannot_be_reclaimed():
    """S6-07: Attempting to reclaim a non-existent task raises LeaseNotFoundError (404)."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    with pytest.raises(LeaseNotFoundError) as exc_info:
        reclaim_mgr.reclaim("non_existent_task", "tenant_A", "worker_standby")
    assert exc_info.value.status_code == 404


def test_p12_3_s6_08_already_completed_task_cannot_be_reclaimed():
    """S6-08: A task marked completed cannot be reclaimed by any standby worker."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l = mgr.acquire("task_done", "tenant_A", "worker_1")
    mgr.release("task_done", l.lease_id, "worker_1", "tenant_A")
    reclaim_mgr.mark_task_completed("task_done")

    with pytest.raises(LeaseConflictError) as exc_info:
        reclaim_mgr.reclaim("task_done", "tenant_A", "worker_standby")
    assert "completed" in exc_info.value.detail.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 4. IDEMPOTENCY & CONCURRENT STANDBY RACES (Tests 9 - 11)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_09_reclaim_rejected_after_successful_reclaim():
    """S6-09: Once a standby worker reclaims, a subsequent standby worker is rejected."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_old = mgr.acquire("task_once", "tenant_A", "worker_crashed", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    # First standby worker wins
    reclaim_mgr.reclaim("task_once", "tenant_A", "standby_1", lease_ttl_seconds=30)

    # Second standby worker arrives -> Conflict!
    with pytest.raises(LeaseConflictError):
        reclaim_mgr.reclaim("task_once", "tenant_A", "standby_2")


def test_p12_3_s6_10_two_standby_workers_concurrent_barrier_race():
    """
    S6-10: HARD CONCURRENCY PROOF
    Two standby workers release simultaneously to reclaim one expired lease.
    Verifies exactly 1 winner and exactly 1 conflict rejection (409).
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_old = mgr.acquire("task_race", "tenant_A", "worker_crashed", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    barrier = threading.Barrier(2)
    winners = []
    conflicts = []

    def standby_attempt(name: str):
        barrier.wait()
        try:
            lease = reclaim_mgr.reclaim("task_race", "tenant_A", name)
            winners.append((name, lease))
        except LeaseConflictError as ex:
            conflicts.append((name, ex))

    t1 = threading.Thread(target=standby_attempt, args=("Standby_Alpha",))
    t2 = threading.Thread(target=standby_attempt, args=("Standby_Beta",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(winners) == 1, "Expected exactly 1 standby worker to win reclaim!"
    assert len(conflicts) == 1, "Expected exactly 1 standby worker to receive conflict!"


def test_p12_3_s6_11_multiple_expired_tasks_reclaimed_independently():
    """S6-11: Multiple expired tasks can be reclaimed concurrently without interference."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    for i in range(5):
        l = mgr.acquire(f"task_multi_{i}", "tenant_A", "worker_old", lease_ttl_seconds=1)
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        l.acquired_at = past
        l.expires_at = past + timedelta(seconds=2)

    def reclaim_task(i: int):
        return reclaim_mgr.reclaim(f"task_multi_{i}", "tenant_A", f"standby_{i}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(reclaim_task, range(5)))

    assert len(results) == 5
    for idx, r in enumerate(results):
        assert r.worker_id == f"standby_{idx}"


# ═════════════════════════════════════════════════════════════════════════════
# 5. HEARTBEAT INTERACTION & TIMING (Tests 12 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_12_valid_heartbeat_prevents_premature_reclaim():
    """S6-12: A living worker maintaining heartbeats cannot have its lease reclaimed."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    cfg = HeartbeatDaemonConfig(worker_id="worker_live", tenant_id="tenant_A", heartbeat_interval_seconds=0.05)
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_heartbeating", "tenant_A", "worker_live", lease_ttl_seconds=5)
    daemon.register_lease("task_heartbeating", lease.lease_id)
    daemon.tick_renewals()  # renews lease

    with pytest.raises(LeaseConflictError):
        reclaim_mgr.reclaim("task_heartbeating", "tenant_A", "worker_standby")


def test_p12_3_s6_13_deterministic_expiry_boundary_check():
    """S6-13: Verifies exact timestamp boundary for expiration and reclaim eligibility."""
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    now = datetime.now(timezone.utc)
    l = mgr.acquire("task_boundary", "tenant_A", "w1", lease_ttl_seconds=10)

    # 1 second before expiry -> Not eligible
    l.acquired_at = now - timedelta(seconds=9)
    l.expires_at = now + timedelta(seconds=1)
    assert reclaim_mgr.is_eligible_for_reclaim("task_boundary", "tenant_A")[0] is False

    # 1 second after expiry -> Eligible
    l.acquired_at = now - timedelta(seconds=11)
    l.expires_at = now - timedelta(seconds=1)
    assert reclaim_mgr.is_eligible_for_reclaim("task_boundary", "tenant_A")[0] is True


# ═════════════════════════════════════════════════════════════════════════════
# 6. QUEUE CONSISTENCY & FULL LIFECYCLE (Tests 14 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s6_14_queue_message_not_duplicated_on_lease_reclaim():
    """
    S6-14: ARCHITECTURAL ASSERTION (Queue != Lease)
    Reclaiming an expired lease does not create new duplicate queue messages.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    msg = QueueMessageContract(message_id="msg_01", task_id="task_01", tenant_id="tenant_A")
    queue.enqueue(msg)
    consumed = queue.dequeue("tenant_A", worker_id="worker_crashed")

    l_old = mgr.acquire(consumed.task_id, consumed.tenant_id, "worker_crashed", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    # Standby worker reclaims
    reclaim_mgr.reclaim("task_01", "tenant_A", "worker_standby")

    # Queue should still have exactly 0 pending messages and 1 in-flight
    assert queue.qsize("tenant_A") == 0
    assert queue.in_flight_count("tenant_A") == 1


def test_p12_3_s6_15_full_queue_lease_expiry_reclaim_ack_lifecycle():
    """
    S6-15: END-TO-END CRASH RECOVERY LIFECYCLE
    1. Producer enqueues task.
    2. Worker Alpha dequeues and acquires lease.
    3. Worker Alpha crashes (heartbeat stops, lease expires).
    4. Standby Worker Beta detects expiration and reclaims task lease.
    5. Standby Worker Beta executes, releases lease, and ACKs message.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    # 1. Enqueue
    msg = QueueMessageContract(message_id="m_e2e", task_id="t_e2e", tenant_id="tenant_mukil")
    queue.enqueue(msg)

    # 2. Worker Alpha dequeues and acquires
    consumed = queue.dequeue("tenant_mukil", worker_id="worker_alpha")
    l_alpha = mgr.acquire(consumed.task_id, consumed.tenant_id, "worker_alpha", lease_ttl_seconds=1)

    # 3. Simulate crash & timeout
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_alpha.acquired_at = past
    l_alpha.expires_at = past + timedelta(seconds=2)

    # 4. Standby Worker Beta reclaims
    l_beta = reclaim_mgr.reclaim("t_e2e", "tenant_mukil", "worker_beta", lease_ttl_seconds=30)
    assert l_beta.worker_id == "worker_beta"
    assert l_beta.fencing_token == 2

    # 5. Worker Beta releases and ACKs
    mgr.release("t_e2e", l_beta.lease_id, "worker_beta", "tenant_mukil")
    reclaim_mgr.mark_task_completed("t_e2e")

    ack_ok = queue.ack(consumed.message_id, "tenant_mukil")
    assert ack_ok is True
    assert queue.in_flight_count("tenant_mukil") == 0
    assert reclaim_mgr.is_task_completed("t_e2e") is True
