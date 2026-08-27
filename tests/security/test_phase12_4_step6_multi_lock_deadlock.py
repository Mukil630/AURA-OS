"""Phase 12.4 Step 6: Dedicated Deadlock Prevention & Multi-Lock Batch Test Suite.
Verifies Lexicographical Canonical Ordering, All-or-Nothing Transactional Rollback,
Circular-Wait Elimination (Two-Worker and Three-Worker Cyclic Dependency Attacks),
Deduplication Precedence, and Zero Lock Leakage.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import time
import pytest

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


def test_p12_4_s6_01_single_resource_batch():
    """S6-01: Batch with 1 resource acquires successfully."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req_01",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[ResourceBatchItem(resource_id="github://repo", mode=LockMode.EXCLUSIVE)],
    )
    locks = mgr.acquire_batch(req)
    assert len(locks) == 1
    assert locks[0].canonical_resource_id == "github://repo"
    assert mgr.is_resource_locked("github://repo", "tenant_A") is True


def test_p12_4_s6_02_multi_resource_batch():
    """S6-02: Batch with 3 distinct resources acquires all 3 atomically."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req_02",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://repo_a", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="drive://vault_b", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="resource://api_quota", mode=LockMode.SHARED),
        ],
    )
    locks = mgr.acquire_batch(req)
    assert len(locks) == 3
    assert mgr.is_resource_locked("github://repo_a", "tenant_A") is True
    assert mgr.is_resource_locked("drive://vault_b", "tenant_A") is True
    assert mgr.is_resource_locked("resource://api_quota", "tenant_A") is True


def test_p12_4_s6_03_canonical_lexicographical_ordering():
    """S6-03: Multi-resource batch executes in strict lexicographical order."""
    req = MultiResourceLockBatchRequest(
        request_id="req_03",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://zeta", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="drive://alpha", mode=LockMode.SHARED),
            ResourceBatchItem(resource_id="github://beta", mode=LockMode.EXCLUSIVE),
        ],
    )
    ordered = req.get_canonical_ordered_items()
    assert ordered[0][0] == "drive://alpha"
    assert ordered[1][0] == "github://beta"
    assert ordered[2][0] == "github://zeta"


def test_p12_4_s6_04_duplicate_resource_deduplication():
    """S6-04: Repeated requests for same resource inside batch are deduplicated."""
    req = MultiResourceLockBatchRequest(
        request_id="req_04",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://repo", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="github://repo/", mode=LockMode.EXCLUSIVE),
        ],
    )
    ordered = req.get_canonical_ordered_items()
    assert len(ordered) == 1


def test_p12_4_s6_05_exclusive_precedence():
    """S6-05: Duplicate resource with SHARED + EXCLUSIVE resolves to EXCLUSIVE."""
    req = MultiResourceLockBatchRequest(
        request_id="req_05",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://repo", mode=LockMode.SHARED),
            ResourceBatchItem(resource_id="github://repo", mode=LockMode.EXCLUSIVE),
        ],
    )
    ordered = req.get_canonical_ordered_items()
    assert ordered[0][1] == LockMode.EXCLUSIVE


def test_p12_4_s6_06_successful_atomic_batch_acquisition():
    """S6-06: Batch acquisition and release cycle cleanly updates state."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req_06",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="res://a", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="res://b", mode=LockMode.EXCLUSIVE),
        ],
    )
    locks = mgr.acquire_batch(req)
    assert len(locks) == 2

    mgr.release_batch(locks, "tenant_A", "worker_1")
    assert mgr.is_resource_locked("res://a", "tenant_A") is False
    assert mgr.is_resource_locked("res://b", "tenant_A") is False


def test_p12_4_s6_07_partial_acquisition_rollback():
    """
    S6-07: TRANSACTIONAL ALL-OR-NOTHING ROLLBACK
    res://a is free, but res://b is locked by worker_2.
    worker_1 attempts batch [res://a, res://b] with 0 timeout.
    Asserts: Batch fails, and res://a is IMMEDIATELY ROLLED BACK (not leaked!).
    """
    mgr = InMemoryResourceLockManager()
    l_b = mgr.acquire("res://b", "tenant_A", "worker_2", "task_2", LockMode.EXCLUSIVE)

    req = MultiResourceLockBatchRequest(
        request_id="req_07",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="res://a", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="res://b", mode=LockMode.EXCLUSIVE),
        ],
        acquire_timeout_seconds=0.05,
    )

    with pytest.raises(LockConflictError):
        mgr.acquire_batch(req)

    # Rollback verification: res://a MUST be completely free!
    assert mgr.is_resource_locked("res://a", "tenant_A") is False
    # res://b is still held by worker_2
    assert mgr.is_resource_locked("res://b", "tenant_A") is True


def test_p12_4_s6_08_batch_timeout():
    """S6-08: Batch respects total acquire_timeout_seconds."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("res://held", "tenant_A", "w_other", "t_o")

    req = MultiResourceLockBatchRequest(
        request_id="req_08",
        tenant_id="tenant_A",
        worker_id="w1",
        task_id="t1",
        items=[
            ResourceBatchItem(resource_id="res://free", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="res://held", mode=LockMode.EXCLUSIVE),
        ],
        acquire_timeout_seconds=0.1,
    )

    start = time.time()
    with pytest.raises(LockConflictError):
        mgr.acquire_batch(req)
    duration = time.time() - start

    assert 0.08 <= duration <= 0.4
    assert mgr.is_resource_locked("res://free", "tenant_A") is False


def test_p12_4_s6_09_opposite_order_deadlock_scenario():
    """
    S6-09: OPPOSITE-ORDER DEADLOCK DEFENSE
    Worker 1 requests [res://A, res://B]
    Worker 2 requests [res://B, res://A]
    Canonical sorting forces both to acquire res://A first -> NO DEADLOCK!
    """
    mgr = InMemoryResourceLockManager()
    barrier = threading.Barrier(2)
    results = []

    def worker_1():
        req = MultiResourceLockBatchRequest(
            request_id="req_w1",
            tenant_id="tenant_A",
            worker_id="w1",
            task_id="t1",
            items=[
                ResourceBatchItem(resource_id="res://a", mode=LockMode.EXCLUSIVE),
                ResourceBatchItem(resource_id="res://b", mode=LockMode.EXCLUSIVE),
            ],
            acquire_timeout_seconds=2.0,
        )
        barrier.wait()
        try:
            locks = mgr.acquire_batch(req)
            results.append(("w1", locks))
            time.sleep(0.05)
            mgr.release_batch(locks, "tenant_A", "w1")
        except Exception as ex:
            results.append(("w1_err", ex))

    def worker_2():
        # Passed in reverse order: [B, A]
        req = MultiResourceLockBatchRequest(
            request_id="req_w2",
            tenant_id="tenant_A",
            worker_id="w2",
            task_id="t2",
            items=[
                ResourceBatchItem(resource_id="res://b", mode=LockMode.EXCLUSIVE),
                ResourceBatchItem(resource_id="res://a", mode=LockMode.EXCLUSIVE),
            ],
            acquire_timeout_seconds=2.0,
        )
        barrier.wait()
        try:
            locks = mgr.acquire_batch(req)
            results.append(("w2", locks))
            time.sleep(0.05)
            mgr.release_batch(locks, "tenant_A", "w2")
        except Exception as ex:
            results.append(("w2_err", ex))

    t1 = threading.Thread(target=worker_1)
    t2 = threading.Thread(target=worker_2)
    t1.start(); t2.start()
    t1.join(timeout=3.0); t2.join(timeout=3.0)

    # Both must complete cleanly (one acquires first, then other acquires after release)
    successes = [r[0] for r in results if r[0] in ("w1", "w2")]
    assert len(successes) == 2
    assert mgr.is_resource_locked("res://a", "tenant_A") is False
    assert mgr.is_resource_locked("res://b", "tenant_A") is False


def test_p12_4_s6_10_canonical_ordering_prevents_deadlock():
    """S6-10: 10 parallel threads with random resource permutations acquire without deadlocks."""
    mgr = InMemoryResourceLockManager()
    num_threads = 10

    def task(w_idx: int):
        # Permute resource ordering based on even/odd
        items = (
            [ResourceBatchItem(resource_id="res://x", mode=LockMode.EXCLUSIVE), ResourceBatchItem(resource_id="res://y", mode=LockMode.EXCLUSIVE)]
            if w_idx % 2 == 0
            else [ResourceBatchItem(resource_id="res://y", mode=LockMode.EXCLUSIVE), ResourceBatchItem(resource_id="res://x", mode=LockMode.EXCLUSIVE)]
        )
        req = MultiResourceLockBatchRequest(
            request_id=f"req_{w_idx}",
            tenant_id="tenant_A",
            worker_id=f"w_{w_idx}",
            task_id=f"t_{w_idx}",
            items=items,
            acquire_timeout_seconds=3.0,
        )
        locks = mgr.acquire_batch(req)
        time.sleep(0.01)
        mgr.release_batch(locks, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        list(executor.map(task, range(num_threads)))

    assert mgr.is_resource_locked("res://x", "tenant_A") is False
    assert mgr.is_resource_locked("res://y", "tenant_A") is False


def test_p12_4_s6_11_concurrent_multi_lock_acquisition():
    """S6-11: Concurrent batches across independent resource sets succeed simultaneously."""
    mgr = InMemoryResourceLockManager()
    req1 = MultiResourceLockBatchRequest(
        request_id="req1", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://1"), ResourceBatchItem(resource_id="res://2")],
    )
    req2 = MultiResourceLockBatchRequest(
        request_id="req2", tenant_id="tenant_A", worker_id="w2", task_id="t2",
        items=[ResourceBatchItem(resource_id="res://3"), ResourceBatchItem(resource_id="res://4")],
    )

    l1 = mgr.acquire_batch(req1)
    l2 = mgr.acquire_batch(req2)
    assert len(l1) == 2 and len(l2) == 2


def test_p12_4_s6_12_concurrent_batch_conflict():
    """S6-12: Overlapping batches conflict and wait cleanly."""
    mgr = InMemoryResourceLockManager()
    req1 = MultiResourceLockBatchRequest(
        request_id="req1", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://a"), ResourceBatchItem(resource_id="res://b")],
    )
    l1 = mgr.acquire_batch(req1)

    req2 = MultiResourceLockBatchRequest(
        request_id="req2", tenant_id="tenant_A", worker_id="w2", task_id="t2",
        items=[ResourceBatchItem(resource_id="res://b"), ResourceBatchItem(resource_id="res://c")],
        acquire_timeout_seconds=0.05,
    )
    with pytest.raises(LockConflictError):
        mgr.acquire_batch(req2)

    # res://c must not be leaked
    assert mgr.is_resource_locked("res://c", "tenant_A") is False


def test_p12_4_s6_13_stale_generation_batch_release_rejected():
    """S6-13: Releasing batch with a stale lock generation raises 409."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req13", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://a")],
    )
    locks = mgr.acquire_batch(req)
    # Advance manager's generation epoch for res://a to 5
    mgr._lock_generations[("tenant_A", "res://a")] = 5

    with pytest.raises(StaleLockConflictError):
        mgr.release_batch(locks, "tenant_A", "w1")


def test_p12_4_s6_14_cross_tenant_batch_rejected():
    """S6-14: Batch release under wrong tenant is rejected (404)."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req14", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://a")],
    )
    locks = mgr.acquire_batch(req)
    with pytest.raises(LockNotFoundError):
        mgr.release_batch(locks, "tenant_B", "w1")


def test_p12_4_s6_15_reentrant_multi_lock_acquisition():
    """S6-15: Same worker re-acquiring same batch succeeds re-entrantly."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req15", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://a"), ResourceBatchItem(resource_id="res://b")],
    )
    l1 = mgr.acquire_batch(req)
    l2 = mgr.acquire_batch(req)

    assert l2[0].reentrant_count == 1
    assert l2[1].reentrant_count == 1


def test_p12_4_s6_16_reentrant_batch_release():
    """S6-16: Re-entrant batch release requires 2 releases to completely unlock."""
    mgr = InMemoryResourceLockManager()
    req = MultiResourceLockBatchRequest(
        request_id="req16", tenant_id="tenant_A", worker_id="w1", task_id="t1",
        items=[ResourceBatchItem(resource_id="res://a")],
    )
    l1 = mgr.acquire_batch(req)
    mgr.acquire_batch(req)

    # First release -> decrements reentrant_count
    mgr.release_batch(l1, "tenant_A", "w1")
    assert mgr.is_resource_locked("res://a", "tenant_A") is True

    # Second release -> full release
    mgr.release_batch(l1, "tenant_A", "w1")
    assert mgr.is_resource_locked("res://a", "tenant_A") is False


def test_p12_4_s6_17_no_leaked_locks_after_failed_batch():
    """S6-17: Multiple failed batches in succession leave zero leaked locks or waiters."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("res://blocker", "tenant_A", "wb", "tb")

    for i in range(5):
        req = MultiResourceLockBatchRequest(
            request_id=f"req_fail_{i}", tenant_id="tenant_A", worker_id=f"w_{i}", task_id=f"t_{i}",
            items=[ResourceBatchItem(resource_id=f"res://free_{i}"), ResourceBatchItem(resource_id="res://blocker")],
            acquire_timeout_seconds=0.02,
        )
        try:
            mgr.acquire_batch(req)
        except LockConflictError:
            pass

    for i in range(5):
        assert mgr.is_resource_locked(f"res://free_{i}", "tenant_A") is False


def test_p12_4_s6_18_repeated_batch_acquisition_release_cycles():
    """S6-18: 20 rapid sequential batch acquire-release cycles advance generations monotonically."""
    mgr = InMemoryResourceLockManager()
    for i in range(20):
        req = MultiResourceLockBatchRequest(
            request_id=f"req_rep_{i}", tenant_id="tenant_A", worker_id="w1", task_id="t1",
            items=[ResourceBatchItem(resource_id="res://cycle")],
        )
        locks = mgr.acquire_batch(req)
        assert locks[0].lock_generation == i + 1
        mgr.release_batch(locks, "tenant_A", "w1")

    assert mgr.get_generation("res://cycle", "tenant_A") == 20


def test_p12_4_s6_19_three_worker_cyclic_dependency_attempt():
    """
    S6-19: THREE-WORKER CYCLIC DEPENDENCY ATTACK
    W1: [res://A, res://B]
    W2: [res://B, res://C]
    W3: [res://C, res://A]
    All three sorted canonically -> NO CIRCULAR WAIT DEADLOCK!
    """
    mgr = InMemoryResourceLockManager()
    barrier = threading.Barrier(3)
    completed = []

    def make_worker(w_id: str, items: list):
        def run():
            req = MultiResourceLockBatchRequest(
                request_id=f"req_{w_id}", tenant_id="tenant_A", worker_id=w_id, task_id=f"t_{w_id}",
                items=items, acquire_timeout_seconds=3.0,
            )
            barrier.wait()
            locks = mgr.acquire_batch(req)
            completed.append(w_id)
            time.sleep(0.02)
            mgr.release_batch(locks, "tenant_A", w_id)
        return run

    t1 = threading.Thread(target=make_worker("w1", [ResourceBatchItem(resource_id="res://a"), ResourceBatchItem(resource_id="res://b")]))
    t2 = threading.Thread(target=make_worker("w2", [ResourceBatchItem(resource_id="res://b"), ResourceBatchItem(resource_id="res://c")]))
    t3 = threading.Thread(target=make_worker("w3", [ResourceBatchItem(resource_id="res://c"), ResourceBatchItem(resource_id="res://a")]))

    t1.start(); t2.start(); t3.start()
    t1.join(timeout=4.0); t2.join(timeout=4.0); t3.join(timeout=4.0)

    assert len(completed) == 3


def test_p12_4_s6_20_high_contention_multi_resource_scenario():
    """S6-20: 20 parallel threads contending for 5 shared resources complete cleanly."""
    mgr = InMemoryResourceLockManager()
    num_threads = 20

    def task(w_idx: int):
        r1 = f"res://{w_idx % 5}"
        r2 = f"res://{(w_idx + 1) % 5}"
        req = MultiResourceLockBatchRequest(
            request_id=f"req_hc_{w_idx}", tenant_id="tenant_A", worker_id=f"w_{w_idx}", task_id=f"t_{w_idx}",
            items=[ResourceBatchItem(resource_id=r1), ResourceBatchItem(resource_id=r2)],
            acquire_timeout_seconds=4.0,
        )
        locks = mgr.acquire_batch(req)
        time.sleep(0.005)
        mgr.release_batch(locks, "tenant_A", f"w_{w_idx}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        list(executor.map(task, range(num_threads)))

    for i in range(5):
        assert mgr.is_resource_locked(f"res://{i}", "tenant_A") is False
