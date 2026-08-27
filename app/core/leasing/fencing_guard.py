"""Phase 12.3: Fencing Token & Stale-Write Defense Guard.
Enforces the strictly monotonic fencing token invariant to guarantee that zombie, delayed,
or frozen workers cannot execute authoritative writes after a task has been reclaimed by a newer generation.
"""
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, Optional

from app.core.contracts.leasing import (
    LeaseExpiredError,
    LeaseNotFoundError,
    LeaseStatus,
    StaleLeaseConflictError,
    TaskLeaseContract,
    UnauthorizedWorkerError,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager


class FencedTaskExecutionGuard:
    """
    Authoritative state guard enforcing monotonic fencing tokens on all state-mutating operations.
    Rejects stale writes from previous generation workers after task reclaim.
    """

    def __init__(self, lease_manager: InMemoryLeaseManager) -> None:
        self.lease_manager = lease_manager
        self._lock = RLock()
        # task_id -> record of authoritative committed state outputs
        self._task_state_store: Dict[str, Dict[str, Any]] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def validate_write_authority(
        self,
        task_id: str,
        tenant_id: str,
        worker_id: str,
        fencing_token: int,
        lease_id: Optional[str] = None,
    ) -> TaskLeaseContract:
        """
        Validate that the caller holds the current, unexpired, and strictly authoritative fencing token.
        Rejects stale tokens (< current_token) with StaleLeaseConflictError (409).
        Rejects future invalid tokens (> current_token) with StaleLeaseConflictError (409).
        Rejects cross-tenant callers with UnauthorizedWorkerError (403).
        """
        if not task_id or not task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not worker_id or not worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        if fencing_token < 1:
            raise ValueError("fencing_token must be a positive integer >= 1.")

        with self._lock:
            # 1. Tenant Isolation Verification
            owner_tenant = self.lease_manager._task_tenants.get(task_id)
            if owner_tenant is not None and owner_tenant != tenant_id:
                raise UnauthorizedWorkerError(
                    f"Cross-tenant write authorization denied: Task '{task_id}' belongs to tenant '{owner_tenant}'."
                )

            # 2. Lease Record Existence
            current_lease = self.lease_manager.get_lease(task_id, tenant_id=tenant_id)
            if current_lease is None:
                raise LeaseNotFoundError(f"No active or historical lease found for task '{task_id}'.")

            # 3. Monotonic Fencing Token Verification
            current_token = self.lease_manager.get_fencing_token(task_id)
            if fencing_token < current_token:
                raise StaleLeaseConflictError(
                    f"Stale write rejected: Provided fencing token {fencing_token} has been superseded by active generation {current_token}."
                )
            if fencing_token > current_token:
                raise StaleLeaseConflictError(
                    f"Invalid fencing token: Provided token {fencing_token} exceeds latest issued generation {current_token}."
                )

            # 4. Worker Ownership Check
            if current_lease.worker_id != worker_id:
                raise UnauthorizedWorkerError(
                    f"Worker '{worker_id}' is not the registered owner of generation {fencing_token} (owned by '{current_lease.worker_id}')."
                )

            # 5. Lease ID Check if provided
            if lease_id and current_lease.lease_id != lease_id:
                raise StaleLeaseConflictError(
                    f"Lease ID mismatch: Provided lease '{lease_id}' does not match current generation lease '{current_lease.lease_id}'."
                )

            # 6. Temporal and Status Validity
            now = self._now()
            if current_lease.status == LeaseStatus.EXPIRED or now >= current_lease.expires_at:
                raise LeaseExpiredError(
                    f"Lease for task '{task_id}' expired at {current_lease.expires_at}. Authoritative write denied."
                )
            if current_lease.status == LeaseStatus.REVOKED:
                raise StaleLeaseConflictError(
                    f"Lease for task '{task_id}' has been administratively revoked."
                )

            return current_lease

    def execute_fenced_write(
        self,
        task_id: str,
        tenant_id: str,
        worker_id: str,
        fencing_token: int,
        write_key: str,
        write_value: Any,
        lease_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atomically validate write authority and commit state changes for a task.
        """
        with self._lock:
            # Validate fencing authority
            lease = self.validate_write_authority(
                task_id=task_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                fencing_token=fencing_token,
                lease_id=lease_id,
            )

            # Commit write into task state store
            if task_id not in self._task_state_store:
                self._task_state_store[task_id] = {
                    "tenant_id": tenant_id,
                    "fencing_token": fencing_token,
                    "last_written_by": worker_id,
                    "updated_at": self._now().isoformat(),
                    "data": {},
                }

            record = self._task_state_store[task_id]
            record["fencing_token"] = fencing_token
            record["last_written_by"] = worker_id
            record["updated_at"] = self._now().isoformat()
            record["data"][write_key] = write_value

            return record

    def get_task_state(self, task_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the committed state for a task with tenant boundary isolation."""
        with self._lock:
            record = self._task_state_store.get(task_id)
            if record is None:
                return None
            if record["tenant_id"] != tenant_id:
                return None
            return record
