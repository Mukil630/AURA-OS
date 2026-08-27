"""Phase 12.3: Version 1 Data Contracts and Enums for Distributed Task Queue & Worker Leasing.
Enforces exclusive single-ownership, monotonic fencing tokens, tenant isolation, and zero raw credential fields.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from pydantic import Field, model_validator

from app.core.contracts.base import VersionedContractBase
from app.core.enums.common import PriorityLevel


# ── 1. Explicit Lifecycle Enums ──────────────────────────────────────────────

class LeaseStatus(str, Enum):
    """Lifecycle states for an exclusive worker task lease."""
    ACQUIRED = "acquired"    # Lease is active and held by a live worker
    RENEWED = "renewed"      # Lease duration was extended via heartbeat
    EXPIRED = "expired"      # Lease timed out without renewal; eligible for reclaim
    RELEASED = "released"    # Task completed normally and lease was voluntarily freed
    REVOKED = "revoked"      # Lease was administratively terminated or superseded


class WorkerStatus(str, Enum):
    """Operational states for distributed task queue workers."""
    ACTIVE = "active"        # Worker is healthy and accepting task leases
    DRAINING = "draining"    # Finishing existing leases, rejecting new acquisitions
    STOPPED = "stopped"      # Worker process has terminated
    DEGRADED = "degraded"    # Worker experiencing resource starvation or errors


# ── 2. Deterministic Lease Exception Hierarchy ───────────────────────────────

class LeaseError(HTTPException):
    """Base exception for all worker leasing and queue failures."""
    pass


class LeaseConflictError(LeaseError):
    """Raised when a worker attempts to acquire a task already leased by another worker (409)."""
    def __init__(self, detail: str = "Task is already leased by another active worker."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class StaleLeaseConflictError(LeaseError):
    """Raised when a zombie/stale worker attempts to write with an expired or superseded fencing token (409)."""
    def __init__(self, detail: str = "Stale lease fencing token: write rejected."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class LeaseNotFoundError(LeaseError):
    """Raised when a requested lease ID does not exist or tenant mismatch occurs (404)."""
    def __init__(self, detail: str = "Lease not found."):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class LeaseExpiredError(LeaseError):
    """Raised when attempting to renew or commit an expired lease (410)."""
    def __init__(self, detail: str = "Lease has expired and cannot be renewed."):
        super().__init__(status_code=status.HTTP_410_GONE, detail=detail)


class UnauthorizedWorkerError(LeaseError):
    """Raised when a worker attempts to operate on a lease it does not own (403)."""
    def __init__(self, detail: str = "Worker is not authorized for this lease."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ── 3. Core Task Lease Contract ──────────────────────────────────────────────

class TaskLeaseContract(VersionedContractBase):
    """
    Represents exclusive, time-bounded ownership of a task by a distributed worker.
    Includes strictly monotonic fencing token to prevent zombie worker split-brain state writes.
    """
    lease_id: str = Field(
        ...,
        min_length=1,
        description="Globally unique lease identifier (e.g. UUIDv4).",
    )
    task_id: str = Field(
        ...,
        min_length=1,
        description="Immutable Task ID under exclusive lease.",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Mandatory tenant boundary identifier.",
    )
    worker_id: str = Field(
        ...,
        min_length=1,
        description="Mandatory identity of the worker holding this lease.",
    )
    fencing_token: int = Field(
        ...,
        ge=1,
        description="Strictly positive monotonically increasing counter (1, 2, 3...) per task lease cycle.",
    )
    status: LeaseStatus = Field(
        default=LeaseStatus.ACQUIRED,
        description="Current lifecycle state of the lease.",
    )
    acquired_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the lease was granted.",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp after which this lease is considered EXPIRED.",
    )
    renewal_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this lease has been successfully extended.",
    )
    lease_ttl_seconds: int = Field(
        default=30,
        gt=0,
        description="Base lease duration in seconds (must be > 0).",
    )

    @model_validator(mode="after")
    def validate_lease_invariants(self) -> "TaskLeaseContract":
        """Enforce strict temporal and identity consistency."""
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not self.worker_id or not self.worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if not self.lease_id or not self.lease_id.strip():
            raise ValueError("lease_id must be non-empty.")
        if self.fencing_token < 1:
            raise ValueError("fencing_token must be a strictly positive integer >= 1.")
        if self.lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be strictly positive > 0.")
        if self.renewal_count < 0:
            raise ValueError("renewal_count cannot be negative.")
        if self.expires_at <= self.acquired_at:
            raise ValueError("expires_at must logically occur strictly after acquired_at.")
        return self


# ── 4. Distributed Queue Message Contract ────────────────────────────────────

class QueueMessageContract(VersionedContractBase):
    """
    Represents an enqueued task execution message sitting in the distributed queue.
    Contains strictly tenant-bound context and indirect credential references only.
    """
    message_id: str = Field(
        ...,
        min_length=1,
        description="Unique message queue identifier.",
    )
    task_id: str = Field(
        ...,
        min_length=1,
        description="Immutable Task ID queued for execution.",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Mandatory tenant boundary identifier.",
    )
    priority: PriorityLevel = Field(
        default=PriorityLevel.NORMAL,
        description="Queue scheduling priority.",
    )
    enqueued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the message entered the queue.",
    )
    attempt_count: int = Field(
        default=0,
        ge=0,
        description="Number of execution attempts previously made.",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum allowed retry attempts before DLQ routing.",
    )
    next_attempt_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Earliest UTC timestamp when this message is eligible for worker pickup.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task execution parameters (carries credential_ref only, zero raw secret fields).",
    )

    @model_validator(mode="after")
    def validate_queue_invariants(self) -> "QueueMessageContract":
        """Enforce retry bounds, tenant identity, and zero raw credential keys."""
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must be non-empty.")
        if not self.message_id or not self.message_id.strip():
            raise ValueError("message_id must be non-empty.")
        if self.attempt_count < 0:
            raise ValueError("attempt_count cannot be negative.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1.")
        if self.attempt_count > self.max_attempts:
            raise ValueError(f"attempt_count ({self.attempt_count}) cannot exceed max_attempts ({self.max_attempts}).")
        return self


# ── 5. Worker Heartbeat Contract ─────────────────────────────────────────────

class WorkerHeartbeatContract(VersionedContractBase):
    """
    Represents worker liveness, health telemetry, and currently held task leases.
    """
    worker_id: str = Field(
        ...,
        min_length=1,
        description="Unique worker node or container identifier.",
    )
    hostname: str = Field(
        default="localhost",
        description="Host machine name or worker runtime node.",
    )
    active_leases: List[str] = Field(
        default_factory=list,
        description="List of lease_ids currently held and actively processed by this worker.",
    )
    last_heartbeat_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the latest liveness signal.",
    )
    status: WorkerStatus = Field(
        default=WorkerStatus.ACTIVE,
        description="Current operational status of the worker daemon.",
    )

    @model_validator(mode="after")
    def validate_worker_invariants(self) -> "WorkerHeartbeatContract":
        if not self.worker_id or not self.worker_id.strip():
            raise ValueError("worker_id must be non-empty.")
        return self
