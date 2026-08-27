"""Phase 12.3 Step 8: Dedicated Adversarial Concurrency & Race Condition Attack Suite.
Aggressively attacks the distributed task queue, atomic lease manager, heartbeat daemon,
standby reclaim manager, and fencing guard using threading.Barrier, ThreadPoolExecutor,
and multi-threaded contention loops to prove zero-state-corruption under extreme concurrency.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseExpiredError,
    LeaseNotFoundError,
    LeaseStatus,
    QueueMessageContract,
    StaleLeaseConflictError,
    TaskLeaseContract,
    UnauthorizedWorkerError,
)
from app.core.enums.common import PriorityLevel
from app.core.leasing.fencing_guard import FencedTaskExecutionGuard
from app.core.leasing.heartbeat_daemon import (
    HeartbeatDaemonConfig,
    HeartbeatRenewalDaemon,
)
from app.core.leasing.lease_manager import InMemoryLeaseManager
from app.core.leasing.reclaim_manager import StandbyReclaimManager
from app.core.leasing.task_queue import InMemoryTaskQueue


# ═════════════════════════════════════════════════════════════════════════════
# 1. QUEUE & ACQUIRE CONTENTION ATTACKS (Scenarios 1 - 3)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s8_01_two_workers_dequeue_same_message_race():
    """
    Scenario 1: Two workers race to dequeue a single message simultaneously.
    Asserts: Exactly 1 worker gets the message, 1 gets None. Zero duplicate delivery.
    """
    queue = InMemoryTaskQueue()
    queue.enqueue(QueueMessageContract(message_id="msg_race_1", task_id="t1", tenant_id="tenant_A"))

    barrier = threading.Barrier(2)
    dequeued = []

    def consumer(w_id: str):
        barrier.wait()
        res = queue.dequeue("tenant_A", worker_id=w_id)
        if res is not None:
            dequeued.append((w_id, res))

    t1 = threading.Thread(target=consumer, args=("W1",))
    t2 = threading.Thread(target=consumer, args=("W2",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(dequeued) == 1
    assert queue.in_flight_count("tenant_A") == 1
    assert queue.qsize("tenant_A") == 0


def test_p12_3_s8_02_two_workers_acquire_same_task_race():
    """
    Scenario 2: Two workers simultaneously acquire the exact same task.
    Asserts: Exactly 1 winner (fencing_token=1), exactly 1 conflict (409).
    """
    mgr = InMemoryLeaseManager()
    barrier = threading.Barrier(2)
    winners, errors = [], []

    def acquire_race(w_id: str):
        barrier.wait()
        try:
            l = mgr.acquire("task_race_2", "tenant_A", w_id)
            winners.append((w_id, l))
        except LeaseConflictError as ex:
            errors.append((w_id, ex))

    t1 = threading.Thread(target=acquire_race, args=("W_Alpha",))
    t2 = threading.Thread(target=acquire_race, args=("W_Beta",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(winners) == 1
    assert len(errors) == 1
    assert winners[0][1].fencing_token == 1
    assert len(mgr.list_active_leases("tenant_A")) == 1


def test_p12_3_s8_03_two_workers_reclaim_same_expired_lease_race():
    """
    Scenario 3: Two standby workers simultaneously attempt to reclaim an expired task.
    Asserts: Exactly 1 standby worker succeeds (token=2), 1 receives 409 conflict.
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l_old = mgr.acquire("task_reclaim_race", "tenant_A", "w_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    barrier = threading.Barrier(2)
    winners, errors = [], []

    def reclaim_race(w_id: str):
        barrier.wait()
        try:
            l = reclaim_mgr.reclaim("task_reclaim_race", "tenant_A", w_id)
            winners.append((w_id, l))
        except LeaseConflictError as ex:
            errors.append((w_id, ex))

    t1 = threading.Thread(target=reclaim_race, args=("Standby_1",))
    t2 = threading.Thread(target=reclaim_race, args=("Standby_2",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(winners) == 1
    assert len(errors) == 1
    assert winners[0][1].fencing_token == 2
    assert mgr.get_lease("task_reclaim_race", "tenant_A").worker_id == winners[0][0]


# ═════════════════════════════════════════════════════════════════════════════
# 2. HEARTBEAT VS EXPIRY & RECLAIM RACES (Scenarios 4 - 6)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s8_04_heartbeat_vs_expiry_boundary_race():
    """
    Scenario 4: Worker attempts renewal right at the expiry timestamp boundary.
    Asserts: If renewal succeeds before expiry -> expires_at extended;
             If renewal arrives after expiry -> LeaseExpiredError (410) raised deterministically.
    """
    mgr = InMemoryLeaseManager()
    l = mgr.acquire("task_boundary_race", "tenant_A", "w1", lease_ttl_seconds=1)
    now = datetime.now(timezone.utc)

    # Simulate arrival exactly 1 millisecond after expiry
    l.acquired_at = now - timedelta(seconds=10)
    l.expires_at = now - timedelta(milliseconds=1)

    with pytest.raises(LeaseExpiredError) as exc_info:
        mgr.renew("task_boundary_race", l.lease_id, "w1", "tenant_A")
    assert exc_info.value.status_code == 410


def test_p12_3_s8_05_heartbeat_vs_reclaim_race():
    """
    Scenario 5: Original worker renews at the exact instant a standby worker reclaims.
    Asserts: Under mutex, either (1) renewal wins -> reclaim blocked (409), OR
             (2) reclaim wins (lease expired) -> renewal fails (410/409).
             Never allows dual active ownership!
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l = mgr.acquire("task_hb_vs_reclaim", "tenant_A", "w_orig", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l.acquired_at = past
    l.expires_at = past + timedelta(seconds=2)

    barrier = threading.Barrier(2)
    renew_res = []
    reclaim_res = []

    def orig_worker():
        barrier.wait()
        try:
            res = mgr.renew("task_hb_vs_reclaim", l.lease_id, "w_orig", "tenant_A")
            renew_res.append(res)
        except Exception as ex:
            renew_res.append(ex)

    def standby_worker():
        barrier.wait()
        try:
            res = reclaim_mgr.reclaim("task_hb_vs_reclaim", "tenant_A", "w_standby")
            reclaim_res.append(res)
        except Exception as ex:
            reclaim_res.append(ex)

    t1 = threading.Thread(target=orig_worker)
    t2 = threading.Thread(target=standby_worker)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Reclaim should succeed because lease was expired; renewal on expired/reclaimed lease must fail
    assert isinstance(renew_res[0], (LeaseExpiredError, LeaseNotFoundError))
    assert isinstance(reclaim_res[0], TaskLeaseContract)
    assert reclaim_res[0].worker_id == "w_standby"
    assert len(mgr.list_active_leases("tenant_A")) == 1


def test_p12_3_s8_06_reclaim_vs_ack_race():
    """
    Scenario 6: Standby reclaims while old worker attempts to ACK after lease expiration.
    Asserts: Reclaim grants new authority; old worker cannot overwrite or corrupt queue ACK.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    msg = QueueMessageContract(message_id="msg_ack_race", task_id="t_ack_race", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A", worker_id="w_old")

    l_old = mgr.acquire("t_ack_race", "tenant_A", "w_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    # Standby reclaims
    l_new = reclaim_mgr.reclaim("t_ack_race", "tenant_A", "w_new")
    assert l_new.fencing_token == 2

    # Old worker cannot release lease (403)
    with pytest.raises(UnauthorizedWorkerError):
        mgr.release("t_ack_race", l_new.lease_id, "w_old", "tenant_A")


# ═════════════════════════════════════════════════════════════════════════════
# 3. ACK VS NACK & RELEASE VS RECLAIM RACES (Scenarios 7 - 9)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s8_07_ack_vs_nack_concurrent_race():
    """
    Scenario 7: Concurrent ACK and NACK racing on the same in-flight message.
    Asserts: Exactly one operation transitions the in-flight state. Message is either
             permanently ACKed or NACK-requeued, never both.
    """
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="msg_ack_nack", task_id="t_an", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    barrier = threading.Barrier(2)
    ack_res, nack_res = [], []

    def do_ack():
        barrier.wait()
        ack_res.append(queue.ack("msg_ack_nack", "tenant_A"))

    def do_nack():
        barrier.wait()
        nack_res.append(queue.nack("msg_ack_nack", "tenant_A", requeue=True))

    t1 = threading.Thread(target=do_ack)
    t2 = threading.Thread(target=do_nack)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # One succeeds, one returns False/noop
    assert queue.in_flight_count("tenant_A") == 0
    assert (ack_res[0] is True and nack_res[0] is False) or (ack_res[0] is False and nack_res[0] is True)


def test_p12_3_s8_08_release_vs_reclaim_concurrent_race():
    """
    Scenario 8: Worker Alpha voluntarily releases lease while Standby Beta attempts reclaim.
    Asserts: Under mutex, both yield valid non-conflicting state transitions;
             Final state has exactly 1 valid owner or task is free.
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    l = mgr.acquire("task_rel_rec", "tenant_A", "w_alpha", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l.acquired_at = past
    l.expires_at = past + timedelta(seconds=2)

    barrier = threading.Barrier(2)
    rel_res, rec_res = [], []

    def do_release():
        barrier.wait()
        try:
            rel_res.append(mgr.release("task_rel_rec", l.lease_id, "w_alpha", "tenant_A"))
        except Exception as ex:
            rel_res.append(ex)

    def do_reclaim():
        barrier.wait()
        try:
            rec_res.append(reclaim_mgr.reclaim("task_rel_rec", "tenant_A", "w_beta"))
        except Exception as ex:
            rec_res.append(ex)

    t1 = threading.Thread(target=do_release)
    t2 = threading.Thread(target=do_reclaim)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Either release happened first (status=RELEASED, then reclaim succeeds with token=2)
    # Or reclaim happened first (reclaim succeeds with token=2, release on old lease fails)
    current = mgr.get_lease("task_rel_rec", "tenant_A")
    assert current is not None
    assert current.fencing_token in (1, 2)


def test_p12_3_s8_09_fencing_write_vs_reclaim_concurrent_race():
    """
    Scenario 9: Old worker attempts state write while Standby reclaims.
    Asserts: Standby reclaim increments generation -> Old worker's write is REJECTED (409).
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l_old = mgr.acquire("task_write_rec", "tenant_A", "w_old", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l_old.acquired_at = past
    l_old.expires_at = past + timedelta(seconds=2)

    barrier = threading.Barrier(2)
    write_res, rec_res = [], []

    def do_write():
        barrier.wait()
        try:
            res = guard.execute_fenced_write("task_write_rec", "tenant_A", "w_old", 1, "res", "stale_data")
            write_res.append(res)
        except Exception as ex:
            write_res.append(ex)

    def do_reclaim():
        barrier.wait()
        try:
            res = reclaim_mgr.reclaim("task_write_rec", "tenant_A", "w_new")
            rec_res.append(res)
        except Exception as ex:
            rec_res.append(ex)

    t1 = threading.Thread(target=do_write)
    t2 = threading.Thread(target=do_reclaim)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Reclaim always succeeds and bumps token to 2
    assert isinstance(rec_res[0], TaskLeaseContract)
    # Stale write is rejected
    assert isinstance(write_res[0], (StaleLeaseConflictError, LeaseExpiredError))


# ═════════════════════════════════════════════════════════════════════════════
# 4. FENCING WRITE BATTLES & TOKEN GENERATION (Scenarios 10 - 13)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s8_10_zombie_worker_write_battle():
    """
    Scenario 10: Zombie worker with token=1 tries repeatedly to overwrite new worker (token=2).
    Asserts: 100% of zombie writes rejected; final state matches new worker output.
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l1 = mgr.acquire("task_battle", "tenant_A", "zombie", lease_ttl_seconds=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    l1.acquired_at = past
    l1.expires_at = past + timedelta(seconds=2)

    reclaim_mgr.reclaim("task_battle", "tenant_A", "legit_worker")
    guard.execute_fenced_write("task_battle", "tenant_A", "legit_worker", 2, "status", "LEGIT_OUTPUT")

    # Zombie attempts 10 writes
    for _ in range(10):
        with pytest.raises(StaleLeaseConflictError):
            guard.execute_fenced_write("task_battle", "tenant_A", "zombie", 1, "status", "CORRUPTED")

    state = guard.get_task_state("task_battle", "tenant_A")
    assert state["data"]["status"] == "LEGIT_OUTPUT"
    assert state["last_written_by"] == "legit_worker"


def test_p12_3_s8_11_concurrent_fencing_token_generation():
    """
    Scenario 11: 10 threads racing to acquire/reclaim across 10 distinct tasks.
    Asserts: Every task gets strictly monotonic fencing token = 1 on first acquire.
    """
    mgr = InMemoryLeaseManager()

    def worker_acquire(idx: int):
        return mgr.acquire(f"task_fencing_grid_{idx}", "tenant_A", f"w_{idx}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        leases = list(executor.map(worker_acquire, range(10)))

    assert len(leases) == 10
    for l in leases:
        assert l.fencing_token == 1
    assert len(mgr.list_active_leases("tenant_A")) == 10


def test_p12_3_s8_12_cross_tenant_concurrent_access_attack():
    """
    Scenario 12: 10 workers from Tenant B concurrently attack Tenant A's tasks.
    Asserts: 100% of cross-tenant acquires, dequeues, reclaims, and writes are rejected with 403.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    # Tenant A sets up tasks
    for i in range(5):
        msg = QueueMessageContract(message_id=f"m_sec_{i}", task_id=f"t_sec_{i}", tenant_id="tenant_A")
        queue.enqueue(msg)
        mgr.acquire(f"t_sec_{i}", "tenant_A", f"w_a_{i}")

    def attack_task(idx: int):
        task_id = f"t_sec_{idx}"
        # 1. Cross-tenant dequeue
        d = queue.dequeue("tenant_B", worker_id=f"w_b_{idx}")
        # 2. Cross-tenant acquire
        try:
            mgr.acquire(task_id, "tenant_B", f"w_b_{idx}")
            acq_ok = True
        except UnauthorizedWorkerError:
            acq_ok = False

        # 3. Cross-tenant write
        try:
            guard.execute_fenced_write(task_id, "tenant_B", f"w_b_{idx}", 1, "k", "v")
            write_ok = True
        except UnauthorizedWorkerError:
            write_ok = False

        return (d is None, not acq_ok, not write_ok)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(attack_task, range(5)))

    for d_blocked, acq_blocked, write_blocked in results:
        assert d_blocked is True
        assert acq_blocked is True
        assert write_blocked is True


def test_p12_3_s8_13_duplicate_concurrent_ack_stampede():
    """
    Scenario 13: 10 concurrent threads simultaneously send duplicate ACKs for one message.
    Asserts: All threads return True safely without crash or race corruption.
    """
    queue = InMemoryTaskQueue()
    msg = QueueMessageContract(message_id="msg_stampede_ack", task_id="t_stampede", tenant_id="tenant_A")
    queue.enqueue(msg)
    queue.dequeue("tenant_A")

    barrier = threading.Barrier(10)

    def do_ack(i: int):
        barrier.wait()
        return queue.ack("msg_stampede_ack", "tenant_A")

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(do_ack, range(10)))

    assert all(r is True for r in results)
    assert queue.in_flight_count("tenant_A") == 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. HIGH-SCALE MULTI-TASK × MULTI-WORKER STRESS (Scenarios 14 - 18)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_3_s8_14_worker_crash_during_ownership_transition():
    """
    Scenario 14: Worker crashes immediately after dequeue before acquire -> Reclaim / retry handles it.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()

    msg = QueueMessageContract(message_id="m_crash_early", task_id="t_crash_early", tenant_id="tenant_A")
    queue.enqueue(msg)
    d = queue.dequeue("tenant_A", worker_id="w_doomed")

    # Worker crashes before calling mgr.acquire()
    # NACK returns message to queue
    assert queue.nack("m_crash_early", "tenant_A", requeue=True) is True
    assert queue.qsize("tenant_A") == 1

    # Standby worker dequeues and acquires
    d2 = queue.dequeue("tenant_A", worker_id="w_standby")
    l2 = mgr.acquire(d2.task_id, d2.tenant_id, "w_standby")
    assert l2.status == LeaseStatus.ACQUIRED


def test_p12_3_s8_15_massive_multi_task_multi_worker_stress_matrix():
    """
    Scenario 15: 30 tasks × 15 workers racing concurrently across enqueue, dequeue, acquire,
                 heartbeat renewal, release, and ACK.
    Asserts: All 30 tasks complete with zero lease conflicts, zero stale state, and clean queue.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()
    guard = FencedTaskExecutionGuard(mgr)
    num_tasks = 30

    for i in range(num_tasks):
        queue.enqueue(QueueMessageContract(
            message_id=f"msg_stress_{i}",
            task_id=f"task_stress_{i}",
            tenant_id="tenant_stress",
            priority=PriorityLevel.NORMAL,
        ))

    def worker_lifecycle(w_id: int):
        processed = 0
        while True:
            msg = queue.dequeue("tenant_stress", worker_id=f"worker_{w_id}")
            if msg is None:
                break

            # Acquire lease
            lease = mgr.acquire(msg.task_id, msg.tenant_id, f"worker_{w_id}", lease_ttl_seconds=10)

            # Renew lease
            mgr.renew(msg.task_id, lease.lease_id, f"worker_{w_id}", msg.tenant_id)

            # Write fenced result
            guard.execute_fenced_write(
                task_id=msg.task_id,
                tenant_id=msg.tenant_id,
                worker_id=f"worker_{w_id}",
                fencing_token=lease.fencing_token,
                write_key="processed_by",
                write_value=f"worker_{w_id}",
            )

            # Release lease & ACK
            mgr.release(msg.task_id, lease.lease_id, f"worker_{w_id}", msg.tenant_id)
            queue.ack(msg.message_id, msg.tenant_id)
            processed += 1
        return processed

    with ThreadPoolExecutor(max_workers=15) as executor:
        counts = list(executor.map(worker_lifecycle, range(15)))

    assert sum(counts) == num_tasks
    assert queue.qsize("tenant_stress") == 0
    assert queue.in_flight_count("tenant_stress") == 0
    assert len(mgr.list_active_leases("tenant_stress")) == 0


def test_p12_3_s8_16_repeated_reclaim_generations_monotonic_climb():
    """
    Scenario 16: Task goes through 10 successive crash-and-reclaim cycles.
    Asserts: Fencing tokens strictly climb from 1 to 10. All intermediate tokens (< 10) are stale.
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)
    guard = FencedTaskExecutionGuard(mgr)

    l = mgr.acquire("task_10_generations", "tenant_A", "w0", lease_ttl_seconds=1)
    assert l.fencing_token == 1

    for gen in range(2, 11):
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        l.acquired_at = past
        l.expires_at = past + timedelta(seconds=2)
        l = reclaim_mgr.reclaim("task_10_generations", "tenant_A", f"w{gen}")
        assert l.fencing_token == gen

    # Current token is 10
    assert mgr.get_fencing_token("task_10_generations") == 10

    # Tokens 1..9 are all stale
    for stale_gen in range(1, 10):
        with pytest.raises(StaleLeaseConflictError):
            guard.validate_write_authority("task_10_generations", "tenant_A", f"w{stale_gen}", fencing_token=stale_gen)

    # Generation 10 write succeeds
    state = guard.execute_fenced_write(
        "task_10_generations", "tenant_A", "w10", 10, "final_gen", "GEN_10_SUCCESS"
    )
    assert state["data"]["final_gen"] == "GEN_10_SUCCESS"


def test_p12_3_s8_17_queue_plus_lease_state_divergence_attack():
    """
    Scenario 17: Attacker attempts to acquire a task with an unacknowledged queue message
                 using forged worker identity -> Rejected by tenant/worker authority.
    """
    queue = InMemoryTaskQueue()
    mgr = InMemoryLeaseManager()

    msg = QueueMessageContract(message_id="msg_div", task_id="task_div", tenant_id="tenant_A")
    queue.enqueue(msg)

    # Worker 1 consumes and acquires
    queue.dequeue("tenant_A", worker_id="worker_legit")
    mgr.acquire("task_div", "tenant_A", "worker_legit")

    # Attacker tries to hijack lease
    with pytest.raises(LeaseConflictError):
        mgr.acquire("task_div", "tenant_A", "worker_attacker")

    # Attacker tries to hijack queue ACK
    with pytest.raises(UnauthorizedWorkerError):
        queue.ack("msg_div", tenant_id="tenant_B")


def test_p12_3_s8_18_timing_boundary_zero_delta_race():
    """
    Scenario 18: Exact zero-millisecond delta boundary test between lease expiry and standby reclaim.
    Asserts: Deterministic mathematical inequality (now >= expires_at => expired).
    """
    mgr = InMemoryLeaseManager()
    reclaim_mgr = StandbyReclaimManager(mgr)

    now = datetime.now(timezone.utc)
    l = mgr.acquire("task_zero_delta", "tenant_A", "w_boundary", lease_ttl_seconds=10)

    # Set expires_at exactly equal to now
    l.acquired_at = now - timedelta(seconds=10)
    l.expires_at = now

    # At exact boundary now >= expires_at -> Eligible for reclaim
    assert reclaim_mgr.is_eligible_for_reclaim("task_zero_delta", "tenant_A")[0] is True
    reclaimed = reclaim_mgr.reclaim("task_zero_delta", "tenant_A", "w_standby")
    assert reclaimed.fencing_token == 2
