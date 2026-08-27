"""Self-Healing and Recovery Orchestrator."""
import asyncio
from typing import Any, Dict, Optional, Tuple

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.tool import ToolExecutionRequest, ToolExecutionResult
from app.core.contracts.verification import VerificationResultContract
from app.core.contracts.workflow import WorkflowContract
from app.core.enums import (
    EventSeverity,
    EventType,
    FailureCategory,
    RecoveryStrategy,
    RiskTier,
    StepStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.tools.registry import ToolExecutor


class SelfHealingEngine:
    """
    Classifies execution/verification failures and executes bounded, safe recovery strategies.
    Ensures bounded retries, explicit repair logic, risk checking, and audit history.
    """

    def classify_failure(
        self,
        error_msg: Optional[str] = None,
        verification_result: Optional[VerificationResultContract] = None,
    ) -> FailureCategory:
        """Categorize failure mode from error messages or verification discrepancies."""
        combined_text = ""
        if error_msg:
            combined_text += f" {error_msg.lower()}"
        if verification_result and verification_result.details:
            combined_text += f" {verification_result.details.lower()}"

        if not combined_text.strip():
            return FailureCategory.UNKNOWN

        # 1. Timeout
        if any(w in combined_text for w in ["timed out", "timeout", "deadline exceeded"]):
            return FailureCategory.TIMEOUT

        # 2. Authorization / Permission
        if any(w in combined_text for w in ["401", "403", "unauthorized", "permission denied", "access denied", "forbidden"]):
            return FailureCategory.AUTHORIZATION

        # 3. Validation / Invariant Discrepancy
        if any(w in combined_text for w in ["test suite reported", "discrepancy", "invariant", "failed count", "mismatch", "tests_failed"]):
            return FailureCategory.VALIDATION

        # 4. Transient Network / Rate Limits
        if any(w in combined_text for w in ["network", "connection reset", "429", "rate limit", "temporary", "econnreset", "lock"]):
            return FailureCategory.TRANSIENT

        # 5. Dependency
        if any(w in combined_text for w in ["unmet dependencies", "missing dependency"]):
            return FailureCategory.DEPENDENCY

        # 6. Permanent Errors
        if any(w in combined_text for w in ["404", "not found", "syntax error", "fatal", "invalid argument"]):
            return FailureCategory.PERMANENT

        return FailureCategory.UNKNOWN

    def select_recovery_strategy(
        self,
        category: FailureCategory,
        step: TaskStepContract,
    ) -> RecoveryStrategy:
        """Determine mitigation strategy based on failure classification and bounds."""
        # 1. Transient / Timeout Failures -> Retry if under max_retries
        if category in (FailureCategory.TRANSIENT, FailureCategory.TIMEOUT):
            if step.retry_count < step.max_retries:
                return RecoveryStrategy.RETRY
            return RecoveryStrategy.ESCALATE_HUMAN

        # 2. Validation / Test Failures -> Repair input if under max_retries
        if category == FailureCategory.VALIDATION:
            if step.retry_count < step.max_retries:
                return RecoveryStrategy.REPAIR_INPUT
            return RecoveryStrategy.ESCALATE_HUMAN

        # 3. Authorization or High-Risk -> Escalate to human
        if category == FailureCategory.AUTHORIZATION or step.risk_tier in (RiskTier.TIER_3_HIGH, RiskTier.TIER_4_CRITICAL):
            return RecoveryStrategy.ESCALATE_HUMAN

        # 4. Permanent / Dependency / Unknown -> Escalate to human
        return RecoveryStrategy.ESCALATE_HUMAN

    async def attempt_recovery(
        self,
        workflow: WorkflowContract,
        step: TaskStepContract,
        category: FailureCategory,
        strategy: RecoveryStrategy,
        tool_executor: ToolExecutor,
        wf_repo: WorkflowRepository,
        event_repo: EventRepository,
        task_repo: Optional[TaskRepository] = None,
        task: Optional[TaskContract] = None,
        merged_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Execute the selected recovery strategy.
        Returns: (success: bool, output_data: Optional[Dict], diagnostic_message: str)
        """
        trace_id = f"tr_{task.task_id}" if task else f"tr_{workflow.workflow_id}"
        new_retry_count = step.retry_count + 1

        # Strategy 1: RETRY (Exponential backoff retry)
        if strategy == RecoveryStrategy.RETRY:
            await event_repo.record_event(
                ExecutionEventContract(
                    trace_id=trace_id,
                    task_id=task.task_id if task else None,
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    event_type=EventType.STEP_RETRIED,
                    severity=EventSeverity.WARNING,
                    source_component="SelfHealingEngine",
                    message=f"Retrying Step {step.step_index} ('{step.name}') - Attempt {new_retry_count}/{step.max_retries}...",
                    payload={"failure_category": category.value, "retry_count": new_retry_count},
                )
            )

            # Re-execute step
            exec_req = ToolExecutionRequest(
                tool_id=step.tool_name,
                step_id=step.step_id,
                parameters=merged_payload or step.input_payload,
                timeout_seconds=step.timeout_seconds + 10,  # Grace period bump
            )
            exec_res = await tool_executor.execute(exec_req)
            if exec_res.success:
                await event_repo.record_event(
                    ExecutionEventContract(
                        trace_id=trace_id,
                        task_id=task.task_id if task else None,
                        workflow_id=workflow.workflow_id,
                        step_id=step.step_id,
                        event_type=EventType.RECOVERY_SUCCEEDED,
                        severity=EventSeverity.INFO,
                        source_component="SelfHealingEngine",
                        message=f"Step {step.step_index} recovered successfully on retry attempt {new_retry_count}.",
                        payload=exec_res.data,
                    )
                )
                return True, exec_res.data, "Recovered on retry."

            return False, None, exec_res.error_message or "Retry attempt failed."

        # Strategy 2: REPAIR_INPUT (Apply adaptive payload adjustment)
        elif strategy == RecoveryStrategy.REPAIR_INPUT:
            await event_repo.record_event(
                ExecutionEventContract(
                    trace_id=trace_id,
                    task_id=task.task_id if task else None,
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    event_type=EventType.RECOVERY_ATTEMPTED,
                    severity=EventSeverity.WARNING,
                    source_component="SelfHealingEngine",
                    message=f"Applying automated self-healing repair on Step {step.step_index} ('{step.name}')...",
                    payload={"strategy": "repair_input", "retry_count": new_retry_count},
                )
            )

            repaired_payload = {**(merged_payload or step.input_payload), "auto_repair_applied": True, "clean_cache": True}
            exec_req = ToolExecutionRequest(
                tool_id=step.tool_name,
                step_id=step.step_id,
                parameters=repaired_payload,
                timeout_seconds=step.timeout_seconds,
            )
            exec_res = await tool_executor.execute(exec_req)
            if exec_res.success:
                await event_repo.record_event(
                    ExecutionEventContract(
                        trace_id=trace_id,
                        task_id=task.task_id if task else None,
                        workflow_id=workflow.workflow_id,
                        step_id=step.step_id,
                        event_type=EventType.RECOVERY_SUCCEEDED,
                        severity=EventSeverity.INFO,
                        source_component="SelfHealingEngine",
                        message=f"Step {step.step_index} self-healing repair succeeded.",
                        payload=exec_res.data,
                    )
                )
                return True, exec_res.data, "Self-healing repair succeeded."

            return False, None, exec_res.error_message or "Self-healing repair failed."

        # Strategy 3: ESCALATE_HUMAN
        else:
            await event_repo.record_event(
                ExecutionEventContract(
                    trace_id=trace_id,
                    task_id=task.task_id if task else None,
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    event_type=EventType.ESCALATED_TO_HUMAN,
                    severity=EventSeverity.ERROR,
                    source_component="SelfHealingEngine",
                    message=f"Step {step.step_index} ('{step.name}') exhausted self-healing capabilities. Escalated to human operator.",
                    payload={"failure_category": category.value, "strategy": strategy.value},
                )
            )
            return False, None, f"Escalated to human operator ({category.value})."
