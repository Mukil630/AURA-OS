"""Connector Circuit Breaker and Fail-Fast Reliability Subsystem."""
import time
from enum import Enum
from typing import Dict, Optional


class CircuitBreakerState(str, Enum):
    """Lifecycle states of the connector circuit breaker."""
    CLOSED = "closed"       # Normal operation, requests pass through
    OPEN = "open"           # Tripped due to failures, requests fail fast immediately
    HALF_OPEN = "half_open" # Trial recovery state to test external service health


class ConnectorCircuitBreaker:
    """
    Guards external integrations from cascading failures.
    Trips open after consecutive faults to prevent resource exhaustion and hanging threads.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 10.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self._states: Dict[str, CircuitBreakerState] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_state_change: Dict[str, float] = {}

    def get_state(self, connector_id: str) -> CircuitBreakerState:
        """Query active circuit state for connector."""
        current_state = self._states.get(connector_id, CircuitBreakerState.CLOSED)
        if current_state == CircuitBreakerState.OPEN:
            elapsed = time.time() - self._last_state_change.get(connector_id, 0.0)
            if elapsed >= self.recovery_timeout:
                self._states[connector_id] = CircuitBreakerState.HALF_OPEN
                self._last_state_change[connector_id] = time.time()
                return CircuitBreakerState.HALF_OPEN
        return current_state

    def can_execute(self, connector_id: str) -> bool:
        """Return True if connector call is permitted."""
        state = self.get_state(connector_id)
        return state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)

    def record_success(self, connector_id: str) -> None:
        """Register successful external dispatch, resetting failure counters."""
        self._failure_counts[connector_id] = 0
        self._states[connector_id] = CircuitBreakerState.CLOSED
        self._last_state_change[connector_id] = time.time()

    def record_failure(self, connector_id: str) -> CircuitBreakerState:
        """Register fault and trip circuit if threshold exceeded."""
        count = self._failure_counts.get(connector_id, 0) + 1
        self._failure_counts[connector_id] = count

        if count >= self.failure_threshold:
            self._states[connector_id] = CircuitBreakerState.OPEN
            self._last_state_change[connector_id] = time.time()
            return CircuitBreakerState.OPEN
        return self._states.get(connector_id, CircuitBreakerState.CLOSED)

    def reset(self, connector_id: Optional[str] = None) -> None:
        """Force reset of circuit breaker state."""
        if connector_id:
            self._states[connector_id] = CircuitBreakerState.CLOSED
            self._failure_counts[connector_id] = 0
            self._last_state_change[connector_id] = time.time()
        else:
            self._states.clear()
            self._failure_counts.clear()
            self._last_state_change.clear()


# Global Singleton Circuit Breaker
default_circuit_breaker = ConnectorCircuitBreaker()
