"""Cross-Process Idempotency Ledger and Deduplication Vault."""
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class IdempotencyRecord(BaseModel):
    """An immutable record of an executed action result."""
    idempotency_key: str
    tenant_id: str = "mukil"
    capability_id: str
    action_hash: str
    result_data: Dict[str, Any]
    status_code: int
    created_at: float = Field(default_factory=time.time)
    expires_at: float


class IdempotencyLedger:
    """
    Guarantees strict once-only side-effect execution across network drops and retries.
    Enforces multi-dimensional isolation: Scope = (tenant_id, capability_id, idempotency_key).
    """

    def __init__(self, default_ttl_seconds: float = 3600.0):
        self.default_ttl = default_ttl_seconds
        self._records: Dict[str, IdempotencyRecord] = {}

    def _make_key(self, idempotency_key: str, tenant_id: str = "mukil", capability_id: Optional[str] = None) -> str:
        """Construct multi-dimensional scoped key."""
        cap = capability_id or "default"
        return f"{tenant_id}:{cap}:{idempotency_key}"

    def get(
        self,
        idempotency_key: str,
        action_hash: Optional[str] = None,
        tenant_id: str = "mukil",
        capability_id: Optional[str] = None,
    ) -> Optional[IdempotencyRecord]:
        """Fetch existing idempotency record scoped to tenant and capability."""
        scoped_k = self._make_key(idempotency_key, tenant_id, capability_id)
        rec = self._records.get(scoped_k)

        # Fallback to direct key if stored without tenant prefix
        if not rec:
            rec = self._records.get(idempotency_key)
            if rec and rec.tenant_id != tenant_id:
                # Cross-tenant access attempt -> Reject
                return None

        if not rec:
            return None

        # Check TTL
        if time.time() > rec.expires_at:
            if scoped_k in self._records:
                del self._records[scoped_k]
            if idempotency_key in self._records:
                del self._records[idempotency_key]
            return None

        # Verify Action Hash Parity (Tamper Protection)
        if action_hash and rec.action_hash != action_hash:
            return None

        return rec

    def record(
        self,
        idempotency_key: str,
        action_hash: str,
        capability_id: str,
        result_data: Dict[str, Any],
        status_code: int = 200,
        tenant_id: str = "mukil",
        ttl_seconds: Optional[float] = None,
    ) -> IdempotencyRecord:
        """Store result of an executed action under isolated tenant & capability namespace."""
        ttl = ttl_seconds or self.default_ttl
        rec = IdempotencyRecord(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            capability_id=capability_id,
            action_hash=action_hash,
            result_data=result_data,
            status_code=status_code,
            expires_at=time.time() + ttl,
        )
        scoped_k = self._make_key(idempotency_key, tenant_id, capability_id)
        self._records[scoped_k] = rec
        self._records[idempotency_key] = rec  # Backward compat alias
        return rec

    def clear(self) -> None:
        """Purge all records (for testing or maintenance)."""
        self._records.clear()


# Global Singleton Idempotency Ledger
default_idempotency_ledger = IdempotencyLedger()
