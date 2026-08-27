"""Verification and Recovery REST API Routes."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.tool import ToolExecutionResult
from app.core.contracts.verification import VerificationResultContract
from app.core.enums import AgentType, FailureCategory, RecoveryStrategy, VerificationStatus
from app.recovery.engine import SelfHealingEngine
from app.verification.engine import VerificationEngine

router = APIRouter(prefix="", tags=["Verification & Self-Healing"])


class VerifyStepRequest(BaseModel):
    step: TaskStepContract
    execution_result: ToolExecutionResult


class ClassifyFailureRequest(BaseModel):
    error_message: Optional[str] = None
    verification_details: Optional[str] = None
    step: Optional[TaskStepContract] = None


class ClassifyFailureResponse(BaseModel):
    failure_category: FailureCategory
    recommended_strategy: RecoveryStrategy
    is_retryable: bool


@router.post("/verification/verify-step", response_model=VerificationResultContract)
async def verify_step_execution(payload: VerifyStepRequest):
    """
    Independently inspect a step's execution result and assert invariant criteria.
    """
    verifier = VerificationEngine()
    result = verifier.verify_step(payload.step, payload.execution_result)
    return result


@router.post("/recovery/classify", response_model=ClassifyFailureResponse)
async def classify_execution_failure(payload: ClassifyFailureRequest):
    """
    Classify an execution or verification failure and determine the optimal recovery strategy.
    """
    healer = SelfHealingEngine()
    dummy_v = VerificationResultContract(
        step_id="temp",
        status=VerificationStatus.FAILED,
        details=payload.verification_details or "",
    ) if payload.verification_details else None

    category = healer.classify_failure(payload.error_message, dummy_v)

    step = payload.step or TaskStepContract(
        workflow_id="wf_default",
        step_index=0,
        name="step_temp",
        agent_type=AgentType.CODING,
        tool_name="temp.tool",
        retry_count=0,
        max_retries=3,
    )
    strategy = healer.select_recovery_strategy(category, step)

    return ClassifyFailureResponse(
        failure_category=category,
        recommended_strategy=strategy,
        is_retryable=strategy in (RecoveryStrategy.RETRY, RecoveryStrategy.REPAIR_INPUT),
    )
