"""Phase 12.3: Heartbeat & Auto-Renewal Daemon.
Maintains worker liveness telemetry and autonomously renews active task leases
against the LeaseManager to prevent premature lease expiration during long-running tasks.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, RLock, Thread
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.contracts.leasing import (
    LeaseError,
    TaskLeaseContract,
    WorkerHeartbeatContract,
    WorkerStatus,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager


@dataclass
class HeartbeatDaemonConfig:
    """Configuration for worker heartbeat emission and automated lease renewal."""
    worker_id: str
    tenant_id: str
    hostname: str = "localhost"
    heartbeat_interval_seconds: float = 1.0
    lease_extension_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HeartbeatRenewalDaemon:
    """
    Dedicated worker background daemon responsible for:
    1. Emitting periodic WorkerHeartbeatContract signals.
    2. Autonomously executing lease renewals for all actively processed tasks.
    3. Handling renewal failures gracefully when leases are revoked or expired.
    4. Deterministic manual tick triggers for fast, synchronous testing.
    """

    def __init__(
        self,
        lease_manager: InMemoryLeaseManager,
        config: HeartbeatDaemonConfig,
    ) -> None:
        if not config.worker_id or not config.worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        if not config.tenant_id or not config.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if config.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be strictly positive > 0.")

        self.lease_manager = lease_manager
        self.config = config

        self._lock = RLock()
        # task_id -> lease_id mapping of actively tracked tasks
        self._tracked_leases: Dict[str, str] = {}
        # task_id -> last renewal error if any
        self._renewal_errors: Dict[str, str] = {}

        # Daemon lifecycle control
        self._status: WorkerStatus = WorkerStatus.ACTIVE
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._heartbeat_count: int = 0
        self._renewal_tick_count: int = 0

    @property
    def is_running(self) -> bool:
        """Check if the background renewal loop is actively running."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> WorkerStatus:
        with self._lock:
            return self._status

    def set_status(self, status: WorkerStatus) -> None:
        """Update the operational status of the worker daemon."""
        with self._lock:
            self._status = status

    def register_lease(self, task_id: str, lease_id: str) -> None:
        """Register an active task lease for automated background heartbeating and renewal."""
        if not task_id or not lease_id:
            raise ValueError("task_id and lease_id must be non-empty.")
        with self._lock:
            self._tracked_leases[task_id] = lease_id
            self._renewal_errors.pop(task_id, None)

    def unregister_lease(self, task_id: str) -> Optional[str]:
        """Unregister a task lease when task finishes execution or is released."""
        with self._lock:
            self._renewal_errors.pop(task_id, None)
            return self._tracked_leases.pop(task_id, None)

    def get_tracked_leases(self) -> Dict[str, str]:
        """Get copy of currently tracked task_id -> lease_id mapping."""
        with self._lock:
            return dict(self._tracked_leases)

    def get_renewal_error(self, task_id: str) -> Optional[str]:
        """Get the latest renewal failure message for a task if one occurred."""
        with self._lock:
            return self._renewal_errors.get(task_id)

    def emit_heartbeat(self) -> WorkerHeartbeatContract:
        """
        Generate and return a structured WorkerHeartbeatContract.
        Carries worker liveness, host telemetry, and currently held active leases.
        """
        with self._lock:
            self._heartbeat_count += 1
            active_leases_list = list(self._tracked_leases.values())
            return WorkerHeartbeatContract(
                worker_id=self.config.worker_id,
                hostname=self.config.hostname,
                active_leases=active_leases_list,
                last_heartbeat_at=datetime.now(timezone.utc),
                status=self._status,
                metadata={
                    **self.config.metadata,
                    "heartbeat_sequence": self._heartbeat_count,
                    "tenant_id": self.config.tenant_id,
                },
            )

    def tick_renewals(self) -> Dict[str, bool]:
        """
        Execute one synchronous renewal tick for all actively tracked task leases.
        Returns a dict of task_id -> success_boolean.
        If a renewal fails (e.g. lease expired or revoked), unregisters the task and records the error.
        """
        results: Dict[str, bool] = {}
        with self._lock:
            self._renewal_tick_count += 1
            current_tasks = list(self._tracked_leases.items())

        for task_id, lease_id in current_tasks:
            try:
                self.lease_manager.renew(
                    task_id=task_id,
                    lease_id=lease_id,
                    worker_id=self.config.worker_id,
                    tenant_id=self.config.tenant_id,
                    extension_seconds=self.config.lease_extension_seconds,
                )
                results[task_id] = True
            except LeaseError as ex:
                results[task_id] = False
                with self._lock:
                    self._renewal_errors[task_id] = str(ex.detail)
                    # Stop tracking unrenewable/expired/revoked leases
                    self._tracked_leases.pop(task_id, None)
            except Exception as ex:
                results[task_id] = False
                with self._lock:
                    self._renewal_errors[task_id] = str(ex)
                    self._tracked_leases.pop(task_id, None)

        return results

    def _loop(self) -> None:
        """Internal background thread worker loop."""
        interval = self.config.heartbeat_interval_seconds
        while not self._stop_event.is_set():
            # 1. Execute renewal tick for all active leases
            self.tick_renewals()
            # 2. Emit worker liveness heartbeat
            self.emit_heartbeat()
            # 3. Sleep until next cycle or stop signal
            self._stop_event.wait(timeout=interval)

    def start(self) -> None:
        """Start the background heartbeat and auto-renewal loop in a dedicated thread."""
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            self._status = WorkerStatus.ACTIVE
            self._thread = Thread(
                target=self._loop,
                name=f"HeartbeatDaemon-{self.config.worker_id}",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Gracefully signal the daemon to stop and wait for loop termination."""
        with self._lock:
            if not self.is_running:
                return
            self._stop_event.set()
            self._status = WorkerStatus.STOPPED

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            with self._lock:
                self._thread = None
