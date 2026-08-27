"""Phase 12.5 Step 7: Distributed Quota Coordination Layer.
Defines the authoritative IQuotaCoordinator abstraction and InMemoryQuotaCoordinator reference implementation.
Provides cross-worker concurrency coordination, atomic check-and-reserve semantics, idempotent operations,
stale reservation protection, Token Bucket rate-limit coordination, and fail-closed tenant boundary isolation.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional, Set, Tuple
import uuid

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
    StorageLimitExceededError,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)
from app.core.governance.budget_manager import ResourceBudgetManager
from app.core.governance.quota_manager import InMemoryTenantQuotaManager
from app.core.governance.rate_limiter import InMemoryTokenBucketRateLimiter


class IQuotaCoordinator(ABC):
    """
    Authoritative Abstract Interface for Distributed Tenant Quota & Governance Coordination.
    Allows pluggable distributed backends (e.g., Redis, PostgreSQL, Distributed Lock-backed stores)
    without altering gateway admission logic.
    """

    @abstractmethod
    def register_tenant_quota(self, quota: TenantQuotaContract) -> None:
        """Register or update multi-dimensional quota limits for a tenant."""
        pass

    @abstractmethod
    def get_tenant_quota(self, tenant_id: str) -> TenantQuotaContract:
        """Retrieve active quota contract for a tenant."""
        pass

    @abstractmethod
    def set_rate_limit_policy(self, policy: RateLimitPolicyContract) -> None:
        """Register custom rate limit policy for a tenant."""
        pass

    @abstractmethod
    def get_rate_limit_policy(self, tenant_id: str) -> RateLimitPolicyContract:
        """Retrieve rate limit policy for a tenant."""
        pass

    @abstractmethod
    def acquire_concurrency_slot(
        self,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Atomically reserve a concurrent execution slot across workers.
        Must be idempotent for identical (tenant_id, task_id).
        """
        pass

    @abstractmethod
    def release_concurrency_slot(
        self,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Atomically release a concurrent execution slot. Idempotent under retries.
        """
        pass

    @abstractmethod
    def reserve_budget(
        self,
        tenant_id: str,
        task_id: str,
        dimension: QuotaDimension,
        amount: float,
        ttl_seconds: int = 60,
        worker_id: Optional[str] = None,
    ) -> BudgetReservationContract:
        """
        Phase 1: Atomically reserve budget before execution across workers.
        """
        pass

    @abstractmethod
    def commit_budget(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        actual_amount: float,
        metadata: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
    ) -> ConsumptionRecordContract:
        """
        Phase 2: Settle actual consumption and refund unused reserved capacity.
        Idempotent and protected against stale/cross-tenant operations.
        """
        pass

    @abstractmethod
    def rollback_budget(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Roll back uncommitted budget reservation with 100% refund. Idempotent.
        """
        pass

    @abstractmethod
    def consume_rate_limit(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> bool:
        """Atomically consume tokens from tenant rate limiter."""
        pass

    @abstractmethod
    def check_rate_limit(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Non-mutating rate limit check returning (allowed, retry_after_seconds, status)."""
        pass

    @abstractmethod
    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Retrieve current usage telemetry snapshot for a tenant."""
        pass

    @abstractmethod
    def get_financial_statement(
        self,
        tenant_id: str,
        dimension: QuotaDimension = QuotaDimension.TOKEN_BUDGET,
    ) -> Dict[str, Any]:
        """Generate structured financial statement for tenant budget accounting."""
        pass


class InMemoryQuotaCoordinator(IQuotaCoordinator):
    """
    Reference In-Memory Implementation of IQuotaCoordinator.
    Provides mutex-synchronized coordination across concurrent worker threads,
    idempotent retry caches, stale operation rejection, and exact financial accounting.

    NOTE: This in-memory implementation uses threading.RLock() for local synchronization.
    It serves as the reference and verification model for future distributed backends (e.g. Redis).
    """

    def __init__(
        self,
        quota_manager: Optional[InMemoryTenantQuotaManager] = None,
        rate_limiter: Optional[InMemoryTokenBucketRateLimiter] = None,
        budget_manager: Optional[ResourceBudgetManager] = None,
    ) -> None:
        self._lock = RLock()
        self.quota_manager = quota_manager or InMemoryTenantQuotaManager()
        self.rate_limiter = rate_limiter or InMemoryTokenBucketRateLimiter()
        self.budget_manager = budget_manager or ResourceBudgetManager(self.quota_manager)

        # Idempotency caches: (tenant_id, task_id) -> record / status
        self._concurrency_records: Dict[Tuple[str, str], str] = {}
        # reservation_id -> ConsumptionRecordContract (for duplicate commit idempotency)
        self._committed_records: Dict[str, ConsumptionRecordContract] = {}
        # reservation_id -> bool (for duplicate rollback idempotency)
        self._rolled_back_reservations: Set[str] = set()

    def register_tenant_quota(self, quota: TenantQuotaContract) -> None:
        with self._lock:
            self.quota_manager.set_tenant_quota(quota)

    def get_tenant_quota(self, tenant_id: str) -> TenantQuotaContract:
        with self._lock:
            return self.quota_manager.get_tenant_quota(tenant_id)

    def set_rate_limit_policy(self, policy: RateLimitPolicyContract) -> None:
        with self._lock:
            self.rate_limiter.set_policy(policy)

    def get_rate_limit_policy(self, tenant_id: str) -> RateLimitPolicyContract:
        with self._lock:
            return self.rate_limiter.get_policy(tenant_id)

    # ── Concurrency Quota Coordination ───────────────────────────────────────

    def acquire_concurrency_slot(
        self,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id must be non-empty.")
        if not task_id or not str(task_id).strip():
            raise ValueError("task_id must be non-empty.")

        with self._lock:
            key = (tenant_id, task_id)
            if key in self._concurrency_records:
                # Idempotent re-acquisition
                return True

            # Atomic Check + Reserve
            acquired = self.quota_manager.acquire_concurrency_slot(tenant_id, task_id)
            if acquired:
                self._concurrency_records[key] = worker_id or "default_worker"
            return acquired

    def release_concurrency_slot(
        self,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            key = (tenant_id, task_id)
            self._concurrency_records.pop(key, None)
            return self.quota_manager.release_concurrency_slot(tenant_id, task_id)

    # ── Two-Phase Budget Coordination ────────────────────────────────────────

    def reserve_budget(
        self,
        tenant_id: str,
        task_id: str,
        dimension: QuotaDimension,
        amount: float,
        ttl_seconds: int = 60,
        worker_id: Optional[str] = None,
    ) -> BudgetReservationContract:
        if amount <= 0:
            raise ValueError("Reservation amount must be strictly positive > 0.")

        with self._lock:
            # Check + Reserve under coordinator lock
            return self.budget_manager.reserve(
                tenant_id=tenant_id,
                task_id=task_id,
                dimension=dimension,
                amount=amount,
                ttl_seconds=ttl_seconds,
            )

    def commit_budget(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        actual_amount: float,
        metadata: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
    ) -> ConsumptionRecordContract:
        with self._lock:
            # Check if this exact reservation was already committed (Idempotency)
            if reservation_id in self._committed_records:
                cached_record = self._committed_records[reservation_id]
                if cached_record.tenant_id != tenant_id:
                    raise UnauthorizedGovernanceError("Cross-tenant commit retry rejected.")
                return cached_record

            # Stale Operation Protection: Check if already rolled back
            if reservation_id in self._rolled_back_reservations:
                raise GovernanceError(
                    f"Stale commit rejected: Reservation '{reservation_id}' was already rolled back.",
                    status_code=409,
                )

            res = self.quota_manager._reservations.get(reservation_id)
            if not res:
                raise GovernanceError(f"Reservation '{reservation_id}' not found.", status_code=404)

            if res.tenant_id != tenant_id:
                raise UnauthorizedGovernanceError(f"Cross-tenant commit rejected for reservation '{reservation_id}'.")

            if res.status != ReservationStatus.PENDING:
                raise GovernanceError(
                    f"Cannot commit reservation '{reservation_id}' in '{res.status}' state.",
                    status_code=409,
                )

            # Settle via BudgetManager
            settlement = self.budget_manager.settle(
                reservation_id=reservation_id,
                tenant_id=tenant_id,
                task_id=task_id,
                actual_consumed=actual_amount,
                metadata=metadata,
            )

            record = ConsumptionRecordContract(
                record_id=settlement["record_id"],
                reservation_id=reservation_id,
                tenant_id=tenant_id,
                task_id=task_id,
                dimension=settlement["dimension"],
                amount_consumed=actual_amount,
                metadata=metadata or {},
            )

            self._committed_records[reservation_id] = record
            return record

    def rollback_budget(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            # Idempotent rollback check
            if reservation_id in self._rolled_back_reservations:
                return True

            # Stale Operation Protection: Check if already committed
            if reservation_id in self._committed_records:
                raise GovernanceError(
                    f"Stale rollback rejected: Reservation '{reservation_id}' was already committed.",
                    status_code=409,
                )

            res = self.quota_manager._reservations.get(reservation_id)
            if not res:
                return False

            if res.tenant_id != tenant_id:
                raise UnauthorizedGovernanceError("Cross-tenant rollback rejected.")

            rolled_back = self.budget_manager.release(reservation_id, tenant_id)
            if rolled_back:
                self._rolled_back_reservations.add(reservation_id)
            return rolled_back

    # ── Rate Limiting Coordination ───────────────────────────────────────────

    def consume_rate_limit(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> bool:
        with self._lock:
            return self.rate_limiter.consume(tenant_id, tokens_required=tokens_required)

    def check_rate_limit(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        with self._lock:
            return self.rate_limiter.check_rate_limit(tenant_id, tokens_required=tokens_required)

    # ── Telemetry & Statements ───────────────────────────────────────────────

    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        with self._lock:
            return self.quota_manager.get_current_usage(tenant_id)

    def get_financial_statement(
        self,
        tenant_id: str,
        dimension: QuotaDimension = QuotaDimension.TOKEN_BUDGET,
    ) -> Dict[str, Any]:
        with self._lock:
            return self.budget_manager.get_financial_statement(tenant_id, dimension=dimension)
