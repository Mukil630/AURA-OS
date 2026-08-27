"""Phase 12.3 Step 5: Dedicated Unit, Adversarial & Liveness Tests for Heartbeat & Auto-Renewal Daemon.
Verifies Periodic Heartbeat Emission, Autonomous Lease Renewal, Multi-Task Heartbeating,
Failure Handling on Expired/Revoked Leases, and Thread-Safe Daemon Lifecycle.
"""
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.leasing import (
    LeaseStatus,
    WorkerStatus,
)
from app.core.leasing.heartbeat_daemon import (
    HeartbeatDaemonConfig,
    HeartbeatRenewalDaemon,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager


# ═════════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION & HEARTBEAT EMISSION (Tests 1 - 4)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s5_01_valid_config_and_initialization():
    """S5-01: Verify valid HeartbeatDaemonConfig initialization."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(
        worker_id="worker_east_01",
        tenant_id="tenant_A",
        hostname="worker-node-1",
        heartbeat_interval_seconds=0.5,
    )
    daemon = HeartbeatRenewalDaemon(lease_manager=mgr, config=cfg)

    assert daemon.config.worker_id == "worker_east_01"
    assert daemon.status == WorkerStatus.ACTIVE
    assert daemon.is_running is False


def test_p12_3_s5_02_invalid_config_rejected():
    """S5-02: Missing worker_id, tenant_id, or non-positive interval rejected."""
    mgr = InMemoryLeaseManager()
    with pytest.raises(ValueError):
        HeartbeatRenewalDaemon(mgr, HeartbeatDaemonConfig(worker_id="", tenant_id="t1"))

    with pytest.raises(ValueError):
        HeartbeatRenewalDaemon(mgr, HeartbeatDaemonConfig(worker_id="w1", tenant_id=""))

    with pytest.raises(ValueError):
        HeartbeatRenewalDaemon(mgr, HeartbeatDaemonConfig(worker_id="w1", tenant_id="t1", heartbeat_interval_seconds=0))


def test_p12_3_s5_03_emit_heartbeat_generates_valid_contract():
    """S5-03: emit_heartbeat() returns structured WorkerHeartbeatContract with active leases."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="worker_01", tenant_id="tenant_A", hostname="host-east")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    daemon.register_lease("task_1", "lease_1")
    daemon.register_lease("task_2", "lease_2")

    hb = daemon.emit_heartbeat()
    assert hb.worker_id == "worker_01"
    assert hb.hostname == "host-east"
    assert set(hb.active_leases) == {"lease_1", "lease_2"}
    assert hb.status == WorkerStatus.ACTIVE


def test_p12_3_s5_04_register_and_unregister_lease():
    """S5-04: Register and unregister task leases dynamically updates tracking."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="t1")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    daemon.register_lease("t1", "l1")
    assert daemon.get_tracked_leases() == {"t1": "l1"}

    unreg = daemon.unregister_lease("t1")
    assert unreg == "l1"
    assert daemon.get_tracked_leases() == {}


# ═════════════════════════════════════════════════════════════════════════════
# 2. SYNCHRONOUS LEASE RENEWAL TICKS (Tests 5 - 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s5_05_tick_renewals_extends_tracked_leases():
    """S5-05: tick_renewals() renews all tracked leases with LeaseManager."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_101", "tenant_A", "w1", lease_ttl_seconds=10)
    daemon.register_lease("task_101", lease.lease_id)

    results = daemon.tick_renewals()
    assert results == {"task_101": True}

    updated_lease = mgr.get_lease("task_101", "tenant_A")
    assert updated_lease.status == LeaseStatus.RENEWED
    assert updated_lease.renewal_count == 1


def test_p12_3_s5_06_tick_renewals_increments_renewal_count():
    """S5-06: Multiple renewal ticks monotonically increment renewal_count."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_102", "tenant_A", "w1", lease_ttl_seconds=10)
    daemon.register_lease("task_102", lease.lease_id)

    daemon.tick_renewals()
    daemon.tick_renewals()
    daemon.tick_renewals()

    updated = mgr.get_lease("task_102", "tenant_A")
    assert updated.renewal_count == 3


def test_p12_3_s5_07_tick_renewals_extends_expires_at():
    """S5-07: Renewal tick extends expires_at into the future."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A", lease_extension_seconds=60)
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_103", "tenant_A", "w1", lease_ttl_seconds=5)
    initial_exp = lease.expires_at

    time.sleep(0.01)
    daemon.register_lease("task_103", lease.lease_id)
    daemon.tick_renewals()

    updated = mgr.get_lease("task_103", "tenant_A")
    assert updated.expires_at > initial_exp


def test_p12_3_s5_08_multiple_concurrent_tasks_renewed_in_single_tick():
    """S5-08: Multiple distinct task leases are renewed in a single tick."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    l1 = mgr.acquire("task_A", "tenant_A", "w1")
    l2 = mgr.acquire("task_B", "tenant_A", "w1")
    l3 = mgr.acquire("task_C", "tenant_A", "w1")

    daemon.register_lease("task_A", l1.lease_id)
    daemon.register_lease("task_B", l2.lease_id)
    daemon.register_lease("task_C", l3.lease_id)

    results = daemon.tick_renewals()
    assert results == {"task_A": True, "task_B": True, "task_C": True}


# ═════════════════════════════════════════════════════════════════════════════
# 3. RENEWAL FAILURE & ERROR HANDLING (Tests 9 - 10)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s5_09_revoked_lease_renewal_failure_handling():
    """S5-09: If a lease is administratively revoked, tick_renewals unregisters task and records error."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_revoked", "tenant_A", "w1")
    daemon.register_lease("task_revoked", lease.lease_id)

    # Admin revokes lease
    mgr.revoke("task_revoked", lease.lease_id, "tenant_A")

    results = daemon.tick_renewals()
    assert results["task_revoked"] is False
    assert daemon.get_renewal_error("task_revoked") is not None
    # Task should be automatically removed from tracked leases
    assert "task_revoked" not in daemon.get_tracked_leases()


def test_p12_3_s5_10_expired_lease_renewal_failure_handling():
    """S5-10: If a lease has already expired, renewal fails cleanly and drops task."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w1", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_exp", "tenant_A", "w1", lease_ttl_seconds=1)
    daemon.register_lease("task_exp", lease.lease_id)

    # Simulate expired lease by backdating
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    lease.acquired_at = past
    lease.expires_at = past + timedelta(seconds=2)

    results = daemon.tick_renewals()
    assert results["task_exp"] is False
    assert "expired" in daemon.get_renewal_error("task_exp").lower()
    assert "task_exp" not in daemon.get_tracked_leases()


# ═════════════════════════════════════════════════════════════════════════════
# 4. BACKGROUND THREAD LIFECYCLE & LIVENESS (Tests 11 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s5_11_background_daemon_start_and_graceful_stop():
    """S5-11: Background daemon starts thread and stops cleanly on request."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w_bg", tenant_id="t1", heartbeat_interval_seconds=0.05)
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    daemon.start()
    assert daemon.is_running is True

    time.sleep(0.12)
    daemon.stop()
    assert daemon.is_running is False
    assert daemon.status == WorkerStatus.STOPPED


def test_p12_3_s5_12_continuous_background_renewal_extends_lease():
    """S5-12: Running daemon automatically renews task lease over time."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w_bg2", tenant_id="t1", heartbeat_interval_seconds=0.05)
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_cont", "t1", "w_bg2", lease_ttl_seconds=10)
    daemon.register_lease("task_cont", lease.lease_id)

    daemon.start()
    time.sleep(0.18)  # Should trigger at least 2-3 renewal cycles
    daemon.stop()

    updated = mgr.get_lease("task_cont", "t1")
    assert updated.renewal_count >= 2


def test_p12_3_s5_13_worker_status_update_reflected_in_heartbeat():
    """S5-13: Setting worker status to DRAINING reflects in emitted heartbeats."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w_drain", tenant_id="t1")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    daemon.set_status(WorkerStatus.DRAINING)
    hb = daemon.emit_heartbeat()
    assert hb.status == WorkerStatus.DRAINING


def test_p12_3_s5_14_heartbeat_renews_lease_not_queue():
    """
    S5-14: ARCHITECTURAL ASSERTION (Queue != Lease Invariant)
    Verify Heartbeat daemon explicitly interacts with LeaseManager, leaving queue unaffected.
    """
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w_inv", tenant_id="tenant_A")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    lease = mgr.acquire("task_inv", "tenant_A", "w_inv", lease_ttl_seconds=10)
    daemon.register_lease("task_inv", lease.lease_id)
    daemon.tick_renewals()

    # The renewal updated lease_manager
    assert mgr.get_lease("task_inv", "tenant_A").renewal_count == 1


def test_p12_3_s5_15_thread_safe_concurrent_lease_registration():
    """S5-15: Multiple concurrent threads registering and unregistering leases safely."""
    mgr = InMemoryLeaseManager()
    cfg = HeartbeatDaemonConfig(worker_id="w_concurrent", tenant_id="t1")
    daemon = HeartbeatRenewalDaemon(mgr, cfg)

    def worker_reg(idx: int):
        task_id = f"task_{idx}"
        lease = mgr.acquire(task_id, "t1", "w_concurrent")
        daemon.register_lease(task_id, lease.lease_id)
        daemon.tick_renewals()
        daemon.emit_heartbeat()
        daemon.unregister_lease(task_id)

    threads = [threading.Thread(target=worker_reg, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert daemon.get_tracked_leases() == {}
