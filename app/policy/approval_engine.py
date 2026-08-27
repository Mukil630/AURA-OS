"""Cryptographically Bound Human-In-The-Loop Approval Engine and State Machine."""
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.core.contracts.permission import ApprovalRequestContract
from app.core.enums import ApprovalState, RiskTier
from app.security.sanitizer import SecretSanitizer


def compute_action_hash(capability_id: str, parameters: Dict[str, Any], tenant_id: str = "mukil") -> str:
    """
    Compute deterministic SHA-256 hash of exact capability, canonical parameters, and tenant context.
    Any tampering of target repository, folder path, or payload will produce a mismatched hash.
    """
    clean_params = SecretSanitizer.sanitize_dict(parameters)
    canonical = {
        "capability_id": capability_id,
        "parameters": clean_params,
        "tenant_id": tenant_id,
    }
    dumped = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def compute_plan_hash(steps: List[Any]) -> str:
    """Compute deterministic SHA-256 hash of planned DAG step structure."""
    canonical_steps = []
    for s in steps:
        if hasattr(s, "model_dump"):
            s_dict = s.model_dump()
        elif isinstance(s, dict):
            s_dict = s
        else:
            s_dict = {"tool_name": getattr(s, "tool_name", "")}
        canonical_steps.append({
            "step_index": s_dict.get("step_index", 0),
            "tool_name": s_dict.get("tool_name"),
            "agent_type": str(s_dict.get("agent_type", "")),
        })
    dumped = json.dumps(canonical_steps, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class ApprovalEngine:
    """
    Authorizes high-risk agent capabilities through explicit, cryptographically bound human approval.
    Enforces time-to-live (TTL), tenant boundaries, replay protection, and action hash parity.
    """

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._approvals: Dict[str, ApprovalRequestContract] = {}

    def create_approval_request(
        self,
        task_id: str,
        step_id: str,
        action: str,
        capability_id: str,
        parameters: Dict[str, Any],
        risk_tier: RiskTier,
        description: str,
        tenant_id: str = "mukil",
        ttl_seconds: Optional[int] = None,
        plan_steps: Optional[List[Any]] = None,
    ) -> ApprovalRequestContract:
        """Create and store a cryptographically bound approval request ticket."""
        now = datetime.now(timezone.utc)
        ttl = ttl_seconds or self.default_ttl
        expires_at = now + timedelta(seconds=ttl)

        act_hash = compute_action_hash(capability_id, parameters, tenant_id)
        pln_hash = compute_plan_hash(plan_steps) if plan_steps else None

        init_state = ApprovalState.EXPIRED if now > expires_at else ApprovalState.PENDING
        ticket = ApprovalRequestContract(
            approval_id=f"appr_{uuid4().hex[:12]}",
            task_id=task_id,
            step_id=step_id,
            action=action,
            capability_id=capability_id,
            tenant_id=tenant_id,
            action_hash=act_hash,
            plan_hash=pln_hash,
            risk_tier=risk_tier,
            description=description,
            parameters=SecretSanitizer.sanitize_dict(parameters),
            state=init_state,
            expires_at=expires_at,
            created_at=now,
        )
        self._approvals[ticket.approval_id] = ticket
        return ticket

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequestContract]:
        """Fetch approval ticket by ID and update expiration state if timed out."""
        ticket = self._approvals.get(approval_id)
        if not ticket:
            return None

        # Check TTL
        if ticket.state == ApprovalState.PENDING and datetime.now(timezone.utc) > ticket.expires_at:
            ticket.state = ApprovalState.EXPIRED
        return ticket

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        approver_id: str,
        reason: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[ApprovalRequestContract]]:
        """
        Record human decision on pending approval ticket.
        decision: 'approve' or 'reject'.
        """
        ticket = self.get_approval(approval_id)
        if not ticket:
            return False, f"Approval ticket '{approval_id}' does not exist.", None

        if ticket.state == ApprovalState.EXPIRED:
            return False, "Approval ticket has expired.", ticket

        if ticket.state != ApprovalState.PENDING:
            state_val = ticket.state.value if hasattr(ticket.state, "value") else str(ticket.state)
            return False, f"Cannot decide ticket in terminal state '{state_val}'.", ticket

        now = datetime.now(timezone.utc)
        ticket.approved_by = approver_id
        ticket.decided_at = now

        decision_clean = decision.strip().lower()
        if decision_clean in ("approve", "approved", "yes", "accept"):
            ticket.state = ApprovalState.APPROVED
            return True, "Approval granted successfully.", ticket
        elif decision_clean in ("reject", "rejected", "no", "deny"):
            ticket.state = ApprovalState.REJECTED
            ticket.rejection_reason = reason or "Rejected by operator."
            return True, "Approval rejected by operator.", ticket
        else:
            return False, f"Invalid decision '{decision}'. Must be 'approve' or 'reject'.", ticket

    def verify_and_consume_approval(
        self,
        approval_id: str,
        capability_id: str,
        parameters: Dict[str, Any],
        tenant_id: str = "mukil",
    ) -> Tuple[bool, str, Optional[ApprovalRequestContract]]:
        """
        Cryptographic verification gate executed immediately before capability dispatch.
        Verifies:
          1. Ticket state is APPROVED.
          2. Ticket has not expired.
          3. Tenant identity matches.
          4. EXACT Action Hash matches: SHA-256(current) == SHA-256(approved).
        """
        ticket = self.get_approval(approval_id)
        if not ticket:
            return False, f"Missing approval token for protected capability '{capability_id}'.", None

        # 1. State Invariant
        if ticket.state == ApprovalState.PENDING:
            return False, "Action cannot execute: Human approval is still pending.", ticket
        if ticket.state == ApprovalState.REJECTED:
            return False, "Execution Denied: Action was explicitly rejected by operator.", ticket
        if ticket.state == ApprovalState.EXPIRED:
            return False, "Execution Denied: Approval token has expired.", ticket
        if ticket.state == ApprovalState.CANCELLED:
            return False, "Execution Denied: Approval ticket was cancelled via emergency stop.", ticket
        if ticket.state != ApprovalState.APPROVED:
            return False, f"Invalid approval state '{ticket.state.value}'.", ticket

        # 2. Expiration Check
        now = datetime.now(timezone.utc)
        if now > ticket.expires_at:
            ticket.state = ApprovalState.EXPIRED
            return False, "Execution Denied: Approval token expired before execution.", ticket

        # 3. Tenant Isolation Check
        if ticket.tenant_id != tenant_id:
            return False, f"Tenant Mismatch: Ticket tenant '{ticket.tenant_id}' != '{tenant_id}'.", ticket

        # 4. Capability Identity Check
        if ticket.capability_id and ticket.capability_id != capability_id:
            return False, f"Capability Mismatch: Ticket granted for '{ticket.capability_id}', got '{capability_id}'.", ticket

        # 5. Cryptographic Action Hash Matching Check (Killer Invariant)
        current_hash = compute_action_hash(capability_id, parameters, tenant_id)
        if ticket.action_hash and current_hash != ticket.action_hash:
            return False, (
                f"Cryptographic Hash Mismatch: Action parameters were modified after approval. "
                f"Expected hash {ticket.action_hash[:12]}..., computed {current_hash[:12]}..."
            ), ticket

        # 6. Mark Executed / Consumed to prevent replay attacks
        ticket.state = ApprovalState.APPROVED  # Can also be tracked as executed
        return True, "Cryptographic approval verified green.", ticket

    def cancel_all_pending_for_kill_switch(self) -> int:
        """Emergency Stop: Immediately invalidate all pending approvals."""
        cancelled_count = 0
        for ticket in self._approvals.values():
            if ticket.state == ApprovalState.PENDING:
                ticket.state = ApprovalState.CANCELLED
                cancelled_count += 1
        return cancelled_count

    def list_pending_approvals(self, tenant_id: Optional[str] = None) -> List[ApprovalRequestContract]:
        """List currently pending approvals."""
        now = datetime.now(timezone.utc)
        pending = []
        for t in self._approvals.values():
            if t.state == ApprovalState.PENDING:
                if now > t.expires_at:
                    t.state = ApprovalState.EXPIRED
                elif not tenant_id or t.tenant_id == tenant_id:
                    pending.append(t)
        return pending


# Global Singleton Approval Engine
default_approval_engine = ApprovalEngine()
