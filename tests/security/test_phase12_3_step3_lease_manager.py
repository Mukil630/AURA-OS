"""Phase 12.3 Step 3: Dedicated Unit, Adversarial & Multi-Threaded Race Condition Test Suite.
Verifies Atomic Lease Acquisition, Heartbeat Renewal, Release, Fencing Token Monotonicity,
Tenant Pinning, and High-Concurrency Multi-Worker Barrier Races.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseExpiredError,
    LeaseNotFoundError,
    LeaseStatus,
    UnauthorizedWorkerError,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager


# ═════════════════════════════════════════════════════════════════════════════
# 1. BASIC ACQUISITION & FENCING COUNTERS (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_01_acquire_free_task():
    """S3-01: Acquiring a free task returns an active lease."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire(task_id="task_101", tenant_id="tenant_A", worker_id="worker_1", lease_ttl_seconds=30)

    assert lease.task_id == "task_101"
    assert lease.tenant_id == "tenant_A"
    assert lease.worker_id == "worker_1"
    assert lease.status == LeaseStatus.ACQUIRED
    assert lease.lease_ttl_seconds == 30


def test_p12_3_s3_02_acquire_creates_valid_contract():
    """S3-02: Lease contract created has valid timestamps and unique lease_id."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_102", "tenant_A", "worker_1", lease_ttl_seconds=10)

    assert lease.lease_id.startswith("lease_")
    assert lease.expires_at > lease.acquired_at
    assert lease.renewal_count == 0


def test_p12_3_s3_03_first_fencing_token_is_one():
    """S3-03: The first acquisition of a task always receives fencing_token = 1."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_103", "tenant_A", "worker_1")
    assert lease.fencing_token == 1
    assert mgr.get_fencing_token("task_103") == 1


def test_p12_3_s3_04_second_acquire_while_active_raises_409():
    """S3-04: Attempting to acquire an actively leased task raises LeaseConflictError (409)."""
    mgr = InMemoryLeaseManager()
    mgr.acquire("task_104", "tenant_A", "worker_1", lease_ttl_seconds=30)

    with pytest.raises(LeaseConflictError) as exc_info:
        mgr.acquire("task_104", "tenant_A", "worker_2", lease_ttl_seconds=30)
    assert exc_info.value.status_code == 409
    assert "currently leased" in exc_info.value.detail


def test_p12_3_s3_05_different_tasks_have_independent_leases():
    """S3-05: Independent tasks can be acquired concurrently by same or different workers."""
    mgr = InMemoryLeaseManager()
    l1 = mgr.acquire("task_A", "tenant_1", "worker_1")
    l2 = mgr.acquire("task_B", "tenant_1", "worker_2")

    assert l1.task_id == "task_A"
    assert l2.task_id == "task_B"
    assert l1.lease_id != l2.lease_id


# ═════════════════════════════════════════════════════════════════════════════
# 2. WORKER OWNERSHIP & VALIDATION (Tests 6 - 9)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_06_wrong_worker_cannot_renew():
    """S3-06: Worker B attempting to renew Worker A's lease raises UnauthorizedWorkerError (403)."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_201", "tenant_A", "worker_A")

    with pytest.raises(UnauthorizedWorkerError) as exc_info:
        mgr.renew("task_201", lease.lease_id, worker_id="worker_B", tenant_id="tenant_A")
    assert exc_info.value.status_code == 403


def test_p12_3_s3_07_wrong_worker_cannot_release():
    """S3-07: Worker B attempting to release Worker A's lease raises UnauthorizedWorkerError (403)."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_202", "tenant_A", "worker_A")

    with pytest.raises(UnauthorizedWorkerError) as exc_info:
        mgr.release("task_202", lease.lease_id, worker_id="worker_B", tenant_id="tenant_A")
    assert exc_info.value.status_code == 403


def test_p12_3_s3_08_fake_lease_id_rejected():
    """S3-08: Renewing with a forged or mismatched lease_id raises LeaseNotFoundError (404)."""
    mgr = InMemoryLeaseManager()
    mgr.acquire("task_203", "tenant_A", "worker_A")

    with pytest.raises(LeaseNotFoundError) as exc_info:
        mgr.renew("task_203", "fake_lease_999", worker_id="worker_A", tenant_id="tenant_A")
    assert exc_info.value.status_code == 404


def test_p12_3_s3_09_missing_task_rejected():
    """S3-09: Operating on a non-existent task raises LeaseNotFoundError (404)."""
    mgr = InMemoryLeaseManager()
    with pytest.raises(LeaseNotFoundError) as exc_info:
        mgr.renew("non_existent_task", "lease_123", worker_id="worker_A", tenant_id="tenant_A")
    assert exc_info.value.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 3. LEASE RENEWAL & EXTENSION (Tests 10 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_10_valid_renewal_succeeds():
    """S3-10: Registered owner can successfully renew an active lease."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_301", "tenant_A", "worker_A", lease_ttl_seconds=10)
    renewed = mgr.renew("task_301", lease.lease_id, "worker_A", "tenant_A")

    assert renewed.status == LeaseStatus.RENEWED
    assert renewed.renewal_count == 1


def test_p12_3_s3_11_renewal_increments_count():
    """S3-11: Multiple heartbeats monotonically increment renewal_count."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_302", "tenant_A", "worker_A", lease_ttl_seconds=10)
    mgr.renew("task_302", lease.lease_id, "worker_A", "tenant_A")
    mgr.renew("task_302", lease.lease_id, "worker_A", "tenant_A")
    final = mgr.renew("task_302", lease.lease_id, "worker_A", "tenant_A")

    assert final.renewal_count == 3


def test_p12_3_s3_12_renewal_extends_expiry():
    """S3-12: Renewal extends expires_at into the future."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_303", "tenant_A", "worker_A", lease_ttl_seconds=5)
    initial_expiry = lease.expires_at

    time.sleep(0.01)  # small delta
    renewed = mgr.renew("task_303", lease.lease_id, "worker_A", "tenant_A", extension_seconds=20)
    assert renewed.expires_at > initial_expiry


def test_p12_3_s3_13_expired_lease_cannot_renew():
    """S3-13: Attempting to renew a lease after expiry raises LeaseExpiredError (410)."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_304", "tenant_A", "worker_A", lease_ttl_seconds=1)
    # Backdate both timestamps to simulate a valid lease that has since expired
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    lease.acquired_at = past
    lease.expires_at = past + timedelta(seconds=2)

    with pytest.raises(LeaseExpiredError) as exc_info:
        mgr.renew("task_304", lease.lease_id, "worker_A", "tenant_A")
    assert exc_info.value.status_code == 410


# ═════════════════════════════════════════════════════════════════════════════
# 4. RELEASE & RE-ACQUISITION CYCLES (Tests 14 - 17)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_14_valid_release_succeeds():
    """S3-14: Voluntary release sets status to RELEASED."""
    mgr = InMemoryLeaseManager()
    lease = mgr.acquire("task_401", "tenant_A", "worker_A")
    released = mgr.release("task_401", lease.lease_id, "worker_A", "tenant_A")

    assert released.status == LeaseStatus.RELEASED
    assert mgr.is_task_acquirable("task_401") is True


def test_p12_3_s3_15_released_task_can_be_reacquired():
    """S3-15: Once released, a task can be acquired by a new worker."""
    mgr = InMemoryLeaseManager()
    lease1 = mgr.acquire("task_402", "tenant_A", "worker_A")
    mgr.release("task_402", lease1.lease_id, "worker_A", "tenant_A")

    lease2 = mgr.acquire("task_402", "tenant_A", "worker_B")
    assert lease2.worker_id == "worker_B"
    assert lease2.lease_id != lease1.lease_id


def test_p12_3_s3_16_expired_task_becomes_acquirable():
    """S3-16: A timed-out lease is automatically reclaimed by a standby worker."""
    mgr = InMemoryLeaseManager()
    lease1 = mgr.acquire("task_403", "tenant_A", "worker_A", lease_ttl_seconds=1)
    # Backdate both timestamps to simulate timeout
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    lease1.acquired_at = past
    lease1.expires_at = past + timedelta(seconds=2)

    # Standby worker acquires
    lease2 = mgr.acquire("task_403", "tenant_A", "worker_B", lease_ttl_seconds=30)
    assert lease2.worker_id == "worker_B"
    assert lease2.status == LeaseStatus.ACQUIRED


def test_p12_3_s3_17_reacquisition_receives_higher_fencing_token():
    """S3-17: Every subsequent lease acquisition receives a strictly higher monotonic fencing token."""
    mgr = InMemoryLeaseManager()
    l1 = mgr.acquire("task_404", "tenant_A", "worker_1")
    assert l1.fencing_token == 1

    mgr.release("task_404", l1.lease_id, "worker_1", "tenant_A")
    l2 = mgr.acquire("task_404", "tenant_A", "worker_2")
    assert l2.fencing_token == 2

    mgr.release("task_404", l2.lease_id, "worker_2", "tenant_A")
    l3 = mgr.acquire("task_404", "tenant_A", "worker_3")
    assert l3.fencing_token == 3
    assert l3.fencing_token > l2.fencing_token > l1.fencing_token


# ═════════════════════════════════════════════════════════════════════════════
# 5. TENANT PINNING & ISOLATION (Tests 18 - 19)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_18_same_tenant_worker_succeeds():
    """S3-18: Workers within the same tenant namespace can acquire and reacquire tasks."""
    mgr = InMemoryLeaseManager()
    l1 = mgr.acquire("task_501", "tenant_mukil", "worker_1")
    mgr.release("task_501", l1.lease_id, "worker_1", "tenant_mukil")

    l2 = mgr.acquire("task_501", "tenant_mukil", "worker_2")
    assert l2.tenant_id == "tenant_mukil"


def test_p12_3_s3_19_cross_tenant_worker_rejected():
    """S3-19: Worker from Tenant B attempting to acquire Tenant A task is rejected."""
    mgr = InMemoryLeaseManager()
    mgr.acquire("task_pinned", "tenant_A", "worker_A")

    # Worker B tries to acquire Tenant A's task
    with pytest.raises(UnauthorizedWorkerError) as exc_info:
        mgr.acquire("task_pinned", tenant_id="tenant_B", worker_id="worker_B")
    assert exc_info.value.status_code == 403
    assert "Cross-tenant task acquisition denied" in exc_info.value.detail


# ═════════════════════════════════════════════════════════════════════════════
# 6. HIGH-CONCURRENCY MULTI-THREADED RACE CONDITIONS (Tests 20 - 22)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s3_20_two_workers_concurrent_barrier_race():
    """
    S3-20: HARD CONCURRENCY PROOF
    Two threads release simultaneously across a threading.Barrier to acquire the same task.
    Verifies exactly 1 Winner (200) and exactly 1 Conflict Denial (409).
    """
    mgr = InMemoryLeaseManager()
    task_id = "task_race_2_workers"
    tenant_id = "tenant_A"
    barrier = threading.Barrier(2)

    results = []
    errors = []

    def worker_job(worker_name: str):
        try:
            barrier.wait()  # synchronize release
            lease = mgr.acquire(task_id, tenant_id, worker_name, lease_ttl_seconds=30)
            results.append((worker_name, lease))
        except LeaseConflictError as ex:
            errors.append((worker_name, ex))

    t1 = threading.Thread(target=worker_job, args=("Worker_Alpha",))
    t2 = threading.Thread(target=worker_job, args=("Worker_Beta",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 1, "Expected exactly 1 winning lease acquisition!"
    assert len(errors) == 1, "Expected exactly 1 denied lease conflict!"
    assert errors[0][1].status_code == 409


def test_p12_3_s3_21_twenty_workers_high_concurrency_race():
    """
    S3-21: 20 distributed workers race simultaneously via ThreadPoolExecutor.
    Asserts: exactly 1 winner, exactly 19 denials (409), exactly 1 active lease.
    """
    mgr = InMemoryLeaseManager()
    task_id = "task_stampede_20"
    tenant_id = "tenant_scale"
    num_workers = 20
    barrier = threading.Barrier(num_workers)

    success_leases = []
    conflict_errors = []

    def worker_acquire(w_id: int):
        barrier.wait()
        try:
            lease = mgr.acquire(task_id, tenant_id, f"worker_node_{w_id}")
            return ("SUCCESS", lease)
        except LeaseConflictError as ex:
            return ("CONFLICT", ex)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_acquire, i) for i in range(num_workers)]
        for f in as_completed(futures):
            res_type, val = f.result()
            if res_type == "SUCCESS":
                success_leases.append(val)
            else:
                conflict_errors.append(val)

    assert len(success_leases) == 1, f"Expected 1 winner, got {len(success_leases)}"
    assert len(conflict_errors) == num_workers - 1, f"Expected {num_workers - 1} denials, got {len(conflict_errors)}"
    active_leases = mgr.list_active_leases(tenant_id="tenant_scale")
    assert len(active_leases) == 1


def test_p12_3_s3_22_single_exclusive_lease_invariant_under_concurrent_cycles():
    """
    S3-22: INVARIANT PROOF (∀ task T: active_leases(T) <= 1)
    Simulates rapid cycles of acquire -> release -> acquire across multiple concurrent workers.
    """
    mgr = InMemoryLeaseManager()
    task_id = "task_cycle_invariant"
    tenant_id = "tenant_A"

    for cycle in range(5):
        # 5 workers race
        barrier = threading.Barrier(5)
        winner = None

        def race_worker(w_idx: int):
            barrier.wait()
            try:
                return mgr.acquire(task_id, tenant_id, f"w_{cycle}_{w_idx}", lease_ttl_seconds=10)
            except LeaseConflictError:
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(race_worker, range(5)))
            winners = [r for r in results if r is not None]
            assert len(winners) == 1, f"Cycle {cycle}: Expected 1 winner, got {len(winners)}"
            winner = winners[0]

        # Invariant check
        active = mgr.list_active_leases(tenant_id)
        assert len(active) == 1
        assert active[0].fencing_token == cycle + 1

        # Release for next cycle
        mgr.release(task_id, winner.lease_id, winner.worker_id, tenant_id)
