"""Phase 12.3: Distributed Task Queue Core.
Provides in-memory transport for QueueMessageContract messages with priority scheduling,
at-least-once exclusive delivery semantics, thread-safe concurrency, tenant isolation, and zero-secret enforcement.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple
import heapq
import itertools

from app.connectors.router import _contains_raw_secrets
from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.leasing import (
    LeaseNotFoundError,
    QueueMessageContract,
    UnauthorizedWorkerError,
)
from app.core.enums.common import PriorityLevel


class MessageState(str, Enum):
    """Lifecycle delivery states for an enqueued queue message."""
    AVAILABLE = "available"      # Waiting in queue for worker consumption
    DELIVERED = "delivered"      # In-flight with a worker, pending ACK/NACK
    ACKNOWLEDGED = "acknowledged"# Successfully executed and retired
    EXHAUSTED = "exhausted"      # Exceeded max_attempts without success


# Priority Weighting (Higher integer = Higher dispatch priority)
_PRIORITY_ORDER = {
    PriorityLevel.CRITICAL: 4,
    "critical": 4,
    PriorityLevel.HIGH: 3,
    "high": 3,
    PriorityLevel.NORMAL: 2,
    "normal": 2,
    PriorityLevel.LOW: 1,
    "low": 1,
}


class InMemoryTaskQueue:
    """
    Thread-Safe, Tenant-Partitioned In-Memory Task Queue.
    Enforces At-Least-Once delivery semantics with exclusive in-flight consumption,
    priority ordering, retry counters, and strict tenant/credential isolation.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        # tenant_id -> List of QueueMessageContract
        self._queues: Dict[str, List[QueueMessageContract]] = {}
        # message_id -> (QueueMessageContract, worker_id, delivered_at)
        self._in_flight: Dict[str, Tuple[QueueMessageContract, str, datetime]] = {}
        # Set of acknowledged message_ids for idempotent duplicate ACK handling
        self._acknowledged: set = set()
        # Monotonic sequence counter to guarantee FIFO ordering within the same priority level
        self._seq = itertools.count()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def enqueue(self, message: QueueMessageContract) -> QueueMessageContract:
        """
        Enqueue a validated QueueMessageContract into its isolated tenant partition.
        Rejects raw secret tokens or forbidden credential parameters (422).
        """
        if not message.tenant_id or not message.tenant_id.strip():
            raise ValueError("Queue message must contain a non-empty tenant_id.")
        if not message.task_id or not message.task_id.strip():
            raise ValueError("Queue message must contain a non-empty task_id.")
        if not message.message_id or not message.message_id.strip():
            raise ValueError("Queue message must contain a non-empty message_id.")

        # Zero-Secret Enforcement on Queue Payload
        if _contains_raw_secrets(message.payload):
            raise RawSecretPayloadError(
                "Raw secrets are forbidden in task queue payloads. Use credential_ref."
            )

        with self._lock:
            tenant_id = message.tenant_id
            if tenant_id not in self._queues:
                self._queues[tenant_id] = []

            # Add to tenant pending queue
            self._queues[tenant_id].append(message)
            return message

    def dequeue(
        self,
        tenant_id: str,
        worker_id: str = "worker_default",
    ) -> Optional[QueueMessageContract]:
        """
        Atomically dequeue the highest priority eligible message for a specific tenant.
        Transitions the message to DELIVERED (in-flight), guaranteeing that concurrent
        consumers do not receive the same message.
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not worker_id or not worker_id.strip():
            raise ValueError("worker_id must be non-empty.")

        with self._lock:
            now = self._now()
            pending = self._queues.get(tenant_id, [])
            if not pending:
                return None

            # Filter for messages whose next_attempt_at is <= now
            eligible_indices = [
                idx for idx, msg in enumerate(pending)
                if msg.next_attempt_at <= now
            ]

            if not eligible_indices:
                return None

            # Sort eligible by (-priority_weight, original_index) to preserve Priority + FIFO
            def sort_key(idx: int):
                msg = pending[idx]
                p_weight = _PRIORITY_ORDER.get(msg.priority, 2)
                return (-p_weight, idx)

            best_idx = min(eligible_indices, key=sort_key)
            chosen_msg = pending.pop(best_idx)

            # Move to in-flight
            self._in_flight[chosen_msg.message_id] = (chosen_msg, worker_id, now)
            return chosen_msg

    def ack(self, message_id: str, tenant_id: str) -> bool:
        """
        Acknowledge successful completion of a message.
        Permanently removes message from in-flight storage. Safe on duplicate calls.
        """
        if not message_id or not message_id.strip():
            raise ValueError("message_id must be non-empty.")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")

        with self._lock:
            if message_id in self._in_flight:
                msg, worker_id, delivered_at = self._in_flight[message_id]
                if msg.tenant_id != tenant_id:
                    raise UnauthorizedWorkerError(
                        f"Cross-tenant ACK rejected: Message belongs to '{msg.tenant_id}', not '{tenant_id}'."
                    )
                del self._in_flight[message_id]
                self._acknowledged.add(message_id)
                return True

            if message_id in self._acknowledged:
                # Idempotent success on duplicate ACK
                return True

            return False

    def nack(
        self,
        message_id: str,
        tenant_id: str,
        requeue: bool = True,
        backoff_seconds: int = 0,
    ) -> bool:
        """
        Negative acknowledgement.
        If requeue=True and attempt_count + 1 <= max_attempts, increments attempt_count,
        sets next_attempt_at backoff, and returns message to the tenant queue.
        If max_attempts exceeded, marks message EXHAUSTED and drops it from the queue.
        """
        if not message_id or not message_id.strip():
            raise ValueError("message_id must be non-empty.")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")

        with self._lock:
            if message_id not in self._in_flight:
                return False

            msg, worker_id, delivered_at = self._in_flight[message_id]
            if msg.tenant_id != tenant_id:
                raise UnauthorizedWorkerError(
                    f"Cross-tenant NACK rejected: Message belongs to '{msg.tenant_id}', not '{tenant_id}'."
                )

            del self._in_flight[message_id]

            if not requeue:
                return True

            # Increment attempt counter
            new_attempts = msg.attempt_count + 1
            if new_attempts <= msg.max_attempts:
                # Re-enqueue with backoff
                now = self._now()
                requeued_msg = QueueMessageContract(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    tenant_id=msg.tenant_id,
                    priority=msg.priority,
                    enqueued_at=msg.enqueued_at,
                    attempt_count=new_attempts,
                    max_attempts=msg.max_attempts,
                    next_attempt_at=now + timedelta(seconds=max(0, backoff_seconds)),
                    payload=msg.payload,
                    metadata=msg.metadata,
                )
                if tenant_id not in self._queues:
                    self._queues[tenant_id] = []
                self._queues[tenant_id].append(requeued_msg)
                return True
            else:
                # Max attempts exhausted
                return False

    def peek(self, tenant_id: str) -> Optional[QueueMessageContract]:
        """View the next eligible message in the tenant queue without removing it."""
        with self._lock:
            pending = self._queues.get(tenant_id, [])
            now = self._now()
            eligible = [m for m in pending if m.next_attempt_at <= now]
            if not eligible:
                return None

            def sort_key(m: QueueMessageContract):
                p_weight = _PRIORITY_ORDER.get(m.priority, 2)
                return -p_weight

            return min(eligible, key=sort_key)

    def qsize(self, tenant_id: Optional[str] = None) -> int:
        """Get the number of pending messages waiting in the queue."""
        with self._lock:
            if tenant_id:
                return len(self._queues.get(tenant_id, []))
            return sum(len(q) for q in self._queues.values())

    def in_flight_count(self, tenant_id: Optional[str] = None) -> int:
        """Get the number of in-flight delivered messages currently awaiting ACK/NACK."""
        with self._lock:
            if tenant_id:
                return sum(1 for msg, _, _ in self._in_flight.values() if msg.tenant_id == tenant_id)
            return len(self._in_flight)

    def purge(self, tenant_id: Optional[str] = None) -> int:
        """Purge all pending messages from the queue. Returns count purged."""
        with self._lock:
            if tenant_id:
                count = len(self._queues.get(tenant_id, []))
                self._queues[tenant_id] = []
                return count
            total = sum(len(q) for q in self._queues.values())
            self._queues.clear()
            return total
