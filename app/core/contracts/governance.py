"""Phase 12.5: Tenant Resource Governance Data Contracts, Enums & Exception Taxonomy.
Provides strongly typed contracts for multi-dimensional tenant quotas, token bucket rate limits,
two-phase resource budget reservations, consumption tracking, and fail-closed admission decisions.
"""
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import Field, model_validator
from starlette.status import (
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
)

from app.connectors.router import _contains_raw_secrets
from app.core.contracts.base import VersionedContractBase
from app.core.contracts.credential import RawSecretPayloadError
from app.security.sanitizer import SECRET_PATTERNS


# ── 1. Governance & Quota Enums ──────────────────────────────────────────────

class QuotaDimension(str, Enum):
    """Orthogonal dimensions of resource capacity tracked per tenant."""
    CONCURRENT_TASKS = "concurrent_tasks"  # Max in-flight worker tasks
    REQUEST_RATE = "request_rate"          # Requests per minute / window
    TOKEN_BUDGET = "token_budget"          # LLM tokens / compute credits
    STORAGE_BYTES = "storage_bytes"        # Vault / payload storage bytes


class BudgetPeriod(str, Enum):
    """Time window for compute and token budget resets."""
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PERPETUAL = "perpetual"


class RateLimitAlgorithm(str, Enum):
    """Algorithm used for request rate throttling."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class AdmissionDecision(str, Enum):
    """Outcome of admission control evaluation at the gateway."""
    ALLOW = "allow"
    DENY_CONCURRENCY = "deny_concurrency"
    DENY_RATE_LIMIT = "deny_rate_limit"
    DENY_BUDGET = "deny_budget"
    DENY_STORAGE = "deny_storage"


class ReservationStatus(str, Enum):
    """Lifecycle status of a two-phase budget reservation."""
    PENDING = "pending"          # Reserved, awaiting task completion
    COMMITTED = "committed"      # Settled with actual consumed amount
    ROLLED_BACK = "rolled_back"  # Released back due to abort/failure
    EXPIRED = "expired"          # Timed out without settlement


# ── 2. Governance Exception Hierarchy ────────────────────────────────────────

class GovernanceError(Exception):
    """Base exception for all tenant resource governance failures."""
    def __init__(self, detail: str, status_code: int = HTTP_429_TOO_MANY_REQUESTS):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class QuotaExceededError(GovernanceError):
    """Raised when concurrent task executions exceed tenant capacity (HTTP 429)."""
    def __init__(self, detail: str):
        super().__init__(detail, status_code=HTTP_429_TOO_MANY_REQUESTS)


class RateLimitExceededError(GovernanceError):
    """Raised when tenant request throughput exceeds rate limit (HTTP 429 with retry-after)."""
    def __init__(self, detail: str, retry_after_seconds: float = 1.0):
        super().__init__(detail, status_code=HTTP_429_TOO_MANY_REQUESTS)
        self.retry_after_seconds = max(0.0, float(retry_after_seconds))


class BudgetExhaustedError(GovernanceError):
    """Raised when tenant LLM token or compute credit budget is exhausted (HTTP 402)."""
    def __init__(self, detail: str):
        super().__init__(detail, status_code=HTTP_402_PAYMENT_REQUIRED)


class StorageLimitExceededError(GovernanceError):
    """Raised when tenant payload/vault storage exceeds byte allocation (HTTP 413)."""
    def __init__(self, detail: str):
        super().__init__(detail, status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class UnauthorizedGovernanceError(GovernanceError):
    """Raised when cross-tenant governance operations or unauthorized quota tampering occurs (HTTP 403)."""
    def __init__(self, detail: str):
        super().__init__(detail, status_code=HTTP_403_FORBIDDEN)


# ── 3. Tenant Quota Contract ─────────────────────────────────────────────────

class TenantQuotaContract(VersionedContractBase):
    """
    Defines the multi-dimensional resource quota thresholds assigned to a tenant.
    """
    tenant_id: str = Field(..., min_length=1, description="Target tenant identifier.")
    max_concurrent_tasks: int = Field(
        default=5,
        ge=1,
        description="Maximum concurrent in-flight task executions.",
    )
    max_requests_per_minute: int = Field(
        default=60,
        ge=1,
        description="Max allowed requests per minute.",
    )
    max_burst_requests: int = Field(
        default=10,
        ge=0,
        description="Additional burst token capacity beyond base rate.",
    )
    max_tokens_per_period: int = Field(
        default=1_000_000,
        ge=0,
        description="Maximum LLM tokens (prompt + completion) permitted per budget period.",
    )
    budget_period: BudgetPeriod = Field(
        default=BudgetPeriod.DAILY,
        description="Reset period for LLM token budget.",
    )
    max_storage_bytes: int = Field(
        default=1_073_741_824,  # 1 GB default
        ge=0,
        description="Total storage allocation in bytes.",
    )
    soft_limit_threshold_percent: float = Field(
        default=80.0,
        ge=1.0,
        le=100.0,
        description="Percentage threshold where soft telemetry warnings are emitted.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tenant tier metadata (zero raw secrets permitted).",
    )

    @model_validator(mode="after")
    def validate_quota_invariants(self) -> "TenantQuotaContract":
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be a non-empty string.")
        if _contains_raw_secrets(self.metadata) or any(p.search(str(self.metadata)) for p in SECRET_PATTERNS):
            raise RawSecretPayloadError("Tenant quota metadata must never contain raw secrets.")
        return self


# ── 4. Rate Limit Policy Contract ────────────────────────────────────────────

class RateLimitPolicyContract(VersionedContractBase):
    """
    Defines the rate-limiting algorithm and parameters for a tenant or endpoint.
    """
    policy_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    algorithm: RateLimitAlgorithm = Field(default=RateLimitAlgorithm.TOKEN_BUCKET)
    requests_per_minute: int = Field(default=60, gt=0)
    burst_capacity: int = Field(default=10, ge=0)
    window_seconds: float = Field(default=60.0, gt=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy_invariants(self) -> "RateLimitPolicyContract":
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if _contains_raw_secrets(self.metadata):
            raise RawSecretPayloadError("Rate limit policy metadata must not contain raw secrets.")
        return self


# ── 5. Two-Phase Budget Reservation Contract ────────────────────────────────

class BudgetReservationContract(VersionedContractBase):
    """
    Represents an atomic, temporary reservation of budget capacity (tokens, storage, or concurrency).
    """
    reservation_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    dimension: QuotaDimension = Field(...)
    reserved_amount: float = Field(..., gt=0.0)
    status: ReservationStatus = Field(default=ReservationStatus.PENDING)
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(...)
    ttl_seconds: int = Field(default=60, gt=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reservation_invariants(self) -> "BudgetReservationContract":
        if self.expires_at <= self.granted_at:
            raise ValueError("expires_at must logically occur strictly after granted_at.")
        if _contains_raw_secrets(self.metadata):
            raise RawSecretPayloadError("Budget reservation metadata must not contain raw secrets.")
        return self


# ── 6. Consumption Record Contract ───────────────────────────────────────────

class ConsumptionRecordContract(VersionedContractBase):
    """
    Represents settled resource consumption after task execution.
    """
    record_id: str = Field(..., min_length=1)
    reservation_id: Optional[str] = Field(default=None)
    tenant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    dimension: QuotaDimension = Field(...)
    amount_consumed: float = Field(..., ge=0.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_consumption_invariants(self) -> "ConsumptionRecordContract":
        if _contains_raw_secrets(self.metadata):
            raise RawSecretPayloadError("Consumption record metadata must not contain raw secrets.")
        return self


# ── 7. Admission Request & Evaluation Contracts ──────────────────────────────

class AdmissionRequestContract(VersionedContractBase):
    """
    Inbound task admission evaluation request presented at the gateway.
    """
    request_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    required_concurrent: int = Field(default=1, ge=1)
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_bytes: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AdmissionEvaluationContract(VersionedContractBase):
    """
    Deterministic result of admission control evaluation at the gateway.
    """
    evaluation_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    decision: AdmissionDecision = Field(...)
    allowed: bool = Field(...)
    reason: Optional[str] = Field(default=None)
    retry_after_seconds: Optional[float] = Field(default=None, ge=0.0)
    current_usage: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
