"""Phase 12.4: Resource Lock Data Contracts, Enums & Canonical Resource URN Normalizer.
Provides strongly typed contracts for cross-worker shared/exclusive resource locking,
deadlock-free canonical ordering, lock generation tracking, and zero-secret URN validation.
"""
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import Field, model_validator

from app.connectors.router import _contains_raw_secrets
from app.core.contracts.base import VersionedContractBase
from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.leasing import (
    LeaseConflictError,
    LeaseExpiredError,
    LeaseNotFoundError,
    UnauthorizedWorkerError,
)


# ── 1. Lock Modes & Lifecycle Enums ──────────────────────────────────────────

class LockMode(str, Enum):
    """Access mode for a requested or granted resource lock."""
    EXCLUSIVE = "exclusive"  # Write authority: exactly 1 worker, 0 readers
    SHARED = "shared"        # Read capacity: multiple readers, 0 writers


class LockStatus(str, Enum):
    """Lifecycle status of a resource lock."""
    GRANTED = "granted"      # Currently active and held by worker
    RELEASED = "released"    # Voluntarily released by owner
    EXPIRED = "expired"      # Authoritative TTL passed without release
    REVOKED = "revoked"      # Administratively invalidated


# ── 2. Specialized Lock Exception Hierarchy ──────────────────────────────────

class LockConflictError(LeaseConflictError):
    """Raised when an exclusive or shared lock cannot be acquired due to active contention (HTTP 409)."""
    pass


class StaleLockConflictError(LeaseConflictError):
    """Raised when a stale lock generation attempts release or authoritative state mutation (HTTP 409)."""
    pass


class LockNotFoundError(LeaseNotFoundError):
    """Raised when operating on a non-existent or un-tracked resource lock (HTTP 404)."""
    pass


class LockExpiredError(LeaseExpiredError):
    """Raised when attempting an operation on an expired resource lock (HTTP 410)."""
    pass


class UnauthorizedLockError(UnauthorizedWorkerError):
    """Raised when cross-tenant or unauthorized workers attempt lock operations (HTTP 403)."""
    pass


# ── 3. Canonical Resource URN Normalizer ─────────────────────────────────────

from app.security.sanitizer import SECRET_PATTERNS


def canonicalize_resource_id(raw_resource_id: str) -> str:
    """
    Deterministic normalization of resource identifiers into standard canonical URNs.
    Enforces lowercase, strips whitespace/redundant slashes, and validates zero raw secrets.

    Examples:
        'github://Mukil630/AURA-OS/' -> 'github://mukil630/aura-os'
        'DRIVE://Vault/1iaHz/'        -> 'drive://vault/1iahz'
        'api_quota:telegram'          -> 'resource://api_quota:telegram'
    """
    if not raw_resource_id or not str(raw_resource_id).strip():
        raise ValueError("raw_resource_id must be a non-empty string.")

    cleaned = str(raw_resource_id).strip()

    # Zero-secret inspection
    cleaned_lower = cleaned.lower()
    sensitive_keywords = ["password", "private_key", "secret_token", "access_token", "auth_token"]
    secret_prefixes = ["ghp_", "gho_", "ghu_", "ghs_", "ghr_", "ya29.", "bearer "]
    if (
        _contains_raw_secrets(cleaned)
        or any(p.search(cleaned) for p in SECRET_PATTERNS)
        or any(kw in cleaned_lower for kw in sensitive_keywords)
        or any(prefix in cleaned_lower for prefix in secret_prefixes)
    ):
        raise RawSecretPayloadError(
            "Resource identifiers must never contain raw credentials or secret tokens."
        )

    if "://" in cleaned:
        scheme, path = cleaned.split("://", 1)
        scheme_norm = scheme.strip().lower()
        path_norm = re.sub(r"/+", "/", path.strip()).strip("/").lower()
        return f"{scheme_norm}://{path_norm}"
    else:
        path_norm = re.sub(r"/+", "/", cleaned).strip("/").lower()
        return f"resource://{path_norm}"


# ── 4. Resource Lock Contract ────────────────────────────────────────────────

class ResourceLockContract(VersionedContractBase):
    """
    Represents an active, held, or historic resource lock granted to a worker for a specific task.
    """
    lock_id: str = Field(
        ...,
        min_length=1,
        description="Unique resource lock grant identifier.",
    )
    canonical_resource_id: str = Field(
        ...,
        min_length=1,
        description="Canonical URN representing the locked external resource.",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Mandatory tenant boundary identifier.",
    )
    worker_id: str = Field(
        ...,
        min_length=1,
        description="Registered worker node or container holding the lock.",
    )
    task_id: str = Field(
        ...,
        min_length=1,
        description="Task on whose behalf the lock was acquired.",
    )
    mode: LockMode = Field(
        default=LockMode.EXCLUSIVE,
        description="Access mode: EXCLUSIVE (write) or SHARED (read).",
    )
    lock_generation: int = Field(
        default=1,
        ge=1,
        description="Strictly monotonic lock generation epoch for this resource (stale release defense).",
    )
    status: LockStatus = Field(
        default=LockStatus.GRANTED,
        description="Current lifecycle status of the resource lock.",
    )
    granted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the lock was granted.",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the lock authority expires.",
    )
    reentrant_count: int = Field(
        default=0,
        ge=0,
        description="Number of re-entrant acquisitions by the same worker.",
    )
    lock_ttl_seconds: int = Field(
        default=30,
        gt=0,
        description="Base TTL in seconds for the resource lock.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary lock context metadata (zero raw secrets allowed).",
    )

    @model_validator(mode="after")
    def validate_lock_invariants(self) -> "ResourceLockContract":
        """Enforce strict temporal, identity, and canonical consistency."""
        if not self.lock_id or not self.lock_id.strip():
            raise ValueError("lock_id must be non-empty.")
        if not self.canonical_resource_id or not self.canonical_resource_id.strip():
            raise ValueError("canonical_resource_id must be non-empty.")
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not self.worker_id or not self.worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if self.lock_generation < 1:
            raise ValueError("lock_generation must be a positive integer >= 1.")
        if self.lock_ttl_seconds <= 0:
            raise ValueError("lock_ttl_seconds must be strictly positive > 0.")
        if self.reentrant_count < 0:
            raise ValueError("reentrant_count cannot be negative.")
        if self.expires_at <= self.granted_at:
            raise ValueError("expires_at must logically occur strictly after granted_at.")

        # Zero-secret validation on metadata
        if _contains_raw_secrets(self.metadata):
            raise RawSecretPayloadError("Resource lock metadata must never contain raw secrets.")

        return self


# ── 5. Multi-Resource Lock Batch Request (Deadlock-Free Ordering) ─────────────

class ResourceBatchItem(VersionedContractBase):
    """Single resource entry in a multi-resource lock batch request."""
    resource_id: str = Field(..., min_length=1)
    mode: LockMode = Field(default=LockMode.EXCLUSIVE)


class MultiResourceLockBatchRequest(VersionedContractBase):
    """
    Represents an atomic request to acquire multiple resource locks.
    Provides canonical lexicographical sorting to eliminate circular-wait deadlocks.
    """
    request_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    worker_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    items: List[ResourceBatchItem] = Field(..., min_length=1)
    lock_ttl_seconds: int = Field(default=30, gt=0)
    acquire_timeout_seconds: float = Field(default=5.0, gt=0.0)

    def get_canonical_ordered_items(self) -> List[Tuple[str, LockMode]]:
        """
        Normalize all resource IDs and return them sorted in deterministic lexicographical order.
        Guarantees that all workers acquire multi-resource batches in the exact same sequence.
        """
        canonical_map: Dict[str, LockMode] = {}
        for item in self.items:
            c_urn = canonicalize_resource_id(item.resource_id)
            # If same resource specified multiple times, EXCLUSIVE takes precedence over SHARED
            if c_urn in canonical_map:
                if item.mode == LockMode.EXCLUSIVE:
                    canonical_map[c_urn] = LockMode.EXCLUSIVE
            else:
                canonical_map[c_urn] = item.mode

        # Sort lexicographically by canonical URN
        return sorted(canonical_map.items(), key=lambda x: x[0])
