"""Version 1 Data Contracts and Exceptions for Credential Isolation and Tenant Vault."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import ConnectorType


class CredentialStatus(str, Enum):
    """Lifecycle states for a tenant-scoped credential reference."""
    ACTIVE = "active"        # Fully operational, valid for execution
    ROTATING = "rotating"    # In migration window (graceful transition)
    DISABLED = "disabled"    # Temporarily suspended by operator policy
    REVOKED = "revoked"      # Permanently invalidated (fails fast with 403)


# ── Deterministic Exception Hierarchy ────────────────────────────────────────

class CredentialError(HTTPException):
    """Base exception for all credential vault failures."""
    pass


class CredentialNotFoundError(CredentialError):
    """Raised when a credential ref does not exist OR belongs to another tenant (404)."""
    def __init__(self, detail: str = "Credential reference not found."):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ProviderMismatchError(CredentialError):
    """Raised when a credential is used against an incompatible connector (400)."""
    def __init__(self, detail: str = "Credential provider mismatch."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class CredentialRevokedError(CredentialError):
    """Raised when an attempt is made to resolve a REVOKED or DISABLED credential (403)."""
    def __init__(self, detail: str = "Credential reference is inactive or revoked."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class RawSecretPayloadError(CredentialError):
    """Raised when a client/LLM payload contains forbidden raw secret tokens (422)."""
    def __init__(self, detail: str = "Raw secrets are forbidden in task parameters. Use credential_ref."):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


# ── Public Metadata Contract (Zero Secret Material) ──────────────────────────

class CredentialRefContract(VersionedContractBase):
    """
    Public metadata contract representing an indirect credential reference.
    Contains ZERO raw secret material. Safe for Planner, Audit Logs, and APIs.
    """
    credential_ref: str = Field(
        ...,
        description="Unique tenant-scoped alias (e.g. 'github_prod_mukil')."
    )
    tenant_id: str = Field(
        ...,
        description="Immutable tenant boundary identifier."
    )
    provider: ConnectorType = Field(
        ...,
        description="Target external connector (github | google_drive | telegram | pc_sidecar)."
    )
    purpose: str = Field(
        default="general",
        description="Operational intent or scope description."
    )
    status: CredentialStatus = Field(
        default=CredentialStatus.ACTIVE,
        description="Current operational lifecycle state."
    )
    masked_preview: str = Field(
        ...,
        description="Sanitized preview showing prefix and suffix only (e.g. 'ghp_****a1b2')."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC last update timestamp."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary non-sensitive metadata (e.g. scopes, expiration dates)."
    )
