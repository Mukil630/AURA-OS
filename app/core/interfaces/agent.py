"""Abstract Interface definitions for Specialist Agents."""
from abc import ABC, abstractmethod
from typing import Any, Dict
from app.core.contracts.agent import AgentContract
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import AgentType


class IAgent(ABC):
    """
    Abstract contract for all reasoning specialist agents in the MUKIL MASTER AGENT OS.
    Agents reason over task step context and dispatch to tools.
    """
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier of the specialist agent."""
        pass

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Specialist agent classification."""
        pass

    @abstractmethod
    async def get_contract(self) -> AgentContract:
        """Return the complete metadata contract describing capabilities and allowed tools."""
        pass

    @abstractmethod
    async def execute_step(self, step: TaskStepContract, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an assigned TaskStep within the given context.
        Returns the resulting output payload dictionary.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Perform internal diagnostic check returning True if operational."""
        pass
