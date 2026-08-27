"""Phase 12.4 Step 5: Dedicated Lock Queuing, Wait Timeout & Fairness Test Suite.
Verifies FIFO Wait Queue Ordering, Writer Starvation Prevention, Event-Driven Wakeups,
Bounded Timeout Eviction, Waiter Cancellation, and Zero Waiter Leakage.
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
    UnauthorizedLockError,
)
from app.core.leasing.resource_lock_manager import InMemoryResourceLockManager


def test_p12_4_s5_01_immediate_acquisition_when_resource_is_free():
    """S5-01: Free resource acquired immediately without queue delay."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE, wait_timeout_seconds=5.0)
    assert lock.status == LockStatus.GRANTED
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_02_conflicting_request_enters_wait_queue():
    """S5-02: Conflicting request blocks in waiter queue when wait_timeout > 0."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    # Thread 2 enters wait queue
    acquired_locks = []
    def waiter_thread():
        l = mgr.acquire("github://repo", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
        acquired_locks.append(l)

    t = threading.Thread(target=waiter_thread)
    t.start()
    time.sleep(0.05)

    assert mgr.get_waiter_count("github://repo", "tenant_A") == 1
    # Release by w1 wakes w2
    active_locks = mgr.get_active_locks("github://repo", "tenant_A")
    mgr.release("github://repo", active_locks[0].lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)

    assert len(acquired_locks) == 1
    assert acquired_locks[0].worker_id == "w2"
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_03_waiter_acquires_after_release():
    """S5-03: Queued waiter acquires resource immediately upon release notification."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    results = []
    def bg():
        l = mgr.acquire("github://repo", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
        results.append(l)

    t = threading.Thread(target=bg)
    t.start()
    time.sleep(0.05)

    mgr.release("github://repo", l1.lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)

    assert len(results) == 1
    assert results[0].worker_id == "w2"


def test_p12_4_s5_04_fifo_ordering():
    """S5-04: Multiple conflicting waiters are granted in strict FIFO arrival order."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    grant_order = []
    def make_waiter(w_id: str):
        def run():
            l = mgr.acquire("github://repo", "tenant_A", w_id, f"task_{w_id}", LockMode.EXCLUSIVE, wait_timeout_seconds=3.0)
            grant_order.append(w_id)
            # quickly release to wake next in FIFO queue
            mgr.release("github://repo", l.lock_id, "tenant_A", w_id)
        return run

    threads = []
    for w_name in ["w_first", "w_second", "w_third"]:
        t = threading.Thread(target=make_waiter(w_name))
        threads.append(t)
        t.start()
        time.sleep(0.04) # Ensure arrival order

    assert mgr.get_waiter_count("github://repo", "tenant_A") == 3

    # Release initial lock to start FIFO cascade
    mgr.release("github://repo", l1.lock_id, "tenant_A", "w1")

    for t in threads:
        t.join(timeout=2.0)

    assert grant_order == ["w_first", "w_second", "w_third"]
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_05_later_worker_cannot_bypass_earlier_conflicting_waiter():
    """S5-05: A new request cannot jump ahead of an existing queued waiter."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    # w_queued waits
    t = threading.Thread(target=lambda: mgr.acquire("github://repo", "tenant_A", "w_queued", "t_q", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0))
    t.start()
    time.sleep(0.05)

    # w_bypasser attempts zero-timeout immediate acquire
    with pytest.raises(LockConflictError):
        mgr.acquire("github://repo", "tenant_A", "w_bypasser", "t_b", LockMode.EXCLUSIVE)

    mgr.release("github://repo", l1.lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)


def test_p12_4_s5_06_writer_starvation_prevention():
    """
    S5-06: WRITER STARVATION DEFENSE
    Active SHARED reader + Queued EXCLUSIVE writer.
    New SHARED reader arrives -> MUST QUEUE behind writer rather than starving writer!
    """
    mgr = InMemoryResourceLockManager()
    r1 = mgr.acquire("drive://vault", "tenant_A", "reader_1", "t1", LockMode.SHARED)

    # Writer queues
    writer_granted = []
    def writer_thread():
        l = mgr.acquire("drive://vault", "tenant_A", "writer_1", "t_w", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
        writer_granted.append(l)
        mgr.release("drive://vault", l.lock_id, "tenant_A", "writer_1")

    tw = threading.Thread(target=writer_thread)
    tw.start()
    time.sleep(0.05)

    # New reader arrives with 0 timeout -> Rejected/Must Queue because writer is waiting!
    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("drive://vault", "tenant_A", "reader_2", "t2", LockMode.SHARED)
    assert "priority to prevent reader starvation" in exc_info.value.detail

    # r1 releases -> writer gets granted!
    mgr.release("drive://vault", r1.lock_id, "tenant_A", "reader_1")
    tw.join(timeout=1.0)

    assert len(writer_granted) == 1
    assert writer_granted[0].worker_id == "writer_1"


def test_p12_4_s5_07_wait_timeout_fires_deterministically():
    """S5-07: Bounded wait timeout raises 409 LockConflictError after timeout expires."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    start = time.time()
    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("github://repo", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE, wait_timeout_seconds=0.1)
    duration = time.time() - start

    assert 0.08 <= duration <= 0.5
    assert "Timed out after 0.1s" in exc_info.value.detail


def test_p12_4_s5_08_timed_out_waiter_removed_from_queue():
    """S5-08: Timed-out waiter is cleanly pruned with zero queue residue."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    with pytest.raises(LockConflictError):
        mgr.acquire("github://repo", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE, wait_timeout_seconds=0.05)

    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_09_cancellation_removes_waiter():
    """S5-09: Explicit waiter cancellation stops waiting and removes from queue."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    errs = []
    def waiter():
        try:
            mgr.acquire("github://repo", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
        except Exception as ex:
            errs.append(ex)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)

    assert mgr.get_waiter_count("github://repo", "tenant_A") == 1
    # Cancel waiter via internal key
    state = mgr.get_lock_state("github://repo", "tenant_A")
    # Cancel waiter
    key = ("tenant_A", "github://repo")
    waiter_obj = mgr._waiters[key][0]
    mgr.cancel_waiter("github://repo", "tenant_A", waiter_obj.waiter_id)

    t.join(timeout=1.0)
    assert len(errs) == 1
    assert "was cancelled" in str(errs[0])
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_10_cancellation_is_idempotent():
    """S5-10: Repeated cancellation of non-existent or cancelled waiter returns False cleanly."""
    mgr = InMemoryResourceLockManager()
    assert mgr.cancel_waiter("github://repo", "tenant_A", "invalid_id") is False


def test_p12_4_s5_11_release_wakes_eligible_waiter():
    """S5-11: Releasing lock instantly wakes eligible queued waiter."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("res://item", "tenant_A", "w1", "t1")

    w2_lock = []
    t = threading.Thread(target=lambda: w2_lock.append(mgr.acquire("res://item", "tenant_A", "w2", "t2", wait_timeout_seconds=2.0)))
    t.start()
    time.sleep(0.05)

    mgr.release("res://item", l1.lock_id, "tenant_A", "w1")
    t.join(timeout=1.0)
    assert len(w2_lock) == 1


def test_p12_4_s5_12_multiple_shared_waiters_admitted_correctly():
    """S5-12: When writer releases, all contiguous SHARED waiters at head are admitted together."""
    mgr = InMemoryResourceLockManager()
    w_lock = mgr.acquire("drive://doc", "tenant_A", "writer", "tw", LockMode.EXCLUSIVE)

    shared_granted = []
    def make_reader(r_id: str):
        def run():
            l = mgr.acquire("drive://doc", "tenant_A", r_id, f"t_{r_id}", LockMode.SHARED, wait_timeout_seconds=2.0)
            shared_granted.append(l)
        return run

    threads = [threading.Thread(target=make_reader(f"reader_{i}")) for i in range(5)]
    for t in threads:
        t.start()
    time.sleep(0.05)

    assert mgr.get_waiter_count("drive://doc", "tenant_A") == 5

    # Writer releases -> all 5 SHARED readers admitted
    mgr.release("drive://doc", w_lock.lock_id, "tenant_A", "writer")
    for t in threads:
        t.join(timeout=1.0)

    assert len(shared_granted) == 5
    active = mgr.get_active_locks("drive://doc", "tenant_A")
    assert len(active) == 5


def test_p12_4_s5_13_exclusive_waiter_blocks_later_shared_request():
    """S5-13: EXCLUSIVE waiter ahead in queue blocks later incoming SHARED request."""
    mgr = InMemoryResourceLockManager()
    r1 = mgr.acquire("drive://doc", "tenant_A", "r1", "t1", LockMode.SHARED)

    # Queue an exclusive writer
    tw = threading.Thread(target=lambda: mgr.acquire("drive://doc", "tenant_A", "w1", "tw", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0))
    tw.start()
    time.sleep(0.05)

    # Immediate SHARED request blocked
    with pytest.raises(LockConflictError):
        mgr.acquire("drive://doc", "tenant_A", "r2", "t2", LockMode.SHARED)

    # Cleanup
    mgr.release("drive://doc", r1.lock_id, "tenant_A", "r1")
    tw.join(timeout=1.0)


def test_p12_4_s5_14_reentrant_owner_does_not_deadlock_itself():
    """S5-14: Owner re-acquiring existing lock never enters wait queue."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
    l2 = mgr.acquire("github://repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)

    assert l1.lock_id == l2.lock_id
    assert l2.reentrant_count == 1
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0


def test_p12_4_s5_15_stale_waiter_generation_rejected():
    """S5-15: Stale release with generation mismatch fails without affecting active waiters."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "t1")

    with pytest.raises(StaleLockConflictError):
        mgr.release("github://repo", l1.lock_id, "tenant_A", "w1", lock_generation=0)


def test_p12_4_s5_16_cross_tenant_waiter_isolation():
    """S5-16: Wait queues on identical resource names in Tenant B operate in total isolation from Tenant A."""
    mgr = InMemoryResourceLockManager()
    l_A = mgr.acquire("github://repo", "tenant_A", "w_A", "t_A", LockMode.EXCLUSIVE)

    # Tenant B can acquire same resource immediately without waiting on Tenant A!
    l_B = mgr.acquire("github://repo", "tenant_B", "w_B", "t_B", LockMode.EXCLUSIVE, wait_timeout_seconds=1.0)
    assert l_B.tenant_id == "tenant_B"
    assert mgr.get_waiter_count("github://repo", "tenant_A") == 0
    assert mgr.get_waiter_count("github://repo", "tenant_B") == 0


def test_p12_4_s5_17_concurrent_enqueue_dequeue_remains_consistent():
    """S5-17: Rapid concurrent acquire/release operations maintain zero state corruption."""
    mgr = InMemoryResourceLockManager()
    num_threads = 8

    def task(w_idx: int):
        for i in range(5):
            l = mgr.acquire("res://hot", "tenant_A", f"w_{w_idx}", f"t_{w_idx}_{i}", LockMode.EXCLUSIVE, wait_timeout_seconds=2.0)
            time.sleep(0.005)
            mgr.release("res://hot", l.lock_id, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        list(executor.map(task, range(num_threads)))

    assert mgr.get_waiter_count("res://hot", "tenant_A") == 0
    assert mgr.is_resource_locked("res://hot", "tenant_A") is False


def test_p12_4_s5_18_no_waiter_leak_after_stress_sequence():
    """S5-18: Verify zero leaked waiters after timeout storms."""
    mgr = InMemoryResourceLockManager()
    l = mgr.acquire("res://leaked", "tenant_A", "w_holder", "t_h")

    # 10 workers time out
    def failing_waiter(idx: int):
        try:
            mgr.acquire("res://leaked", "tenant_A", f"w_{idx}", f"t_{idx}", wait_timeout_seconds=0.02)
        except LockConflictError:
            pass

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(failing_waiter, range(10)))

    assert mgr.get_waiter_count("res://leaked", "tenant_A") == 0
    mgr.release("res://leaked", l.lock_id, "tenant_A", "w_holder")
    assert mgr.is_resource_locked("res://leaked", "tenant_A") is False
