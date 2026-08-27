"""SQLAlchemy ORM Model for Human-In-The-Loop Approval Tickets."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.contracts.permission import ApprovalRequestContract
from app.core.enums import ApprovalState, RiskTier
from app.database.base import Base, dump_json, load_json


class ApprovalRequestModel(Base):
    """
    Persistent table for human authorization requests when executing High/Critical risk actions.
    """
    __tablename__ = "approval_requests"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="mukil", nullable=False, index=True)
    action_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plan_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    risk_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    state: Mapped[str] = mapped_column(String(32), default=ApprovalState.PENDING.value, nullable=False, index=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_approvals_task_state", "task_id", "state"),
    )

    def to_contract(self) -> ApprovalRequestContract:
        """Convert ORM model to ApprovalRequestContract."""
        return ApprovalRequestContract(
            approval_id=self.approval_id,
            task_id=self.task_id,
            step_id=self.step_id,
            action=self.action,
            capability_id=self.capability_id,
            tenant_id=self.tenant_id,
            action_hash=self.action_hash,
            plan_hash=self.plan_hash,
            risk_tier=RiskTier(self.risk_tier),
            description=self.description,
            parameters=load_json(self.parameters_json),
            state=ApprovalState(self.state),
            approved_by=self.approved_by,
            rejection_reason=self.rejection_reason,
            decided_at=self.decided_at,
            expires_at=self.expires_at,
            created_at=self.created_at,
        )

    @classmethod
    def from_contract(cls, contract: ApprovalRequestContract) -> "ApprovalRequestModel":
        """Instantiate ORM model from ApprovalRequestContract."""
        return cls(
            approval_id=contract.approval_id,
            task_id=contract.task_id,
            step_id=contract.step_id,
            action=contract.action,
            capability_id=contract.capability_id,
            tenant_id=contract.tenant_id,
            action_hash=contract.action_hash,
            plan_hash=contract.plan_hash,
            risk_tier=contract.risk_tier.value if hasattr(contract.risk_tier, "value") else str(contract.risk_tier),
            description=contract.description,
            parameters_json=dump_json(contract.parameters),
            state=contract.state.value if hasattr(contract.state, "value") else str(contract.state),
            approved_by=contract.approved_by,
            rejection_reason=contract.rejection_reason,
            decided_at=contract.decided_at,
            expires_at=contract.expires_at,
            created_at=contract.created_at,
        )
