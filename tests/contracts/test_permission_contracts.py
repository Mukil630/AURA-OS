"""Unit tests for Permission and Approval Contracts."""
from app.core.contracts.permission import (
    ApprovalRequestContract,
    PermissionPolicyContract,
)
from app.core.enums import (
    ApprovalState,
    PermissionAction,
    RiskTier,
)


def test_permission_policy_contract():
    policy = PermissionPolicyContract(
        policy_id="pol_shell_exec",
        name="Allow Sandboxed Shell Execution",
        role="developer",
        action=PermissionAction.EXECUTE,
        resource_pattern="pc:powershell:*",
        risk_tier=RiskTier.TIER_3_HIGH,
        requires_explicit_approval=True,
        is_allowed=True,
    )
    assert policy.policy_id == "pol_shell_exec"
    assert policy.action == PermissionAction.EXECUTE
    assert policy.risk_tier == RiskTier.TIER_3_HIGH
    assert policy.requires_explicit_approval is True


def test_approval_request_contract():
    appr = ApprovalRequestContract(
        task_id="task_123",
        step_id="step_456",
        action="delete_cloud_bucket",
        risk_tier=RiskTier.TIER_4_CRITICAL,
        description="Delete AWS S3 bucket 'old-backups'",
        parameters={"bucket_name": "old-backups"},
    )
    assert appr.approval_id.startswith("appr_")
    assert appr.state == ApprovalState.PENDING
    assert appr.risk_tier == RiskTier.TIER_4_CRITICAL
