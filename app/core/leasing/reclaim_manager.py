"""Phase 12.3: Crash Detection & Standby Reclaim Manager.
Detects expired task leases resulting from worker crashes or network partitions,
evaluates reclaim eligibility, and atomically transfers task execution authority to standby workers.
"""
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseNotFoundError,
    LeaseStatus,
    TaskLeaseContract,
    UnauthorizedWorkerError,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager


class StandbyReclaimManager:
    """
    Coordinates crash detection and standby worker reclaim for expired task leases.
    Enforces atomic ownership transfer, strict tenant boundary isolation, and
    preserves the Queue != Lease separation of concerns.
    """

    def __init__(self, lease_manager: InMemoryLeaseManager) -> None:
        self.lease_manager = lease_manager
        self._lock = RLock()
        # Set of task_ids that have been marked completed (terminal state, not reclaimable)
        self._completed_tasks: set = set()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as permanently completed to prevent subsequent reclaim attempts."""
        with self._lock:
            self._completed_tasks.add(task_id)

    def is_task_completed(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._completed_tasks

    def detect_expired_leases(self, tenant_id: Optional[str] = None) -> List[TaskLeaseContract]:
        """
        Scan all tracked leases in LeaseManager and return those that have physically expired
        and are eligible for crash recovery.
        """
        with self._lock:
            now = self._now()
            expired_leases = []
            # Use LeaseManager's internal snapshot
            with self.lease_manager._lock:
                for task_id, lease in self.lease_manager._leases.items():
                    if tenant_id and lease.tenant_id != tenant_id:
                        continue
                    if task_id in self._completed_tasks:
                        continue
                    # Check if status is EXPIRED or physically past expiry timestamp
                    if lease.status == LeaseStatus.EXPIRED or (
                        lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED) and now >= lease.expires_at
                    ):
                        expired_leases.append(lease)
            return expired_leases

    def is_eligible_for_reclaim(self, task_id: str, tenant_id: str) -> Tuple[bool, str]:
        """
        Evaluate if a task is currently eligible for reclaim by a standby worker.
        Returns (is_eligible, reason_message).
        """
        with self._lock:
            if task_id in self._completed_tasks:
                return False, f"Task '{task_id}' has already been marked completed."

            lease = self.lease_manager.get_lease(task_id, tenant_id=tenant_id)
            if lease is None:
                # Check if task exists under a different tenant
                owner_tenant = self.lease_manager._task_tenants.get(task_id)
                if owner_tenant and owner_tenant != tenant_id:
                    return False, f"Task '{task_id}' belongs to tenant '{owner_tenant}', not '{tenant_id}'."
                return False, f"No lease record found for task '{task_id}'."

            now = self._now()
            if lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED) and now < lease.expires_at:
                return False, f"Task '{task_id}' is currently held by active worker '{lease.worker_id}' until {lease.expires_at}."

            if lease.status in (LeaseStatus.EXPIRED, LeaseStatus.RELEASED) or now >= lease.expires_at:
                return True, f"Task '{task_id}' lease is expired/released and eligible for reclaim."

            return False, f"Task '{task_id}' is in non-reclaimable state '{lease.status}'."

    def reclaim(
        self,
        task_id: str,
        tenant_id: str,
        standby_worker_id: str,
        lease_ttl_seconds: int = 30,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskLeaseContract:
        """
        Atomically reclaim an expired task lease on behalf of a standby worker.
        Enforces tenant isolation, verifies expiration, and mints a new TaskLeaseContract
        with a strictly incremented fencing token via LeaseManager.acquire().
        """
        if not task_id or not task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not standby_worker_id or not standby_worker_id.strip():
            raise ValueError("standby_worker_id must be non-empty.")

        with self._lock:
            # 1. Check Completed State
            if task_id in self._completed_tasks:
                raise LeaseConflictError(f"Cannot reclaim completed task '{task_id}'.")

            # 2. Check Tenant Isolation
            owner_tenant = self.lease_manager._task_tenants.get(task_id)
            if owner_tenant is not None and owner_tenant != tenant_id:
                raise UnauthorizedWorkerError(
                    f"Cross-tenant reclaim denied: Task '{task_id}' belongs to tenant '{owner_tenant}'."
                )

            # 3. Check Existing Lease Existence
            current_lease = self.lease_manager.get_lease(task_id, tenant_id=tenant_id)
            if current_lease is None:
                raise LeaseNotFoundError(f"No lease record found for task '{task_id}'.")

            # 4. Check Active Status (Premature Reclaim Guard)
            now = self._now()
            if current_lease.status in (LeaseStatus.ACQUIRED, LeaseStatus.RENEWED) and now < current_lease.expires_at:
                raise LeaseConflictError(
                    f"Cannot reclaim task '{task_id}': active lease held by worker '{current_lease.worker_id}' until {current_lease.expires_at}."
                )

            # 5. Atomically acquire new lease on behalf of standby worker
            reclaim_metadata = {
                **(metadata or {}),
                "reclaimed_from_worker": current_lease.worker_id,
                "reclaimed_from_lease": current_lease.lease_id,
                "reclaim_timestamp": now.isoformat(),
            }

            new_lease = self.lease_manager.acquire(
                task_id=task_id,
                tenant_id=tenant_id,
                worker_id=standby_worker_id,
                lease_ttl_seconds=lease_ttl_seconds,
                metadata=reclaim_metadata,
            )

            return new_lease
