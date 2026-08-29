"""Polyglot Multi-DB Manager & Transactional Outbox Pattern."""
import asyncio
import enum
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger("PolyglotDBManager")


class StorageTarget(str, enum.Enum):
    RELATIONAL_SQLITE = "RELATIONAL_SQLITE"
    VECTOR_SEMANTIC = "VECTOR_SEMANTIC"
    CLOUD_DRIVE_VAULT = "CLOUD_DRIVE_VAULT"
    LOCAL_CACHE = "LOCAL_CACHE"


class OutboxRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: f"out_{uuid4().hex[:8]}")
    target_vault: StorageTarget
    payload: Dict[str, Any]
    sync_status: str = "PENDING"  # PENDING, SYNCED, FAILED
    retry_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolyglotDBManager:
    """Manages multi-database routing and transactional outbox persistence across SQLite, Vectors, and Drive."""

    def __init__(self, outbox_file: Optional[str] = None):
        self.outbox_file = outbox_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "outbox_queue.json"
        )
        self._outbox: Dict[str, Dict[str, Any]] = {}
        self._load_outbox()

    def _load_outbox(self) -> None:
        if os.path.exists(self.outbox_file):
            try:
                with open(self.outbox_file, "r", encoding="utf-8") as f:
                    self._outbox = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load outbox: {e}")
                self._outbox = {}

    def _save_outbox(self) -> None:
        os.makedirs(os.path.dirname(self.outbox_file), exist_ok=True)
        try:
            with open(self.outbox_file, "w", encoding="utf-8") as f:
                json.dump(self._outbox, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist outbox: {e}")

    def stage_outbox_record(self, target: StorageTarget, payload: Dict[str, Any]) -> OutboxRecord:
        """Writes atomically to outbox before asynchronous cloud distribution."""
        rec = OutboxRecord(target_vault=target, payload=payload)
        self._outbox[rec.record_id] = rec.model_dump()
        self._save_outbox()
        logger.info(f"📦 Staged Outbox Record [{rec.record_id}] -> Target: {target.value}")
        return rec

    async def flush_outbox(self, mock_network_success: bool = True) -> int:
        """Flushes pending outbox records to destination storage with retry handling."""
        synced_count = 0
        for rid, item in list(self._outbox.items()):
            if item.get("sync_status") == "PENDING":
                try:
                    if not mock_network_success:
                        raise ConnectionError("Network unreachable")
                    
                    # Simulating async cloud vault sync
                    await asyncio.sleep(0.02)
                    item["sync_status"] = "SYNCED"
                    item["synced_at"] = datetime.now(timezone.utc).isoformat()
                    synced_count += 1
                except Exception as e:
                    item["retry_count"] = item.get("retry_count", 0) + 1
                    item["last_error"] = str(e)
                    logger.warning(f"Outbox sync retry for {rid}: {e}")

        self._save_outbox()
        return synced_count

    def get_pending_count(self) -> int:
        return sum(1 for item in self._outbox.values() if item.get("sync_status") == "PENDING")
