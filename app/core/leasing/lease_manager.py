"""Phase 12.3: Atomic In-Memory Lease Manager.
Provides thread-safe, atomic task lease acquisition, heartbeat renewal, voluntary release,
deterministic monotonic fencing tokens, and cross-tenant execution isolation.
"""
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, List, Optional
import uuid

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseExpiredError,
    LeaseNotFoundError,
    LeaseStatus,
    StaleLeaseConflictError,
    TaskLeaseContract,
    UnauthorizedWorkerError,
)


class InMemoryLeaseManager:
    """
    Atomic, thread-safe In-Memory Task Lease Manager.
    Enforces the 'Single Exclusive Lease' and 'Monotonic Fencing Counter' invariants
    across distributed worker pools within an isolated tenant namespace.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        # task_id -> TaskLeaseContract
        self._leases: Dict[str, TaskLeaseContract] = {}
        # task_id -> tenant_id (immutable tenant pinning)
        self._task_tenants: Dict[str, str] = {}
        # task_id -> current monotonic fencing token counter
        self._fencing_counters: Dict[str, int] = {}
        # worker_id -> Set of active lease_ids
        self._worker_leases: Dict[str, set] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def acquire(
        self,
        task_id: str,
        tenant_id: str,
        worker_id: str,
        lease_ttl_seconds: int = 30,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskLeaseContract:
        """
        Atomically acquire an exclusive lease on a task.
        If the task is already leased by an active worker, raises LeaseConflictError (409).
        If the task belongs to a different tenant, raises UnauthorizedWorkerError (403).
        If the previous lease has expired or released, issues a new lease with incremented fencing token.
        """
        if not task_id or not task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not worker_id or not worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be strictly positive > 0.")

        with self._lock:
            now = self._now()

            # 1. Tenant Pinning & Isolation Check
            existing_tenant = self._task_tenants.get(task_id)
            if existing_tenant is not None and existing_tenant != tenant_id:
                raise UnauthorizedWorkerError(
                    f"Cross-tenant task acquisition denied: Task '{task_id}' belongs to tenant '{existing_tenant}'."
                )

            # 2. Check Existing Lease State
            existing_lease = self._leases.get(task_id)
            if existing_lease is not None:
                # If lease is marked active or renewed, verify whether it has physically expired
                if existing_lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED):
                    if existing_lease.expires_at > now:
                        # Lease is currently live and unexpired -> Conflict!
                        if existing_lease.worker_id == worker_id:
                            raise LeaseConflictError(
                                f"Task '{task_id}' is already leased by this worker (lease '{existing_lease.lease_id}')."
                            )
                        raise LeaseConflictError(
                            f"Task '{task_id}' is currently leased by worker '{existing_lease.worker_id}' until {existing_lease.expires_at}."
                        )
                    else:
                        # Lease has expired temporally -> Transition status
                        existing_lease.status = LeaseStatus.EXPIRED
                        if existing_lease.worker_id in self._worker_leases:
                            self._worker_leases[existing_lease.worker_id].discard(existing_lease.lease_id)

            # 3. Pin Task to Tenant (first-time acquisition)
            if existing_tenant is None:
                self._task_tenants[task_id] = tenant_id

            # 4. Strictly Monotonic Fencing Token Increment
            current_fencing = self._fencing_counters.get(task_id, 0) + 1
            self._fencing_counters[task_id] = current_fencing

            # 5. Mint New Lease
            lease_id = f"lease_{uuid.uuid4().hex[:12]}"
            acquired_at = now
            expires_at = now + timedelta(seconds=lease_ttl_seconds)

            new_lease = TaskLeaseContract(
                lease_id=lease_id,
                task_id=task_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                fencing_token=current_fencing,
                status=LeaseStatus.ACQUIRED,
                acquired_at=acquired_at,
                expires_at=expires_at,
                renewal_count=0,
                lease_ttl_seconds=lease_ttl_seconds,
                metadata=metadata or {},
            )

            self._leases[task_id] = new_lease

            if worker_id not in self._worker_leases:
                self._worker_leases[worker_id] = set()
            self._worker_leases[worker_id].add(lease_id)

            return new_lease

    def renew(
        self,
        task_id: str,
        lease_id: str,
        worker_id: str,
        tenant_id: str,
        extension_seconds: Optional[int] = None,
    ) -> TaskLeaseContract:
        """
        Atomically extend the duration of an active task lease.
        Enforces tenant matching, worker ownership, and non-expired state.
        """
        with self._lock:
            now = self._now()
            lease = self._leases.get(task_id)

            if lease is None:
                raise LeaseNotFoundError(f"No lease record found for task '{task_id}'.")

            # Tenant Isolation check
            if lease.tenant_id != tenant_id:
                raise LeaseNotFoundError(f"Lease '{lease_id}' not found under tenant '{tenant_id}'.")

            # Lease ID check
            if lease.lease_id != lease_id:
                raise LeaseNotFoundError(
                    f"Lease ID mismatch for task '{task_id}': expected '{lease.lease_id}', got '{lease_id}'."
                )

            # Worker Ownership check
            if lease.worker_id != worker_id:
                raise UnauthorizedWorkerError(
                    f"Worker '{worker_id}' is not the registered owner of lease '{lease_id}' (owned by '{lease.worker_id}')."
                )

            # Revocation / Released Check
            if lease.status == LeaseStatus.REVOKED:
                raise LeaseConflictError(f"Lease '{lease_id}' has been administratively revoked.")
            if lease.status == LeaseStatus.RELEASED:
                raise LeaseConflictError(f"Lease '{lease_id}' has already been released.")

            # Temporal Expiry Check
            if lease.status == LeaseStatus.EXPIRED or now >= lease.expires_at:
                lease.status = LeaseStatus.EXPIRED
                if worker_id in self._worker_leases:
                    self._worker_leases[worker_id].discard(lease_id)
                raise LeaseExpiredError(
                    f"Lease '{lease_id}' expired at {lease.expires_at} and cannot be renewed."
                )

            # Extend Lease
            ext_duration = extension_seconds if extension_seconds and extension_seconds > 0 else lease.lease_ttl_seconds
            lease.expires_at = now + timedelta(seconds=ext_duration)
            lease.renewal_count += 1
            lease.status = LeaseStatus.RENEWED

            return lease

    def release(
        self,
        task_id: str,
        lease_id: str,
        worker_id: str,
        tenant_id: str,
    ) -> TaskLeaseContract:
        """
        Voluntarily release an active lease upon normal task completion or cancellation.
        """
        with self._lock:
            lease = self._leases.get(task_id)

            if lease is None:
                raise LeaseNotFoundError(f"No lease record found for task '{task_id}'.")

            if lease.tenant_id != tenant_id or lease.lease_id != lease_id:
                raise LeaseNotFoundError(f"Lease '{lease_id}' not found for task '{task_id}'.")

            if lease.worker_id != worker_id:
                raise UnauthorizedWorkerError(
                    f"Worker '{worker_id}' cannot release lease owned by '{lease.worker_id}'."
                )

            lease.status = LeaseStatus.RELEASED
            if worker_id in self._worker_leases:
                self._worker_leases[worker_id].discard(lease_id)

            return lease

    def revoke(
        self,
        task_id: str,
        lease_id: str,
        tenant_id: str,
        reason: str = "administrative_revocation",
    ) -> TaskLeaseContract:
        """
        Administratively revoke an active lease.
        """
        with self._lock:
            lease = self._leases.get(task_id)

            if lease is None or lease.tenant_id != tenant_id or lease.lease_id != lease_id:
                raise LeaseNotFoundError(f"Lease '{lease_id}' not found for task '{task_id}'.")

            lease.status = LeaseStatus.REVOKED
            if lease.worker_id in self._worker_leases:
                self._worker_leases[lease.worker_id].discard(lease_id)

            return lease

    def get_lease(self, task_id: str, tenant_id: Optional[str] = None) -> Optional[TaskLeaseContract]:
        """
        Retrieve the current lease record for a task with automatic lazy expiration evaluation.
        """
        with self._lock:
            lease = self._leases.get(task_id)
            if lease is None:
                return None

            if tenant_id and lease.tenant_id != tenant_id:
                return None

            now = self._now()
            if lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED) and now >= lease.expires_at:
                lease.status = LeaseStatus.EXPIRED
                if lease.worker_id in self._worker_leases:
                    self._worker_leases[lease.worker_id].discard(lease.lease_id)

            return lease

    def list_active_leases(self, tenant_id: Optional[str] = None) -> List[TaskLeaseContract]:
        """
        List all currently active, non-expired leases.
        """
        with self._lock:
            active = []
            now = self._now()
            for task_id, lease in self._leases.items():
                if tenant_id and lease.tenant_id != tenant_id:
                    continue
                if lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED):
                    if now < lease.expires_at:
                        active.append(lease)
                    else:
                        lease.status = LeaseStatus.EXPIRED
            return active

    def check_and_expire_leases(self) -> int:
        """
        Sweep all leases and mark timed-out leases as EXPIRED.
        Returns the number of newly expired leases.
        """
        with self._lock:
            expired_count = 0
            now = self._now()
            for lease in self._leases.values():
                if lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED) and now >= lease.expires_at:
                    lease.status = LeaseStatus.EXPIRED
                    if lease.worker_id in self._worker_leases:
                        self._worker_leases[lease.worker_id].discard(lease.lease_id)
                    expired_count += 1
            return expired_count

    def get_fencing_token(self, task_id: str) -> int:
        """Get the latest monotonic fencing token issued for a task."""
        with self._lock:
            return self._fencing_counters.get(task_id, 0)

    def is_task_acquirable(self, task_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if a task is currently free for worker acquisition.
        """
        with self._lock:
            if tenant_id:
                owner_tenant = self._task_tenants.get(task_id)
                if owner_tenant and owner_tenant != tenant_id:
                    return False

            lease = self._leases.get(task_id)
            if lease is None:
                return True

            if lease.status in (LeaseStatus.EXPIRED, LeaseStatus.RELEASED, LeaseStatus.REVOKED):
                return True

            if self._now() >= lease.expires_at:
                lease.status = LeaseStatus.EXPIRED
                return True

            return False
