"""Engine Crash State Recovery, Incomplete Task Reconciliation, and Approval Restoration."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.workflow import WorkflowContract
from app.core.enums import ApprovalState, StepStatus, TaskStatus, WorkflowStatus
from app.database.models.approval import ApprovalRequestModel
from app.database.models.task import TaskModel
from app.database.models.workflow import TaskStepModel, WorkflowModel
from app.database.repositories.approval_repo import ApprovalRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.policy.approval_engine import ApprovalEngine, default_approval_engine
from app.reliability.idempotency import IdempotencyLedger, default_idempotency_ledger


class CrashStateRecoveryEngine:
    """
    Recovers incomplete tasks and approval state following an unexpected process restart or server reboot.
    Prevents blind re-execution of mutating steps and reconciles dangling states.
    """

    def __init__(
        self,
        approval_engine: Optional[ApprovalEngine] = None,
        idempotency_ledger: Optional[IdempotencyLedger] = None,
    ):
        self.approval_engine = approval_engine or default_approval_engine
        self.idempotency_ledger = idempotency_ledger or default_idempotency_ledger

    async def inspect_and_recover_crashed_workflows(self, session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Scan database for workflows left in 'running' state during a crash and reconcile them safely.
        """
        stmt = select(WorkflowModel).where(WorkflowModel.status == WorkflowStatus.RUNNING.value)
        res = await session.execute(stmt)
        running_wfs = res.scalars().all()

        recovery_summary = []

        for wf in running_wfs:
            step_stmt = select(TaskStepModel).where(
                TaskStepModel.workflow_id == wf.workflow_id,
                TaskStepModel.status == StepStatus.RUNNING.value,
            )
            step_res = await session.execute(step_stmt)
            dangling_steps = step_res.scalars().all()

            for step in dangling_steps:
                # Check if idempotent result exists
                idempotent_key = f"step_{step.step_id}"
                cached = self.idempotency_ledger.get(idempotent_key)

                if cached:
                    # External execution succeeded before crash
                    step.status = StepStatus.COMPLETED.value
                    step.error_message = None
                    action_taken = "reconciled_from_idempotency_ledger"
                else:
                    # External state unknown -> Pause safely for operator review (NO BLIND RE-EXECUTION)
                    step.status = StepStatus.FAILED.value
                    step.error_message = "Step interrupted by process crash. Paused safely without duplicate execution."
                    action_taken = "safely_marked_failed_to_prevent_duplicate_mutation"

            wf.status = WorkflowStatus.PAUSED.value
            recovery_summary.append({
                "workflow_id": wf.workflow_id,
                "dangling_steps_count": len(dangling_steps),
                "recovered_status": "paused_for_safety",
            })

        await session.commit()
        return recovery_summary

    async def restore_approval_state_from_db(self, session: AsyncSession) -> int:
        """
        Reload pending/approved tickets from database and re-evaluate TTL expiration.
        """
        stmt = select(ApprovalRequestModel).where(
            ApprovalRequestModel.state.in_([ApprovalState.PENDING.value, ApprovalState.APPROVED.value])
        )
        res = await session.execute(stmt)
        tickets = res.scalars().all()

        now = datetime.now(timezone.utc)
        restored_count = 0

        for t in tickets:
            contract = t.to_contract()
            # If expired while offline, update to EXPIRED
            if contract.state == ApprovalState.PENDING and now > contract.expires_at:
                contract.state = ApprovalState.EXPIRED
                t.state = ApprovalState.EXPIRED.value

            self.approval_engine._approvals[contract.approval_id] = contract
            restored_count += 1

        await session.commit()
        return restored_count


# Global Singleton Crash State Recovery Engine
default_crash_recovery_engine = CrashStateRecoveryEngine()
