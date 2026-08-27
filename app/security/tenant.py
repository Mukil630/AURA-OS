"""Multi-Tenant Context, Immutability Guards, and Tenant Boundary Contracts."""
from typing import Any, Dict, Optional
from uuid import uuid4
from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field


class TenantMismatchError(HTTPException):
    """Raised when an actor attempts an operation across tenant boundaries."""
    def __init__(self, detail: str = "Cross-tenant access forbidden."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ImmutableTenantError(ValueError):
    """Raised when an attempt is made to mutate tenant ownership on an existing record."""
    pass


class TenantContext(BaseModel):
    """
    Immutable trusted multi-tenant request context derived strictly from authenticated credentials.
    NEVER populated from client request body or LLM generation.
    """
    tenant_id: str = Field(..., description="Immutable tenant boundary identifier (e.g. 'tenant_mukil').")
    actor_id: str = Field(..., description="Authenticated user / service account identifier.")
    role: str = Field(default="authenticated_user", description="Tenant-scoped role.")
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:12]}", description="Trace request ID.")

    def model_post_init(self, __context: Any) -> None:
        """Validate non-empty tenant identity."""
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("TenantContext requires a non-empty tenant_id.")
        if not self.actor_id or not self.actor_id.strip():
            raise ValueError("TenantContext requires a non-empty actor_id.")


class TenantScopedEntity(BaseModel):
    """Base contract mixin for all tenant-owned domain contracts."""
    tenant_id: str = Field(..., description="Immutable tenant boundary identifier.")

    def assert_tenant_ownership(self, expected_tenant_id: str) -> None:
        """Verify object belongs to the requesting tenant."""
        if self.tenant_id != expected_tenant_id:
            raise TenantMismatchError(
                f"Tenant ownership violation: object belongs to '{self.tenant_id}', caller is '{expected_tenant_id}'."
            )
