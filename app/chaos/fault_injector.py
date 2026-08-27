"""Chaos Testing and Controlled Fault Injection Engine."""
from enum import Enum
from typing import Dict, List, Optional


class ChaosFaultType(str, Enum):
    """Types of synthetic faults for chaos engineering tests."""
    TIMEOUT = "timeout"
    SERVER_ERROR_500 = "server_error_500"
    BAD_GATEWAY_502 = "bad_gateway_502"
    RATE_LIMIT_429 = "rate_limit_429"
    CORRUPT_PAYLOAD = "corrupt_payload"
    NETWORK_DROP = "network_drop"


class ChaosFaultInjector:
    """
    Simulates real-world infrastructure failures to prove agent resilience.
    Can inject synthetic network partitions, rate limits, 500s, and payload corruptions.
    """

    def __init__(self):
        self._fault_queue: Dict[str, List[ChaosFaultType]] = {}

    def inject_fault(self, capability_id: str, fault_type: ChaosFaultType, count: int = 1) -> None:
        """Queue one or more faults for a specific capability."""
        if capability_id not in self._fault_queue:
            self._fault_queue[capability_id] = []
        for _ in range(count):
            self._fault_queue[capability_id].append(fault_type)

    def consume_fault(self, capability_id: str) -> Optional[ChaosFaultType]:
        """Check if an active fault is queued for capability and consume it."""
        if capability_id in self._fault_queue and self._fault_queue[capability_id]:
            return self._fault_queue[capability_id].pop(0)
        return None

    def has_fault(self, capability_id: str) -> bool:
        """Check if faults remain queued."""
        return bool(self._fault_queue.get(capability_id))

    def clear_all(self) -> None:
        """Reset all queued faults."""
        self._fault_queue.clear()


# Global Singleton Chaos Injector
default_chaos_injector = ChaosFaultInjector()
