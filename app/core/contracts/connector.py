"""Version 1 Data Contracts for External Connectors, Capability Routing, and Credential Isolation."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    AuthType,
    ConnectorStatus,
    ConnectorType,
    RiskTier,
)


class CapabilityContract(VersionedContractBase):
    """
    Contract defining an atomic capability offered by an external connector.
    """
    capability_id: str = Field(..., description="Unique capability slug (e.g. 'github.list_failed_workflows').")
    connector_id: str = Field(..., description="Parent connector ID (e.g. 'connector_github').")
    name: str = Field(..., description="Human-readable capability name.")
    description: str = Field(..., description="Description of what this capability does.")
    risk_tier: RiskTier = Field(default=RiskTier.TIER_1_LOW, description="Risk assessment for this capability.")
    required_scopes: List[str] = Field(default_factory=list, description="Scopes required on remote provider.")
    timeout_seconds: int = Field(default=30, ge=1, le=600, description="Max execution timeout in seconds.")
    rate_limit_per_minute: int = Field(default=60, ge=1, description="Rate limit ceiling per minute.")


class CredentialContract(VersionedContractBase):
    """
    Metadata representation of a stored secret.
    RAW SECRETS ARE NEVER EXPOSED IN CONTRACTS ACCESSIBLE TO THE LLM/AGENT.
    """
    secret_id: str = Field(default_factory=lambda: f"sec_{uuid4().hex[:10]}", description="Unique secret handle.")
    provider: ConnectorType = Field(..., description="Target service provider classification.")
    user_id: str = Field(default="system", description="Owner tenant or user ID.")
    masked_value: str = Field(..., description="Safe masked string (e.g. 'ghp_****1234').")
    is_valid: bool = Field(default=True, description="True if credentials passed verification.")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date if OAuth token.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp."
    )


class ConnectorContract(VersionedContractBase):
    """
    Contract defining an integration bridge to an external system or service.
    A Connector manages credentials, network transport, protocol adapters, and rate limits.
    """
    connector_id: str = Field(..., description="Unique slug for connector (e.g. 'connector_github').")
    name: str = Field(..., description="Human-readable name (e.g. 'GitHub Cloud API Connector').")
    connector_type: ConnectorType = Field(..., description="Standardized connector provider classification.")
    auth_type: AuthType = Field(default=AuthType.API_KEY, description="Authentication mechanism used.")
    status: ConnectorStatus = Field(default=ConnectorStatus.DISCONNECTED, description="Current operational state.")
    base_url: Optional[str] = Field(default=None, description="Base API endpoint if applicable.")
    supported_tools: List[str] = Field(default_factory=list, description="Tool IDs hosted by this connector.")
    supported_capabilities: List[str] = Field(default_factory=list, description="Capability IDs hosted by this connector.")
    required_scopes: List[str] = Field(default_factory=list, description="OAuth or API token permission scopes needed.")
    health_check_endpoint: Optional[str] = Field(default=None, description="URL or method for health probing.")
    last_health_check: Optional[datetime] = Field(default=None, description="UTC timestamp of last health verification.")
    is_mcp: bool = Field(default=False, description="True if this connector speaks the Model Context Protocol (MCP).")
    is_mock: bool = Field(default=True, description="True if operating in mock mode.")


class ConnectorHealthContract(VersionedContractBase):
    """Health check diagnostic payload for a Connector."""
    connector_id: str = Field(..., description="ID of the probed connector.")
    status: ConnectorStatus = Field(..., description="Resulting health state.")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Ping/response roundtrip latency.")
    message: str = Field(default="Healthy", description="Diagnostic detail message.")
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when health probe occurred."
    )


class ConnectorExecutionRequest(VersionedContractBase):
    """Execution dispatch request sent to a Connector."""
    request_id: str = Field(default_factory=lambda: f"creq_{uuid4().hex[:10]}", description="Unique dispatch ID.")
    capability_id: str = Field(..., description="Target capability slug.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Input parameters.")
    credential_ref: Optional[str] = Field(default=None, description="Optional indirect credential reference alias.")
    tenant_id: Optional[str] = Field(default=None, description="Optional tenant boundary identifier.")
    trace_id: Optional[str] = Field(default=None, description="Distributed trace ID.")
    task_id: Optional[str] = Field(default=None, description="Associated task ID.")
    step_id: Optional[str] = Field(default=None, description="Associated task step ID.")
    timeout_seconds: int = Field(default=30, ge=1, description="Execution timeout.")


class ConnectorExecutionResult(VersionedContractBase):
    """Structured output returned by a Connector execution."""
    execution_id: str = Field(default_factory=lambda: f"cres_{uuid4().hex[:10]}", description="Unique result ID.")
    request_id: str = Field(..., description="Originating request ID.")
    capability_id: str = Field(..., description="Executed capability ID.")
    success: bool = Field(..., description="True if executed and returned valid data.")
    status_code: int = Field(default=200, description="HTTP or protocol response code.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Payload data returned by remote service.")
    error_message: Optional[str] = Field(default=None, description="Error detail if execution failed.")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Roundtrip execution latency.")
    rate_limit_remaining: Optional[int] = Field(default=None, description="Remaining API calls in quota window.")
