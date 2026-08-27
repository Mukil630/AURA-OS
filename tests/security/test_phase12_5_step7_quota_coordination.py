"""Phase 12.5 Step 7: Dedicated Distributed Quota Coordination Test Suite.
Verifies Authoritative IQuotaCoordinator Interface, InMemoryQuotaCoordinator Reference Implementation,
Cross-Worker Concurrency Control, Atomic Check-and-Reserve, Idempotent Retries, Stale Operation
Protection, Exact Balance Sheet Accounting, and Fail-Closed Tenant Isolation.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.governance import (
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
from app.core.governance.quota_coordinator import (
    IQuotaCoordinator,
    InMemoryQuotaCoordinator,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. CORE QUOTA COORDINATION & ATOMICITY (S7-01 to S7-06)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s7_01_single_tenant_quota_reservation_succeeds():
    """S7-01: Single tenant quota reservation succeeds through coordinator."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_mukil", max_concurrent_tasks=5))

    assert coord.acquire_concurrency_slot("tenant_mukil", "task_1", worker_id="worker_alpha") is True
    usage = coord.get_tenant_usage("tenant_mukil")
    assert usage["active_concurrent_tasks"] == 1


def test_p12_5_s7_02_quota_exhaustion_is_rejected():
    """S7-02: Quota exhaustion is rejected with QuotaExceededError (429)."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=2))

    coord.acquire_concurrency_slot("tenant_A", "t1", worker_id="w1")
    coord.acquire_concurrency_slot("tenant_A", "t2", worker_id="w2")

    with pytest.raises(QuotaExceededError) as exc_info:
        coord.acquire_concurrency_slot("tenant_A", "t3", worker_id="w3")
    assert exc_info.value.status_code == 429


def test_p12_5_s7_03_concurrent_workers_cannot_overallocate_quota():
    """S7-03: 20 concurrent workers racing across barrier for 5 slots -> exactly 5 succeed, 15 rejected."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=5))

    num_workers = 20
    barrier = threading.Barrier(num_workers)
    winners, rejected = [], []

    def worker_task(w_idx: int):
        barrier.wait()
        try:
            acquired = coord.acquire_concurrency_slot("tenant_A", f"task_{w_idx}", worker_id=f"worker_{w_idx}")
            if acquired:
                winners.append(w_idx)
        except QuotaExceededError as ex:
            rejected.append((w_idx, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(worker_task, range(num_workers)))

    assert len(winners) == 5
    assert len(rejected) == 15
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 5


def test_p12_5_s7_04_concurrent_budget_reservations_cannot_exceed_budget():
    """S7-04: 20 workers racing to reserve 10,000 tokens each from 50,000 budget -> exactly 5 succeed."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))

    num_workers = 20
    barrier = threading.Barrier(num_workers)
    granted, denied = [], []

    def worker_budget(w_idx: int):
        barrier.wait()
        try:
            res = coord.reserve_budget(
                tenant_id="tenant_A",
                task_id=f"task_{w_idx}",
                dimension=QuotaDimension.TOKEN_BUDGET,
                amount=10_000.0,
                worker_id=f"w_{w_idx}",
            )
            granted.append(res)
        except BudgetExhaustedError as ex:
            denied.append((w_idx, ex))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(worker_budget, range(num_workers)))

    assert len(granted) == 5
    assert len(denied) == 15
    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 50_000.0
    assert stmt["net_available_balance"] == 0.0


def test_p12_5_s7_05_concurrent_rate_limit_consumption_remains_atomic():
    """S7-05: 20 concurrent threads consuming rate limit tokens evaluated atomically."""
    coord = InMemoryQuotaCoordinator()
    coord.set_rate_limit_policy(RateLimitPolicyContract(policy_id="p1", tenant_id="tenant_A", requests_per_minute=10, burst_capacity=0))

    num_threads = 20
    barrier = threading.Barrier(num_threads)
    consumed, throttled = [], []

    def task_rate(idx: int):
        barrier.wait()
        try:
            coord.consume_rate_limit("tenant_A", tokens_required=1.0)
            consumed.append(idx)
        except RateLimitExceededError as ex:
            throttled.append((idx, ex))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        list(executor.map(task_rate, range(num_threads)))

    assert len(consumed) == 10
    assert len(throttled) == 10


def test_p12_5_s7_06_tenant_a_exhaustion_does_not_affect_tenant_b():
    """S7-06: Tenant A exhaustion has zero impact on Tenant B capacity."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=2, max_tokens_per_period=5_000))
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_B", max_concurrent_tasks=10, max_tokens_per_period=100_000))

    # Exhaust Tenant A
    coord.acquire_concurrency_slot("tenant_A", "tA1")
    coord.acquire_concurrency_slot("tenant_A", "tA2")
    with pytest.raises(QuotaExceededError):
        coord.acquire_concurrency_slot("tenant_A", "tA3")

    # Tenant B acquires freely
    assert coord.acquire_concurrency_slot("tenant_B", "tB1") is True
    resB = coord.reserve_budget("tenant_B", "tB1", QuotaDimension.TOKEN_BUDGET, amount=50_000)
    assert resB.status == ReservationStatus.PENDING


# ═════════════════════════════════════════════════════════════════════════════
# 2. IDEMPOTENCY & STALE OPERATION DEFENSE (S7-07 to S7-12)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s7_07_duplicate_reservation_is_idempotent():
    """S7-07: Duplicate concurrency reservation with same task_id is idempotent."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=1))

    assert coord.acquire_concurrency_slot("tenant_A", "task_repeat", worker_id="w1") is True
    assert coord.acquire_concurrency_slot("tenant_A", "task_repeat", worker_id="w1_retry") is True
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 1


def test_p12_5_s7_08_duplicate_release_is_idempotent():
    """S7-08: Duplicate concurrency release is safe and idempotent."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=2))

    coord.acquire_concurrency_slot("tenant_A", "task_rel")
    assert coord.release_concurrency_slot("tenant_A", "task_rel") is True
    assert coord.release_concurrency_slot("tenant_A", "task_rel") is False
    assert coord.get_tenant_usage("tenant_A")["active_concurrent_tasks"] == 0


def test_p12_5_s7_09_duplicate_commit_does_not_double_consume():
    """S7-09: Duplicate commit on the same reservation returns cached record without double-debiting."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=20_000))

    res = coord.reserve_budget("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=5_000)
    rec1 = coord.commit_budget(res.reservation_id, "tenant_A", "task_1", actual_amount=3_000)

    # Retry commit
    rec2 = coord.commit_budget(res.reservation_id, "tenant_A", "task_1", actual_amount=3_000)

    assert rec1.record_id == rec2.record_id
    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["total_consumed"] == 3_000.0  # NOT 6000!


def test_p12_5_s7_10_rollback_restores_reserved_capacity():
    """S7-10: Rollback restores 100% of reserved capacity."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))

    res = coord.reserve_budget("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=7_000)
    assert coord.rollback_budget(res.reservation_id, "tenant_A", "task_1") is True

    # Duplicate rollback is idempotent
    assert coord.rollback_budget(res.reservation_id, "tenant_A", "task_1") is True

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 0.0
    assert stmt["net_available_balance"] == 10_000.0


def test_p12_5_s7_11_stale_reservation_operation_is_rejected_safely():
    """S7-11: Late commit on rolled-back reservation is rejected with HTTP 409."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))

    res = coord.reserve_budget("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=5_000)
    coord.rollback_budget(res.reservation_id, "tenant_A", "task_1")

    # Stale commit arrives late
    with pytest.raises(GovernanceError) as exc_info:
        coord.commit_budget(res.reservation_id, "tenant_A", "task_1", actual_amount=5_000)
    assert exc_info.value.status_code == 409


def test_p12_5_s7_12_failed_operation_does_not_leak_quota():
    """S7-12: A failed reservation attempt leaves zero residual leaks."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))

    with pytest.raises(BudgetExhaustedError):
        coord.reserve_budget("tenant_A", "task_fail", QuotaDimension.TOKEN_BUDGET, amount=15_000)

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 0.0
    assert stmt["total_consumed"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 3. ACCOUNTING, RATE LIMITING & SECURITY AUDIT (S7-13 to S7-18)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s7_13_reservation_and_commit_maintains_exact_accounting():
    """S7-13: Reservation + commit maintains exact accounting (10000 res - 7500 used = 2500 refund)."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))

    res = coord.reserve_budget("tenant_A", "task_exact", QuotaDimension.TOKEN_BUDGET, amount=10_000)
    coord.commit_budget(res.reservation_id, "tenant_A", "task_exact", actual_amount=7_500)

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["total_consumed"] == 7_500.0
    assert stmt["total_refunded"] == 2_500.0
    assert stmt["net_available_balance"] == 42_500.0


def test_p12_5_s7_14_reservation_and_rollback_restores_exact_accounting():
    """S7-14: Reservation + rollback restores exact balance sheet."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=50_000))

    res = coord.reserve_budget("tenant_A", "task_rb", QuotaDimension.TOKEN_BUDGET, amount=12_000)
    coord.rollback_budget(res.reservation_id, "tenant_A", "task_rb")

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["active_reserved_pending"] == 0.0
    assert stmt["total_consumed"] == 0.0
    assert stmt["net_available_balance"] == 50_000.0


def test_p12_5_s7_15_rate_limiter_preserves_retry_after_behavior():
    """S7-15: Rate limiter through coordinator returns accurate retry_after_seconds."""
    coord = InMemoryQuotaCoordinator()
    coord.set_rate_limit_policy(RateLimitPolicyContract(policy_id="p1", tenant_id="tenant_A", requests_per_minute=60, burst_capacity=0))

    coord.consume_rate_limit("tenant_A", tokens_required=60)

    allowed, retry_after, _ = coord.check_rate_limit("tenant_A", tokens_required=1)
    assert allowed is False
    assert retry_after > 0.0

    with pytest.raises(RateLimitExceededError) as exc_info:
        coord.consume_rate_limit("tenant_A", tokens_required=1)
    assert exc_info.value.retry_after_seconds > 0.0


def test_p12_5_s7_16_concurrent_high_contention_tenant_test():
    """S7-16: 30 concurrent workers executing reservation, commit, and rollback cycles."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=10, max_tokens_per_period=100_000))

    num_workers = 30
    barrier = threading.Barrier(num_workers)

    def heavy_worker(w_idx: int):
        barrier.wait()
        try:
            coord.acquire_concurrency_slot("tenant_A", f"task_{w_idx}")
            res = coord.reserve_budget("tenant_A", f"task_{w_idx}", QuotaDimension.TOKEN_BUDGET, amount=2_000)
            time.sleep(0.005)
            if w_idx % 2 == 0:
                coord.commit_budget(res.reservation_id, "tenant_A", f"task_{w_idx}", actual_amount=1_500)
            else:
                coord.rollback_budget(res.reservation_id, "tenant_A", f"task_{w_idx}")
            coord.release_concurrency_slot("tenant_A", f"task_{w_idx}")
        except (QuotaExceededError, BudgetExhaustedError):
            pass

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(executor.map(heavy_worker, range(num_workers)))

    stmt = coord.get_financial_statement("tenant_A")
    assert stmt["net_available_balance"] >= 0.0
    assert stmt["active_reserved_pending"] == 0.0


def test_p12_5_s7_17_cross_tenant_mutation_rejected():
    """S7-17: Cross-tenant commit and rollback are rejected with 403."""
    coord = InMemoryQuotaCoordinator()
    coord.register_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=10_000))
    res = coord.reserve_budget("tenant_A", "t1", QuotaDimension.TOKEN_BUDGET, amount=1_000)

    with pytest.raises(UnauthorizedGovernanceError):
        coord.commit_budget(res.reservation_id, "tenant_B", "t1", actual_amount=1_000)

    with pytest.raises(UnauthorizedGovernanceError):
        coord.rollback_budget(res.reservation_id, "tenant_B", "t1")


def test_p12_5_s7_18_coordinator_preserves_existing_governance_contracts():
    """S7-18: Coordinator operates strictly on TenantQuotaContract and preserves zero secrets."""
    coord = InMemoryQuotaCoordinator()
    assert isinstance(coord, IQuotaCoordinator)

    # Valid contract
    quota = TenantQuotaContract(tenant_id="tenant_A")
    coord.register_tenant_quota(quota)
    retrieved = coord.get_tenant_quota("tenant_A")
    assert retrieved.tenant_id == "tenant_A"

    # Secret check preserved
    with pytest.raises(RawSecretPayloadError):
        TenantQuotaContract(tenant_id="tenant_bad", metadata={"secret": "ghp_LEAKED_SECRET_HERE"})
