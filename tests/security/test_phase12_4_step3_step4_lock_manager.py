"""Phase 12.4 Steps 3 & 4: Dedicated Unit, Concurrency & Shared/Exclusive Lock Tests.
Verifies InMemoryResourceLockManager Mutex Guarantees, Shared Read Concurrency,
Exclusive Write Isolation, Re-entrant Nesting, Stale Generation Defense, and Tenant Partitioning.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import pytest

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.locking import (
    LockConflictError,
    LockMode,
    LockNotFoundError,
    LockStatus,
    StaleLockConflictError,
    UnauthorizedLockError,
)
from app.core.leasing.resource_lock_manager import InMemoryResourceLockManager


# ═════════════════════════════════════════════════════════════════════════════
# 1. EXCLUSIVE & SHARED ACCESS ENGINE (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s3_01_first_exclusive_acquisition_succeeds():
    """S3/4-01: First EXCLUSIVE acquisition of a free resource succeeds."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire(
        resource_id="github://Mukil630/AURA-OS",
        tenant_id="tenant_mukil",
        worker_id="worker_1",
        task_id="task_1",
        mode=LockMode.EXCLUSIVE,
        lock_ttl_seconds=30,
    )
    assert lock.canonical_resource_id == "github://mukil630/aura-os"
    assert lock.mode == LockMode.EXCLUSIVE
    assert lock.lock_generation == 1
    assert lock.status == LockStatus.GRANTED


def test_p12_4_s3_02_second_exclusive_acquisition_conflicts():
    """S3/4-02: Second worker requesting EXCLUSIVE on an actively held resource raises 409."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://Mukil630/AURA-OS", "tenant_mukil", "worker_1", "task_1", LockMode.EXCLUSIVE)

    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("github://mukil630/aura-os/", "tenant_mukil", "worker_2", "task_2", LockMode.EXCLUSIVE)
    assert exc_info.value.status_code == 409
    assert "locked exclusively" in exc_info.value.detail


def test_p12_4_s3_03_shared_plus_shared_succeeds():
    """S3/4-03: Multiple read workers can concurrently hold SHARED locks on same resource."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("drive://vault/1iahz", "tenant_A", "reader_1", "task_1", LockMode.SHARED)
    l2 = mgr.acquire("drive://vault/1iahz", "tenant_A", "reader_2", "task_2", LockMode.SHARED)

    assert l1.mode == LockMode.SHARED
    assert l2.mode == LockMode.SHARED
    active = mgr.get_active_locks("drive://vault/1iahz", "tenant_A")
    assert len(active) == 2


def test_p12_4_s3_04_shared_plus_exclusive_conflicts():
    """S3/4-04: Writer requesting EXCLUSIVE lock is blocked when SHARED readers are active (409)."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("drive://vault/1iahz", "tenant_A", "reader_1", "task_1", LockMode.SHARED)

    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("drive://vault/1iahz", "tenant_A", "writer_1", "task_2", LockMode.EXCLUSIVE)
    assert exc_info.value.status_code == 409
    assert "active SHARED readers exist" in exc_info.value.detail


def test_p12_4_s3_05_exclusive_plus_shared_conflicts():
    """S3/4-05: Reader requesting SHARED lock is blocked when an EXCLUSIVE writer is active (409)."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("drive://vault/1iahz", "tenant_A", "writer_1", "task_1", LockMode.EXCLUSIVE)

    with pytest.raises(LockConflictError) as exc_info:
        mgr.acquire("drive://vault/1iahz", "tenant_A", "reader_1", "task_2", LockMode.SHARED)
    assert exc_info.value.status_code == 409
    assert "locked exclusively" in exc_info.value.detail


# ═════════════════════════════════════════════════════════════════════════════
# 2. OWNERSHIP, RELEASES & GENERATION SAFETY (Tests 6 - 9)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s3_06_correct_owner_can_release():
    """S3/4-06: Registered lock owner can voluntarily release the lock."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire("github://repo", "tenant_A", "worker_1", "task_1")
    released = mgr.release("github://repo", lock.lock_id, "tenant_A", "worker_1")

    assert released.status == LockStatus.RELEASED
    assert mgr.is_resource_locked("github://repo", "tenant_A") is False


def test_p12_4_s3_07_wrong_worker_cannot_release():
    """S3/4-07: Worker B cannot release Worker A's resource lock (403)."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire("github://repo", "tenant_A", "worker_1", "task_1")

    with pytest.raises(UnauthorizedLockError) as exc_info:
        mgr.release("github://repo", lock.lock_id, "tenant_A", "worker_impostor")
    assert exc_info.value.status_code == 403


def test_p12_4_s3_08_wrong_tenant_cannot_release():
    """S3/4-08: Cross-tenant release is rejected with LockNotFoundError (404)."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire("github://repo", "tenant_A", "worker_1", "task_1")

    with pytest.raises(LockNotFoundError) as exc_info:
        mgr.release("github://repo", lock.lock_id, "tenant_B", "worker_1")
    assert exc_info.value.status_code == 404


def test_p12_4_s3_09_stale_generation_cannot_release_newer_generation():
    """
    S3/4-09: STALE GENERATION DEFENSE
    Worker Alpha's lock (gen=1) expires -> Worker Beta acquires (gen=2).
    Worker Alpha's late release with gen=1 is REJECTED with StaleLockConflictError (409).
    """
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w_alpha", "t1", lock_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.granted_at = past
    l1.expires_at = past + timedelta(seconds=2)

    # Worker Beta acquires next generation
    l2 = mgr.acquire("github://repo", "tenant_A", "w_beta", "t2", lock_ttl_seconds=30)
    assert l2.lock_generation == 2

    # Worker Alpha attempts late release specifying gen=1
    with pytest.raises(StaleLockConflictError) as exc_info:
        mgr.release("github://repo", l1.lock_id, "tenant_A", "w_alpha", lock_generation=1)
    assert exc_info.value.status_code == 409
    assert "superseded by current generation 2" in exc_info.value.detail


# ═════════════════════════════════════════════════════════════════════════════
# 3. RE-ENTRANT NESTING & MONOTONIC GENERATIONS (Tests 10 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s3_10_reentrant_acquisition_increments_count():
    """S3/4-10: Same worker and task acquiring existing lock increments reentrant_count."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("github://repo", "tenant_A", "w1", "task_1", LockMode.EXCLUSIVE)
    assert l1.reentrant_count == 0

    l2 = mgr.acquire("github://repo", "tenant_A", "w1", "task_1", LockMode.EXCLUSIVE)
    assert l2.lock_id == l1.lock_id
    assert l2.reentrant_count == 1


def test_p12_4_s3_11_reentrant_release_decrements_correctly():
    """S3/4-11: Re-entrant release decrements count until zero before final release."""
    mgr = InMemoryResourceLockManager()
    lock = mgr.acquire("github://repo", "tenant_A", "w1", "task_1", LockMode.EXCLUSIVE)
    mgr.acquire("github://repo", "tenant_A", "w1", "task_1", LockMode.EXCLUSIVE)
    assert lock.reentrant_count == 1

    # First release -> decrements to 0, still locked
    r1 = mgr.release("github://repo", lock.lock_id, "tenant_A", "w1")
    assert r1.reentrant_count == 0
    assert mgr.is_resource_locked("github://repo", "tenant_A") is True

    # Second release -> full release
    r2 = mgr.release("github://repo", lock.lock_id, "tenant_A", "w1")
    assert r2.status == LockStatus.RELEASED
    assert mgr.is_resource_locked("github://repo", "tenant_A") is False


def test_p12_4_s3_12_resource_canonicalization_enforced():
    """S3/4-12: Differently cased / formatted resource strings resolve to same lock."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://Mukil630/AURA-OS/", "tenant_A", "w1", "t1")

    # Lowercase without slash should detect existing lock
    with pytest.raises(LockConflictError):
        mgr.acquire("github://mukil630/aura-os", "tenant_A", "w2", "t2")


def test_p12_4_s3_13_lock_generation_remains_monotonic():
    """S3/4-13: Sequential lock acquire-release cycles advance generation monotonically."""
    mgr = InMemoryResourceLockManager()
    l1 = mgr.acquire("res://db", "tenant_A", "w1", "t1")
    mgr.release("res://db", l1.lock_id, "tenant_A", "w1")

    l2 = mgr.acquire("res://db", "tenant_A", "w2", "t2")
    mgr.release("res://db", l2.lock_id, "tenant_A", "w2")

    l3 = mgr.acquire("res://db", "tenant_A", "w3", "t3")
    assert l3.lock_generation == 3
    assert mgr.get_generation("res://db", "tenant_A") == 3


# ═════════════════════════════════════════════════════════════════════════════
# 4. CONCURRENCY & ZERO SECRET SECURITY (Tests 14 - 18)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s3_14_different_resources_do_not_interfere():
    """S3/4-14: Independent resources can be acquired concurrently without conflict."""
    mgr = InMemoryResourceLockManager()
    l_gh = mgr.acquire("github://repo_a", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)
    l_dr = mgr.acquire("drive://vault_b", "tenant_A", "w2", "t2", LockMode.EXCLUSIVE)

    assert l_gh.canonical_resource_id == "github://repo_a"
    assert l_dr.canonical_resource_id == "drive://vault_b"


def test_p12_4_s3_15_concurrent_exclusive_acquisition_produces_one_winner():
    """
    S3/4-15: HARD CONCURRENCY PROOF
    10 workers race simultaneously across threading.Barrier to acquire EXCLUSIVE lock.
    Asserts: Exactly 1 winner, exactly 9 conflicts (409).
    """
    mgr = InMemoryResourceLockManager()
    num_workers = 10
    barrier = threading.Barrier(num_workers)
    winners, errors = [], []

    def worker_acquire(w_id: int):
        barrier.wait()
        try:
            l = mgr.acquire("github://hot_repo", "tenant_A", f"w_{w_id}", f"t_{w_id}", LockMode.EXCLUSIVE)
            winners.append((w_id, l))
        except LockConflictError as ex:
            errors.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(worker_acquire, range(num_workers)))

    assert len(winners) == 1
    assert len(errors) == num_workers - 1


def test_p12_4_s3_16_concurrent_shared_acquisition_allows_all_valid_readers():
    """
    S3/4-16: 10 workers race simultaneously to acquire SHARED locks.
    Asserts: All 10 workers succeed concurrently with zero conflicts.
    """
    mgr = InMemoryResourceLockManager()
    num_readers = 10
    barrier = threading.Barrier(num_readers)

    def reader_acquire(r_id: int):
        barrier.wait()
        return mgr.acquire("drive://shared_doc", "tenant_A", f"reader_{r_id}", f"task_{r_id}", LockMode.SHARED)

    with ThreadPoolExecutor(max_workers=num_readers) as executor:
        results = list(executor.map(reader_acquire, range(num_readers)))

    assert len(results) == num_readers
    active = mgr.get_active_locks("drive://shared_doc", "tenant_A")
    assert len(active) == num_readers


def test_p12_4_s3_17_get_lock_state_inspection_snapshot():
    """S3/4-17: get_lock_state() provides structured snapshot of active holders."""
    mgr = InMemoryResourceLockManager()
    mgr.acquire("github://inspect_repo", "tenant_A", "w1", "t1", LockMode.EXCLUSIVE)

    state = mgr.get_lock_state("github://inspect_repo", "tenant_A")
    assert state is not None
    assert state["canonical_resource_id"] == "github://inspect_repo"
    assert state["mode"] == LockMode.EXCLUSIVE
    assert len(state["active_holders"]) == 1
    assert state["active_holders"][0]["worker_id"] == "w1"


def test_p12_4_s3_18_no_secret_material_stored_in_lock_state():
    """S3/4-18: Raw secret rejection in resource ID prevents token pollution."""
    mgr = InMemoryResourceLockManager()
    with pytest.raises(RawSecretPayloadError):
        mgr.acquire("github://token/ghp_LEAKED_SECRET_999", "tenant_A", "w1", "t1")
