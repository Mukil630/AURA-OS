"""Unit tests for Verification Contracts."""
from app.core.contracts.verification import (
    VerificationResultContract,
    VerificationSpecContract,
)
from app.core.enums import VerificationMethod, VerificationStatus


def test_verification_spec_contract():
    spec = VerificationSpecContract(
        method=VerificationMethod.FILE_HASH_CHECK,
        target_resource="C:/Users/mukil/backup.zip",
        expected_condition={"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    )
    assert spec.spec_id.startswith("vspec_")
    assert spec.method == VerificationMethod.FILE_HASH_CHECK
    assert spec.timeout_seconds == 30


def test_verification_result_contract():
    res = VerificationResultContract(
        step_id="step_123",
        status=VerificationStatus.VERIFIED,
        details="Google Drive API confirmed file ID 1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ exists with size 4096 bytes.",
        evidence={"file_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ", "size_bytes": 4096},
    )
    assert res.result_id.startswith("vres_")
    assert res.status == VerificationStatus.VERIFIED
    assert res.evidence["size_bytes"] == 4096
