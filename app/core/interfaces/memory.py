"""Abstract Interface definitions for Memory Stores and Retrieval Engines."""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.contracts.memory import (
    MemoryContract,
    MemoryQueryContract,
)


class IMemoryStore(ABC):
    """
    Abstract interface for persisting and managing structured memory across tiers.
    """
    @abstractmethod
    async def store(self, memory: MemoryContract) -> str:
        """Persist a memory entry and return its memory_id."""
        pass

    @abstractmethod
    async def retrieve(self, memory_id: str) -> Optional[MemoryContract]:
        """Fetch a specific memory record by ID."""
        pass

    @abstractmethod
    async def query(self, query: MemoryQueryContract) -> List[MemoryContract]:
        """Retrieve relevant memories matching the query specification."""
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Remove a memory record by ID."""
        pass


class IContextBuilder(ABC):
    """
    Abstract interface for synthesizing relevant retrieved memories into a prompt context package.
    """
    @abstractmethod
    async def build_context(self, user_id: str, raw_input: str, project_id: Optional[str] = None) -> List[MemoryContract]:
        """Retrieve and assemble context package for the Master Planner."""
        pass
