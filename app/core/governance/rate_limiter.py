"""Phase 12.5 Step 4: Token Bucket Rate Limiter Engine.
Provides thread-safe token bucket rate limiting with burst capacity, continuous replenishment,
deterministic retry-after calculations, and strict tenant boundary isolation under mutex.
"""
from datetime import datetime, timezone
from threading import RLock
import time
from typing import Any, Dict, Optional, Tuple

from app.core.contracts.governance import (
    RateLimitAlgorithm,
    RateLimitExceededError,
    RateLimitPolicyContract,
)


class InMemoryTokenBucketRateLimiter:
    """
    Thread-Safe Token Bucket Rate Limiter Engine.
    Enforces requests-per-minute throughput limits and burst capacity per tenant.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        # tenant_id -> RateLimitPolicyContract
        self._policies: Dict[str, RateLimitPolicyContract] = {}
        # tenant_id -> current float token balance
        self._tokens: Dict[str, float] = {}
        # tenant_id -> last refill timestamp float
        self._last_refill: Dict[str, float] = {}

    def _now_seconds(self) -> float:
        return time.time()

    def _get_or_default_policy(self, tenant_id: str) -> RateLimitPolicyContract:
        if tenant_id in self._policies:
            return self._policies[tenant_id]
        default_policy = RateLimitPolicyContract(
            policy_id=f"pol_default_{tenant_id}",
            tenant_id=tenant_id,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            requests_per_minute=60,
            burst_capacity=10,
        )
        self._policies[tenant_id] = default_policy
        return default_policy

    def _refill_tokens_under_lock(self, tenant_id: str, policy: RateLimitPolicyContract) -> None:
        """Continuous token refill calculation based on elapsed time."""
        now = self._now_seconds()
        last_refill = self._last_refill.get(tenant_id, now)
        elapsed = max(0.0, now - last_refill)

        max_capacity = float(policy.requests_per_minute + policy.burst_capacity)
        refill_rate = float(policy.requests_per_minute) / policy.window_seconds  # tokens per second

        current = self._tokens.get(tenant_id, max_capacity)
        replenished = min(max_capacity, current + (elapsed * refill_rate))

        self._tokens[tenant_id] = replenished
        self._last_refill[tenant_id] = now

    def set_policy(self, policy: RateLimitPolicyContract) -> None:
        """Register custom rate limit policy for a tenant."""
        with self._lock:
            self._policies[policy.tenant_id] = policy
            # Reset bucket to full capacity
            max_capacity = float(policy.requests_per_minute + policy.burst_capacity)
            self._tokens[policy.tenant_id] = max_capacity
            self._last_refill[policy.tenant_id] = self._now_seconds()

    def get_policy(self, tenant_id: str) -> RateLimitPolicyContract:
        """Get active rate limit policy for a tenant."""
        with self._lock:
            return self._get_or_default_policy(tenant_id)

    def check_rate_limit(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Non-mutating evaluation of rate limit status.
        Returns (is_allowed, retry_after_seconds, status_metadata).
        """
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id must be non-empty.")

        with self._lock:
            policy = self._get_or_default_policy(tenant_id)
            self._refill_tokens_under_lock(tenant_id, policy)

            current = self._tokens.get(tenant_id, 0.0)
            max_capacity = float(policy.requests_per_minute + policy.burst_capacity)
            refill_rate = float(policy.requests_per_minute) / policy.window_seconds

            if current >= tokens_required:
                return True, 0.0, {
                    "tenant_id": tenant_id,
                    "allowed": True,
                    "available_tokens": current,
                    "max_capacity": max_capacity,
                    "retry_after_seconds": 0.0,
                }
            else:
                missing = tokens_required - current
                retry_after = missing / refill_rate if refill_rate > 0 else policy.window_seconds
                return False, retry_after, {
                    "tenant_id": tenant_id,
                    "allowed": False,
                    "available_tokens": current,
                    "max_capacity": max_capacity,
                    "retry_after_seconds": retry_after,
                }

    def consume(
        self,
        tenant_id: str,
        tokens_required: float = 1.0,
    ) -> bool:
        """
        Atomically consume tokens. If rate limit exceeded, raises RateLimitExceededError (429).
        """
        if tokens_required <= 0:
            raise ValueError("tokens_required must be strictly positive > 0.")

        with self._lock:
            allowed, retry_after, status = self.check_rate_limit(tenant_id, tokens_required)
            if not allowed:
                raise RateLimitExceededError(
                    f"Rate limit exceeded for tenant '{tenant_id}'. Retry after {retry_after:.2f} seconds.",
                    retry_after_seconds=retry_after,
                )

            # Deduct tokens
            self._tokens[tenant_id] -= tokens_required
            return True

    def get_token_balance(self, tenant_id: str) -> float:
        """Get the current available token balance for a tenant."""
        with self._lock:
            policy = self._get_or_default_policy(tenant_id)
            self._refill_tokens_under_lock(tenant_id, policy)
            return self._tokens.get(tenant_id, 0.0)
