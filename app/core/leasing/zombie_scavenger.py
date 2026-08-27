"""Phase 12.4 Step 7: Auto-Expiry & Zombie Lock Scavenger Daemon.
Detects expired resource locks, reclaims abandoned resource ownerships from crashed/zombie workers,
triggers waiter wakeups, and enforces stale generation rejection on late releases.
"""
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional

from app.core.contracts.locking import LockStatus, ResourceLockContract
from app.core.leasing.resource_lock_manager import InMemoryResourceLockManager


class ZombieLockScavenger:
    """
    Autonomous background scavenger and on-demand sweeper for expired resource locks.
    Guarantees that crashed workers do not cause permanent resource starvation.
    """

    def __init__(
        self,
        lock_manager: InMemoryResourceLockManager,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self.lock_manager = lock_manager
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def scavenge_now(self) -> Dict[str, Any]:
        """
        Perform an immediate, thread-safe sweep of all expired resource locks across all tenants.
        Evicts expired contracts, frees resources, and triggers wakeups for eligible queued waiters.
        """
        now = datetime.now(timezone.utc)
        scavenged: List[ResourceLockContract] = []

        with self.lock_manager._lock:
            keys_to_check = list(self.lock_manager._active_locks.keys())
            for key in keys_to_check:
                current_locks = self.lock_manager._active_locks.get(key, [])
                valid_locks = []
                for l in current_locks:
                    if l.status == LockStatus.GRANTED and now < l.expires_at:
                        valid_locks.append(l)
                    else:
                        l.status = LockStatus.EXPIRED
                        scavenged.append(l)

                if valid_locks:
                    self.lock_manager._active_locks[key] = valid_locks
                else:
                    self.lock_manager._active_locks.pop(key, None)
                    self.lock_manager._resource_modes.pop(key, None)

                # If any lock on this resource expired, notify queued waiters
                if len(valid_locks) < len(current_locks):
                    self.lock_manager._notify_waiters(key)

        return {
            "scavenged_count": len(scavenged),
            "scavenged_locks": [
                {
                    "lock_id": l.lock_id,
                    "canonical_resource_id": l.canonical_resource_id,
                    "tenant_id": l.tenant_id,
                    "worker_id": l.worker_id,
                    "mode": l.mode,
                    "lock_generation": l.lock_generation,
                }
                for l in scavenged
            ],
            "timestamp": now.isoformat(),
        }

    def _scavenge_loop(self) -> None:
        """Internal background polling loop running as daemon."""
        while not self._stop_event.is_set():
            try:
                self.scavenge_now()
            except Exception:
                pass
            self._stop_event.wait(timeout=self.poll_interval_seconds)

    def start(self) -> None:
        """Start the background scavenger daemon thread."""
        if self._is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scavenge_loop, name="ZombieLockScavengerThread", daemon=True)
        self._thread.start()
        self._is_running = True

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background scavenger daemon thread."""
        if not self._is_running:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Return True if background scavenger daemon is active."""
        return self._is_running
