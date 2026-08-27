"""Abstract Interface definitions for Permission and Approval Engines."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.contracts.permission import (
    ApprovalRequestContract,
    PermissionPolicyContract,
)
from app.core.enums import ApprovalState, PermissionAction, RiskTier


class IPermissionEngine(ABC):
    """
    Abstract interface for evaluating security permissions and managing approval workflows.
    """
    @abstractmethod
    async def evaluate_action(
        self,
        user_id: str,
        action: PermissionAction,
        resource: str,
        risk_tier: RiskTier,
        context: Dict[str, Any],
    ) -> bool:
        """
        Evaluate whether an action is permitted under current policies.
        Returns True if action is authorized without blocking approval.
        """
        pass

    @abstractmethod
    async def request_approval(self, request: ApprovalRequestContract) -> str:
        """Create and queue a human-in-the-loop approval ticket. Returns approval_id."""
        pass

    @abstractmethod
    async def record_approval_decision(
        self,
        approval_id: str,
        decision: ApprovalState,
        decided_by: str,
    ) -> ApprovalRequestContract:
        """Record human decision (APPROVED or REJECTED) on a pending ticket."""
        pass

    @abstractmethod
    async def get_pending_approvals(self, user_id: Optional[str] = None) -> List[ApprovalRequestContract]:
        """List all currently pending approval requests awaiting human input."""
        pass
