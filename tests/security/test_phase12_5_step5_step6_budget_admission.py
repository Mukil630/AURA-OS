"""Phase 12.5 Steps 5 & 6: Dedicated Resource Budget Accounting & Admission Controller Test Suite.
Verifies Financial Balance Sheets, Refund Calculations, Period Rollovers, Gateway Multi-Dimensional
Admission Decisions (Rate, Concurrency, Token, Storage), Task Lifecycle Settlement, and Rollback.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
import pytest

from app.core.contracts.governance import (
    AdmissionDecision,
    AdmissionEvaluationContract,
    AdmissionRequestContract,
    BudgetExhaustedError,
    BudgetPeriod,
    QuotaDimension,
    QuotaExceededError,
    RateLimitAlgorithm,
    RateLimitExceededError,
    RateLimitPolicyContract,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)
from app.core.governance.admission_controller import AdmissionController
from app.core.governance.budget_manager import ResourceBudgetManager
from app.core.governance.quota_manager import InMemoryTenantQuotaManager
from app.core.governance.rate_limiter import InMemoryTokenBucketRateLimiter


# ═════════════════════════════════════════════════════════════════════════════
# 1. RESOURCE BUDGET ACCOUNTING & FINANCIAL STATEMENTS (Tests 1 - 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s5_01_allocate_budget_initializes_ledger():
    """S5-01: Explicit budget allocation initializes clean financial ledger."""
    bm = ResourceBudgetManager()
    rec = bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=500_000, period=BudgetPeriod.MONTHLY)
    assert rec["allocated"] == 500_000.0
    assert rec["consumed"] == 0.0
    assert rec["refunded"] == 0.0


def test_p12_5_s5_02_budget_reservation_deducts_available_balance():
    """S5-02: Reserving budget deducts from net available balance in statement."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=10_000)

    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=4_000)
    stmt = bm.get_financial_statement("tenant_A", QuotaDimension.TOKEN_BUDGET)

    assert stmt["allocated_budget"] == 10_000.0
    assert stmt["active_reserved_pending"] == 4_000.0
    assert stmt["net_available_balance"] == 6_000.0


def test_p12_5_s5_03_settle_calculates_exact_refund():
    """S5-03: Settle actual consumption and calculate exact refund (5000 res - 3200 used = 1800 refund)."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=20_000)

    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=5_000)
    settlement = bm.settle(res.reservation_id, "tenant_A", "task_1", actual_consumed=3_200)

    assert settlement["actual_consumed"] == 3_200.0
    assert settlement["refund_amount"] == 1_800.0
    assert settlement["total_consumed"] == 3_200.0
    assert settlement["total_refunded"] == 1_800.0
    assert settlement["net_remaining_budget"] == 16_800.0


def test_p12_5_s5_04_release_reservation_full_refund():
    """S5-04: Releasing uncommitted reservation refunds 100% of reserved amount."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=10_000)

    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=7_000)
    assert bm.release(res.reservation_id, "tenant_A") is True

    stmt = bm.get_financial_statement("tenant_A", QuotaDimension.TOKEN_BUDGET)
    assert stmt["active_reserved_pending"] == 0.0
    assert stmt["net_available_balance"] == 10_000.0
    assert stmt["total_refunded"] == 7_000.0


def test_p12_5_s5_05_period_rollover_resets_consumption():
    """S5-05: Window rollover to next period resets consumed amount to zero."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=10_000, period=BudgetPeriod.HOURLY)

    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=5_000)
    bm.settle(res.reservation_id, "tenant_A", "task_1", actual_consumed=5_000)

    # Manually simulate previous period key
    bm._accounting_ledger["tenant_A"][QuotaDimension.TOKEN_BUDGET]["period_key"] = "2026-01-01-00"

    # Next check should roll over to current hour
    stmt = bm.get_financial_statement("tenant_A", QuotaDimension.TOKEN_BUDGET)
    assert stmt["total_consumed"] == 0.0
    assert stmt["net_available_balance"] == 10_000.0


def test_p12_5_s5_06_financial_statement_breakdown():
    """S5-06: get_financial_statement returns comprehensive balance sheet metrics."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=100_000)

    stmt = bm.get_financial_statement("tenant_A", QuotaDimension.TOKEN_BUDGET)
    assert stmt["tenant_id"] == "tenant_A"
    assert stmt["dimension"] == QuotaDimension.TOKEN_BUDGET
    assert stmt["allocated_budget"] == 100_000.0
    assert stmt["is_hard_limit_exhausted"] is False


def test_p12_5_s5_07_soft_limit_warning_in_statement():
    """S5-07: Usage crossing 80% flags is_soft_limit_exceeded in financial statement."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=10_000)

    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=8_500)
    stmt = bm.get_financial_statement("tenant_A", QuotaDimension.TOKEN_BUDGET)
    assert stmt["is_soft_limit_exceeded"] is True


def test_p12_5_s5_08_cross_tenant_settlement_rejected():
    """S5-08: Cross-tenant settlement on another tenant's reservation raises 403."""
    bm = ResourceBudgetManager()
    bm.allocate_budget("tenant_A", QuotaDimension.TOKEN_BUDGET, amount=10_000)
    res = bm.reserve("tenant_A", "task_1", QuotaDimension.TOKEN_BUDGET, amount=1_000)

    with pytest.raises(UnauthorizedGovernanceError):
        bm.settle(res.reservation_id, "tenant_B", "task_1", actual_consumed=1_000)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADMISSION CONTROLLER & GATEWAY DECISIONS (Tests 9 - 18)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s6_09_admission_allow_decision():
    """S6-09: Valid task request within all capacity limits receives ALLOW decision."""
    ac = AdmissionController()
    req = AdmissionRequestContract(
        request_id="req_01",
        tenant_id="tenant_mukil",
        task_id="task_1",
        required_concurrent=1,
        estimated_tokens=2_000,
    )
    eval_res = ac.evaluate_admission(req)
    assert eval_res.allowed is True
    assert eval_res.decision == AdmissionDecision.ALLOW


def test_p12_5_s6_10_admission_deny_rate_limit():
    """S6-10: Inbound request blocked when tenant exceeds requests-per-minute rate limit."""
    ac = AdmissionController()
    ac.rate_limiter.set_policy(RateLimitPolicyContract(policy_id="p1", tenant_id="tenant_A", requests_per_minute=2, burst_capacity=0))

    # Drain 2 tokens
    ac.rate_limiter.consume("tenant_A", 2)

    req = AdmissionRequestContract(request_id="req_rl", tenant_id="tenant_A", task_id="task_rl")
    eval_res = ac.evaluate_admission(req)

    assert eval_res.allowed is False
    assert eval_res.decision == AdmissionDecision.DENY_RATE_LIMIT
    assert eval_res.retry_after_seconds is not None
    assert eval_res.retry_after_seconds > 0.0


def test_p12_5_s6_11_admission_deny_concurrency():
    """S6-11: Inbound request blocked when tenant exceeds active concurrent tasks."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=1))

    # Fill concurrency slot
    ac.quota_manager.acquire_concurrency_slot("tenant_A", "task_active")

    req = AdmissionRequestContract(request_id="req_cc", tenant_id="tenant_A", task_id="task_blocked")
    eval_res = ac.evaluate_admission(req)

    assert eval_res.allowed is False
    assert eval_res.decision == AdmissionDecision.DENY_CONCURRENCY
    assert "Concurrency quota exceeded" in eval_res.reason


def test_p12_5_s6_12_admission_deny_token_budget():
    """S6-12: Inbound request blocked when estimated tokens exceed remaining budget."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=5_000))

    req = AdmissionRequestContract(
        request_id="req_tb", tenant_id="tenant_A", task_id="task_tb", estimated_tokens=10_000,
    )
    eval_res = ac.evaluate_admission(req)

    assert eval_res.allowed is False
    assert eval_res.decision == AdmissionDecision.DENY_BUDGET
    assert "Token budget exhausted" in eval_res.reason


def test_p12_5_s6_13_admission_deny_storage_limit():
    """S6-13: Inbound request blocked when estimated storage bytes exceed allocation."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_storage_bytes=1024 * 1024)) # 1MB

    req = AdmissionRequestContract(
        request_id="req_st", tenant_id="tenant_A", task_id="task_st", estimated_bytes=5 * 1024 * 1024,
    )
    eval_res = ac.evaluate_admission(req)

    assert eval_res.allowed is False
    assert eval_res.decision == AdmissionDecision.DENY_STORAGE
    assert "Storage allocation exceeded" in eval_res.reason


def test_p12_5_s6_14_complete_task_lifecycle_settlement():
    """S6-14: Task completion releases concurrency slot and settles token budget."""
    ac = AdmissionController()
    req = AdmissionRequestContract(
        request_id="req_life", tenant_id="tenant_A", task_id="task_life", estimated_tokens=5_000,
    )
    eval_res = ac.evaluate_admission(req)
    assert eval_res.allowed is True
    res_id = eval_res.current_usage.get("reservation_id")

    # Complete task with 3500 actual tokens consumed
    complete_res = ac.complete_task("tenant_A", "task_life", actual_tokens_consumed=3_500, reservation_id=res_id)
    assert complete_res["status"] == "completed"
    assert complete_res["active_concurrency"] == 0
    assert complete_res["financial_settlement"]["actual_consumed"] == 3_500.0
    assert complete_res["financial_settlement"]["refund_amount"] == 1_500.0


def test_p12_5_s6_15_abort_task_lifecycle_rollback():
    """S6-15: Aborting task releases concurrency slot and refunds token reservation."""
    ac = AdmissionController()
    req = AdmissionRequestContract(
        request_id="req_abort", tenant_id="tenant_A", task_id="task_abort", estimated_tokens=4_000,
    )
    eval_res = ac.evaluate_admission(req)
    res_id = eval_res.current_usage.get("reservation_id")

    abort_res = ac.abort_task("tenant_A", "task_abort", reservation_id=res_id)
    assert abort_res["status"] == "aborted"
    assert abort_res["reservation_refunded"] is True
    assert abort_res["active_concurrency"] == 0


def test_p12_5_s6_16_cross_tenant_admission_isolation():
    """S6-16: Tenant A exhausting token budget has zero impact on Tenant B admission."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_tokens_per_period=1_000))
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_B", max_tokens_per_period=10_000))

    # Tenant A request blocked
    req_A = AdmissionRequestContract(request_id="rA", tenant_id="tenant_A", task_id="tA", estimated_tokens=5_000)
    assert ac.evaluate_admission(req_A).allowed is False

    # Tenant B request allowed
    req_B = AdmissionRequestContract(request_id="rB", tenant_id="tenant_B", task_id="tB", estimated_tokens=5_000)
    assert ac.evaluate_admission(req_B).allowed is True


def test_p12_5_s6_17_concurrent_admission_evaluations_mutex_safe():
    """S6-17: 20 concurrent threads evaluated through admission controller without race corruption."""
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(TenantQuotaContract(tenant_id="tenant_A", max_concurrent_tasks=5, max_requests_per_minute=100))

    admitted, denied = [], []
    barrier = threading.Barrier(20)

    def task(idx: int):
        barrier.wait()
        req = AdmissionRequestContract(request_id=f"req_{idx}", tenant_id="tenant_A", task_id=f"t_{idx}")
        res = ac.evaluate_admission(req)
        if res.allowed:
            admitted.append(idx)
        else:
            denied.append((idx, res))

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(task, range(20)))

    # Exactly 5 admitted (due to max_concurrent_tasks=5) and 15 denied
    assert len(admitted) == 5
    assert len(denied) == 15


def test_p12_5_s6_18_invalid_admission_request_type_rejected():
    """S6-18: Non-contract input to evaluate_admission raises TypeError."""
    ac = AdmissionController()
    with pytest.raises(TypeError):
        ac.evaluate_admission("invalid_str") # pyright: ignore[reportArgumentType]
