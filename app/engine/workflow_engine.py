"""Workflow Execution Engine and State Machine Orchestrator with Verification, Self-Healing, and Memory Distillation."""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryContract
from app.core.contracts.permission import ApprovalRequestContract
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.tool import ToolExecutionRequest, ToolExecutionResult
from app.core.contracts.workflow import WorkflowContract, WorkflowStateContract
from app.core.dag import DAGValidator
from app.core.enums import (
    ApprovalState,
    EventSeverity,
    EventType,
    FailureCategory,
    MemoryScope,
    MemoryType,
    RecoveryStrategy,
    RiskTier,
    StepStatus,
    TaskStatus,
    VerificationStatus,
    WorkflowStatus,
)
from app.core.interfaces.workflow import IWorkflowEngine
from app.database.repositories.approval_repo import ApprovalRepository
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.recovery.engine import SelfHealingEngine
from app.tools.registry import ToolExecutor, ToolRegistry
from app.verification.engine import VerificationEngine


class WorkflowExecutionError(Exception):
    """Raised when workflow execution encounters a critical fault."""
    pass


class WorkflowEngine(IWorkflowEngine):
    """
    Durable DAG state machine engine.
    Orchestrates step progression, dependency satisfaction, tool dispatch,
    independent verification, bounded self-healing recovery, checkpoint resume, and memory distillation.
    """

    def __init__(
        self,
        db_session: Optional[AsyncSession] = None,
        tool_executor: Optional[ToolExecutor] = None,
        verifier: Optional[VerificationEngine] = None,
        self_healer: Optional[SelfHealingEngine] = None,
    ):
        self.session = db_session
        self.tool_executor = tool_executor or ToolExecutor()
        self.verifier = verifier or VerificationEngine()
        self.self_healer = self_healer or SelfHealingEngine()

    # ── IWorkflowEngine Interface Implementations ─────────────────────────────────────

    async def start_workflow(self, workflow: WorkflowContract) -> WorkflowStateContract:
        """Initialize and begin execution of a workflow."""
        wf, _ = await self.execute_workflow(workflow.workflow_id)
        state = await self.get_workflow_state(workflow.workflow_id)
        if not state:
            state = WorkflowStateContract(workflow_id=workflow.workflow_id, status=wf.status)
        return state

    async def pause_workflow(self, workflow_id: str, reason: str = "") -> WorkflowStateContract:
        """Pause a running workflow and record checkpoint."""
        if not self.session:
            raise WorkflowExecutionError("Database session required.")
        wf_repo = WorkflowRepository(self.session)
        await wf_repo.update_workflow_status(workflow_id, WorkflowStatus.PAUSED)
        checkpoint = WorkflowStateContract(workflow_id=workflow_id, status=WorkflowStatus.PAUSED)
        await wf_repo.record_checkpoint(checkpoint)
        await self.session.commit()
        return checkpoint

    async def resume_workflow(self, workflow_id: str) -> WorkflowStateContract:
        """Resume a paused or approval-gated workflow from its latest checkpoint."""
        wf, _ = await self.execute_workflow(workflow_id)
        state = await self.get_workflow_state(workflow_id)
        if not state:
            state = WorkflowStateContract(workflow_id=workflow_id, status=wf.status)
        return state

    async def cancel_workflow(self, workflow_id: str, reason: str = "") -> WorkflowStateContract:
        """Cancel workflow execution gracefully."""
        if not self.session:
            raise WorkflowExecutionError("Database session required.")
        wf_repo = WorkflowRepository(self.session)
        await wf_repo.update_workflow_status(workflow_id, WorkflowStatus.CANCELLED)
        checkpoint = WorkflowStateContract(workflow_id=workflow_id, status=WorkflowStatus.CANCELLED)
        await wf_repo.record_checkpoint(checkpoint)
        await self.session.commit()
        return checkpoint

    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowStateContract]:
        """Fetch the current state checkpoint of a workflow."""
        if not self.session:
            return None
        wf_repo = WorkflowRepository(self.session)
        return await wf_repo.get_latest_checkpoint(workflow_id)

    async def get_state(self, workflow_id: str) -> Optional[WorkflowStateContract]:
        """Alias for get_workflow_state."""
        return await self.get_workflow_state(workflow_id)

    async def record_checkpoint(self, state: WorkflowStateContract) -> bool:
        """Persist state checkpoint to durable storage."""
        if not self.session:
            return False
        wf_repo = WorkflowRepository(self.session)
        await wf_repo.record_checkpoint(state)
        await self.session.commit()
        return True

    # ── Core Orchestrator Execution ───────────────────────────────────────────────────

    async def execute_workflow(
        self,
        workflow_id: str,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[WorkflowContract, Optional[TaskContract]]:
        """
        Run the complete DAG workflow lifecycle to completion or pause/failure.
        Supports crash recovery, step skipping from checkpoint, and idempotency.
        """
        if not self.session:
            raise WorkflowExecutionError("Database session is required to execute durable workflows.")

        wf_repo = WorkflowRepository(self.session)
        task_repo = TaskRepository(self.session)
        event_repo = EventRepository(self.session)
        approval_repo = ApprovalRepository(self.session)
        memory_repo = MemoryRepository(self.session)

        # 1. Fetch Workflow from Database
        workflow = await wf_repo.get_workflow(workflow_id)
        if not workflow:
            raise WorkflowExecutionError(f"Workflow '{workflow_id}' not found in database.")

        task = await task_repo.get_task(workflow.task_id) if workflow.task_id else None
        trace_id = f"tr_{task.task_id}" if task else f"tr_{workflow_id}"

        # 2. Check Idempotency / Terminal State
        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return workflow, task

        # 3. Check for Checkpoint Restoration (Crash Recovery)
        latest_checkpoint = await wf_repo.get_latest_checkpoint(workflow_id)
        completed_step_ids: Set[str] = set(latest_checkpoint.completed_step_ids) if latest_checkpoint else set()
        step_outputs: Dict[str, Any] = dict(latest_checkpoint.step_outputs) if latest_checkpoint else {}
        accumulated_context: Dict[str, Any] = {
            **(workflow.context_variables or {}),
            **(latest_checkpoint.accumulated_context if latest_checkpoint else {}),
            **(initial_context or {}),
        }

        # Hydrate completed steps directly from DB step records
        for step in workflow.steps:
            if step.status == StepStatus.COMPLETED:
                completed_step_ids.add(step.step_id)
                if step.output_payload:
                    step_outputs[step.step_id] = step.output_payload

        # 4. Transition Workflow & Task to RUNNING
        await wf_repo.update_workflow_status(workflow_id, WorkflowStatus.RUNNING)
        if task:
            await task_repo.update_task_status(task.task_id, TaskStatus.RUNNING, workflow_id=workflow_id)

        # Emit WORKFLOW_STARTED event if starting fresh
        if not completed_step_ids:
            await event_repo.record_event(
                ExecutionEventContract(
                    trace_id=trace_id,
                    task_id=task.task_id if task else None,
                    workflow_id=workflow_id,
                    event_type=EventType.WORKFLOW_STARTED,
                    severity=EventSeverity.INFO,
                    source_component="WorkflowEngine",
                    message=f"Workflow '{workflow.name}' started execution ({len(workflow.steps)} steps).",
                )
            )

        # 5. Resolve Execution Batches (DAG Topological Stages)
        batches = DAGValidator.resolve_execution_batches(workflow.steps)
        step_map: Dict[str, TaskStepContract] = {s.step_id: s for s in workflow.steps}

        # 6. Execute Stage-by-Stage
        for batch_idx, batch_step_ids in enumerate(batches):
            for step_id in batch_step_ids:
                step = step_map[step_id]

                # If step already completed in previous checkpoint, skip re-execution!
                if step_id in completed_step_ids and step.status == StepStatus.COMPLETED:
                    continue

                # Verify Dependencies are 100% Satisfied
                unmet_deps = [dep for dep in step.dependencies if dep not in completed_step_ids]
                if unmet_deps:
                    await self._fail_workflow(
                        wf_repo, task_repo, event_repo, workflow, task, step,
                        f"Step '{step.name}' failed dependency constraint: unmet dependencies {unmet_deps}"
                    )
                    return await wf_repo.get_workflow(workflow_id), await task_repo.get_task(task.task_id) if task else None

                # Check Approval Requirement (Human-in-the-Loop)
                if step.requires_approval or step.risk_tier in (RiskTier.TIER_3_HIGH, RiskTier.TIER_4_CRITICAL):
                    # Check if already approved via database ticket
                    existing_approvals = await approval_repo.get_approvals_for_task(task.task_id) if task else []
                    is_ticket_approved = any(a.step_id == step_id and a.state == ApprovalState.APPROVED for a in existing_approvals)

                    if step.approval_state != ApprovalState.APPROVED and not is_ticket_approved:
                        # Pause Workflow and create Approval Ticket
                        await wf_repo.update_step_status(step_id, StepStatus.WAITING_FOR_APPROVAL)
                        await wf_repo.update_workflow_status(workflow_id, WorkflowStatus.PAUSED)
                        if task:
                            await task_repo.update_task_status(task.task_id, TaskStatus.WAITING_FOR_APPROVAL)

                        ticket = ApprovalRequestContract(
                            task_id=task.task_id if task else workflow.task_id,
                            step_id=step_id,
                            action=step.tool_name,
                            risk_tier=step.risk_tier,
                            description=f"Approve execution of high-risk step: {step.name} ({step.tool_name})",
                            parameters=step.input_payload,
                        )
                        await approval_repo.create_approval_request(ticket)

                        await event_repo.record_event(
                            ExecutionEventContract(
                                trace_id=trace_id,
                                task_id=task.task_id if task else None,
                                workflow_id=workflow_id,
                                step_id=step_id,
                                event_type=EventType.APPROVAL_REQUESTED,
                                severity=EventSeverity.WARNING,
                                source_component="WorkflowEngine",
                                message=f"Step '{step.name}' requires authorization (Ticket: {ticket.approval_id}).",
                            )
                        )
                        await self.session.commit()
                        return await wf_repo.get_workflow(workflow_id), await task_repo.get_task(task.task_id) if task else None

                # Transition Step to RUNNING
                await wf_repo.update_step_status(step_id, StepStatus.RUNNING)
                await event_repo.record_event(
                    ExecutionEventContract(
                        trace_id=trace_id,
                        task_id=task.task_id if task else None,
                        workflow_id=workflow_id,
                        step_id=step_id,
                        event_type=EventType.STEP_STARTED,
                        severity=EventSeverity.INFO,
                        source_component="WorkflowEngine",
                        message=f"Executing Step {step.step_index}: '{step.name}' via {step.tool_name}...",
                    )
                )

                # Prepare Step Input (Merge parent outputs + context variables)
                merged_payload = {**accumulated_context, **step.input_payload}

                # Dispatch to ToolExecutor
                exec_req = ToolExecutionRequest(
                    tool_id=step.tool_name,
                    step_id=step.step_id,
                    parameters=merged_payload,
                    timeout_seconds=step.timeout_seconds,
                )
                exec_res = await self.tool_executor.execute(exec_req)

                # ── Independent Verification Engine Check ────────────────────
                v_res = self.verifier.verify_step(step, exec_res)

                if v_res.status == VerificationStatus.VERIFIED:
                    # Verification PASSED
                    await event_repo.record_event(
                        ExecutionEventContract(
                            trace_id=trace_id,
                            task_id=task.task_id if task else None,
                            workflow_id=workflow_id,
                            step_id=step_id,
                            event_type=EventType.VERIFICATION_PASSED,
                            severity=EventSeverity.INFO,
                            source_component="VerificationEngine",
                            message=f"Verification PASSED for Step {step.step_index} ('{step.name}').",
                        )
                    )

                    output = exec_res.data or {}
                    step_outputs[step_id] = output
                    completed_step_ids.add(step_id)
                    accumulated_context[f"{step.name}_output"] = output

                    await wf_repo.update_step_status(step_id, StepStatus.COMPLETED, output_payload=output)

                    await event_repo.record_event(
                        ExecutionEventContract(
                            trace_id=trace_id,
                            task_id=task.task_id if task else None,
                            workflow_id=workflow_id,
                            step_id=step_id,
                            event_type=EventType.STEP_COMPLETED,
                            severity=EventSeverity.INFO,
                            source_component="WorkflowEngine",
                            message=f"Step {step.step_index} ('{step.name}') completed successfully.",
                            payload=output,
                        )
                    )

                    # Save Checkpoint
                    checkpoint = WorkflowStateContract(
                        workflow_id=workflow_id,
                        status=WorkflowStatus.RUNNING,
                        active_step_id=step_id,
                        completed_step_ids=list(completed_step_ids),
                        step_outputs=step_outputs,
                        accumulated_context=accumulated_context,
                    )
                    await wf_repo.record_checkpoint(checkpoint)

                else:
                    # Verification or Tool Execution FAILED
                    await event_repo.record_event(
                        ExecutionEventContract(
                            trace_id=trace_id,
                            task_id=task.task_id if task else None,
                            workflow_id=workflow_id,
                            step_id=step_id,
                            event_type=EventType.VERIFICATION_FAILED,
                            severity=EventSeverity.WARNING,
                            source_component="VerificationEngine",
                            message=f"Verification FAILED for Step {step.step_index}: {v_res.details}",
                            payload={"discrepancy": v_res.details},
                        )
                    )

                    # Classify failure and select recovery strategy
                    cat = self.self_healer.classify_failure(exec_res.error_message, v_res)
                    strategy = self.self_healer.select_recovery_strategy(cat, step)

                    recovered = False
                    if strategy != RecoveryStrategy.ESCALATE_HUMAN:
                        rec_ok, rec_data, rec_msg = await self.self_healer.attempt_recovery(
                            workflow=workflow,
                            step=step,
                            category=cat,
                            strategy=strategy,
                            tool_executor=self.tool_executor,
                            wf_repo=wf_repo,
                            event_repo=event_repo,
                            task_repo=task_repo,
                            task=task,
                            merged_payload=merged_payload,
                        )
                        if rec_ok and rec_data:
                            # Re-verify recovery outcome
                            rec_result = ToolExecutionResult(
                                execution_id=f"rec_{uuid4().hex[:8]}",
                                tool_id=step.tool_name,
                                success=True,
                                data=rec_data,
                            )
                            v_rec = self.verifier.verify_step(step, rec_result)
                            if v_rec.status == VerificationStatus.VERIFIED:
                                recovered = True
                                step_outputs[step_id] = rec_data
                                completed_step_ids.add(step_id)
                                accumulated_context[f"{step.name}_output"] = rec_data

                                await wf_repo.update_step_status(step_id, StepStatus.COMPLETED, output_payload=rec_data)
                                checkpoint = WorkflowStateContract(
                                    workflow_id=workflow_id,
                                    status=WorkflowStatus.RUNNING,
                                    active_step_id=step_id,
                                    completed_step_ids=list(completed_step_ids),
                                    step_outputs=step_outputs,
                                    accumulated_context=accumulated_context,
                                )
                                await wf_repo.record_checkpoint(checkpoint)

                    if not recovered:
                        # Step Failed Permanently / Exhausted Retries
                        err_msg = v_res.details or exec_res.error_message or "Step failed verification"
                        await wf_repo.update_step_status(step_id, StepStatus.FAILED, error_message=err_msg)

                        await self._fail_workflow(
                            wf_repo, task_repo, event_repo, workflow, task, step, err_msg
                        )
                        return await wf_repo.get_workflow(workflow_id), await task_repo.get_task(task.task_id) if task else None

        # 7. Workflow Completed Successfully
        await wf_repo.update_workflow_status(workflow_id, WorkflowStatus.COMPLETED)

        # Final Checkpoint
        final_checkpoint = WorkflowStateContract(
            workflow_id=workflow_id,
            status=WorkflowStatus.COMPLETED,
            completed_step_ids=list(completed_step_ids),
            step_outputs=step_outputs,
            accumulated_context=accumulated_context,
        )
        await wf_repo.record_checkpoint(final_checkpoint)

        # Update Task Status and Results
        summary = self._generate_task_summary(workflow, step_outputs)
        if task:
            await task_repo.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result_summary=summary,
                result_data=step_outputs,
            )

        # Emit Completion Events
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=trace_id,
                task_id=task.task_id if task else None,
                workflow_id=workflow_id,
                event_type=EventType.WORKFLOW_COMPLETED,
                severity=EventSeverity.INFO,
                source_component="WorkflowEngine",
                message=f"Workflow '{workflow.name}' executed all {len(workflow.steps)} steps successfully.",
                payload={"step_outputs": step_outputs},
            )
        )
        if task:
            await event_repo.record_event(
                ExecutionEventContract(
                    trace_id=trace_id,
                    task_id=task.task_id,
                    event_type=EventType.TASK_COMPLETED,
                    severity=EventSeverity.INFO,
                    source_component="WorkflowEngine",
                    message=f"Task {task.task_id} completed successfully.",
                    payload={"result_summary": summary},
                )
            )

            # ── Multi-Turn Episodic Memory Distillation ───────────────────────
            raw_input_text = task.raw_input if task else ""
            distilled_mem = MemoryContract(
                user_id=task.user_id,
                memory_type=MemoryType.EPISODIC_TASK,
                scope=MemoryScope.USER,
                content=f"Task '{task.task_id}' for '{raw_input_text}' completed: {summary}",
                summary=summary,
                importance_score=0.85,
                source_task_id=task.task_id,
                tags=["task_outcome", workflow.name.replace("_workflow", "")] + list(task.tags or []),
            )
            await memory_repo.create_or_update_memory(distilled_mem)

        await self.session.commit()
        return await wf_repo.get_workflow(workflow_id), await task_repo.get_task(task.task_id) if task else None

    async def _fail_workflow(
        self,
        wf_repo: WorkflowRepository,
        task_repo: TaskRepository,
        event_repo: EventRepository,
        workflow: WorkflowContract,
        task: Optional[TaskContract],
        failed_step: TaskStepContract,
        error_msg: str,
    ) -> None:
        """Handle workflow failure gracefully without state corruption."""
        # Update workflow status to FAILED
        await wf_repo.update_workflow_status(workflow.workflow_id, WorkflowStatus.FAILED)

        # Cancel remaining pending steps
        for step in workflow.steps:
            if step.step_id != failed_step.step_id and step.status == StepStatus.PENDING:
                await wf_repo.update_step_status(step.step_id, StepStatus.CANCELLED)

        # Update Task to FAILED
        if task:
            await task_repo.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error_message=f"Failed at step '{failed_step.name}': {error_msg}",
            )

        # Emit audit event
        trace_id = f"tr_{task.task_id}" if task else f"tr_{workflow.workflow_id}"
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=trace_id,
                task_id=task.task_id if task else None,
                workflow_id=workflow.workflow_id,
                step_id=failed_step.step_id,
                event_type=EventType.WORKFLOW_FAILED,
                severity=EventSeverity.ERROR,
                source_component="WorkflowEngine",
                message=f"Workflow failed at step '{failed_step.name}': {error_msg}",
                payload={"error": error_msg, "failed_step_id": failed_step.step_id},
            )
        )
        await self.session.commit()

    def _generate_task_summary(self, workflow: WorkflowContract, outputs: Dict[str, Any]) -> str:
        """Generate human-readable summary from execution outputs."""
        step_count = len(workflow.steps)
        return f"Successfully executed all {step_count} steps in workflow '{workflow.name}'. All automated actions verified green."
