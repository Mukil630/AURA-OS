"""Phase 12.3 Step 4: Dedicated Unit, Adversarial & Multi-Threaded Task Queue Test Suite.
Verifies Enqueue, Dequeue, Priority FIFO Scheduling, ACK/NACK Requeue Semantics,
Tenant Isolation, Zero-Secret Payload Enforcement, and Multi-Consumer Concurrent Races.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest
from pydantic import ValidationError

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.leasing import (
    LeaseStatus,
    QueueMessageContract,
    UnauthorizedWorkerError,
)
from app.core.enums.common import PriorityLevel
from app.core.leasing.lease_manager import InMemoryLeaseManager
from app.core.leasing.task_queue import InMemoryTaskQueue


# ═════════════════════════════════════════════════════════════════════════════
# 1. QUEUE BASICS & IDENTITY PRESERVATION (Tests 1 - 6)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_01_enqueue_valid_message():
    """S4-01: Enqueue a valid QueueMessageContract into tenant partition."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="msg_001",
        task_id="task_101",
        tenant_id="tenant_A",
        priority=PriorityLevel.NORMAL,
        payload={"repo": "Mukil630/AURA-OS", "credential_ref": "github_prod_01"},
    )
    enqueued = queue.enqueue(msg)
    assert enqueued.message_id == "msg_001"
    assert queue.qsize("tenant_A") == 1


def test_p12_3_s4_02_dequeue_returns_message():
    """S4-02: Dequeue returns the pending message and moves it to in-flight."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="msg_002",
        task_id="task_102",
        tenant_id="tenant_A",
    )
    queue.enqueue(msg)
    dequeued = queue.dequeue(tenant_id="tenant_A", worker_id="worker_1")

    assert dequeued is not None
    assert dequeued.message_id == "msg_002"
    assert queue.qsize("tenant_A") == 0
    assert queue.in_flight_count("tenant_A") == 1


def test_p12_3_s4_03_empty_queue_returns_none():
    """S4-03: Dequeue on an empty queue returns None."""
    queue = InMemoryTaskQueue()
    assert queue.dequeue(tenant_id="tenant_empty") is None


def test_p12_3_s4_04_message_identity_preserved():
    """S4-04: message_id is preserved exactly across enqueue and dequeue."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="uuid_999", task_id="t_1", tenant_id="tenant_A")
    queue.enqueue(msg)
    dequeued = queue.dequeue("tenant_A")
    assert dequeued.message_id == "uuid_999"


def test_p12_3_s4_05_task_identity_preserved():
    """S4-05: task_id is preserved exactly across the queue lifecycle."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_1", task_id="task_special_777", tenant_id="tenant_A")
    queue.enqueue(msg)
    dequeued = queue.dequeue("tenant_A")
    assert dequeued.task_id == "task_special_777"


def test_p12_3_s4_06_tenant_identity_preserved():
    """S4-06: tenant_id is strictly preserved throughout the queue lifecycle."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_1", task_id="t_1", tenant_id="tenant_mukil")
    queue.enqueue(msg)
    dequeued = queue.dequeue("tenant_mukil")
    assert dequeued.tenant_id == "tenant_mukil"


# ═════════════════════════════════════════════════════════════════════════════
# 2. PRIORITY SCHEDULING & FIFO ORDERING (Tests 7 - 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_07_higher_priority_consumed_first():
    """S4-07: Messages with higher priority are dequeued before lower priority ones."""
    queue = InMemoryTaskQueue()
    m_low = QueueMessageContract(message_id="m_low", task_id="t_low", tenant_id="t1", priority=PriorityLevel.LOW)
    m_crit = QueueMessageContract(message_id="m_crit", task_id="t_crit", tenant_id="t1", priority=PriorityLevel.CRITICAL)
    m_norm = QueueMessageContract(message_id="m_norm", task_id="t_norm", tenant_id="t1", priority=PriorityLevel.NORMAL)

    queue.enqueue(m_low)
    queue.enqueue(m_crit)
    queue.enqueue(m_norm)

    assert queue.dequeue("t1").message_id == "m_crit"
    assert queue.dequeue("t1").message_id == "m_norm"
    assert queue.dequeue("t1").message_id == "m_low"


def test_p12_3_s4_08_same_priority_follows_fifo_ordering():
    """S4-08: Messages with identical priority follow First-In-First-Out ordering."""
    queue = InMemoryTaskQueue()
    m1 = QueueMessageContract(message_id="msg_first", task_id="t1", tenant_id="t1", priority=PriorityLevel.HIGH)
    m2 = QueueMessageContract(message_id="msg_second", task_id="t2", tenant_id="t1", priority=PriorityLevel.HIGH)
    m3 = QueueMessageContract(message_id="msg_third", task_id="t3", tenant_id="t1", priority=PriorityLevel.HIGH)

    queue.enqueue(m1)
    queue.enqueue(m2)
    queue.enqueue(m3)

    assert queue.dequeue("t1").message_id == "msg_first"
    assert queue.dequeue("t1").message_id == "msg_second"
    assert queue.dequeue("t1").message_id == "msg_third"


# ═════════════════════════════════════════════════════════════════════════════
# 3. RETRY METADATA & NEXT ATTEMPT BACKOFF (Tests 9 - 12)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_09_attempt_count_starts_correctly():
    """S4-09: attempt_count defaults to 0 on new messages."""
    msg = QueueMessageContract(message_id="m_1", task_id="t_1", tenant_id="tenant_A")
    assert msg.attempt_count == 0


def test_p12_3_s4_10_max_attempts_preserved():
    """S4-10: max_attempts is preserved across the queue."""
    msg = QueueMessageContract(message_id="m_1", task_id="t_1", tenant_id="tenant_A", max_attempts=5)
    queue = InMemoryTaskQueue()
    queue.enqueue(msg)
    dequeued = queue.dequeue("tenant_A")
    assert dequeued.max_attempts == 5


def test_p12_3_s4_11_invalid_retry_state_rejected():
    """S4-11: Contracts reject invalid retry counters (attempt > max)."""
    with pytest.raises(ValidationError):
        QueueMessageContract(message_id="m_1", task_id="t_1", tenant_id="t1", attempt_count=5, max_attempts=3)


def test_p12_3_s4_12_next_attempt_at_respected():
    """S4-12: Messages scheduled with future next_attempt_at are skipped until time arrives."""
    queue = InMemoryTaskQueue()
    future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
    msg_delayed = QueueMessageContract(
        message_id="m_delayed",
        task_id="t_delayed",
        tenant_id="t1",
        next_attempt_at=future_time,
    )
    msg_ready = QueueMessageContract(
        message_id="m_ready",
        task_id="t_ready",
        tenant_id="t1",
    )

    queue.enqueue(msg_delayed)
    queue.enqueue(msg_ready)

    # Dequeue should skip msg_delayed and pick msg_ready
    first = queue.dequeue("t1")
    assert first.message_id == "m_ready"

    # Next dequeue returns None because m_delayed is still in the future
    assert queue.dequeue("t1") is None


# ═════════════════════════════════════════════════════════════════════════════
# 4. ACKNOWLEDGEMENT & REQUEUE SEMANTICS (Tests 13 - 18)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_13_successful_ack_removes_message():
    """S4-13: Acknowledging a message removes it from in-flight storage."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_ack", task_id="t_1", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    assert queue.in_flight_count("tenant_A") == 1
    assert queue.ack("m_ack", tenant_id="tenant_A") is True
    assert queue.in_flight_count("tenant_A") == 0


def test_p12_3_s4_14_duplicate_ack_handled_safely():
    """S4-14: Duplicate ACK on an already-acknowledged message returns True idempotently."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_dup_ack", task_id="t_1", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    assert queue.ack("m_dup_ack", "tenant_A") is True
    assert queue.ack("m_dup_ack", "tenant_A") is True  # Idempotent second ack


def test_p12_3_s4_15_invalid_message_ack_rejected():
    """S4-15: Attempting to ACK a non-existent message returns False."""
    queue = InMemoryTaskQueue()
    assert queue.ack("non_existent_msg", "tenant_A") is False


def test_p12_3_s4_16_nack_requeue_preserves_task_identity():
    """S4-16: NACK with requeue=True returns message to queue with preserved task identity."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_nack", task_id="task_retry_99", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    assert queue.nack("m_nack", "tenant_A", requeue=True) is True
    assert queue.qsize("tenant_A") == 1

    requeued = queue.dequeue("tenant_A")
    assert requeued.task_id == "task_retry_99"


def test_p12_3_s4_17_requeue_increments_attempt_count():
    """S4-17: NACK requeue increments attempt_count."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_count", task_id="t1", tenant_id="tenant_A", max_attempts=3)
    queue.enqueue(msg)
    d1 = queue.dequeue("tenant_A")
    assert d1.attempt_count == 0

    queue.nack("m_count", "tenant_A", requeue=True)
    d2 = queue.dequeue("tenant_A")
    assert d2.attempt_count == 1


def test_p12_3_s4_18_max_attempt_boundary_exhausts_message():
    """S4-18: NACK beyond max_attempts exhausts message (returns False and drops from queue)."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_max", task_id="t1", tenant_id="tenant_A", attempt_count=2, max_attempts=2)
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    # attempt_count + 1 would be 3 > 2 (max)
    assert queue.nack("m_max", "tenant_A", requeue=True) is False
    assert queue.qsize("tenant_A") == 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. TENANT ISOLATION DEFENSE (Tests 19 - 21)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_19_tenant_a_message_cannot_be_consumed_by_tenant_b():
    """S4-19: Tenant B worker cannot dequeue Tenant A messages."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_A", task_id="t_A", tenant_id="tenant_A")
    queue.enqueue(msg)

    # Tenant B requests dequeue
    assert queue.dequeue("tenant_B") is None
    # Tenant A requests dequeue
    assert queue.dequeue("tenant_A") is not None


def test_p12_3_s4_20_cross_tenant_ack_rejected():
    """S4-20: Tenant B attempting to ACK a Tenant A in-flight message is rejected."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="m_iso", task_id="t_iso", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    with pytest.raises(UnauthorizedWorkerError):
        queue.ack("m_iso", tenant_id="tenant_B")


def test_p12_3_s4_21_missing_tenant_rejected():
    """S4-21: Dequeue with empty tenant_id is rejected."""
    queue = InMemoryTaskQueue()
    with pytest.raises(ValueError):
        queue.dequeue("")


# ═════════════════════════════════════════════════════════════════════════════
# 6. CREDENTIAL ISOLATION DEFENSE (Tests 22 - 25)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_22_credential_ref_allowed_in_queue_payload():
    """S4-22: Legitimate indirect credential_ref is accepted in payload."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="m_ref",
        task_id="t_ref",
        tenant_id="tenant_A",
        payload={"repo": "Mukil630/AURA-OS", "credential_ref": "github_prod_01"},
    )
    enqueued = queue.enqueue(msg)
    assert enqueued.payload["credential_ref"] == "github_prod_01"


def test_p12_3_s4_23_raw_github_token_rejected_on_enqueue():
    """S4-23: Malicious payload containing raw ghp_ token is rejected on enqueue (422)."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="m_bad_token",
        task_id="t_bad",
        tenant_id="tenant_A",
        payload={"api_key": "ghp_MALICIOUS_TOKEN_12345"},
    )
    with pytest.raises(RawSecretPayloadError):
        queue.enqueue(msg)


def test_p12_3_s4_24_raw_password_in_nested_payload_rejected():
    """S4-24: Nested payload containing password/secret is rejected on enqueue (422)."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="m_nested_sec",
        task_id="t_nested",
        tenant_id="tenant_A",
        payload={"config": {"auth": {"password": "super_secret_password"}}},
    )
    with pytest.raises(RawSecretPayloadError):
        queue.enqueue(msg)


def test_p12_3_s4_25_bearer_token_in_headers_rejected():
    """S4-25: Bearer token in headers rejected on enqueue (422)."""
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(
        message_id="m_bearer",
        task_id="t_bearer",
        tenant_id="tenant_A",
        payload={"headers": {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"}},
    )
    with pytest.raises(RawSecretPayloadError):
        queue.enqueue(msg)


# ═════════════════════════════════════════════════════════════════════════════
# 7. CONCURRENCY & LEASE MANAGER INTEGRATION (Tests 26 - 28)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s4_26_two_consumers_compete_for_one_message():
    """
    S4-26: CONCURRENCY RACE PROOF
    Two concurrent worker threads race to dequeue a single message.
    Verifies exactly 1 worker gets the message; 1 worker gets None.
    Zero duplicate deliveries!
    """
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="msg_single_prize", task_id="t_1", tenant_id="tenant_A")
    queue.enqueue(msg)

    barrier = threading.Barrier(2)
    dequeued_results = []

    def consumer_job(w_name: str):
        barrier.wait()
        res = queue.dequeue(tenant_id="tenant_A", worker_id=w_name)
        if res is not None:
            dequeued_results.append((w_name, res))

    t1 = threading.Thread(target=consumer_job, args=("Worker_1",))
    t2 = threading.Thread(target=consumer_job, args=("Worker_2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(dequeued_results) == 1, "Expected exactly 1 consumer to receive the message!"
    assert queue.in_flight_count("tenant_A") == 1


def test_p12_3_s4_27_twenty_consumers_compete_for_five_messages():
    """
    S4-27: 20 worker threads concurrently compete for 5 queued messages.
    Asserts exactly 5 distinct messages are delivered, with zero duplicates.
    """
    queue = InMemoryTaskQueue()
    num_msgs = 5
    for i in range(num_msgs):
        queue.enqueue(QueueMessageContract(message_id=f"msg_{i}", task_id=f"t_{i}", tenant_id="tenant_scale"))

    num_workers = 20
    barrier = threading.Barrier(num_workers)
    delivered_msgs = []

    def worker_dequeue(w_id: int):
        barrier.wait()
        return queue.dequeue(tenant_id="tenant_scale", worker_id=f"worker_{w_id}")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(worker_dequeue, range(num_workers)))
        delivered = [r for r in results if r is not None]

    assert len(delivered) == num_msgs
    # Verify all delivered message IDs are unique
    delivered_ids = {m.message_id for m in delivered}
    assert len(delivered_ids) == num_msgs
    assert queue.qsize("tenant_scale") == 0
    assert queue.in_flight_count("tenant_scale") == num_msgs


def test_p12_3_s4_28_queue_to_s3_lease_manager_integration_lifecycle():
    """
    S4-28: END-TO-END QUEUE-TO-LEASE INTEGRATION
    Verifies:
    1. Producer enqueues message.
    2. Consumer dequeues message.
    3. Consumer acquires exclusive lease on task from S3 InMemoryLeaseManager.
    4. Second consumer cannot acquire task lease while active (409).
    5. Consumer processes task, releases lease, and ACKs message.
    """
    queue = InMemoryTaskQueue()
    lease_mgr = InMemoryLeaseManager()

    # 1. Enqueue Task Message
    msg = QueueMessageContract(
        message_id="msg_workflow_01",
        task_id="task_workflow_01",
        tenant_id="tenant_mukil",
        payload={"repo": "Mukil630/AURA-OS", "credential_ref": "github_master_key"},
    )
    queue.enqueue(msg)

    # 2. Worker 1 Dequeues Message
    consumed = queue.dequeue("tenant_mukil", worker_id="worker_alpha")
    assert consumed is not None
    assert consumed.task_id == "task_workflow_01"

    # 3. Worker 1 Acquires Exclusive Task Lease from S3 LeaseManager
    lease = lease_mgr.acquire(
        task_id=consumed.task_id,
        tenant_id=consumed.tenant_id,
        worker_id="worker_alpha",
        lease_ttl_seconds=30,
    )
    assert lease.status == LeaseStatus.ACQUIRED
    assert lease.fencing_token == 1

    # 4. Worker 2 attempts to acquire same task lease -> Conflict!
    with pytest.raises(Exception) as exc_info:
        lease_mgr.acquire(consumed.task_id, consumed.tenant_id, "worker_beta")
    assert exc_info.value.status_code == 409

    # 5. Worker 1 completes work, releases lease, and ACKs message
    released = lease_mgr.release(consumed.task_id, lease.lease_id, "worker_alpha", consumed.tenant_id)
    assert released.status == LeaseStatus.RELEASED

    ack_res = queue.ack(consumed.message_id, tenant_id=consumed.tenant_id)
    assert ack_res is True
    assert queue.in_flight_count("tenant_mukil") == 0
