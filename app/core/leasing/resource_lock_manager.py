"""Phase 12.4: Atomic In-Memory Resource Lock Manager.
Provides thread-safe, mutex-protected Exclusive (Write) and Shared (Read) resource locking,
canonical URN normalization, re-entrant acquisition tracking, tenant boundary isolation,
monotonic lock generation epoch tracking, FIFO waiter queueing, writer starvation prevention,
and bounded wait timeouts.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Condition, RLock
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from app.core.contracts.locking import (
    LockConflictError,
    LockExpiredError,
    LockMode,
    LockNotFoundError,
    LockStatus,
    ResourceLockContract,
    StaleLockConflictError,
    UnauthorizedLockError,
    canonicalize_resource_id,
)


@dataclass
class _LockWaiter:
    """Internal representation of a worker thread waiting for a resource lock."""
    waiter_id: str
    tenant_id: str
    canonical_urn: str
    worker_id: str
    task_id: str
    mode: LockMode
    lock_ttl_seconds: int
    metadata: Dict[str, Any]
    condition: Condition
    granted_lock: Optional[ResourceLockContract] = None
    is_cancelled: bool = False
    is_timed_out: bool = False


class InMemoryResourceLockManager:
    """
    Thread-Safe, Tenant-Partitioned Resource Lock Authority.
    Manages Exclusive (Writer) and Shared (Reader) lock lifecycles across concurrent workers,
    with deterministic FIFO wait queueing, writer starvation prevention, and bounded wait timeouts.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        # Condition variable bound to internal mutex for event-driven waiter wakeups
        self._cond = Condition(self._lock)
        # (tenant_id, canonical_urn) -> List of active ResourceLockContract
        self._active_locks: Dict[tuple, List[ResourceLockContract]] = {}
        # (tenant_id, canonical_urn) -> current monotonic lock generation int
        self._lock_generations: Dict[tuple, int] = {}
        # (tenant_id, canonical_urn) -> current mode (LockMode.EXCLUSIVE or LockMode.SHARED)
        self._resource_modes: Dict[tuple, LockMode] = {}
        # (tenant_id, canonical_urn) -> List of _LockWaiter
        self._waiters: Dict[tuple, List[_LockWaiter]] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _cleanup_expired(self, key: tuple) -> None:
        """Internal helper to sweep expired locks for a specific resource key."""
        now = self._now()
        locks = self._active_locks.get(key, [])
        valid_locks = []
        for l in locks:
            if l.status == LockStatus.GRANTED and now < l.expires_at:
                valid_locks.append(l)
            else:
                l.status = LockStatus.EXPIRED

        if valid_locks:
            self._active_locks[key] = valid_locks
        else:
            self._active_locks.pop(key, None)
            self._resource_modes.pop(key, None)

    def _has_waiting_exclusive_writers(self, key: tuple) -> bool:
        """Check if any EXCLUSIVE writer is queued in the wait queue for this resource."""
        waiters = self._waiters.get(key, [])
        return any(w.mode == LockMode.EXCLUSIVE and not w.is_cancelled and not w.is_timed_out for w in waiters)

    def _can_grant_immediately(
        self,
        key: tuple,
        worker_id: str,
        task_id: str,
        mode: LockMode,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if a lock request can be granted immediately without queueing.
        Enforces Writer Starvation Prevention (readers cannot bypass queued exclusive writers).
        """
        current_locks = self._active_locks.get(key, [])
        current_mode = self._resource_modes.get(key)
        waiters = self._waiters.get(key, [])

        # 1. Re-entrant check
        for existing in current_locks:
            if existing.worker_id == worker_id and existing.task_id == task_id:
                if existing.mode == mode:
                    return True, None
                else:
                    return False, f"Lock mode conflict for worker '{worker_id}': cannot change '{existing.mode}' to '{mode}'."

        # 2. If there are existing active locks
        if current_locks:
            if current_mode == LockMode.EXCLUSIVE:
                holder = current_locks[0]
                return False, f"Resource locked exclusively by worker '{holder.worker_id}'."
            elif current_mode == LockMode.SHARED:
                if mode == LockMode.EXCLUSIVE:
                    return False, "Cannot acquire EXCLUSIVE lock: active SHARED readers exist."
                elif mode == LockMode.SHARED:
                    # Writer Starvation Prevention: If an EXCLUSIVE writer is already waiting,
                    # new SHARED requests must queue behind the writer rather than bypassing it!
                    if self._has_waiting_exclusive_writers(key):
                        return False, "Queued EXCLUSIVE writer has priority to prevent reader starvation."

        # 3. If resource is free but waiters are queued ahead (FIFO fairness)
        if not current_locks and waiters:
            # Only head of queue can be granted
            return False, "Waiters are queued ahead."

        return True, None

    def _grant_lock_internal(
        self,
        key: tuple,
        canonical_urn: str,
        tenant_id: str,
        worker_id: str,
        task_id: str,
        mode: LockMode,
        lock_ttl_seconds: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ResourceLockContract:
        """Mint or re-entrantly extend a resource lock contract under mutex."""
        now = self._now()
        current_locks = self._active_locks.get(key, [])

        # Re-entrant check
        for existing in current_locks:
            if existing.worker_id == worker_id and existing.task_id == task_id and existing.mode == mode:
                existing.reentrant_count += 1
                existing.expires_at = now + timedelta(seconds=lock_ttl_seconds)
                return existing

        # Increment monotonic generation
        next_gen = self._lock_generations.get(key, 0) + 1
        self._lock_generations[key] = next_gen

        lock_id = f"lock_{uuid.uuid4().hex[:12]}"
        new_lock = ResourceLockContract(
            lock_id=lock_id,
            canonical_resource_id=canonical_urn,
            tenant_id=tenant_id,
            worker_id=worker_id,
            task_id=task_id,
            mode=mode,
            lock_generation=next_gen,
            status=LockStatus.GRANTED,
            granted_at=now,
            expires_at=now + timedelta(seconds=lock_ttl_seconds),
            reentrant_count=0,
            lock_ttl_seconds=lock_ttl_seconds,
            metadata=metadata or {},
        )

        if key not in self._active_locks:
            self._active_locks[key] = []
        self._active_locks[key].append(new_lock)
        self._resource_modes[key] = mode

        return new_lock

    def _notify_waiters(self, key: tuple) -> None:
        """
        Process the waiter queue for a resource key and grant locks to eligible head waiter(s).
        """
        self._cleanup_expired(key)
        current_locks = self._active_locks.get(key, [])
        current_mode = self._resource_modes.get(key)
        waiters = self._waiters.get(key, [])

        # Clean out dead waiters
        valid_waiters = [w for w in waiters if not w.is_cancelled and not w.is_timed_out]
        if valid_waiters:
            self._waiters[key] = valid_waiters
        else:
            self._waiters.pop(key, None)
            return

        head = valid_waiters[0]

        if not current_locks:
            # Resource is free!
            if head.mode == LockMode.EXCLUSIVE:
                # Grant EXCLUSIVE to head waiter
                valid_waiters.pop(0)
                granted = self._grant_lock_internal(
                    key=key,
                    canonical_urn=head.canonical_urn,
                    tenant_id=head.tenant_id,
                    worker_id=head.worker_id,
                    task_id=head.task_id,
                    mode=head.mode,
                    lock_ttl_seconds=head.lock_ttl_seconds,
                    metadata=head.metadata,
                )
                head.granted_lock = granted
                head.condition.notify_all()
            elif head.mode == LockMode.SHARED:
                # Grant SHARED to all contiguous SHARED waiters at front of queue
                while valid_waiters and valid_waiters[0].mode == LockMode.SHARED:
                    w = valid_waiters.pop(0)
                    granted = self._grant_lock_internal(
                        key=key,
                        canonical_urn=w.canonical_urn,
                        tenant_id=w.tenant_id,
                        worker_id=w.worker_id,
                        task_id=w.task_id,
                        mode=w.mode,
                        lock_ttl_seconds=w.lock_ttl_seconds,
                        metadata=w.metadata,
                    )
                    w.granted_lock = granted
                    w.condition.notify_all()
        elif current_mode == LockMode.SHARED:
            # Active readers exist; we can only admit more readers if no EXCLUSIVE writer is queued ahead
            if not self._has_waiting_exclusive_writers(key):
                while valid_waiters and valid_waiters[0].mode == LockMode.SHARED:
                    w = valid_waiters.pop(0)
                    granted = self._grant_lock_internal(
                        key=key,
                        canonical_urn=w.canonical_urn,
                        tenant_id=w.tenant_id,
                        worker_id=w.worker_id,
                        task_id=w.task_id,
                        mode=w.mode,
                        lock_ttl_seconds=w.lock_ttl_seconds,
                        metadata=w.metadata,
                    )
                    w.granted_lock = granted
                    w.condition.notify_all()

    def acquire(
        self,
        resource_id: str,
        tenant_id: str,
        worker_id: str,
        task_id: str,
        mode: LockMode = LockMode.EXCLUSIVE,
        lock_ttl_seconds: int = 30,
        wait_timeout_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ResourceLockContract:
        """
        Atomically acquire a resource lock. If the lock is held or queued with conflict:
        - If wait_timeout_seconds is None or <= 0: raises LockConflictError (409) immediately.
        - If wait_timeout_seconds > 0: enqueues in FIFO wait queue and waits until granted or timed out.
        """
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id must be non-empty.")
        if not worker_id or not str(worker_id).strip():
            raise ValueError("worker_id must be non-empty.")
        if not task_id or not str(task_id).strip():
            raise ValueError("task_id must be non-empty.")
        if lock_ttl_seconds <= 0:
            raise ValueError("lock_ttl_seconds must be strictly positive > 0.")

        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)

        with self._lock:
            self._cleanup_expired(key)
            can_grant, conflict_reason = self._can_grant_immediately(key, worker_id, task_id, mode)

            if can_grant:
                return self._grant_lock_internal(
                    key=key,
                    canonical_urn=canonical_urn,
                    tenant_id=tenant_id,
                    worker_id=worker_id,
                    task_id=task_id,
                    mode=mode,
                    lock_ttl_seconds=lock_ttl_seconds,
                    metadata=metadata,
                )

            # Cannot grant immediately
            if wait_timeout_seconds is None or wait_timeout_seconds <= 0:
                raise LockConflictError(
                    conflict_reason or f"Lock on '{canonical_urn}' is currently held with conflict."
                )

            # Enqueue waiter with bounded timeout
            waiter_cond = Condition(self._lock)
            waiter_id = f"waiter_{uuid.uuid4().hex[:8]}"
            waiter = _LockWaiter(
                waiter_id=waiter_id,
                tenant_id=tenant_id,
                canonical_urn=canonical_urn,
                worker_id=worker_id,
                task_id=task_id,
                mode=mode,
                lock_ttl_seconds=lock_ttl_seconds,
                metadata=metadata or {},
                condition=waiter_cond,
            )

            if key not in self._waiters:
                self._waiters[key] = []
            self._waiters[key].append(waiter)

            deadline = time.time() + wait_timeout_seconds

            while waiter.granted_lock is None and not waiter.is_cancelled:
                remaining = deadline - time.time()
                if remaining <= 0:
                    waiter.is_timed_out = True
                    break
                waiter_cond.wait(timeout=remaining)

            # Clean up waiter entry from list
            if key in self._waiters and waiter in self._waiters[key]:
                self._waiters[key].remove(waiter)
                if not self._waiters[key]:
                    self._waiters.pop(key, None)

            if waiter.granted_lock is not None:
                return waiter.granted_lock

            if waiter.is_cancelled:
                raise LockConflictError(f"Lock acquisition for '{canonical_urn}' was cancelled while waiting.")

            raise LockConflictError(
                f"Timed out after {wait_timeout_seconds}s waiting for lock on '{canonical_urn}'."
            )

    def release(
        self,
        resource_id: str,
        lock_id: str,
        tenant_id: str,
        worker_id: str,
        lock_generation: Optional[int] = None,
    ) -> ResourceLockContract:
        """
        Atomically release a held resource lock and notify eligible queued waiters.
        """
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id must be non-empty.")
        if not worker_id or not str(worker_id).strip():
            raise ValueError("worker_id must be non-empty.")
        if not lock_id or not str(lock_id).strip():
            raise ValueError("lock_id must be non-empty.")

        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)

        with self._lock:
            self._cleanup_expired(key)

            current_locks = self._active_locks.get(key, [])
            current_gen = self._lock_generations.get(key, 0)

            # Stale generation check
            if lock_generation is not None and lock_generation < current_gen:
                raise StaleLockConflictError(
                    f"Stale lock release rejected: Provided generation {lock_generation} is superseded by current generation {current_gen}."
                )

            target_lock: Optional[ResourceLockContract] = None
            for l in current_locks:
                if l.lock_id == lock_id:
                    target_lock = l
                    break

            if target_lock is None:
                raise LockNotFoundError(
                    f"Lock '{lock_id}' not found on active resource '{canonical_urn}' for tenant '{tenant_id}'."
                )

            if target_lock.worker_id != worker_id:
                raise UnauthorizedLockError(
                    f"Worker '{worker_id}' cannot release lock owned by '{target_lock.worker_id}'."
                )

            if target_lock.reentrant_count > 0:
                target_lock.reentrant_count -= 1
                return target_lock

            target_lock.status = LockStatus.RELEASED
            current_locks.remove(target_lock)

            if not current_locks:
                self._active_locks.pop(key, None)
                self._resource_modes.pop(key, None)

            # Wake up eligible waiters
            self._notify_waiters(key)

            return target_lock

    def cancel_waiter(self, resource_id: str, tenant_id: str, waiter_id: str) -> bool:
        """Cancel a waiting request in the queue. Safe and idempotent."""
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)

        with self._lock:
            waiters = self._waiters.get(key, [])
            for w in waiters:
                if w.waiter_id == waiter_id:
                    w.is_cancelled = True
                    w.condition.notify_all()
                    waiters.remove(w)
                    if not waiters:
                        self._waiters.pop(key, None)
                    return True
            return False

    def acquire_batch(
        self,
        batch_request: "MultiResourceLockBatchRequest",
    ) -> List[ResourceLockContract]:
        """
        Atomically acquire a multi-resource lock batch in strict lexicographical canonical order.
        Eliminates circular-wait deadlocks.
        Enforces all-or-nothing transactional semantics: If any resource cannot be acquired
        within the batch timeout, all previously acquired locks in the batch are rolled back.
        """
        from app.core.contracts.locking import MultiResourceLockBatchRequest

        if not isinstance(batch_request, MultiResourceLockBatchRequest):
            raise TypeError("batch_request must be an instance of MultiResourceLockBatchRequest.")

        tenant_id = batch_request.tenant_id
        worker_id = batch_request.worker_id
        task_id = batch_request.task_id
        ttl = batch_request.lock_ttl_seconds
        timeout = batch_request.acquire_timeout_seconds

        ordered_items = batch_request.get_canonical_ordered_items()
        acquired_locks: List[ResourceLockContract] = []
        deadline = time.time() + timeout

        try:
            for canonical_urn, mode in ordered_items:
                remaining_time = deadline - time.time()
                if remaining_time <= 0:
                    raise LockConflictError(
                        f"Batch request '{batch_request.request_id}' timed out before acquiring '{canonical_urn}'."
                    )

                grant = self.acquire(
                    resource_id=canonical_urn,
                    tenant_id=tenant_id,
                    worker_id=worker_id,
                    task_id=task_id,
                    mode=mode,
                    lock_ttl_seconds=ttl,
                    wait_timeout_seconds=remaining_time,
                )
                acquired_locks.append(grant)

            return acquired_locks

        except Exception as ex:
            # Transactional Rollback: Release all previously acquired locks in this batch
            for grant in reversed(acquired_locks):
                try:
                    self.release(
                        resource_id=grant.canonical_resource_id,
                        lock_id=grant.lock_id,
                        tenant_id=tenant_id,
                        worker_id=worker_id,
                        lock_generation=grant.lock_generation,
                    )
                except Exception:
                    pass
            raise ex

    def release_batch(
        self,
        batch_locks: List[ResourceLockContract],
        tenant_id: str,
        worker_id: str,
    ) -> List[ResourceLockContract]:
        """
        Release a collection of resource locks acquired via batch.
        """
        released_locks: List[ResourceLockContract] = []
        for grant in batch_locks:
            res = self.release(
                resource_id=grant.canonical_resource_id,
                lock_id=grant.lock_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                lock_generation=grant.lock_generation,
            )
            released_locks.append(res)
        return released_locks

    def get_waiter_count(self, resource_id: str, tenant_id: str) -> int:
        """Get the number of pending waiters in the queue for a resource."""
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)
        with self._lock:
            waiters = self._waiters.get(key, [])
            return len([w for w in waiters if not w.is_cancelled and not w.is_timed_out])

    def get_lock_state(self, resource_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve structured snapshot of active holders and waiters."""
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)

        with self._lock:
            self._cleanup_expired(key)
            current_locks = self._active_locks.get(key, [])
            waiters = self._waiters.get(key, [])

            if not current_locks and not waiters:
                return None

            return {
                "canonical_resource_id": canonical_urn,
                "tenant_id": tenant_id,
                "mode": self._resource_modes.get(key),
                "lock_generation": self._lock_generations.get(key, 0),
                "active_holders": [
                    {
                        "lock_id": l.lock_id,
                        "worker_id": l.worker_id,
                        "task_id": l.task_id,
                        "mode": l.mode,
                        "granted_at": l.granted_at.isoformat(),
                        "expires_at": l.expires_at.isoformat(),
                        "reentrant_count": l.reentrant_count,
                    }
                    for l in current_locks
                ],
                "waiter_count": len([w for w in waiters if not w.is_cancelled and not w.is_timed_out]),
            }

    def get_active_locks(self, resource_id: str, tenant_id: str) -> List[ResourceLockContract]:
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)
        with self._lock:
            self._cleanup_expired(key)
            return list(self._active_locks.get(key, []))

    def get_generation(self, resource_id: str, tenant_id: str) -> int:
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)
        with self._lock:
            return self._lock_generations.get(key, 0)

    def is_resource_locked(self, resource_id: str, tenant_id: str) -> bool:
        canonical_urn = canonicalize_resource_id(resource_id)
        key = (tenant_id, canonical_urn)
        with self._lock:
            self._cleanup_expired(key)
            return bool(self._active_locks.get(key))
