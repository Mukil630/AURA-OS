"""Abstract Interface definitions for Post-Action Verification."""
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.verification import (
    VerificationResultContract,
    VerificationSpecContract,
)
from app.core.enums import VerificationMethod


class IVerifier(ABC):
    """
    Abstract interface for independent post-action validation.
    Verifiers confirm ground-truth state changes after tool executions.
    """
    @property
    @abstractmethod
    def supported_method(self) -> VerificationMethod:
        """Verification method handled by this verifier."""
        pass

    @abstractmethod
    async def verify(
        self,
        step: TaskStepContract,
        spec: VerificationSpecContract,
        tool_output: Dict[str, Any],
    ) -> VerificationResultContract:
        """
        Perform independent verification probe.
        Returns detailed VerificationResultContract with empirical evidence.
        """
        pass
