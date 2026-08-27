"""Comprehensive Reliability Controller, Bounded Retry, and Fail-Fast Orchestrator."""
import asyncio
import random
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.contracts.connector import ConnectorExecutionResult
from app.reliability.circuit_breaker import (
    CircuitBreakerState,
    ConnectorCircuitBreaker,
    default_circuit_breaker,
)
from app.reliability.idempotency import (
    IdempotencyLedger,
    default_idempotency_ledger,
)
from app.security.sanitizer import SecretSanitizer


class DeadLetterRecord(BaseModel):
    """Entry stored in the Dead-Letter Queue (DLQ) after retry exhaustion or non-recoverable error."""
    task_id: Optional[str] = None
    capability_id: str
    connector_id: str
    action_hash: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    error_message: str
    status_code: int
    failed_at: float = Field(default_factory=time.time)
    attempts: int


class RetryClassifier:
    """Classifies HTTP status codes and error messages into retryable vs non-retryable categories."""

    @staticmethod
    def is_retryable(status_code: Optional[int], error_message: Optional[str] = None) -> bool:
        """
        Return True if error is transient (500, 502, 503, 504, 429, timeouts).
        Return False for permanent / client errors (400, 401, 403, 404, 422).
        """
        if status_code in (500, 502, 503, 504, 429):
            return True

        if status_code in (400, 401, 403, 404, 422):
            return False

        if error_message:
            msg_lower = error_message.lower()
            if any(w in msg_lower for w in ["timeout", "timed out", "connection reset", "econnreset", "network drop", "503", "502", "500", "429"]):
                return True
            if any(w in msg_lower for w in ["401", "403", "unauthorized", "forbidden", "permission denied", "not found", "404", "invalid argument", "syntax error"]):
                return False

        return False


class ReliabilityController:
    """
    Central Reliability Controller enforcing:
      1. Concurrent Circuit Breaker Protection (fail-fast without upstream hammering)
      2. Strictly bounded retries (Max Retries = N, NO infinite loops)
      3. Exponential backoff with jitter
      4. Idempotency dedup across network drops
      5. Dead-Letter Queue (DLQ) for unrecoverable failures
    """

    def __init__(
        self,
        circuit_breaker: Optional[ConnectorCircuitBreaker] = None,
        idempotency_ledger: Optional[IdempotencyLedger] = None,
        max_retries_default: int = 2,
        base_backoff_seconds: float = 0.05,
    ):
        self.circuit_breaker = circuit_breaker or default_circuit_breaker
        self.idempotency_ledger = idempotency_ledger or default_idempotency_ledger
        self.max_retries_default = max_retries_default
        self.base_backoff = base_backoff_seconds
        self.dead_letter_queue: List[DeadLetterRecord] = []

    async def execute_with_reliability(
        self,
        connector_id: str,
        capability_id: str,
        callable_fn: Callable[[], Coroutine[Any, Any, ConnectorExecutionResult]],
        action_hash: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: float = 30.0,
    ) -> ConnectorExecutionResult:
        """
        Execute an external connector capability with comprehensive reliability guarantees.
        """
        start_time = time.time()
        max_attempts = (max_retries if max_retries is not None else self.max_retries_default) + 1

        # ── 1. Circuit Breaker Pre-Flight Check ───────────────────────────────────────
        if not self.circuit_breaker.can_execute(connector_id):
            return ConnectorExecutionResult(
                request_id="creq_circuit_open",
                capability_id=capability_id,
                success=False,
                status_code=503,
                error_message=f"Service Unavailable: Circuit breaker is OPEN for '{connector_id}'. Failing fast.",
                latency_ms=round((time.time() - start_time) * 1000, 2),
            )

        # ── 2. Idempotency Pre-Flight Check ───────────────────────────────────────────
        if idempotency_key:
            cached = self.idempotency_ledger.get(idempotency_key, action_hash=action_hash)
            if cached:
                return ConnectorExecutionResult(
                    request_id="creq_idempotent_hit",
                    capability_id=capability_id,
                    success=True,
                    status_code=cached.status_code,
                    data={**cached.result_data, "idempotent_hit": True},
                    latency_ms=round((time.time() - start_time) * 1000, 2),
                )

        # ── 3. Bounded Retry Loop with Exponential Backoff ───────────────────────────
        last_result: Optional[ConnectorExecutionResult] = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Execute with strict timeout budget
                result = await asyncio.wait_for(callable_fn(), timeout=timeout_seconds)
                last_result = result

                if result.success:
                    # Success: Record in circuit breaker and idempotency ledger
                    self.circuit_breaker.record_success(connector_id)
                    if idempotency_key and action_hash:
                        self.idempotency_ledger.record(
                            idempotency_key=idempotency_key,
                            action_hash=action_hash,
                            capability_id=capability_id,
                            result_data=result.data or {},
                            status_code=result.status_code,
                        )
                    return result

                # Execution failed: Check retryability
                self.circuit_breaker.record_failure(connector_id)
                if not RetryClassifier.is_retryable(result.status_code, result.error_message):
                    # Non-retryable (e.g. 401, 403, 404): Terminate immediately
                    break

            except asyncio.TimeoutError:
                self.circuit_breaker.record_failure(connector_id)
                last_result = ConnectorExecutionResult(
                    request_id="creq_timeout",
                    capability_id=capability_id,
                    success=False,
                    status_code=504,
                    error_message=f"Gateway Timeout: Capability '{capability_id}' exceeded {timeout_seconds}s.",
                    latency_ms=round((time.time() - start_time) * 1000, 2),
                )

            except Exception as ex:
                self.circuit_breaker.record_failure(connector_id)
                last_result = ConnectorExecutionResult(
                    request_id="creq_exception",
                    capability_id=capability_id,
                    success=False,
                    status_code=500,
                    error_message=SecretSanitizer.sanitize_text(f"Unhandled fault: {str(ex)}"),
                    latency_ms=round((time.time() - start_time) * 1000, 2),
                )

            # If more attempts remain, apply exponential backoff + jitter
            if attempt < max_attempts:
                jitter = random.uniform(0.01, 0.03)
                delay = (self.base_backoff * (2 ** (attempt - 1))) + jitter
                await asyncio.sleep(delay)

        # ── 4. Retry Exhaustion -> Route to Dead-Letter Queue (DLQ) ───────────────────
        dlq_entry = DeadLetterRecord(
            task_id=task_id,
            capability_id=capability_id,
            connector_id=connector_id,
            action_hash=action_hash,
            parameters=SecretSanitizer.sanitize_dict(parameters or {}),
            error_message=SecretSanitizer.sanitize_text(last_result.error_message) if last_result and last_result.error_message else "Execution exhausted retries.",
            status_code=last_result.status_code if last_result else 500,
            attempts=max_attempts,
        )
        self.dead_letter_queue.append(dlq_entry)

        return last_result or ConnectorExecutionResult(
            request_id="creq_exhausted",
            capability_id=capability_id,
            success=False,
            status_code=500,
            error_message="Retry exhaustion: Maximum retry limit reached.",
            latency_ms=round((time.time() - start_time) * 1000, 2),
        )


# Global Singleton Reliability Controller
default_reliability_controller = ReliabilityController()
