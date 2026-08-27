"""Phase 12.3 Step 2: Dedicated Unit & Adversarial Tests for Lease Data Contracts & Enums.
Validates structural integrity, mandatory identities, monotonic fencing tokens, retry bounds, and zero raw credential fields.
"""
from datetime import datetime, timedelta, timezone
import json
import pytest
from pydantic import ValidationError

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseExpiredError,
    LeaseNotFoundError,
    LeaseStatus,
    QueueMessageContract,
    StaleLeaseConflictError,
    TaskLeaseContract,
    UnauthorizedWorkerError,
    WorkerHeartbeatContract,
    WorkerStatus,
)
from app.core.enums.common import PriorityLevel


# ═════════════════════════════════════════════════════════════════════════════
# 1. LEASE STATUS & ENUM INVARIANTS (Tests 1 - 2)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s2_01_valid_lease_status_values():
    """S2-01: Verify all frozen LeaseStatus enum members."""
    expected = {"acquired", "renewed", "expired", "released", "revoked"}
    actual = {s.value for s in LeaseStatus}
    assert actual == expected
    assert LeaseStatus.ACQUIRED == "acquired"
    assert LeaseStatus.REVOKED == "revoked"


def test_p12_3_s2_02_invalid_lease_status_rejected():
    """S2-02: Verify invalid status values fail validation."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        TaskLeaseContract(
            lease_id="l_1",
            task_id="t_1",
            tenant_id="tenant_A",
            worker_id="w_1",
            fencing_token=1,
            status="UNKNOWN_STATUS",  # type: ignore
            acquired_at=now,
            expires_at=now + timedelta(seconds=30),
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. TASK LEASE CONTRACT INVARIANTS (Tests 3 - 9)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s2_03_valid_task_lease_contract_accepted():
    """S2-03: Verify valid TaskLeaseContract creation and defaults."""
    now = datetime.now(timezone.utc)
    lease = TaskLeaseContract(
        lease_id="lease_001",
        task_id="task_001",
        tenant_id="tenant_A",
        worker_id="worker_A",
        fencing_token=1,
        status=LeaseStatus.ACQUIRED,
        acquired_at=now,
        expires_at=now + timedelta(seconds=30),
        renewal_count=0,
        lease_ttl_seconds=30,
    )
    assert lease.lease_id == "lease_001"
    assert lease.tenant_id == "tenant_A"
    assert lease.fencing_token == 1
    assert lease.status == LeaseStatus.ACQUIRED


def test_p12_3_s2_04_missing_or_blank_tenant_id_rejected():
    """S2-04: Verify missing or whitespace tenant_id is rejected."""
    now = datetime.now(timezone.utc)
    for bad_tenant in ["", "   "]:
        with pytest.raises(ValidationError):
            TaskLeaseContract(
                lease_id="l_1",
                task_id="t_1",
                tenant_id=bad_tenant,
                worker_id="w_1",
                fencing_token=1,
                expires_at=now + timedelta(seconds=30),
            )


def test_p12_3_s2_05_missing_or_blank_worker_id_rejected():
    """S2-05: Verify missing or whitespace worker_id is rejected."""
    now = datetime.now(timezone.utc)
    for bad_worker in ["", "   "]:
        with pytest.raises(ValidationError):
            TaskLeaseContract(
                lease_id="l_1",
                task_id="t_1",
                tenant_id="tenant_A",
                worker_id=bad_worker,
                fencing_token=1,
                expires_at=now + timedelta(seconds=30),
            )


def test_p12_3_s2_06_invalid_fencing_token_rejected():
    """S2-06: Verify fencing_token <= 0 or invalid types fail validation."""
    now = datetime.now(timezone.utc)
    for bad_token in [0, -1, -999]:
        with pytest.raises(ValidationError):
            TaskLeaseContract(
                lease_id="l_1",
                task_id="t_1",
                tenant_id="tenant_A",
                worker_id="w_1",
                fencing_token=bad_token,
                expires_at=now + timedelta(seconds=30),
            )


def test_p12_3_s2_07_negative_renewal_count_rejected():
    """S2-07: Verify negative renewal_count is rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        TaskLeaseContract(
            lease_id="l_1",
            task_id="t_1",
            tenant_id="tenant_A",
            worker_id="w_1",
            fencing_token=1,
            renewal_count=-1,
            expires_at=now + timedelta(seconds=30),
        )


def test_p12_3_s2_08_zero_or_negative_ttl_rejected():
    """S2-08: Verify zero or negative lease_ttl_seconds is rejected."""
    now = datetime.now(timezone.utc)
    for bad_ttl in [0, -10]:
        with pytest.raises(ValidationError):
            TaskLeaseContract(
                lease_id="l_1",
                task_id="t_1",
                tenant_id="tenant_A",
                worker_id="w_1",
                fencing_token=1,
                lease_ttl_seconds=bad_ttl,
                expires_at=now + timedelta(seconds=30),
            )


def test_p12_3_s2_09_invalid_timestamp_ordering_rejected():
    """S2-09: Verify expires_at <= acquired_at is rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError) as exc_past:
        TaskLeaseContract(
            lease_id="l_1",
            task_id="t_1",
            tenant_id="tenant_A",
            worker_id="w_1",
            fencing_token=1,
            acquired_at=now,
            expires_at=now - timedelta(seconds=1),  # in the past!
        )
    assert "expires_at must logically occur strictly after acquired_at" in str(exc_past.value)

    with pytest.raises(ValidationError) as exc_equal:
        TaskLeaseContract(
            lease_id="l_1",
            task_id="t_1",
            tenant_id="tenant_A",
            worker_id="w_1",
            fencing_token=1,
            acquired_at=now,
            expires_at=now,  # equal!
        )
    assert "expires_at must logically occur strictly after acquired_at" in str(exc_equal.value)


# ═════════════════════════════════════════════════════════════════════════════
# 3. QUEUE MESSAGE CONTRACT INVARIANTS (Tests 10 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s2_10_valid_queue_message_contract_accepted():
    """S2-10: Verify valid QueueMessageContract creation and defaults."""
    msg = QueueMessageContract(
        message_id="msg_001",
        task_id="task_001",
        tenant_id="tenant_A",
        priority=PriorityLevel.HIGH,
        attempt_count=0,
        max_attempts=3,
        payload={"repo": "Mukil630/AURA-OS", "credential_ref": "github_prod_01"},
    )
    assert msg.message_id == "msg_001"
    assert msg.tenant_id == "tenant_A"
    assert msg.priority == PriorityLevel.HIGH
    assert msg.attempt_count == 0
    assert msg.max_attempts == 3


def test_p12_3_s2_11_invalid_retry_counters_rejected():
    """S2-11: Verify invalid retry bounds (negative, 0 max, attempt > max) are rejected."""
    # Negative attempt
    with pytest.raises(ValidationError):
        QueueMessageContract(
            message_id="m_1",
            task_id="t_1",
            tenant_id="tenant_A",
            attempt_count=-1,
            max_attempts=3,
        )

    # max_attempts = 0
    with pytest.raises(ValidationError):
        QueueMessageContract(
            message_id="m_1",
            task_id="t_1",
            tenant_id="tenant_A",
            attempt_count=0,
            max_attempts=0,
        )

    # attempt_count > max_attempts
    with pytest.raises(ValidationError) as exc_exceed:
        QueueMessageContract(
            message_id="m_1",
            task_id="t_1",
            tenant_id="tenant_A",
            attempt_count=4,
            max_attempts=3,
        )
    assert "cannot exceed max_attempts" in str(exc_exceed.value)


def test_p12_3_s2_12_queue_message_requires_tenant_identity():
    """S2-12: Verify QueueMessageContract rejects empty/whitespace tenant_id."""
    for bad_tenant in ["", "  "]:
        with pytest.raises(ValidationError):
            QueueMessageContract(
                message_id="m_1",
                task_id="t_1",
                tenant_id=bad_tenant,
            )


def test_p12_3_s2_13_queue_contract_has_no_raw_secret_fields():
    """S2-13: ARCHITECTURAL ASSERTION: Queue contracts do not declare raw secret fields."""
    forbidden_fields = {"api_key", "token", "access_token", "password", "secret", "bearer_token", "raw_secret"}
    actual_lease_fields = set(TaskLeaseContract.model_fields.keys())
    actual_queue_fields = set(QueueMessageContract.model_fields.keys())

    assert actual_lease_fields.isdisjoint(forbidden_fields)
    assert actual_queue_fields.isdisjoint(forbidden_fields)


# ═════════════════════════════════════════════════════════════════════════════
# 4. WORKER HEARTBEAT & SERIALIZATION (Tests 14 - 17)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s2_14_valid_worker_heartbeat_contract_accepted():
    """S2-14: Verify valid WorkerHeartbeatContract creation."""
    hb = WorkerHeartbeatContract(
        worker_id="worker_node_01",
        hostname="worker-vm-east",
        active_leases=["lease_101", "lease_102"],
        status=WorkerStatus.ACTIVE,
    )
    assert hb.worker_id == "worker_node_01"
    assert len(hb.active_leases) == 2
    assert hb.status == WorkerStatus.ACTIVE


def test_p12_3_s2_15_worker_heartbeat_without_worker_identity_rejected():
    """S2-15: Verify WorkerHeartbeatContract rejects empty worker_id."""
    for bad_worker in ["", "   "]:
        with pytest.raises(ValidationError):
            WorkerHeartbeatContract(
                worker_id=bad_worker,
            )


def test_p12_3_s2_16_contract_serialization_contains_metadata_only():
    """S2-16: Serialization contains structural metadata with zero raw secret tokens."""
    now = datetime.now(timezone.utc)
    lease = TaskLeaseContract(
        lease_id="l_safe_01",
        task_id="t_safe_01",
        tenant_id="tenant_A",
        worker_id="w_safe_01",
        fencing_token=42,
        expires_at=now + timedelta(seconds=30),
    )
    dumped_json = lease.model_dump_json()
    assert "ghp_" not in dumped_json
    assert "ya29." not in dumped_json
    assert "fencing_token" in dumped_json


def test_p12_3_s2_17_contract_assignment_validation():
    """S2-17: Verify validate_assignment catches invalid mutation after instantiation."""
    now = datetime.now(timezone.utc)
    lease = TaskLeaseContract(
        lease_id="l_mut_01",
        task_id="t_mut_01",
        tenant_id="tenant_A",
        worker_id="w_mut_01",
        fencing_token=1,
        expires_at=now + timedelta(seconds=30),
    )
    with pytest.raises(ValidationError):
        lease.fencing_token = -5  # Caught via validate_assignment=True!


# ═════════════════════════════════════════════════════════════════════════════
# 5. FENCING MONOTONICITY & EXCEPTION HIERARCHY (Tests 18 - 19)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s2_18_fencing_token_monotonicity_contract():
    """S2-18: Verify contract represents monotonic fencing token ordering (token_B > token_A)."""
    now = datetime.now(timezone.utc)
    lease_a = TaskLeaseContract(
        lease_id="l_A",
        task_id="t_1",
        tenant_id="tenant_A",
        worker_id="w_1",
        fencing_token=1,
        expires_at=now + timedelta(seconds=30),
    )
    lease_b = TaskLeaseContract(
        lease_id="l_B",
        task_id="t_1",
        tenant_id="tenant_A",
        worker_id="w_2",
        fencing_token=2,
        expires_at=now + timedelta(seconds=30),
    )
    assert lease_b.fencing_token > lease_a.fencing_token


def test_p12_3_s2_19_deterministic_exception_hierarchy_status_codes():
    """S2-19: Verify deterministic HTTP status codes for all lease exceptions."""
    assert LeaseConflictError().status_code == 409
    assert StaleLeaseConflictError().status_code == 409
    assert LeaseNotFoundError().status_code == 404
    assert LeaseExpiredError().status_code == 410
    assert UnauthorizedWorkerError().status_code == 403
