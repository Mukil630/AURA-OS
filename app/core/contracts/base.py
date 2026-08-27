"""Base class and metadata standards for all Version 1 Data Contracts."""
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class VersionedContractBase(BaseModel):
    """
    Foundational base class for all MUKIL MASTER AGENT contracts.
    Enforces explicit schema versioning, strict type validation, and creation timestamps.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True,
    )

    schema_version: str = Field(
        default="v1",
        description="Semantic version of this contract schema (e.g. 'v1', 'v2')."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this contract instance was instantiated."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible key-value metadata container for non-breaking custom attributes."
    )
