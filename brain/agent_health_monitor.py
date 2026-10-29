"""
Agent Health Registry & Connectivity Monitor (agent_health_monitor.py)
Tracks live status, latency, and circuit-breaker state of all registered agents.
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from brain.circuit_breaker import CircuitBreaker, BreakerState

logger = logging.getLogger("AgentHealthMonitor")


@dataclass
class AgentHealth:
    name: str
    last_seen: Optional[datetime] = None
    status: str = "UNKNOWN"  # "ONLINE", "OFFLINE", "DEGRADED", "UNKNOWN"
    circuit_breaker: CircuitBreaker = field(default_factory=lambda: CircuitBreaker("default"))
    total_calls: int = 0
    failed_calls: int = 0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status,
            "circuit_breaker": self.circuit_breaker.get_metrics(),
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


class AgentHealthRegistry:
    """
    Central registry for tracking the health and connectivity of every swarm agent.
    Provides circuit breaker lookup, health snapshots, and connectivity status.
    """

    def __init__(self):
        self._agents: Dict[str, AgentHealth] = {}

    def register_agent(self, name: str, failure_threshold: int = 3, timeout: float = 30.0):
        if name not in self._agents:
            cb = CircuitBreaker(name=name, failure_threshold=failure_threshold, timeout_seconds=timeout)
            self._agents[name] = AgentHealth(name=name, circuit_breaker=cb, status="ONLINE")
            logger.info(f"[HealthRegistry] Registered agent: {name}")

    def get_health(self, name: str) -> Optional[AgentHealth]:
        return self._agents.get(name)

    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        health = self._agents.get(name)
        return health.circuit_breaker if health else None

    def record_call_start(self, name: str):
        health = self._agents.get(name)
        if health:
            health.total_calls += 1

    def record_success(self, name: str, latency_ms: float):
        health = self._agents.get(name)
        if health:
            health.circuit_breaker.record_success()
            health.status = "ONLINE"
            health.last_seen = datetime.now()
            # Exponential moving average of latency
            if health.avg_latency_ms == 0:
                health.avg_latency_ms = latency_ms
            else:
                health.avg_latency_ms = 0.7 * health.avg_latency_ms + 0.3 * latency_ms

    def record_failure(self, name: str, exc: Optional[Exception] = None, latency_ms: Optional[float] = None):
        health = self._agents.get(name)
        if health:
            health.failed_calls += 1
            just_opened = health.circuit_breaker.record_failure(exc)
            if just_opened or health.circuit_breaker.state == BreakerState.OPEN:
                health.status = "OFFLINE"
            else:
                health.status = "DEGRADED"
            health.last_seen = datetime.now()
            if latency_ms is not None:
                health.avg_latency_ms = 0.7 * health.avg_latency_ms + 0.3 * latency_ms

    def is_available(self, name: str) -> bool:
        health = self._agents.get(name)
        if not health:
            return False
        return health.circuit_breaker.allow_call()

    def get_snapshot(self) -> Dict[str, Any]:
        return {name: h.to_dict() for name, h in self._agents.items()}

    def get_unhealthy_agents(self) -> list:
        unhealthy = []
        for name, health in self._agents.items():
            if health.status in ("OFFLINE",) or health.circuit_breaker.state == BreakerState.OPEN:
                unhealthy.append(name)
        return unhealthy


health_registry = AgentHealthRegistry()
