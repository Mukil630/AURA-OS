"""Phase 12.5 Step 3: Atomic In-Memory Tenant Quota Manager.
Manages multi-dimensional tenant capacity thresholds, active concurrency tracking,
two-phase budget reservations (reserve -> commit/rollback), and soft/hard limit enforcement under mutex.
"""
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, List, Optional, Set
import uuid

from app.core.contracts.governance import (
    BudgetExhaustedError,
    BudgetPeriod,
    BudgetReservationContract,
    ConsumptionRecordContract,
    GovernanceError,
    QuotaDimension,
    QuotaExceededError,
    ReservationStatus,
    StorageLimitExceededError,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)


class InMemoryTenantQuotaManager:
    """
    Thread-Safe Multi-Dimensional Tenant Quota Manager.
    Enforces concurrency limits, token budgets, and storage ceilings with atomic CAS reservations.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        # tenant_id -> TenantQuotaContract
        self._quotas: Dict[str, TenantQuotaContract] = {}
        # tenant_id -> Set of active task_id strings
        self._active_tasks: Dict[str, Set[str]] = {}
        # tenant_id -> Dict of dimension -> accumulated consumption float
        self._accumulated_usage: Dict[str, Dict[QuotaDimension, float]] = {}
        # reservation_id -> BudgetReservationContract
        self._reservations: Dict[str, BudgetReservationContract] = {}
        # tenant_id -> Dict of dimension -> actively reserved float
        self._active_reserved: Dict[str, Dict[QuotaDimension, float]] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_or_default_quota(self, tenant_id: str) -> TenantQuotaContract:
        if tenant_id in self._quotas:
            return self._quotas[tenant_id]
        default_q = TenantQuotaContract(tenant_id=tenant_id)
        self._quotas[tenant_id] = default_q
        return default_q

    def _cleanup_expired_reservations(self) -> None:
        """Sweep expired pending reservations under lock and restore uncommitted quota."""
        now = self._now()
        for res_id, res in list(self._reservations.items()):
            if res.status == ReservationStatus.PENDING and now >= res.expires_at:
                res.status = ReservationStatus.EXPIRED
                t_id = res.tenant_id
                dim = res.dimension
                if t_id in self._active_reserved and dim in self._active_reserved[t_id]:
                    self._active_reserved[t_id][dim] = max(0.0, self._active_reserved[t_id][dim] - res.reserved_amount)

    def set_tenant_quota(self, quota: TenantQuotaContract) -> None:
        """Register or update multi-dimensional quota limits for a tenant."""
        with self._lock:
            self._quotas[quota.tenant_id] = quota

    def get_tenant_quota(self, tenant_id: str) -> TenantQuotaContract:
        """Retrieve active quota contract for a tenant."""
        with self._lock:
            return self._get_or_default_quota(tenant_id)

    # ── Concurrency Quota Tracking ───────────────────────────────────────────

    def acquire_concurrency_slot(self, tenant_id: str, task_id: str) -> bool:
        """
        Atomically reserve a concurrent execution slot for a task.
        Raises QuotaExceededError (429) if tenant exceeds max_concurrent_tasks.
        """
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id must be non-empty.")
        if not task_id or not str(task_id).strip():
            raise ValueError("task_id must be non-empty.")

        with self._lock:
            quota = self._get_or_default_quota(tenant_id)
            active_set = self._active_tasks.setdefault(tenant_id, set())

            # Idempotent re-acquisition
            if task_id in active_set:
                return True

            if len(active_set) >= quota.max_concurrent_tasks:
                raise QuotaExceededError(
                    f"Tenant '{tenant_id}' exceeded max concurrent tasks ({len(active_set)}/{quota.max_concurrent_tasks})."
                )

            active_set.add(task_id)
            return True

    def release_concurrency_slot(self, tenant_id: str, task_id: str) -> bool:
        """Release an active concurrency slot upon task completion. Idempotent."""
        with self._lock:
            active_set = self._active_tasks.get(tenant_id, set())
            if task_id in active_set:
                active_set.remove(task_id)
                return True
            return False

    def get_active_concurrency_count(self, tenant_id: str) -> int:
        """Get the number of in-flight concurrent tasks for a tenant."""
        with self._lock:
            return len(self._active_tasks.get(tenant_id, set()))

    # ── Two-Phase Budget Reservations (Tokens & Storage) ────────────────────

    def reserve_budget(
        self,
        tenant_id: str,
        task_id: str,
        dimension: QuotaDimension,
        amount: float,
        ttl_seconds: int = 60,
    ) -> BudgetReservationContract:
        """
        Phase 1 of Two-Phase Consumption: Atomically reserve estimated budget.
        Checks (used + reserved + amount <= max_limit).
        """
        if amount <= 0:
            raise ValueError("Reservation amount must be strictly positive > 0.")

        with self._lock:
            self._cleanup_expired_reservations()
            quota = self._get_or_default_quota(tenant_id)

            t_used = self._accumulated_usage.setdefault(tenant_id, {}).get(dimension, 0.0)
            t_reserved = self._active_reserved.setdefault(tenant_id, {}).get(dimension, 0.0)

            # Determine max limit for requested dimension
            if dimension == QuotaDimension.TOKEN_BUDGET:
                max_limit = float(quota.max_tokens_per_period)
                if t_used + t_reserved + amount > max_limit:
                    raise BudgetExhaustedError(
                        f"Tenant '{tenant_id}' token budget exhausted (used={t_used}, reserved={t_reserved}, requested={amount}, max={max_limit})."
                    )
            elif dimension == QuotaDimension.STORAGE_BYTES:
                max_limit = float(quota.max_storage_bytes)
                if t_used + t_reserved + amount > max_limit:
                    raise StorageLimitExceededError(
                        f"Tenant '{tenant_id}' storage allocation exceeded (used={t_used}, requested={amount}, max={max_limit})."
                    )

            # Mint reservation
            now = self._now()
            res_id = f"res_{uuid.uuid4().hex[:12]}"
            reservation = BudgetReservationContract(
                reservation_id=res_id,
                tenant_id=tenant_id,
                task_id=task_id,
                dimension=dimension,
                reserved_amount=amount,
                status=ReservationStatus.PENDING,
                granted_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                ttl_seconds=ttl_seconds,
            )

            self._reservations[res_id] = reservation
            self._active_reserved[tenant_id][dimension] = t_reserved + amount

            return reservation

    def commit_consumption(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        actual_amount: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConsumptionRecordContract:
        """
        Phase 2 of Two-Phase Consumption: Settle actual consumption and adjust reserved amount.
        """
        if actual_amount < 0:
            raise ValueError("actual_amount cannot be negative.")

        with self._lock:
            self._cleanup_expired_reservations()
            res = self._reservations.get(reservation_id)
            if not res:
                raise GovernanceError(f"Reservation '{reservation_id}' not found.", status_code=404)

            if res.tenant_id != tenant_id:
                raise UnauthorizedGovernanceError(f"Cross-tenant commitment on reservation '{reservation_id}' rejected.")

            if res.status != ReservationStatus.PENDING:
                raise GovernanceError(f"Cannot commit reservation in '{res.status}' state.", status_code=409)

            dim = res.dimension
            # Remove pending reservation amount
            curr_reserved = self._active_reserved.setdefault(tenant_id, {}).get(dim, 0.0)
            self._active_reserved[tenant_id][dim] = max(0.0, curr_reserved - res.reserved_amount)

            # Accumulate actual used
            curr_used = self._accumulated_usage.setdefault(tenant_id, {}).get(dim, 0.0)
            self._accumulated_usage[tenant_id][dim] = curr_used + actual_amount

            res.status = ReservationStatus.COMMITTED

            record_id = f"rec_{uuid.uuid4().hex[:12]}"
            return ConsumptionRecordContract(
                record_id=record_id,
                reservation_id=reservation_id,
                tenant_id=tenant_id,
                task_id=task_id,
                dimension=dim,
                amount_consumed=actual_amount,
                timestamp=self._now(),
                metadata=metadata or {},
            )

    def rollback_reservation(self, reservation_id: str, tenant_id: str) -> bool:
        """Roll back an uncommitted reservation (e.g. task failed or aborted). Idempotent."""
        with self._lock:
            res = self._reservations.get(reservation_id)
            if not res:
                return False

            if res.tenant_id != tenant_id:
                raise UnauthorizedGovernanceError("Cross-tenant rollback rejected.")

            if res.status == ReservationStatus.PENDING:
                dim = res.dimension
                curr_reserved = self._active_reserved.setdefault(tenant_id, {}).get(dim, 0.0)
                self._active_reserved[tenant_id][dim] = max(0.0, curr_reserved - res.reserved_amount)
                res.status = ReservationStatus.ROLLED_BACK
                return True

            return False

    def get_current_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Return structured snapshot of active concurrency, used tokens, reserved capacity."""
        with self._lock:
            self._cleanup_expired_reservations()
            quota = self._get_or_default_quota(tenant_id)
            active_c = len(self._active_tasks.get(tenant_id, set()))
            used = self._accumulated_usage.get(tenant_id, {})
            reserved = self._active_reserved.get(tenant_id, {})

            tokens_used = used.get(QuotaDimension.TOKEN_BUDGET, 0.0)
            tokens_res = reserved.get(QuotaDimension.TOKEN_BUDGET, 0.0)
            tokens_total = tokens_used + tokens_res
            token_pct = (tokens_total / quota.max_tokens_per_period * 100.0) if quota.max_tokens_per_period > 0 else 0.0

            return {
                "tenant_id": tenant_id,
                "active_concurrent_tasks": active_c,
                "max_concurrent_tasks": quota.max_concurrent_tasks,
                "tokens_used": tokens_used,
                "tokens_reserved": tokens_res,
                "max_tokens_per_period": quota.max_tokens_per_period,
                "token_usage_percent": token_pct,
                "is_soft_limit_exceeded": token_pct >= quota.soft_limit_threshold_percent,
                "storage_bytes_used": used.get(QuotaDimension.STORAGE_BYTES, 0.0),
                "max_storage_bytes": quota.max_storage_bytes,
            }
