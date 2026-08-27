"""Connector Safety Policy, Rate Limiter, and Emergency Kill-Switch Subsystem."""
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set


class ConnectorPolicyEngine:
    """
    Enforces security invariants, rate limits, emergency kill-switches,
    and capability permissions across all external connectors.
    """

    def __init__(self):
        self._disabled_connectors: Set[str] = set()
        self._blocked_capabilities: Set[str] = set()
        self._rate_limits: Dict[str, int] = {}
        self._rate_buckets: Dict[str, List[float]] = defaultdict(list)

    # ── Emergency Kill-Switch ─────────────────────────────────────────────────────────

    def disable_connector(self, connector_id: str) -> None:
        """Trigger emergency stop / kill-switch for a specific connector."""
        self._disabled_connectors.add(connector_id)

    def enable_connector(self, connector_id: str) -> None:
        """Re-enable a previously disabled connector."""
        self._disabled_connectors.discard(connector_id)

    def is_connector_enabled(self, connector_id: str) -> bool:
        """Return True if connector is allowed to execute."""
        return connector_id not in self._disabled_connectors

    # ── Capability Blocklist ──────────────────────────────────────────────────────────

    def block_capability(self, capability_id: str) -> None:
        """Block a specific capability from being executed."""
        self._blocked_capabilities.add(capability_id)

    def unblock_capability(self, capability_id: str) -> None:
        """Unblock a capability."""
        self._blocked_capabilities.discard(capability_id)

    def is_capability_allowed(self, capability_id: str) -> bool:
        """Return True if capability is not explicitly blocked."""
        return capability_id not in self._blocked_capabilities

    # ── Rate Limiting Token Bucket ────────────────────────────────────────────────────

    def set_rate_limit(self, capability_id: str, max_per_minute: int) -> None:
        """Explicitly override rate limit ceiling for a capability."""
        self._rate_limits[capability_id] = max_per_minute

    def check_and_consume_rate_limit(self, capability_id: str, max_per_minute: Optional[int] = None) -> bool:
        """
        Check if capability request conforms to rate limit.
        Returns True if request is allowed, False if rate limited (429).
        """
        ceiling = self._rate_limits.get(capability_id, max_per_minute or 60)
        now = time.time()
        window_start = now - 60.0

        # Purge timestamps older than 60s
        self._rate_buckets[capability_id] = [
            ts for ts in self._rate_buckets[capability_id] if ts > window_start
        ]

        if len(self._rate_buckets[capability_id]) >= ceiling:
            return False

        self._rate_buckets[capability_id].append(now)
        return True

    def reset(self) -> None:
        """Reset all policy and rate limit state."""
        self._disabled_connectors.clear()
        self._blocked_capabilities.clear()
        self._rate_limits.clear()
        self._rate_buckets.clear()


# Global Singleton Instance
default_policy_engine = ConnectorPolicyEngine()
