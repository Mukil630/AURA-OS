"""Phase 12.5 Step 6: Gateway Admission Controller & Backpressure Guard.
Central decision engine evaluating inbound tasks across rate limits, concurrency ceilings,
estimated token budgets, and storage allocations before granting admission to locks and worker queues.
"""
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional
import uuid

from app.core.contracts.governance import (
    AdmissionDecision,
    AdmissionEvaluationContract,
    AdmissionRequestContract,
    BudgetExhaustedError,
    QuotaDimension,
    QuotaExceededError,
    RateLimitExceededError,
    TenantQuotaContract,
)
from app.core.governance.budget_manager import ResourceBudgetManager
from app.core.governance.quota_manager import InMemoryTenantQuotaManager
from app.core.governance.rate_limiter import InMemoryTokenBucketRateLimiter


class AdmissionController:
    """
    Central Gateway Admission Controller & Backpressure Evaluator.
    Guarantees fail-closed governance before tasks consume compute, mutex locks, or worker leases.
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

    def evaluate_admission(
        self,
        request: AdmissionRequestContract,
        auto_reserve: bool = True,
    ) -> AdmissionEvaluationContract:
        """
        Evaluate an inbound task request against all four governance dimensions.
        If allowed and auto_reserve is True, atomically consumes rate limit tokens,
        acquires concurrency slots, and pre-allocates estimated budget.
        """
        if not isinstance(request, AdmissionRequestContract):
            raise TypeError("request must be an instance of AdmissionRequestContract.")

        tenant_id = request.tenant_id
        task_id = request.task_id
        eval_id = f"eval_{uuid.uuid4().hex[:12]}"

        with self._lock:
            # 1. Rate Limit Check
            allowed_rate, retry_after, rate_status = self.rate_limiter.check_rate_limit(tenant_id, tokens_required=1.0)
            if not allowed_rate:
                return AdmissionEvaluationContract(
                    evaluation_id=eval_id,
                    tenant_id=tenant_id,
                    task_id=task_id,
                    decision=AdmissionDecision.DENY_RATE_LIMIT,
                    allowed=False,
                    reason=f"Rate limit exceeded. Retry after {retry_after:.2f}s.",
                    retry_after_seconds=retry_after,
                    current_usage=rate_status,
                )

            # 2. Concurrency Quota Check
            quota = self.quota_manager.get_tenant_quota(tenant_id)
            active_tasks = self.quota_manager.get_active_concurrency_count(tenant_id)
            if active_tasks + request.required_concurrent > quota.max_concurrent_tasks:
                return AdmissionEvaluationContract(
                    evaluation_id=eval_id,
                    tenant_id=tenant_id,
                    task_id=task_id,
                    decision=AdmissionDecision.DENY_CONCURRENCY,
                    allowed=False,
                    reason=f"Concurrency quota exceeded ({active_tasks}/{quota.max_concurrent_tasks} active).",
                    current_usage={"active_concurrency": active_tasks, "max": quota.max_concurrent_tasks},
                )

            # 3. Estimated Token Budget Check
            usage = self.quota_manager.get_current_usage(tenant_id)
            if request.estimated_tokens > 0:
                current_used_tokens = usage["tokens_used"] + usage["tokens_reserved"]
                if current_used_tokens + request.estimated_tokens > quota.max_tokens_per_period:
                    return AdmissionEvaluationContract(
                        evaluation_id=eval_id,
                        tenant_id=tenant_id,
                        task_id=task_id,
                        decision=AdmissionDecision.DENY_BUDGET,
                        allowed=False,
                        reason=f"Token budget exhausted ({current_used_tokens + request.estimated_tokens} > {quota.max_tokens_per_period}).",
                        current_usage=usage,
                    )

            # 4. Storage Byte Check
            if request.estimated_bytes > 0:
                current_storage = usage["storage_bytes_used"]
                if current_storage + request.estimated_bytes > quota.max_storage_bytes:
                    return AdmissionEvaluationContract(
                        evaluation_id=eval_id,
                        tenant_id=tenant_id,
                        task_id=task_id,
                        decision=AdmissionDecision.DENY_STORAGE,
                        allowed=False,
                        reason=f"Storage allocation exceeded ({current_storage + request.estimated_bytes} > {quota.max_storage_bytes}).",
                        current_usage=usage,
                    )

            # ── All Checks Passed: Commit Admission ───────────────────────────
            reservation_id: Optional[str] = None
            if auto_reserve:
                # Deduct rate limiter token
                self.rate_limiter.consume(tenant_id, tokens_required=1.0)
                # Acquire concurrency slot
                self.quota_manager.acquire_concurrency_slot(tenant_id, task_id)
                # Pre-allocate estimated budget if specified
                if request.estimated_tokens > 0:
                    res = self.budget_manager.reserve(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        dimension=QuotaDimension.TOKEN_BUDGET,
                        amount=float(request.estimated_tokens),
                    )
                    reservation_id = res.reservation_id

            current_usage = self.quota_manager.get_current_usage(tenant_id)
            if reservation_id:
                current_usage["reservation_id"] = reservation_id

            return AdmissionEvaluationContract(
                evaluation_id=eval_id,
                tenant_id=tenant_id,
                task_id=task_id,
                decision=AdmissionDecision.ALLOW,
                allowed=True,
                current_usage=current_usage,
            )

    def complete_task(
        self,
        tenant_id: str,
        task_id: str,
        actual_tokens_consumed: Optional[float] = None,
        reservation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Finalize task execution: Releases concurrency slot and settles token budget consumption.
        """
        with self._lock:
            # Release concurrency slot
            self.quota_manager.release_concurrency_slot(tenant_id, task_id)

            financial_res = None
            if reservation_id and actual_tokens_consumed is not None:
                financial_res = self.budget_manager.settle(
                    reservation_id=reservation_id,
                    tenant_id=tenant_id,
                    task_id=task_id,
                    actual_consumed=actual_tokens_consumed,
                    metadata=metadata,
                )

            return {
                "tenant_id": tenant_id,
                "task_id": task_id,
                "status": "completed",
                "financial_settlement": financial_res,
                "active_concurrency": self.quota_manager.get_active_concurrency_count(tenant_id),
            }

    def abort_task(
        self,
        tenant_id: str,
        task_id: str,
        reservation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Abort task execution: Releases concurrency slot and rolls back uncommitted budget.
        """
        with self._lock:
            self.quota_manager.release_concurrency_slot(tenant_id, task_id)
            refunded = False
            if reservation_id:
                refunded = self.budget_manager.release(reservation_id, tenant_id)

            return {
                "tenant_id": tenant_id,
                "task_id": task_id,
                "status": "aborted",
                "reservation_refunded": refunded,
                "active_concurrency": self.quota_manager.get_active_concurrency_count(tenant_id),
            }
