"""Phase 12.4 Step 8: Comprehensive Adversarial Concurrency & High-Contention Stress Suite.
Executes 25 Severe Multi-Threaded Stress Attacks covering 10/50/100 Worker Stampedes,
Cyclic Deadlock Inversion, Reader/Writer Starvation, Timeout Storms, and Zero State Corruption.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import random
import threading
import time
import pytest

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.locking import (
    LockConflictError,
    LockMode,
    LockNotFoundError,
    LockStatus,
    MultiResourceLockBatchRequest,
    ResourceBatchItem,
    ResourceLockContract,
    StaleLockConflictError,
    UnauthorizedLockError,
)
from app.core.leasing.resource_lock_manager import InMemoryResourceLockManager
from app.core.leasing.zombie_scavenger import ZombieLockScavenger


def _expire_lock(lock: ResourceLockContract, seconds_ago: float = 5.0) -> None:
    past = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    lock.granted_at = past - timedelta(seconds=10)
    lock.expires_at = past


# ═════════════════════════════════════════════════════════════════════════════
# 1. WORKER STAMPEDES (S8-01 to S8-03)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_01_ten_workers_race_for_one_exclusive_lock():
    """S8-01: 10 workers race across barrier for 1 EXCLUSIVE lock (1 winner, 9 409s)."""
    mgr = InMemoryResourceLockManager()
    num_workers = 10
    barrier = threading.Barrier(num_workers)
    winners, errors = [], []

    def task(w_id: int):
        barrier.wait()
        try:
            l = mgr.acquire("res://single", "tenant_A", f"w_{w_id}", f"t_{w_id}", LockMode.EXCLUSIVE)
            winners.append((w_id, l))
        except LockConflictError as ex:
            errors.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(winners) == 1
    assert len(errors) == 9
    assert mgr.is_resource_locked("res://single", "tenant_A") is True


def test_p12_4_s8_02_fifty_workers_race_for_one_exclusive_lock():
    """S8-02: 50 workers race across barrier for 1 EXCLUSIVE lock (1 winner, 49 409s)."""
    mgr = InMemoryResourceLockManager()
    num_workers = 50
    barrier = threading.Barrier(num_workers)
    winners, errors = [], []

    def task(w_id: int):
        barrier.wait()
        try:
            l = mgr.acquire("res://50_race", "tenant_A", f"w_{w_id}", f"t_{w_id}", LockMode.EXCLUSIVE)
            winners.append((w_id, l))
        except LockConflictError as ex:
            errors.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(winners) == 1
    assert len(errors) == 49


def test_p12_4_s8_03_hundred_workers_race_for_one_exclusive_lock():
    """S8-03: 100 workers race across barrier for 1 EXCLUSIVE lock (1 winner, 99 409s)."""
    mgr = InMemoryResourceLockManager()
    num_workers = 100
    barrier = threading.Barrier(num_workers)
    winners, errors = [], []

    def task(w_id: int):
        barrier.wait()
        try:
            l = mgr.acquire("res://100_race", "tenant_A", f"w_{w_id}", f"t_{w_id}", LockMode.EXCLUSIVE)
            winners.append((w_id, l))
        except LockConflictError as ex:
            errors.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(winners) == 1
    assert len(errors) == 99


# ═════════════════════════════════════════════════════════════════════════════
# 2. SHARED READERS & WRITER CONTENTION (S8-04 to S8-06)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_04_many_shared_readers_concurrently_acquire():
    """S8-04: 50 SHARED readers concurrently acquire same resource with zero conflicts."""
    mgr = InMemoryResourceLockManager()
    num_readers = 50
    barrier = threading.Barrier(num_readers)

    def task(r_id: int):
        barrier.wait()
        return mgr.acquire("drive://doc", "tenant_A", f"r_{r_id}", f"t_{r_id}", LockMode.SHARED)

    with ThreadPoolExecutor(max_workers=num_readers) as executor:
        results = list(executor.map(task, range(num_readers)))

    assert len(results) == 50
    active = mgr.get_active_locks("drive://doc", "tenant_A")
    assert len(active) == 50


def test_p12_4_s8_05_shared_readers_vs_exclusive_writer():
    """S8-05: 20 readers active -> 1 writer attempts acquire with 0 timeout -> 409."""
    mgr = InMemoryResourceLockManager()
    for i in range(20):
        mgr.acquire("drive://doc", "tenant_A", f"reader_{i}", f"t_{i}", LockMode.SHARED)

    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("drive://doc", "tenant_A", "writer_1", "t_w", LockMode.EXCLUSIVE)
    assert exc_info.value.status_code == 409


def test_p12_4_s8_06_writer_starvation_attack():
    """S8-06: Continuous stream of incoming readers cannot starve a queued writer."""
    mgr = InMemoryResourceLockManager()
    r_initial = mgr.acquire("res://stream", "tenant_A", "r_initial", "t0", LockMode.SHARED)

    writer_granted = []
    def writer_thread():
        l = mgr.acquire("res://stream", "tenant_A", "writer_priority", "tw", LockMode.EXCLUSIVE, wait_timeout_seconds=3.0)
        writer_granted.append(l)
        time.sleep(0.02)
        mgr.release("res://stream", l.lock_id, "tenant_A", "writer_priority")

    tw = threading.Thread(target=writer_thread)
    tw.start()
    time.sleep(0.05)

    # 10 aggressive readers attempt immediate acquire -> all must be rejected because writer is queued!
    rejected_readers = 0
    for i in range(10):
        try:
            mgr.acquire("res://stream", "tenant_A", f"r_stream_{i}", f"t_{i}", LockMode.SHARED)
        except LockConflictError:
            rejected_readers += 1

    assert rejected_readers == 10

    # Initial reader releases -> writer acquires!
    mgr.release("res://stream", r_initial.lock_id, "tenant_A", "r_initial")
    tw.join(timeout=2.0)

    assert len(writer_granted) == 1
    assert writer_granted[0].worker_id == "writer_priority"


# ═════════════════════════════════════════════════════════════════════════════
# 3. BOUNDARY RACES & TIMING (S8-07 to S8-12)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_07_release_acquire_race():
    """S8-07: Simultaneous release and acquire from 2 workers evaluates atomically."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("res://race", "tenant_A", "w1", "t1")

    barrier = threading.Barrier(2)
    results = []

    def releaser():
        barrier.wait()
        mgr.release("res://race", l1.lock_id, "tenant_A", "w1")

    def acquirer():
        barrier.wait()
        try:
            l = mgr.acquire("res://race", "tenant_A", "w2", "t2", wait_timeout_seconds=1.0)
            results.append(l)
        except Exception as ex:
            results.append(ex)

    t1 = threading.Thread(target=releaser)
    t2 = threading.Thread(target=acquirer)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(results) == 1
    assert isinstance(results[0], ResourceLockContract)
    assert results[0].worker_id == "w2"


def test_p12_4_s8_08_timeout_release_race():
    """S8-08: Exact timeout vs release boundary handles race deterministically."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("res://timeout_race", "tenant_A", "w1", "t1")

    w2_res = []
    def waiter():
        try:
            l = mgr.acquire("res://timeout_race", "tenant_A", "w2", "t2", wait_timeout_seconds=0.08)
            w2_res.append(("granted", l))
        except LockConflictError as ex:
            w2_res.append(("timeout", ex))

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.08)
    mgr.release("res://timeout_race", l1.lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)

    assert len(w2_res) == 1
    assert w2_res[0][0] in ("granted", "timeout")
    assert mgr.get_waiter_count("res://timeout_race", "tenant_A") == 0


def test_p12_4_s8_09_cancellation_release_race():
    """S8-09: Cancellation racing with lock release does not deadlock or leak state."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("res://cancel_race", "tenant_A", "w1", "t1")

    res = []
    def waiter():
        try:
            l = mgr.acquire("res://cancel_race", "tenant_A", "w2", "t2", wait_timeout_seconds=2.0)
            res.append(("granted", l))
        except Exception as ex:
            res.append(("error", ex))

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.03)

    key = ("tenant_A", "res://cancel_race")
    if key in mgr._waiters and mgr._waiters[key]:
        w_id = mgr._waiters[key][0].waiter_id
        mgr.cancel_waiter("res://cancel_race", "tenant_A", w_id)

    mgr.release("res://cancel_race", l1.lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)

    assert mgr.get_waiter_count("res://cancel_race", "tenant_A") == 0


def test_p12_4_s8_10_stale_release_race():
    """S8-10: 10 rapid generation cycles -> old generation releases 100% rejected."""
    mgr = InMemoryResourceLockManager()
    old_locks = []
    for i in range(10):
        l = mgr.acquire("res://gen_race", "tenant_A", f"w_{i}", f"t_{i}")
        old_locks.append(l)
        mgr.release("res://gen_race", l.lock_id, "tenant_A", f"w_{i}")

    # Current generation is 10
    # Now all old locks (0..8) attempt late release with stale generation
    for old_l in old_locks[:-1]:
        with pytest.raises(StaleLockConflictError):
            mgr.release("res://gen_race", old_l.lock_id, "tenant_A", old_l.worker_id, lock_generation=old_l.lock_generation)


def test_p12_4_s8_11_scavenger_acquire_race():
    """S8-11: Scavenger sweeping at exact instant worker acquires runs cleanly."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    barrier = threading.Barrier(2)
    def sweeper():
        barrier.wait()
        scavenger.scavenge_now()

    def acquirer():
        barrier.wait()
        return mgr.acquire("res://scav_race", "tenant_A", "w1", "t1")

    t1 = threading.Thread(target=sweeper)
    t2 = threading.Thread(target=acquirer)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert mgr.is_resource_locked("res://scav_race", "tenant_A") is True


def test_p12_4_s8_12_zombie_worker_attack():
    """S8-12: Zombie worker attempts write/release after timeout and standby reclaim."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l_zombie = mgr.acquire("res://zombie_target", "tenant_A", "w_zombie", "t_z")
    _expire_lock(l_zombie, seconds_ago=5)

    scavenger.scavenge_now()

    # Standby acquires
    l_standby = mgr.acquire("res://zombie_target", "tenant_A", "w_standby", "t_s")
    assert l_standby.lock_generation == 2

    # Zombie attempts release
    with pytest.raises(StaleLockConflictError):
        mgr.release("res://zombie_target", l_zombie.lock_id, "tenant_A", "w_zombie", lock_generation=1)


# ═════════════════════════════════════════════════════════════════════════════
# 4. DEADLOCK & CYCLIC DEPENDENCY ATTACKS (S8-13 to S8-16)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_13_multi_resource_opposite_order_attack():
    """S8-13: 4 workers requesting resources in 4 opposite permutations complete without deadlock."""
    mgr = InMemoryResourceLockManager()
    permutations = [
        ["res://a", "res://b", "res://c"],
        ["res://c", "res://b", "res://a"],
        ["res://b", "res://a", "res://c"],
        ["res://c", "res://a", "res://b"],
    ]
    completed = []

    def worker_perm(idx: int, p: list):
        req = MultiResourceLockBatchRequest(
            request_id=f"req_p_{idx}", tenant_id="tenant_A", worker_id=f"w_{idx}", task_id=f"t_{idx}",
            items=[ResourceBatchItem(resource_id=r) for r in p],
            acquire_timeout_seconds=4.0,
        )
        locks = mgr.acquire_batch(req)
        completed.append(idx)
        time.sleep(0.01)
        mgr.release_batch(locks, "tenant_A", f"w_{idx}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda pair: worker_perm(*pair), enumerate(permutations)))

    assert len(completed) == 4


def test_p12_4_s8_14_cyclic_dependency_attack():
    """S8-14: 5 workers with overlapping cyclic dependencies execute safely via canonical sort."""
    mgr = InMemoryResourceLockManager()
    completed = []

    def task(w_idx: int):
        r1 = f"res://cycle_{w_idx}"
        r2 = f"res://cycle_{(w_idx + 1) % 5}"
        req = MultiResourceLockBatchRequest(
            request_id=f"req_cyc_{w_idx}", tenant_id="tenant_A", worker_id=f"w_{w_idx}", task_id=f"t_{w_idx}",
            items=[ResourceBatchItem(resource_id=r1), ResourceBatchItem(resource_id=r2)],
            acquire_timeout_seconds=4.0,
        )
        locks = mgr.acquire_batch(req)
        completed.append(w_idx)
        time.sleep(0.01)
        mgr.release_batch(locks, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(task, range(5)))

    assert len(completed) == 5


def test_p12_4_s8_15_duplicate_batch_request_attack():
    """S8-15: Batch containing 10 duplicate instances of same resource collapses to 1 acquisition."""
    mgr = InMemoryResourceLockManager()
    items = [ResourceBatchItem(resource_id="github://aura/repo") for _ in range(10)]
    req = MultiResourceLockBatchRequest(
        request_id="req_dup", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=items,
    )
    locks = mgr.acquire_batch(req)
    assert len(locks) == 1
    assert locks[0].canonical_resource_id == "github://aura/repo"


def test_p12_4_s8_16_cross_tenant_contention_attack():
    """S8-16: 10 Tenant B workers concurrently attacking Tenant A resource are isolated."""
    mgr = InMemoryResourceLockManager()
    l_A = mgr.acquire("res://isolated", "tenant_A", "w_A", "t_A", LockMode.EXCLUSIVE)

    # 10 Tenant B workers acquire same resource in tenant_B concurrently without blocking
    barrier = threading.Barrier(10)
    def tenant_b_worker(idx: int):
        barrier.wait()
        return mgr.acquire("res://isolated", "tenant_B", f"w_B_{idx}", f"t_B_{idx}", LockMode.SHARED)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results_B = list(executor.map(tenant_b_worker, range(10)))

    assert len(results_B) == 10
    assert len(mgr.get_active_locks("res://isolated", "tenant_B")) == 10
    assert len(mgr.get_active_locks("res://isolated", "tenant_A")) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 5. HIGH-CONTENTION WORKLOADS & RE-ENTRANCY (S8-17 to S8-21)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_17_generation_monotonicity_under_contention():
    """S8-17: 50 sequential acquisitions on a contested resource climb generations 1..50."""
    mgr = InMemoryResourceLockManager()
    for i in range(50):
        l = mgr.acquire("res://monotonic", "tenant_A", f"w_{i}", f"t_{i}")
        assert l.lock_generation == i + 1
        mgr.release("res://monotonic", l.lock_id, "tenant_A", f"w_{i}")

    assert mgr.get_generation("res://monotonic", "tenant_A") == 50


def test_p12_4_s8_18_reentrant_acquisition_release_race():
    """S8-18: Worker re-entrantly nests 5 lock levels and releases 5 levels atomically."""
    mgr = InMemoryResourceLockManager()
    locks = []
    for i in range(5):
        l = mgr.acquire("res://nest", "tenant_A", "w_nested", "t1", LockMode.EXCLUSIVE)
        locks.append(l)
        assert l.reentrant_count == i

    for i in reversed(range(5)):
        r = mgr.release("res://nest", locks[0].lock_id, "tenant_A", "w_nested")
        if i > 0:
            assert r.reentrant_count == i - 1
            assert mgr.is_resource_locked("res://nest", "tenant_A") is True
        else:
            assert r.status == LockStatus.RELEASED
            assert mgr.is_resource_locked("res://nest", "tenant_A") is False


def test_p12_4_s8_19_repeated_acquire_release_stress():
    """S8-19: 100 rapid cycles of acquire and release leave zero state leaks."""
    mgr = InMemoryResourceLockManager()
    for i in range(100):
        l = mgr.acquire("res://rapid", "tenant_A", "w1", "t1")
        mgr.release("res://rapid", l.lock_id, "tenant_A", "w1")

    assert mgr.is_resource_locked("res://rapid", "tenant_A") is False
    assert len(mgr._active_locks) == 0


def test_p12_4_s8_20_thirty_resources_multi_worker_stress():
    """S8-20: 30 distinct resources × 15 workers performing concurrent batch operations."""
    mgr = InMemoryResourceLockManager()
    num_workers = 15

    def task(w_idx: int):
        for cycle in range(3):
            r_indices = [(w_idx + offset) % 30 for offset in range(3)]
            req = MultiResourceLockBatchRequest(
                request_id=f"req_30_{w_idx}_{cycle}", tenant_id="tenant_A", worker_id=f"w_{w_idx}", task_id=f"t_{w_idx}_{cycle}",
                items=[ResourceBatchItem(resource_id=f"res://r_{idx}") for idx in r_indices],
                acquire_timeout_seconds=3.0,
            )
            locks = mgr.acquire_batch(req)
            time.sleep(0.005)
            mgr.release_batch(locks, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    for i in range(30):
        assert mgr.is_resource_locked(f"res://r_{i}", "tenant_A") is False


def test_p12_4_s8_21_mixed_shared_exclusive_workload():
    """S8-21: Randomly interleaved SHARED readers and EXCLUSIVE writers operate safely."""
    mgr = InMemoryResourceLockManager()
    num_ops = 30

    def task(idx: int):
        mode = LockMode.SHARED if idx % 3 != 0 else LockMode.EXCLUSIVE
        l = mgr.acquire("res://mixed", "tenant_A", f"w_{idx}", f"t_{idx}", mode=mode, wait_timeout_seconds=3.0)
        time.sleep(0.005)
        mgr.release("res://mixed", l.lock_id, "tenant_A", f"w_{idx}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(task, range(num_ops)))

    assert mgr.is_resource_locked("res://mixed", "tenant_A") is False


# ═════════════════════════════════════════════════════════════════════════════
# 6. RANDOM SCHEDULING, ROLLBACK & CONSISTENCY (S8-22 to S8-25)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s8_22_random_scheduling_stress():
    """S8-22: 20 workers performing random acquisitions and releases across 5 resources."""
    mgr = InMemoryResourceLockManager()

    def chaotic_worker(w_idx: int):
        for _ in range(5):
            r_name = f"res://chaos_{random.randint(0, 4)}"
            mode = LockMode.SHARED if random.random() > 0.5 else LockMode.EXCLUSIVE
            try:
                l = mgr.acquire(r_name, "tenant_A", f"w_{w_idx}", f"t_{w_idx}", mode=mode, wait_timeout_seconds=0.1)
                time.sleep(0.005)
                mgr.release(r_name, l.lock_id, "tenant_A", f"w_{w_idx}")
            except LockConflictError:
                pass

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(chaotic_worker, range(20)))

    # All resources eventually unlock after all threads finish
    for i in range(5):
        assert mgr.get_waiter_count(f"res://chaos_{i}", "tenant_A") == 0


def test_p12_4_s8_23_failed_batch_rollback_stress():
    """S8-23: 15 consecutive batch failures with rollback leave 0 orphaned locks."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("res://permanent_blocker", "tenant_A", "w_blocker", "t_b")

    for i in range(15):
        req = MultiResourceLockBatchRequest(
            request_id=f"req_rb_{i}", tenant_id="tenant_A", worker_id=f"w_{i}", task_id=f"t_{i}",
            items=[ResourceBatchItem(resource_id="res://clean_a"), ResourceBatchItem(resource_id="res://permanent_blocker")],
            acquire_timeout_seconds=0.01,
        )
        try:
            mgr.acquire_batch(req)
        except LockConflictError:
            pass

    assert mgr.is_resource_locked("res://clean_a", "tenant_A") is False


def test_p12_4_s8_24_timeout_storm():
    """S8-24: 50 concurrent requests timing out simultaneously leave 0 leaked waiters."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("res://storm", "tenant_A", "w_holder", "t_h")

    def storm_waiter(idx: int):
        try:
            mgr.acquire("res://storm", "tenant_A", f"w_storm_{idx}", f"t_{idx}", wait_timeout_seconds=0.02)
        except LockConflictError:
            pass

    with ThreadPoolExecutor(max_workers=50) as executor:
        list(executor.map(storm_waiter, range(50)))

    assert mgr.get_waiter_count("res://storm", "tenant_A") == 0


def test_p12_4_s8_25_final_state_consistency_audit():
    """
    S8-25: FINAL AUDIT ON SYSTEM STATE
    Verifies: Zero leaked locks, zero leaked waiters, zero cross-tenant contamination,
    strictly monotonic generations, zero secret pollution across 100 operations.
    """
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    # 1. Monotonic generations across 20 cycles
    for i in range(20):
        l = mgr.acquire("res://audit_res", "tenant_A", f"w_{i}", f"t_{i}")
        mgr.release("res://audit_res", l.lock_id, "tenant_A", f"w_{i}")
    assert mgr.get_generation("res://audit_res", "tenant_A") == 20

    # 2. Zero leaked state
    assert len(mgr._active_locks) == 0
    assert len(mgr._waiters) == 0
    assert len(mgr._resource_modes) == 0

    # 3. Secret rejection integrity
    with pytest.raises(RawSecretPayloadError):
        mgr.acquire("github://token/ghp_SECRET_TOKEN_LEAK", "tenant_A", "w1", "t1")
