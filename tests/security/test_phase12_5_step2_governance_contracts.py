"""Phase 12.5 Step 2: Dedicated Governance Contracts & Taxonomy Test Suite.
Verifies Multi-Dimensional Tenant Quota Contracts, Rate Limit Policies, Two-Phase Budget
Reservations, Consumption Records, Admission Evaluations, and Zero-Secret Invariants.
"""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

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
    StorageLimitExceededError,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. TENANT QUOTA CONTRACT INVARIANTS (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s2_01_valid_tenant_quota_contract_defaults():
    """S2-01: Create TenantQuotaContract with default values."""
    quota = TenantQuotaContract(tenant_id="tenant_mukil")
    assert quota.tenant_id == "tenant_mukil"
    assert quota.max_concurrent_tasks == 5
    assert quota.max_requests_per_minute == 60
    assert quota.max_tokens_per_period == 1_000_000
    assert quota.budget_period == BudgetPeriod.DAILY
    assert quota.soft_limit_threshold_percent == 80.0


def test_p12_5_s2_02_valid_tenant_quota_custom_dimensions():
    """S2-02: Create TenantQuotaContract with enterprise custom tier dimensions."""
    quota = TenantQuotaContract(
        tenant_id="tenant_enterprise",
        max_concurrent_tasks=25,
        max_requests_per_minute=600,
        max_burst_requests=50,
        max_tokens_per_period=10_000_000,
        budget_period=BudgetPeriod.MONTHLY,
        max_storage_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
        soft_limit_threshold_percent=85.0,
    )
    assert quota.max_concurrent_tasks == 25
    assert quota.max_requests_per_minute == 600
    assert quota.budget_period == BudgetPeriod.MONTHLY


def test_p12_5_s2_03_empty_tenant_id_rejected():
    """S2-03: Empty tenant_id in quota contract is rejected by validation."""
    with pytest.raises(ValidationError):
        TenantQuotaContract(tenant_id="")
    with pytest.raises(ValidationError):
        TenantQuotaContract(tenant_id="   ")


def test_p12_5_s2_04_invalid_dimensions_rejected():
    """S2-04: Negative concurrency or out-of-range soft limit percent rejected."""
    with pytest.raises(ValidationError):
        TenantQuotaContract(tenant_id="t1", max_concurrent_tasks=0)
    with pytest.raises(ValidationError):
        TenantQuotaContract(tenant_id="t1", soft_limit_threshold_percent=105.0)


def test_p12_5_s2_05_metadata_with_raw_secret_rejected():
    """S2-05: Raw secrets in quota contract metadata rejected with RawSecretPayloadError (422)."""
    with pytest.raises(RawSecretPayloadError):
        TenantQuotaContract(
            tenant_id="tenant_leaker",
            metadata={"admin_token": "ghp_SECRET_TOKEN_LEAK_999"},
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. RATE LIMIT POLICY CONTRACT (Tests 6 - 7)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s2_06_valid_rate_limit_policy():
    """S2-06: Create valid RateLimitPolicyContract."""
    policy = RateLimitPolicyContract(
        policy_id="pol_01",
        tenant_id="tenant_mukil",
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        requests_per_minute=120,
        burst_capacity=20,
        window_seconds=60.0,
    )
    assert policy.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
    assert policy.requests_per_minute == 120
    assert policy.burst_capacity == 20


def test_p12_5_s2_07_rate_limit_policy_rejects_raw_secrets():
    """S2-07: RateLimitPolicyContract rejects raw secrets in metadata."""
    with pytest.raises(RawSecretPayloadError):
        RateLimitPolicyContract(
            policy_id="pol_sec",
            tenant_id="t1",
            metadata={"secret_key": "Bearer ya29.LEAKED_OAUTH_TOKEN_VALUE"},
        )


# ═════════════════════════════════════════════════════════════════════════════
# 3. BUDGET RESERVATION & CONSUMPTION CONTRACTS (Tests 8 - 12)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s2_08_valid_budget_reservation():
    """S2-08: Create BudgetReservationContract in PENDING state."""
    now = datetime.now(timezone.utc)
    res = BudgetReservationContract(
        reservation_id="res_01",
        tenant_id="tenant_A",
        task_id="task_101",
        dimension=QuotaDimension.TOKEN_BUDGET,
        reserved_amount=5000.0,
        status=ReservationStatus.PENDING,
        granted_at=now,
        expires_at=now + timedelta(seconds=60),
    )
    assert res.status == ReservationStatus.PENDING
    assert res.reserved_amount == 5000.0


def test_p12_5_s2_09_budget_reservation_temporal_invariant_rejected():
    """S2-09: Budget reservation with expires_at <= granted_at is rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        BudgetReservationContract(
            reservation_id="res_inv",
            tenant_id="t1",
            task_id="t1",
            dimension=QuotaDimension.STORAGE_BYTES,
            reserved_amount=1024.0,
            granted_at=now,
            expires_at=now - timedelta(seconds=1),
        )


def test_p12_5_s2_10_budget_reservation_rejects_raw_secrets():
    """S2-10: Budget reservation metadata with raw secrets is rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(RawSecretPayloadError):
        BudgetReservationContract(
            reservation_id="res_sec",
            tenant_id="t1",
            task_id="t1",
            dimension=QuotaDimension.CONCURRENT_TASKS,
            reserved_amount=1.0,
            granted_at=now,
            expires_at=now + timedelta(seconds=10),
            metadata={"auth_token": "ghp_LEAKED_TOKEN_HERE_NOW"},
        )


def test_p12_5_s2_11_valid_consumption_record():
    """S2-11: Create valid ConsumptionRecordContract."""
    rec = ConsumptionRecordContract(
        record_id="rec_01",
        reservation_id="res_01",
        tenant_id="tenant_A",
        task_id="task_101",
        dimension=QuotaDimension.TOKEN_BUDGET,
        amount_consumed=4250.0,
    )
    assert rec.amount_consumed == 4250.0
    assert rec.reservation_id == "res_01"


def test_p12_5_s2_12_consumption_record_rejects_raw_secrets():
    """S2-12: ConsumptionRecordContract metadata with raw secrets is rejected."""
    with pytest.raises(RawSecretPayloadError):
        ConsumptionRecordContract(
            record_id="rec_sec",
            tenant_id="t1",
            task_id="t1",
            dimension=QuotaDimension.TOKEN_BUDGET,
            amount_consumed=100.0,
            metadata={"password": "raw_password_value_123"},
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. ADMISSION EVALUATION & STATUS CODES (Tests 13 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_5_s2_13_admission_request_and_allow_evaluation():
    """S2-13: Create AdmissionRequestContract and corresponding ALLOW evaluation."""
    req = AdmissionRequestContract(
        request_id="adm_req_01",
        tenant_id="tenant_mukil",
        task_id="task_99",
        required_concurrent=1,
        estimated_tokens=2000,
    )
    eval_res = AdmissionEvaluationContract(
        evaluation_id="eval_01",
        tenant_id=req.tenant_id,
        task_id=req.task_id,
        decision=AdmissionDecision.ALLOW,
        allowed=True,
    )
    assert eval_res.allowed is True
    assert eval_res.decision == AdmissionDecision.ALLOW


def test_p12_5_s2_14_admission_deny_evaluation_with_retry_after():
    """S2-14: DENY_RATE_LIMIT evaluation carries retry_after_seconds."""
    eval_res = AdmissionEvaluationContract(
        evaluation_id="eval_02",
        tenant_id="tenant_mukil",
        task_id="task_100",
        decision=AdmissionDecision.DENY_RATE_LIMIT,
        allowed=False,
        reason="Rate limit exceeded: 60/minute limit reached",
        retry_after_seconds=5.5,
    )
    assert eval_res.allowed is False
    assert eval_res.retry_after_seconds == 5.5


def test_p12_5_s2_15_governance_exception_hierarchy_status_codes():
    """S2-15: Governance exception hierarchy preserves deterministic HTTP status codes."""
    assert QuotaExceededError("concurrency limit").status_code == 429
    rate_err = RateLimitExceededError("rate limit", retry_after_seconds=3.0)
    assert rate_err.status_code == 429
    assert rate_err.retry_after_seconds == 3.0
    assert BudgetExhaustedError("tokens out").status_code == 402
    assert StorageLimitExceededError("disk full").status_code == 413
    assert UnauthorizedGovernanceError("cross tenant").status_code == 403
