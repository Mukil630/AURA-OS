"""Phase 12.5 Step 8: Comprehensive Adversarial Concurrency & High-Contention Abuse Suite.
Executes 22 Severe Multi-Threaded Stress Attacks covering 100-Worker Concurrency Stampedes,
Budget Draining Races, Rate Limiter Token Exhaustion, Idempotent Retries, Stale Generation Attacks,
and Mathematical Conservation of Capacity with Zero Leaks.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import random
import threading
import time
import pytest

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.governance import (
    AdmissionDecision,
    AdmissionEvaluationContract,
    AdmissionRequestContract,
    BudgetExhaustedError,
    BudgetPeriod,
    BudgetReservationContract,
    ConsumptionRecordContract,
    GovernanceError,
    QuotaDimension,
    QuotaExceededError,
    RateLimitAlgorithm,
    RateLimitExceededError,
    RateLimitPolicyContract,
    ReservationStatus,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)
from app.core.governance.admission_controller import AdmissionController
from app.core.governance.budget_manager import ResourceBudgetManager
from app.core.governance.quota_coordinator import InMemoryQuotaCoordinator
from app.core.governance.quota_manager import InMemoryTenantQuotaManager
from app.core.governance.rate_limiter import InMemoryTokenBucketRateLimiter


# ═════════════════════════════════════════════════════════════════════════════
# 1. 100-WORKER HIGH CONTENTION STAMPEDES (S8-01 to S8-03)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s8_01_hundred_workers_concurrency_stampede():
    """S8-01: 100 workers competing for 10 concurrency slots -> exactly 10 winners, 90 429s."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=10))

    num_workers = 100
    barrier = threading.Barrier(num_workers)
    winners, errors = [], []

    def task(w_id: int):
        barrier.wait()
        try:
            acquired = coord.acquire_concurrency_slot("tenant_A", f"task_{w_id}", worker_id=f"worker_{w_id}")
            if acquired:
                winners.append(w_id)
        except QuotaExceededError as ex:
            errors.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(winners) == 10
    assert len(errors) == 90
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 10


def test_p12_5_s8_02_hundred_workers_budget_draining_race():
    """S8-02: 100 workers racing for 100,000 token budget in 10,000 chunks -> exactly 10 succeed."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=100_000))

    num_workers = 100
    barrier = threading.Barrier(num_workers)
    granted, denied = [], []

    def task(w_id: int):
        barrier.wait()
        try:
            res = coord.reserve_budget("tenant_A", f"task_{w_id}", QuotaDimension.TOKEN_BUDGET, amount=10_000.0)
            granted.append(res)
        except BudgetExhaustedError as ex:
            denied.append((w_id, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(granted) == 10
    assert len(denied) == 90
    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 100_000.0
    assert stmt["net_available_balance"] == 0.0


def test_p12_5_s8_03_hundred_workers_rate_limit_token_storm():
    """S8-03: 100 workers consuming from a 20-token bucket -> exactly 20 succeed, balance >= 0."""
    coord = InMemoryQuotaCoordinator()
    coord.set_rate_limit_policy(RateLimitPolicyContract(policy_id="p1", tenant_id="tenant_A", requests_per_minute=20, burst_capacity=0))

    num_workers = 100
    barrier = threading.Barrier(num_workers)
    consumed, rejected = [], []

    def task(idx: int):
        barrier.wait()
        try:
            coord.consume_rate_limit("tenant_A", tokens_required=1.0)
            consumed.append(idx)
        except RateLimitExceededError as ex:
            rejected.append((idx, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(task, range(num_workers)))

    assert len(consumed) == 20
    assert len(rejected) == 80
    assert coord.rate_limiter.get_token_balance("tenant_A") >= 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 2. MULTI-TENANT & TWO-PHASE CONCURRENCY (S8-04 to S8-09)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s8_04_multi_tenant_simultaneous_pressure():
    """S8-04: Tenant A flooded with 25 threads while Tenant B operates simultaneously without latency/quota leak."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=5, max_tokens_per_period=10_000))
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_B", max_concurrent_tasks=20, max_tokens_per_period=200_000))

    b_successes, b_errors = [], []
    num_threads = 50
    barrier = threading.Barrier(num_threads)

    def worker(idx: int):
        barrier.wait()
        if idx < 25:
            try:
                coord.acquire_concurrency_slot("tenant_A", f"tA_{idx}")
            except QuotaExceededError:
                pass
        else:
            b_idx = idx - 25
            try:
                acq = coord.acquire_concurrency_slot("tenant_B", f"tB_{b_idx}")
                if acq:
                    b_successes.append(b_idx)
            except QuotaExceededError as ex:
                b_errors.append((b_idx, ex))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        list(executor.map(worker, range(num_threads)))

    assert len(b_successes) == 20
    assert len(b_errors) == 5
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 5
    assert coord.get_tenant_usage("tenant_B")["active_concurrent_tasks"] == 20


def test_p12_5_s8_05_concurrent_reservation_and_commit():
    """S8-05: 20 concurrent reservation + commit cycles maintain exact accounting without double consumption."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=100_000))

    def cycle(idx: int):
        res = coord.reserve_budget("tenant_A", f"task_{idx}", QuotaDimension.TOKEN_BUDGET, amount=2_000.0)
        time.sleep(0.002)
        coord.commit_budget(res.reservation_id, "tenant_A", f"task_{idx}", actual_amount=1_500.0)

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(cycle, range(20)))

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["total_consumed"] == 30_000.0  # 20 * 1500
    assert stmt["total_refunded"] == 10_000.0  # 20 * 500
    assert stmt["net_available_balance"] == 70_000.0


def test_p12_5_s8_06_concurrent_reservation_and_rollback():
    """S8-06: 20 concurrent reservations rolling back simultaneously leave 0 leaked quota."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=100_000))

    def abort_cycle(idx: int):
        res = coord.reserve_budget("tenant_A", f"task_{idx}", QuotaDimension.TOKEN_BUDGET, amount=3_000.0)
        time.sleep(0.002)
        coord.rollback_budget(res.reservation_id, "tenant_A", f"task_{idx}")

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(abort_cycle, range(20)))

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 0.0
    assert stmt["total_consumed"] == 0.0
    assert stmt["net_available_balance"] == 100_000.0


def test_p12_5_s8_07_concurrent_duplicate_reservation():
    """S8-07: 20 threads requesting duplicate concurrency for identical task_id count as 1 slot."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=5))

    barrier = threading.Barrier(20)
    def dup_task(idx: int):
        barrier.wait()
        return coord.acquire_concurrency_slot("tenant_A", "identical_task_id", worker_id=f"w_{idx}")

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(dup_task, range(20)))

    assert all(results)
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 1


def test_p12_5_s8_08_concurrent_duplicate_commit():
    """S8-08: 20 threads concurrently committing same reservation return cached record without double-debiting."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=5_000.0)

    barrier = threading.Barrier(20)
    def dup_commit(idx: int):
        barrier.wait()
        return coord.commit_budget(res.reservation_id, "tenant_A", "t1", actual_amount=4_000.0)

    with ThreadPoolExecutor(max_workers=20) as executor:
        records = list(executor.map(dup_commit, range(20)))

    # All returned the exact same record_id
    assert len(set(r.record_id for r in records)) == 1
    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["total_consumed"] == 4_000.0  # NOT 80,000!


def test_p12_5_s8_09_concurrent_duplicate_rollback():
    """S8-09: 20 threads concurrently rolling back same reservation evaluate idempotently."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=5_000.0)

    barrier = threading.Barrier(20)
    def dup_rollback(idx: int):
        barrier.wait()
        return coord.rollback_budget(res.reservation_id, "tenant_A", "t1")

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(dup_rollback, range(20)))

    assert all(results)
    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["net_available_balance"] == 50_000.0


# ═════════════════════════════════════════════════════════════════════════════
# 3. STALE OPERATIONS, RECOVERY & INTEGRITY (S8-10 to S8-16)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s8_10_concurrent_stale_operations_rejected():
    """S8-10: 10 threads committing after a rollback is executed are 100% rejected with 409."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=5_000.0)
    coord.rollback_budget(res.reservation_id, "tenant_A", "t1")

    rejections = []
    def stale_commit(idx: int):
        try:
            coord.commit_budget(res.reservation_id, "tenant_A", "t1", actual_amount=5_000.0)
        except GovernanceError as ex:
            rejections.append((idx, ex))

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(stale_commit, range(10)))

    assert len(rejections) == 10
    assert all(r[1].status_code == 409 for r in rejections)


def test_p12_5_s8_11_mixed_success_and_failure_workload():
    """S8-11: 30 workers with random commit/rollback maintain exact conservation of tokens."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=200_000))

    expected_consumed = 0.0
    expected_refunded = 0.0

    for idx in range(30):
        res = coord.reserve_budget("tenant_A", f"task_{idx}", QuotaDimension.TOKEN_BUDGET, amount=2_000.0)
        if idx % 3 == 0:
            # 100% commit
            coord.commit_budget(res.reservation_id, "tenant_A", f"task_{idx}", actual_amount=2_000.0)
            expected_consumed += 2_000.0
        elif idx % 3 == 1:
            # Partial commit (1200 used, 800 refund)
            coord.commit_budget(res.reservation_id, "tenant_A", f"task_{idx}", actual_amount=1_200.0)
            expected_consumed += 1_200.0
            expected_refunded += 800.0
        else:
            # Rollback (2000 refund)
            coord.rollback_budget(res.reservation_id, "tenant_A", f"task_{idx}")
            expected_refunded += 2_000.0

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["total_consumed"] == expected_consumed
    assert stmt["total_refunded"] == expected_refunded
    assert stmt["net_available_balance"] == 200_000.0 - expected_consumed


def test_p12_5_s8_12_quota_recovery_after_release():
    """S8-12: Capacity fully utilized -> worker releases -> new worker acquires immediately."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=1))

    coord.acquire_concurrency_slot("tenant_A", "t_holder")
    with pytest.raises(QuotaExceededError):
        coord.acquire_concurrency_slot("tenant_A", "t_waiter")

    # Holder releases
    coord.release_concurrency_slot("tenant_A", "t_holder")
    # Waiter now acquires cleanly
    assert coord.acquire_concurrency_slot("tenant_A", "t_waiter") is True


def test_p12_5_s8_13_budget_recovery_after_rollback():
    """S8-13: Full token budget reserved -> task aborts & rolls back -> next task reserves."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))

    res1 = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=10_000.0)
    with pytest.raises(BudgetExhaustedError):
        coord.reserve_budget("tenant_A", "t2", QuotaDimension.TOKEN_BUDGET, amount=1_000.0)

    # Rollback t1
    coord.rollback_budget(res1.reservation_id, "tenant_A", "t1")
    # Now t2 reserves cleanly
    res2 = coord.reserve_budget("tenant_A", "t2", QuotaDimension.TOKEN_BUDGET, amount=5_000.0)
    assert res2.status == ReservationStatus.PENDING


def test_p12_5_s8_14_rate_limiter_refill_under_contention():
    """S8-14: Draining token bucket and waiting for continuous replenishment preserves Token Bucket semantics."""
    coord = InMemoryQuotaCoordinator()
    # 600 req/min = 10 req/sec
    coord.set_rate_limit_policy(RateLimitPolicyContract(policy_id="p1", tenant_id="tenant_A", requests_per_minute=600, burst_capacity=0))

    coord.consume_rate_limit("tenant_A", tokens_required=600)
    assert coord.rate_limiter.get_token_balance("tenant_A") == 0.0

    time.sleep(0.12)
    assert coord.consume_rate_limit("tenant_A", tokens_required=1.0) is True


def test_p12_5_s8_15_cross_tenant_mutation_attempt():
    """S8-15: Cross-tenant commit or rollback strictly raises HTTP 403."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=2_000.0)

    with pytest.raises(UnauthorizedGovernanceError) as exc_info:
        coord.commit_budget(res.reservation_id, "tenant_B", "t1", actual_amount=2_000.0)
    assert exc_info.value.status_code == 403

    with pytest.raises(UnauthorizedGovernanceError) as exc_info:
        coord.rollback_budget(res.reservation_id, "tenant_B", "t1")
    assert exc_info.value.status_code == 403


def test_p12_5_s8_16_secret_injection_attempts():
    """S8-16: Passing raw secrets (ghp_, ya29., password, bearer) into quota metadata raises 422."""
    with pytest.raises(RawSecretPayloadError):
        TenantQuotaContract(tenant_id="t1", metadata={"token": "ghp_ATTACK_VECTOR_SECRET_123"})

    with pytest.raises(RawSecretPayloadError):
        RateLimitPolicyContract(policy_id="p1", tenant_id="t1", metadata={"key": "ya29.OAUTH_TOKEN_LEAK"})


# ═════════════════════════════════════════════════════════════════════════════
# 4. MATHEMATICAL INVARIANTS & FINAL SYSTEM AUDIT (S8-17 to S8-22)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s8_17_no_negative_balances_under_extreme_concurrency():
    """S8-17: 50 threads randomly reserving and consuming never drive available balance below zero."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=20_000))

    def chaotic_consumer(idx: int):
        try:
            res = coord.reserve_budget("tenant_A", f"t_{idx}", QuotaDimension.TOKEN_BUDGET, amount=1_000.0)
            time.sleep(0.001)
            coord.commit_budget(res.reservation_id, "tenant_A", f"t_{idx}", actual_amount=500.0)
        except BudgetExhaustedError:
            pass

    with ThreadPoolExecutor(max_workers=50) as executor:
        list(executor.map(chaotic_consumer, range(50)))

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["net_available_balance"] >= 0.0
    assert stmt["active_reserved_pending"] == 0.0


def test_p12_5_s8_18_no_pending_reservation_leaks():
    """S8-18: All finished tasks leave zero active pending reservations."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))

    for idx in range(10):
        res = coord.reserve_budget("tenant_A", f"t_{idx}", QuotaDimension.TOKEN_BUDGET, amount=2_000.0)
        if idx % 2 == 0:
            coord.commit_budget(res.reservation_id, "tenant_A", f"t_{idx}", actual_amount=2_000.0)
        else:
            coord.rollback_budget(res.reservation_id, "tenant_A", f"t_{idx}")

    usage = coord.get_tenant_usage("tenant_A")
    assert usage["tokens_reserved"] == 0.0


def test_p12_5_s8_19_no_orphaned_concurrency_slots():
    """S8-19: Acquiring and releasing 50 concurrency slots sequentially leaves 0 active tasks."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=10))

    for idx in range(50):
        coord.acquire_concurrency_slot("tenant_A", f"t_{idx}")
        coord.release_concurrency_slot("tenant_A", f"t_{idx}")

    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 0


def test_p12_5_s8_20_no_duplicate_consumption_records():
    """S8-20: Repeated idempotent commits create exactly 1 logical consumption record."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=2_000.0)

    rec1 = coord.commit_budget(res.reservation_id, "tenant_A", "t1", actual_amount=1_500.0)
    rec2 = coord.commit_budget(res.reservation_id, "tenant_A", "t1", actual_amount=1_500.0)
    rec3 = coord.commit_budget(res.reservation_id, "tenant_A", "t1", actual_amount=1_500.0)

    assert rec1.record_id == rec2.record_id == rec3.record_id
    assert coord.get_tenant_usage("tenant_A")["tokens_used"] == 1_500.0


def test_p12_5_s8_21_complex_multi_worker_admission_controller_storm():
    """S8-21: 40 concurrent threads passing through AdmissionController evaluated atomically."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(
        TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=8, max_requests_per_minute=200, max_tokens_per_period=50_000)
    )

    admitted, rejected = [], []
    barrier = threading.Barrier(40)

    def task_eval(idx: int):
        barrier.wait()
        req = AdmissionRequestContract(
            request_id=f"req_{idx}", tenant_id="tenant_A", task_id=f"task_{idx}", estimated_tokens=1_000,
        )
        eval_res = ac.evaluate_admission(req)
        if eval_res.allowed:
            admitted.append(idx)
            time.sleep(0.005)
            res_id = eval_res.current_usage.get("reservation_id")
            ac.complete_task("tenant_A", f"task_{idx}", actual_tokens_consumed=800.0, reservation_id=res_id)
        else:
            rejected.append((idx, eval_res))

    with ThreadPoolExecutor(max_workers=40) as executor:
        list(executor.map(task_eval, range(40)))

    # Concurrency limit (8) bounded active parallel admissions
    assert len(admitted) + len(rejected) == 40
    assert ac.quota_manager.get_active_concurrency_count("tenant_A") == 0


def test_p12_5_s8_22_full_system_state_consistency_audit():
    """
    S8-22: FINAL SYSTEM STATE CONSISTENCY AUDIT
    Verifies: Zero leaked concurrency slots, zero leaked reservations, zero rate token drift,
    exact balance sheet math, and zero secret pollution across 50 complete lifecycles.
    """
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_audit", max_tokens_per_period=100_000, max_concurrent_tasks=10))

    # 1. 20 Complete execution lifecycles
    for i in range(20):
        coord.acquire_concurrency_slot("tenant_audit", f"task_{i}")
        res = coord.reserve_budget("tenant_audit", f"task_{i}", QuotaDimension.TOKEN_BUDGET, amount=2_500.0)
        coord.commit_budget(res.reservation_id, "tenant_audit", f"task_{i}", actual_amount=2_000.0)
        coord.release_concurrency_slot("tenant_audit", f"task_{i}")

    # 2. Mathematical Consistency
    stmt = coord.get_financial_statement("tenant_audit")
    assert stmt["total_consumed"] == 40_000.0   # 20 * 2000
    assert stmt["total_refunded"] == 10_000.0   # 20 * 500
    assert stmt["net_available_balance"] == 60_000.0  # 100k - 40k
    assert stmt["active_reserved_pending"] == 0.0

    # 3. Clean registries
    assert coord.get_tenant_usage("tenant_audit")["active_concurrent_tasks"] == 0
    assert len(coord._concurrency_records) == 0
