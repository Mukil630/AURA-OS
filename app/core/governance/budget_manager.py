"""Phase 12.5 Step 5: Resource Budget & Consumption Accounting Engine.
Provides comprehensive financial and compute accounting for tenant token and compute budgets,
period rollover management (Hourly/Daily/Monthly), two-phase settlement with explicit refund calculation,
and observability statement generation under mutex.
"""
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional
import uuid

from app.core.contracts.governance import (
    BudgetExhaustedError,
    BudgetPeriod,
    BudgetReservationContract,
    ConsumptionRecordContract,
    GovernanceError,
    QuotaDimension,
    ReservationStatus,
    TenantQuotaContract,
    UnauthorizedGovernanceError,
)
from app.core.governance.quota_manager import InMemoryTenantQuotaManager


class ResourceBudgetManager:
    """
    Financial & Compute Accounting Engine for Multi-Tenant Resource Budgets.
    Tracks Allocations, Reservations, Actual Consumptions, Refunds, and Period Rollovers.
    """

    def __init__(self, quota_manager: Optional[InMemoryTenantQuotaManager] = None) -> None:
        self._lock = RLock()
        self.quota_manager = quota_manager or InMemoryTenantQuotaManager()
        # tenant_id -> {dimension -> {"period_key": str, "allocated": float, "consumed": float, "refunded": float}}
        self._accounting_ledger: Dict[str, Dict[QuotaDimension, Dict[str, Any]]] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_period_key(self, period: BudgetPeriod, dt: datetime) -> str:
        """Generate deterministic string key identifying the current budget time window."""
        if period == BudgetPeriod.HOURLY:
            return dt.strftime("%Y-%m-%d-%H")
        elif period == BudgetPeriod.DAILY:
            return dt.strftime("%Y-%m-%d")
        elif period == BudgetPeriod.MONTHLY:
            return dt.strftime("%Y-%m")
        return "perpetual"

    def _ensure_period_window_under_lock(self, tenant_id: str, dimension: QuotaDimension) -> Dict[str, Any]:
        """Check for period rollover and initialize fresh accounting window if period transitioned."""
        quota = self.quota_manager.get_tenant_quota(tenant_id)
        now = self._now()
        period_key = self._get_period_key(quota.budget_period, now)

        tenant_ledger = self._accounting_ledger.setdefault(tenant_id, {})
        record = tenant_ledger.get(dimension)

        if not record or record["period_key"] != period_key:
            # New period window initialized
            allocated = (
                float(quota.max_tokens_per_period)
                if dimension == QuotaDimension.TOKEN_BUDGET
                else float(quota.max_storage_bytes)
            )
            record = {
                "period_key": period_key,
                "period_type": quota.budget_period,
                "period_start": now.isoformat(),
                "allocated": allocated,
                "consumed": 0.0,
                "refunded": 0.0,
            }
            tenant_ledger[dimension] = record

        return record

    def allocate_budget(
        self,
        tenant_id: str,
        dimension: QuotaDimension,
        amount: float,
        period: BudgetPeriod = BudgetPeriod.DAILY,
    ) -> Dict[str, Any]:
        """Explicitly override or set allocated budget for a tenant dimension."""
        if amount < 0:
            raise ValueError("Allocation amount cannot be negative.")

        with self._lock:
            quota = self.quota_manager.get_tenant_quota(tenant_id)
            if dimension == QuotaDimension.TOKEN_BUDGET:
                quota.max_tokens_per_period = int(amount)
                quota.budget_period = period
            elif dimension == QuotaDimension.STORAGE_BYTES:
                quota.max_storage_bytes = int(amount)

            self.quota_manager.set_tenant_quota(quota)
            record = self._ensure_period_window_under_lock(tenant_id, dimension)
            record["allocated"] = float(amount)
            return record

    def reserve(
        self,
        tenant_id: str,
        task_id: str,
        dimension: QuotaDimension,
        amount: float,
        ttl_seconds: int = 60,
    ) -> BudgetReservationContract:
        """
        Phase 1: Reserve budget before execution.
        """
        with self._lock:
            self._ensure_period_window_under_lock(tenant_id, dimension)
            return self.quota_manager.reserve_budget(
                tenant_id=tenant_id,
                task_id=task_id,
                dimension=dimension,
                amount=amount,
                ttl_seconds=ttl_seconds,
            )

    def settle(
        self,
        reservation_id: str,
        tenant_id: str,
        task_id: str,
        actual_consumed: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Phase 2: Settle actual consumption, calculate exact refund, and commit to ledger.
        Returns complete financial accounting statement.
        """
        if actual_consumed < 0:
            raise ValueError("actual_consumed cannot be negative.")

        with self._lock:
            res = self.quota_manager._reservations.get(reservation_id)
            if not res:
                raise GovernanceError(f"Reservation '{reservation_id}' not found.", status_code=404)

            if res.tenant_id != tenant_id:
                raise UnauthorizedGovernanceError("Cross-tenant settlement rejected.")

            reserved_amount = res.reserved_amount
            dimension = res.dimension

            # Commit to quota manager
            record = self.quota_manager.commit_consumption(
                reservation_id=reservation_id,
                tenant_id=tenant_id,
                task_id=task_id,
                actual_amount=actual_consumed,
                metadata=metadata,
            )

            # Update accounting ledger
            ledger_rec = self._ensure_period_window_under_lock(tenant_id, dimension)
            refund_amount = max(0.0, reserved_amount - actual_consumed)
            ledger_rec["consumed"] += actual_consumed
            ledger_rec["refunded"] += refund_amount

            remaining = max(0.0, ledger_rec["allocated"] - ledger_rec["consumed"])

            return {
                "reservation_id": reservation_id,
                "record_id": record.record_id,
                "tenant_id": tenant_id,
                "task_id": task_id,
                "dimension": dimension,
                "reserved_amount": reserved_amount,
                "actual_consumed": actual_consumed,
                "refund_amount": refund_amount,
                "allocated_budget": ledger_rec["allocated"],
                "total_consumed": ledger_rec["consumed"],
                "total_refunded": ledger_rec["refunded"],
                "net_remaining_budget": remaining,
                "period_key": ledger_rec["period_key"],
                "settled_at": self._now().isoformat(),
            }

    def release(self, reservation_id: str, tenant_id: str) -> bool:
        """Roll back an uncommitted reservation with 100% refund."""
        with self._lock:
            res = self.quota_manager._reservations.get(reservation_id)
            if not res:
                return False
            dim = res.dimension
            rolled_back = self.quota_manager.rollback_reservation(reservation_id, tenant_id)
            if rolled_back:
                ledger_rec = self._ensure_period_window_under_lock(tenant_id, dim)
                ledger_rec["refunded"] += res.reserved_amount
            return rolled_back

    def get_financial_statement(
        self,
        tenant_id: str,
        dimension: QuotaDimension = QuotaDimension.TOKEN_BUDGET,
    ) -> Dict[str, Any]:
        """Generate structured financial balance sheet for a tenant's resource consumption."""
        with self._lock:
            ledger_rec = self._ensure_period_window_under_lock(tenant_id, dimension)
            quota = self.quota_manager.get_tenant_quota(tenant_id)
            usage = self.quota_manager.get_current_usage(tenant_id)

            allocated = ledger_rec["allocated"]
            consumed = ledger_rec["consumed"]
            refunded = ledger_rec["refunded"]
            reserved_pending = usage.get("tokens_reserved", 0.0) if dimension == QuotaDimension.TOKEN_BUDGET else 0.0

            remaining = max(0.0, allocated - (consumed + reserved_pending))
            usage_pct = ((consumed + reserved_pending) / allocated * 100.0) if allocated > 0 else 0.0

            return {
                "tenant_id": tenant_id,
                "dimension": dimension,
                "period_key": ledger_rec["period_key"],
                "period_type": ledger_rec["period_type"],
                "period_start": ledger_rec["period_start"],
                "allocated_budget": allocated,
                "total_consumed": consumed,
                "total_refunded": refunded,
                "active_reserved_pending": reserved_pending,
                "net_available_balance": remaining,
                "usage_percentage": round(usage_pct, 2),
                "is_soft_limit_exceeded": usage_pct >= quota.soft_limit_threshold_percent,
                "is_hard_limit_exhausted": remaining <= 0.0,
            }
