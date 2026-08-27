"""Independent Verification Engine for validating step execution results and invariants."""
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.tool import ToolExecutionResult
from app.core.contracts.verification import (
    VerificationResultContract,
    VerificationSpecContract,
)
from app.core.enums import VerificationMethod, VerificationStatus
from app.core.interfaces.verifier import IVerifier


class VerificationEngine(IVerifier):
    """
    Independent verification evaluator.
    Validates that a step's execution actually satisfied its intended invariants,
    preventing silent failures or false positives.
    """

    @property
    def supported_method(self) -> VerificationMethod:
        return VerificationMethod.RETURN_CODE_CHECK

    async def verify(
        self,
        step: TaskStepContract,
        spec: VerificationSpecContract,
        tool_output: Dict[str, Any],
    ) -> VerificationResultContract:
        """Implements IVerifier.verify."""
        passed = True
        discrepancies = []

        for key, expected_val in (spec.expected_condition or {}).items():
            actual_val = tool_output.get(key)
            if actual_val != expected_val:
                passed = False
                discrepancies.append(f"Field '{key}' expected '{expected_val}', got '{actual_val}'.")

        return VerificationResultContract(
            spec_id=spec.spec_id,
            step_id=step.step_id,
            status=VerificationStatus.VERIFIED if passed else VerificationStatus.FAILED,
            details="Verification passed." if passed else "; ".join(discrepancies),
            evidence=tool_output,
        )

    def verify_step(
        self,
        step: TaskStepContract,
        result: ToolExecutionResult,
    ) -> VerificationResultContract:
        """
        Evaluate step execution result against domain rules and invariant checks.
        """
        spec_id = f"vspec_{step.step_id}"

        # 1. Check Tool Execution Status
        if not result.success:
            return VerificationResultContract(
                spec_id=spec_id,
                step_id=step.step_id,
                status=VerificationStatus.FAILED,
                details=f"Tool execution failed: {result.error_message}",
                evidence={"error": result.error_message},
            )

        data = result.data or {}

        # 2. Domain-Specific Invariant Checks (Prevent Silent Failures)

        # Invariant Check: Test execution must have 0 failures
        if step.tool_name == "coding.run_tests":
            failed_count = data.get("tests_failed", 0)
            status_val = data.get("status", "")
            if failed_count > 0 or status_val == "failed":
                return VerificationResultContract(
                    spec_id=spec_id,
                    step_id=step.step_id,
                    status=VerificationStatus.FAILED,
                    details=f"Automated test suite reported {failed_count} failures (status='{status_val}').",
                    evidence=data,
                )

        # Invariant Check: Drive upload must yield non-empty file_id
        elif step.tool_name == "drive.upload":
            if not data.get("file_id") or data.get("status") == "failed":
                return VerificationResultContract(
                    spec_id=spec_id,
                    step_id=step.step_id,
                    status=VerificationStatus.FAILED,
                    details="Google Drive upload completed without returning a valid file_id.",
                    evidence=data,
                )

        # Invariant Check: Telegram message must be delivered
        elif step.tool_name == "telegram.send_message":
            if data.get("delivered") is False:
                return VerificationResultContract(
                    spec_id=spec_id,
                    step_id=step.step_id,
                    status=VerificationStatus.FAILED,
                    details="Telegram message dispatch was reported as undelivered.",
                    evidence=data,
                )

        # Invariant Check: Patch analysis must identify target files
        elif step.tool_name == "coding.analyze_patch":
            if not data.get("patch_strategy") and not data.get("files_to_modify"):
                return VerificationResultContract(
                    spec_id=spec_id,
                    step_id=step.step_id,
                    status=VerificationStatus.FAILED,
                    details="Patch analysis yielded no actionable strategy or modified files.",
                    evidence=data,
                )

        # 3. Standard Verification Passed
        return VerificationResultContract(
            spec_id=spec_id,
            step_id=step.step_id,
            status=VerificationStatus.VERIFIED,
            details=f"Step '{step.name}' passed verification successfully.",
            evidence=data,
        )
