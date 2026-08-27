"""Phase 12.4 Step 7: Dedicated Auto-Expiry & Zombie Lock Scavenger Test Suite.
Verifies Expiration Detection, Autonomous Reclamation, Stale Generation Defense on Late Release,
Concurrent Scavenging Thread Safety, and Daemon Lifecycle Management.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.locking import (
    LockConflictError,
    LockMode,
    LockNotFoundError,
    LockStatus,
    ResourceLockContract,
    StaleLockConflictError,
)
from app.core.leasing.resource_lock_manager import InMemoryResourceLockManager
from app.core.leasing.zombie_scavenger import ZombieLockScavenger


def _expire_lock(lock: ResourceLockContract, seconds_ago: float = 5.0) -> None:
    """Helper to backdate both granted_at and expires_at maintaining expires_at > granted_at."""
    past = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    lock.granted_at = past - timedelta(seconds=10)
    lock.expires_at = past


def test_p12_4_s7_01_active_lock_is_not_scavenged():
    """S7-01: Active, non-expired lock is preserved during sweep."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    lock = mgr.acquire("github://active", "tenant_A", "w1", "t1", lock_ttl_seconds=30)

    report = scavenger.scavenge_now()
    assert report["scavenged_count"] == 0
    assert mgr.is_resource_locked("github://active", "tenant_A") is True


def test_p12_4_s7_02_expired_lock_detected():
    """S7-02: Lock past its expires_at timestamp is identified and evicted."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    lock = mgr.acquire("github://expired", "tenant_A", "w1", "t1", lock_ttl_seconds=1)
    _expire_lock(lock, seconds_ago=10)

    report = scavenger.scavenge_now()
    assert report["scavenged_count"] == 1
    assert report["scavenged_locks"][0]["canonical_resource_id"] == "github://expired"
    assert mgr.is_resource_locked("github://expired", "tenant_A") is False


def test_p12_4_s7_03_expired_lock_reclaimed():
    """S7-03: Scavenged resource status transitions to EXPIRED."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    lock = mgr.acquire("res://item", "tenant_A", "w1", "t1", lock_ttl_seconds=1)
    _expire_lock(lock, seconds_ago=5)

    scavenger.scavenge_now()
    assert lock.status == LockStatus.EXPIRED


def test_p12_4_s7_04_new_worker_acquires_reclaimed_resource():
    """S7-04: Standby worker can immediately acquire a scavenged resource."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://reclaim", "tenant_A", "w1", "t1", lock_ttl_seconds=1)
    _expire_lock(l1, seconds_ago=5)

    scavenger.scavenge_now()

    l2 = mgr.acquire("res://reclaim", "tenant_A", "w2", "t2", lock_ttl_seconds=30)
    assert l2.worker_id == "w2"
    assert l2.status == LockStatus.GRANTED


def test_p12_4_s7_05_generation_increments_on_reclaim():
    """S7-05: Lock generation increments to 2 on new acquisition after scavenge."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://gen", "tenant_A", "w1", "t1")
    assert l1.lock_generation == 1
    _expire_lock(l1, seconds_ago=5)

    scavenger.scavenge_now()

    l2 = mgr.acquire("res://gen", "tenant_A", "w2", "t2")
    assert l2.lock_generation == 2


def test_p12_4_s7_06_old_worker_stale_release_rejected():
    """
    S7-06: ZOMBIE LATE RELEASE REJECTION
    Worker Alpha expires -> Scavenged -> Worker Beta acquires (gen=2).
    Worker Alpha sends late release with gen=1 -> REJECTED (409).
    """
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://stale_rel", "tenant_A", "w_alpha", "t1")
    _expire_lock(l1, seconds_ago=5)

    scavenger.scavenge_now()

    l2 = mgr.acquire("res://stale_rel", "tenant_A", "w_beta", "t2")
    assert l2.lock_generation == 2

    with pytest.raises(StaleLockConflictError):
        mgr.release("res://stale_rel", l1.lock_id, "tenant_A", "w_alpha", lock_generation=1)


def test_p12_4_s7_07_repeated_scavenging_is_idempotent():
    """S7-07: Consecutive sweeps without new expired locks return 0 scavenged."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://idem", "tenant_A", "w1", "t1")
    _expire_lock(l1, seconds_ago=5)

    r1 = scavenger.scavenge_now()
    assert r1["scavenged_count"] == 1

    r2 = scavenger.scavenge_now()
    assert r2["scavenged_count"] == 0


def test_p12_4_s7_08_multiple_expired_locks_reclaimed():
    """S7-08: Batch of 5 expired locks swept in single sweep."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    for i in range(5):
        l = mgr.acquire(f"res://batch_{i}", "tenant_A", f"w_{i}", f"t_{i}")
        _expire_lock(l, seconds_ago=5)

    report = scavenger.scavenge_now()
    assert report["scavenged_count"] == 5


def test_p12_4_s7_09_active_plus_expired_mixed_set():
    """S7-09: Sweep selectively evicts only expired locks while leaving active ones untouched."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    l_exp = mgr.acquire("res://mixed_exp", "tenant_A", "w1", "t1")
    _expire_lock(l_exp, seconds_ago=5)

    l_act = mgr.acquire("res://mixed_act", "tenant_A", "w2", "t2", lock_ttl_seconds=60)

    report = scavenger.scavenge_now()
    assert report["scavenged_count"] == 1
    assert mgr.is_resource_locked("res://mixed_exp", "tenant_A") is False
    assert mgr.is_resource_locked("res://mixed_act", "tenant_A") is True


def test_p12_4_s7_10_concurrent_scavenger_and_acquire():
    """S7-10: Background scavenging concurrent with acquisitions runs without race errors."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr, poll_interval_seconds=0.02)
    scavenger.start()

    def worker_loop(w_idx: int):
        for i in range(5):
            l = mgr.acquire(f"res://con_{w_idx}_{i}", "tenant_A", f"w_{w_idx}", f"t_{i}", lock_ttl_seconds=1)
            time.sleep(0.01)
            mgr.release(f"res://con_{w_idx}_{i}", l.lock_id, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(worker_loop, range(6)))

    scavenger.stop()


def test_p12_4_s7_11_concurrent_scavenger_and_release():
    """S7-11: Simultaneous voluntary release and scavenger sweep handle race cleanly."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://race_rel", "tenant_A", "w1", "t1")

    barrier = threading.Barrier(2)
    def release_worker():
        barrier.wait()
        try:
            mgr.release("res://race_rel", l1.lock_id, "tenant_A", "w1")
        except Exception:
            pass

    def scavenger_worker():
        barrier.wait()
        scavenger.scavenge_now()

    t1 = threading.Thread(target=release_worker)
    t2 = threading.Thread(target=scavenger_worker)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert mgr.is_resource_locked("res://race_rel", "tenant_A") is False


def test_p12_4_s7_12_cross_tenant_isolation_during_scavenging():
    """S7-12: Expired lock in Tenant A does not affect Tenant B locks."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    l_A = mgr.acquire("github://same_name", "tenant_A", "wA", "tA")
    _expire_lock(l_A, seconds_ago=5)

    l_B = mgr.acquire("github://same_name", "tenant_B", "wB", "tB", lock_ttl_seconds=60)

    scavenger.scavenge_now()
    assert mgr.is_resource_locked("github://same_name", "tenant_A") is False
    assert mgr.is_resource_locked("github://same_name", "tenant_B") is True


def test_p12_4_s7_13_deterministic_expiry_boundary():
    """S7-13: Lock 1 second before expiry is kept; 1 second after is evicted."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    now = datetime.now(timezone.utc)

    l_kept = mgr.acquire("res://kept", "tenant_A", "w1", "t1")
    l_kept.granted_at = now
    l_kept.expires_at = now + timedelta(seconds=2)

    l_swept = mgr.acquire("res://swept", "tenant_A", "w2", "t2")
    _expire_lock(l_swept, seconds_ago=1)

    report = scavenger.scavenge_now()
    assert report["scavenged_count"] == 1
    assert report["scavenged_locks"][0]["canonical_resource_id"] == "res://swept"


def test_p12_4_s7_14_no_lock_leakage():
    """S7-14: Active lock registry has zero orphaned keys after all locks expire and are swept."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    for i in range(10):
        l = mgr.acquire(f"res://leak_{i}", "tenant_A", f"w_{i}", f"t_{i}")
        _expire_lock(l, seconds_ago=10)

    scavenger.scavenge_now()
    assert len(mgr._active_locks) == 0
    assert len(mgr._resource_modes) == 0


def test_p12_4_s7_15_background_lifecycle_start_stop():
    """S7-15: Background daemon thread starts, reports is_running, and stops cleanly."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr, poll_interval_seconds=0.05)

    assert scavenger.is_running is False
    scavenger.start()
    assert scavenger.is_running is True

    # Repeated start is idempotent
    scavenger.start()
    assert scavenger.is_running is True

    scavenger.stop()
    assert scavenger.is_running is False


def test_p12_4_s7_16_zombie_worker_cannot_regain_authority():
    """S7-16: Zombie worker attempting to release after scavenge gets 404 (not found)."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://zombie", "tenant_A", "w_zombie", "tz")
    _expire_lock(l1, seconds_ago=5)

    scavenger.scavenge_now()

    with pytest.raises(LockNotFoundError):
        mgr.release("res://zombie", l1.lock_id, "tenant_A", "w_zombie")


def test_p12_4_s7_17_stale_generation_defense_after_multiple_cycles():
    """S7-17: Multiple cycles of expire->scavenge->acquire advance generation monotonically."""
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)

    for gen in range(1, 6):
        l = mgr.acquire("res://cycles", "tenant_A", f"w_{gen}", f"t_{gen}")
        assert l.lock_generation == gen
        _expire_lock(l, seconds_ago=5)
        scavenger.scavenge_now()

    assert mgr.get_generation("res://cycles", "tenant_A") == 5


def test_p12_4_s7_18_scavenger_wakes_queued_waiters():
    """
    S7-18: When active lock expires, scavenger sweep automatically wakes queued waiters!
    """
    mgr = InMemoryResourceLockManager()
    scavenger = ZombieLockScavenger(mgr)
    l1 = mgr.acquire("res://wait_scavenge", "tenant_A", "w1", "t1")
    _expire_lock(l1, seconds_ago=5)

    w2_lock = []
    def waiter_thread():
        l = mgr.acquire("res://wait_scavenge", "tenant_A", "w2", "t2", wait_timeout_seconds=2.0)
        w2_lock.append(l)

    t = threading.Thread(target=waiter_thread)
    t.start()
    time.sleep(0.05)

    # Scavenger sweep evicts l1 and wakes w2!
    scavenger.scavenge_now()
    t.join(timeout=1.0)

    assert len(w2_lock) == 1
    assert w2_lock[0].worker_id == "w2"
    assert w2_lock[0].lock_generation == 2
