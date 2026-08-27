"""Post-action verification status and method enums."""
from enum import Enum


class VerificationStatus(str, Enum):
    """Result of independent post-execution verification."""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


class VerificationMethod(str, Enum):
    """Strategy used by Verifier to confirm true task completion."""
    API_LOOKUP = "api_lookup"
    FILE_HASH_CHECK = "file_hash_check"
    GIT_REMOTE_CHECK = "git_remote_check"
    DOM_STATE_CHECK = "dom_state_check"
    RETURN_CODE_CHECK = "return_code_check"
    SCHEMA_VALIDATION = "schema_validation"
    MANUAL_INSPECTION = "manual_inspection"
