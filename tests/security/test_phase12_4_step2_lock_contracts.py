"""Phase 12.4 Step 2: Dedicated Data Contracts & Canonical URN Normalizer Test Suite.
Verifies ResourceLockContract Invariants, Canonical URN Sanitization, Deadlock-Free
Lexicographical Sorting in Multi-Resource Batches, and Exception Hierarchy.
"""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.locking import (
    LockConflictError,
    LockExpiredError,
    LockMode,
    LockNotFoundError,
    LockStatus,
    MultiResourceLockBatchRequest,
    ResourceBatchItem,
    ResourceLockContract,
    StaleLockConflictError,
    UnauthorizedLockError,
    canonicalize_resource_id,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. CANONICAL RESOURCE URN NORMALIZER (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s2_01_canonicalize_github_repo_urn():
    """S2-01: GitHub repository URNs are normalized to lowercase without trailing slashes."""
    urn = canonicalize_resource_id("github://Mukil630/AURA-OS/")
    assert urn == "github://mukil630/aura-os"


def test_p12_4_s2_02_canonicalize_drive_vault_urn():
    """S2-02: Drive folder URNs are normalized with single slash separators."""
    urn = canonicalize_resource_id("DRIVE://Vault//1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ/")
    assert urn == "drive://vault/1iahzdzc7kijk2flmds7enw7vkyxdeaxz"


def test_p12_4_s2_03_canonicalize_bare_path_prefixes_resource_scheme():
    """S2-03: Bare resource names are automatically prefixed with resource://."""
    urn = canonicalize_resource_id("api_quota:telegram_bot")
    assert urn == "resource://api_quota:telegram_bot"


def test_p12_4_s2_04_canonicalize_rejects_raw_token_in_urn():
    """S2-04: Raw secrets in resource URNs are rejected with RawSecretPayloadError (422)."""
    with pytest.raises(RawSecretPayloadError):
        canonicalize_resource_id("github://Mukil/token/ghp_SECRET_TOKEN_12345")


def test_p12_4_s2_05_canonicalize_rejects_empty_or_whitespace():
    """S2-05: Empty or whitespace resource strings are rejected with ValueError."""
    with pytest.raises(ValueError):
        canonicalize_resource_id("")
    with pytest.raises(ValueError):
        canonicalize_resource_id("   ")


# ═════════════════════════════════════════════════════════════════════════════
# 2. RESOURCE LOCK CONTRACT INVARIANTS (Tests 6 - 11)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s2_06_valid_exclusive_lock_contract():
    """S2-06: Create valid ResourceLockContract in EXCLUSIVE mode."""
    now = datetime.now(timezone.utc)
    lock = ResourceLockContract(
        lock_id="lock_001",
        canonical_resource_id="github://mukil630/aura-os",
        tenant_id="tenant_mukil",
        worker_id="worker_alpha",
        task_id="task_101",
        mode=LockMode.EXCLUSIVE,
        lock_generation=1,
        granted_at=now,
        expires_at=now + timedelta(seconds=30),
        lock_ttl_seconds=30,
    )
    assert lock.lock_id == "lock_001"
    assert lock.mode == LockMode.EXCLUSIVE
    assert lock.lock_generation == 1
    assert lock.status == LockStatus.GRANTED


def test_p12_4_s2_07_valid_shared_lock_contract():
    """S2-07: Create valid ResourceLockContract in SHARED mode."""
    now = datetime.now(timezone.utc)
    lock = ResourceLockContract(
        lock_id="lock_002",
        canonical_resource_id="drive://vault/1iahz",
        tenant_id="tenant_mukil",
        worker_id="worker_reader_1",
        task_id="task_102",
        mode=LockMode.SHARED,
        granted_at=now,
        expires_at=now + timedelta(seconds=15),
    )
    assert lock.mode == LockMode.SHARED
    assert lock.reentrant_count == 0


def test_p12_4_s2_08_temporal_invariant_violation_rejected():
    """S2-08: expires_at <= granted_at is rejected by model validator."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ResourceLockContract(
            lock_id="lock_inv",
            canonical_resource_id="github://repo",
            tenant_id="t1",
            worker_id="w1",
            task_id="t1",
            granted_at=now,
            expires_at=now - timedelta(seconds=5),  # in past
        )


def test_p12_4_s2_09_invalid_generation_or_ttl_rejected():
    """S2-09: lock_generation < 1 or lock_ttl_seconds <= 0 rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ResourceLockContract(
            lock_id="l", canonical_resource_id="r", tenant_id="t", worker_id="w", task_id="t",
            lock_generation=0, expires_at=now + timedelta(seconds=10),
        )
    with pytest.raises(ValidationError):
        ResourceLockContract(
            lock_id="l", canonical_resource_id="r", tenant_id="t", worker_id="w", task_id="t",
            lock_ttl_seconds=0, expires_at=now + timedelta(seconds=10),
        )


def test_p12_4_s2_10_missing_mandatory_identities_rejected():
    """S2-10: Empty tenant_id, worker_id, task_id, or lock_id rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ResourceLockContract(
            lock_id="", canonical_resource_id="r", tenant_id="t", worker_id="w", task_id="t",
            expires_at=now + timedelta(seconds=10),
        )


def test_p12_4_s2_11_metadata_with_raw_secret_rejected():
    """S2-11: Raw secret key or token in lock metadata rejected (422)."""
    now = datetime.now(timezone.utc)
    with pytest.raises(RawSecretPayloadError):
        ResourceLockContract(
            lock_id="lock_sec",
            canonical_resource_id="github://repo",
            tenant_id="t1",
            worker_id="w1",
            task_id="t1",
            expires_at=now + timedelta(seconds=10),
            metadata={"auth_token": "ghp_LEAKED_SECRET_123"},
        )


# ═════════════════════════════════════════════════════════════════════════════
# 3. MULTI-RESOURCE BATCH ORDERING & DEADLOCK AVOIDANCE (Tests 12 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s2_12_multi_resource_batch_lexicographical_sorting():
    """
    S2-12: MultiResourceLockBatchRequest returns items sorted in deterministic
    lexicographical order to eliminate circular-wait deadlocks.
    """
    req = MultiResourceLockBatchRequest(
        request_id="req_batch_01",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://zeta/repo", mode=LockMode.EXCLUSIVE),
            ResourceBatchItem(resource_id="drive://alpha/vault", mode=LockMode.SHARED),
            ResourceBatchItem(resource_id="github://beta/repo", mode=LockMode.EXCLUSIVE),
        ],
    )

    ordered = req.get_canonical_ordered_items()
    # Lexicographical sort order: drive://alpha/vault < github://beta/repo < github://zeta/repo
    assert ordered[0] == ("drive://alpha/vault", LockMode.SHARED)
    assert ordered[1] == ("github://beta/repo", LockMode.EXCLUSIVE)
    assert ordered[2] == ("github://zeta/repo", LockMode.EXCLUSIVE)


def test_p12_4_s2_13_multi_resource_batch_deduplication_precedence():
    """
    S2-13: Deduplicates repeated resource requests, granting EXCLUSIVE precedence over SHARED.
    """
    req = MultiResourceLockBatchRequest(
        request_id="req_batch_02",
        tenant_id="tenant_A",
        worker_id="worker_1",
        task_id="task_1",
        items=[
            ResourceBatchItem(resource_id="github://Mukil/Repo", mode=LockMode.SHARED),
            ResourceBatchItem(resource_id="github://mukil/repo/", mode=LockMode.EXCLUSIVE),
        ],
    )

    ordered = req.get_canonical_ordered_items()
    assert len(ordered) == 1
    assert ordered[0] == ("github://mukil/repo", LockMode.EXCLUSIVE)


# ═════════════════════════════════════════════════════════════════════════════
# 4. EXCEPTION HIERARCHY STATUS CODES (Tests 14 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_4_s2_14_exception_hierarchy_status_codes():
    """S2-14: Lock exception hierarchy preserves deterministic HTTP status codes."""
    assert LockConflictError("conflict").status_code == 409
    assert StaleLockConflictError("stale").status_code == 409
    assert LockNotFoundError("not found").status_code == 404
    assert LockExpiredError("expired").status_code == 410
    assert UnauthorizedLockError("unauthorized").status_code == 403


def test_p12_4_s2_15_reentrant_count_starts_at_zero():
    """S2-15: Default reentrant_count is 0 on initial lock contract creation."""
    now = datetime.now(timezone.utc)
    lock = ResourceLockContract(
        lock_id="l_reent",
        canonical_resource_id="res://db",
        tenant_id="t1",
        worker_id="w1",
        task_id="t1",
        expires_at=now + timedelta(seconds=10),
    )
    assert lock.reentrant_count == 0
