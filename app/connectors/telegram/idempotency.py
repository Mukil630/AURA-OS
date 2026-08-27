"""Replay Guard and Idempotency Subsystem for Telegram Updates."""
import time
from typing import Dict, Optional, Set


class TelegramReplayGuard:
    """
    Guarantees idempotency for incoming Telegram updates.
    Prevents duplicate task creation if Telegram retries webhook delivery.
    """

    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._processed_updates: Dict[int, float] = {}
        self._update_to_task: Dict[int, str] = {}

    def is_duplicate(self, update_id: int) -> bool:
        """Check if update_id was previously seen within TTL window."""
        self._cleanup_expired()
        return update_id in self._processed_updates

    def record_update(self, update_id: int, task_id: Optional[str] = None) -> None:
        """Record update_id with timestamp and associated task ID."""
        self._cleanup_expired()
        self._processed_updates[update_id] = time.time()
        if task_id:
            self._update_to_task[update_id] = task_id

    def get_associated_task_id(self, update_id: int) -> Optional[str]:
        """Retrieve task_id spawned from an update_id."""
        return self._update_to_task.get(update_id)

    def _cleanup_expired(self) -> None:
        """Purge entries older than TTL window."""
        now = time.time()
        cutoff = now - self.ttl_seconds
        expired_ids = [uid for uid, ts in self._processed_updates.items() if ts < cutoff]
        for uid in expired_ids:
            self._processed_updates.pop(uid, None)
            self._update_to_task.pop(uid, None)

        # Evict oldest if exceeding max entries
        if len(self._processed_updates) > self.max_entries:
            sorted_items = sorted(self._processed_updates.items(), key=lambda x: x[1])
            excess = len(self._processed_updates) - self.max_entries
            for uid, _ in sorted_items[:excess]:
                self._processed_updates.pop(uid, None)
                self._update_to_task.pop(uid, None)

    def reset(self) -> None:
        """Reset replay cache."""
        self._processed_updates.clear()
        self._update_to_task.clear()
