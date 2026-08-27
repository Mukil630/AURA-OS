"""Version 1 Data Contracts for Action Verification and Validation Results."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase
from app.core.enums import (
    VerificationMethod,
    VerificationStatus,
)


class VerificationSpecContract(VersionedContractBase):
    """
    Contract specifying independent post-action validation criteria.
    Ensures an action is verifiably complete rather than trusting an API return code.
    """
    spec_id: str = Field(
        default_factory=lambda: f"vspec_{uuid4().hex[:12]}",
        description="Unique verification specification ID."
    )
    method: VerificationMethod = Field(..., description="Verification approach to apply.")
    target_resource: str = Field(..., description="URI or identifier of the resource to inspect.")
    expected_condition: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value expectations (e.g. {'file_size_gt': 0, 'status': 'success'})."
    )
    timeout_seconds: int = Field(default=30, gt=0, description="Timeout for verification probe.")
    retry_on_inconclusive: bool = Field(default=True, description="Whether to retry if status is inconclusive.")


class VerificationResultContract(VersionedContractBase):
    """
    Contract representing the conclusive finding of a verification check.
    """
    result_id: str = Field(
        default_factory=lambda: f"vres_{uuid4().hex[:12]}",
        description="Unique verification result ID."
    )
    spec_id: Optional[str] = Field(default=None, description="Matching verification spec ID.")
    step_id: str = Field(..., description="TaskStep ID evaluated.")
    status: VerificationStatus = Field(..., description="Final verification outcome.")
    details: str = Field(..., description="Summary explanation of verification findings.")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Recorded empirical evidence (e.g. hashes, HTTP codes, DOM selectors)."
    )
    verified_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when verification finished."
    )
