"""Stage 5: Step Verifier, Compensating Actions & SAGA Rollback Engine."""
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

from app.brain.dag_planner import ExecutionPlan, PlanStep

logger = logging.getLogger("SAGARollbackEngine")


class StepStatus(str):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class StepExecutionResult(BaseModel):
    step_id: str
    status: str
    output: Any = None
    error_message: Optional[str] = None
    verification_passed: bool = True


class SAGARollbackEngine:
    """Executes execution plans step-by-step with post-step verification and automatic compensating rollbacks."""

    def __init__(self, tool_executor: Optional[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Any]]] = None):
        self.tool_executor = tool_executor

    async def execute_plan(self, plan: ExecutionPlan) -> List[StepExecutionResult]:
        """Executes each step in order, verifying success. If a step fails, rolls back prior steps."""
        results: List[StepExecutionResult] = []
        executed_steps: List[PlanStep] = []

        for step in plan.steps:
            logger.info(f"⚡ [SAGA Step {step.order}/{len(plan.steps)}] Executing: {step.name}")
            try:
                # 1. Execute Step Action
                output = await self._run_step_action(step)

                # 2. Verify Step Output
                verification_passed, v_err = self._verify_step_output(step, output)
                if not verification_passed:
                    raise RuntimeError(f"Verification Gate Failed: {v_err}")

                result = StepExecutionResult(
                    step_id=step.step_id,
                    status=StepStatus.SUCCESS,
                    output=output,
                    verification_passed=True,
                )
                results.append(result)
                executed_steps.append(step)

            except Exception as e:
                logger.error(f"❌ Step [{step.name}] Failed with error: {e}. Initiating SAGA Rollback...")
                fail_result = StepExecutionResult(
                    step_id=step.step_id,
                    status=StepStatus.FAILED,
                    error_message=str(e),
                    verification_passed=False,
                )
                results.append(fail_result)

                # 3. Trigger Compensating Actions in Reverse Order
                await self._rollback_executed_steps(executed_steps)
                break

        return results

    async def _run_step_action(self, step: PlanStep) -> Any:
        if self.tool_executor:
            return await self.tool_executor(step.tool_name or "exec", step.args)
        # Mock default success if no external executor provided
        await asyncio.sleep(0.05)
        return {"status": "success", "step": step.name}

    def _verify_step_output(self, step: PlanStep, output: Any) -> tuple[bool, Optional[str]]:
        """Asserts that output is non-empty and contains no error markers."""
        if output is None:
            return False, "Output is None"
        if isinstance(output, dict) and "error" in output:
            return False, str(output.get("error"))
        return True, None

    async def _rollback_executed_steps(self, executed_steps: List[PlanStep]) -> None:
        """Executes compensating actions in LIFO order."""
        for step in reversed(executed_steps):
            if step.is_compensable and step.compensating_action:
                logger.warning(f"🔄 Rolling back Step [{step.name}] via [{step.compensating_action}]...")
                try:
                    if self.tool_executor:
                        await self.tool_executor(step.compensating_action, step.args)
                except Exception as rollback_err:
                    logger.error(f"Failed to execute rollback for step {step.step_id}: {rollback_err}")
