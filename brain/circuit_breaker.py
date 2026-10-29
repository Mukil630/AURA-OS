"""
Circuit Breaker for Multi-Agent Connectivity (circuit_breaker.py)
Prevents cascading failures when an agent is unreachable or timing out.
"""
import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("CircuitBreaker")


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker pattern for agent-to-agent calls.
    - CLOSED: Normal operation, calls go through.
    - OPEN: Failures exceeded threshold, calls blocked until reset_timeout expires.
    - HALF_OPEN: Probe state — allow one test call.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout_seconds: float = 30.0,
        expected_exceptions: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exceptions = expected_exceptions
        self._state: BreakerState = BreakerState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> BreakerState:
        if self._state == BreakerState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.timeout_seconds:
                logger.info(f"[Breaker:{self.name}] Timeout elapsed, transitioning to HALF_OPEN")
                self._state = BreakerState.HALF_OPEN
        return self._state

    def allow_call(self) -> bool:
        """Check if a call is allowed through the breaker."""
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.HALF_OPEN:
            return True
        return False  # OPEN — blocked

    def record_success(self):
        """Record a successful call, resetting the breaker."""
        if self._state != BreakerState.CLOSED:
            logger.info(f"[Breaker:{self.name}] Call succeeded, resetting to CLOSED")
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def record_failure(self, exc: Optional[Exception] = None) -> bool:
        """
        Record a failure. Returns True if the breaker just opened.
        """
        self._failure_count += 1
        self._last_failure_time = time.time()
        if exc:
            logger.warning(f"[Breaker:{self.name}] Failure #{self._failure_count}: {type(exc).__name__}: {exc}")

        if self._failure_count >= self.failure_threshold:
            if self._state != BreakerState.OPEN:
                logger.error(f"[Breaker:{self.name}] Failure threshold ({self.failure_threshold}) reached, OPENING breaker")
            self._state = BreakerState.OPEN
            return True
        return False

    def get_metrics(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout_seconds": self.timeout_seconds,
            "last_failure_time": self._last_failure_time,
        }
