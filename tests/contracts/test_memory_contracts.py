"""Unit tests for Memory Contracts."""
import pytest
from pydantic import ValidationError

from app.core.contracts.memory import (
    MemoryContract,
    MemoryQueryContract,
)
from app.core.enums import MemoryScope, MemoryType


def test_memory_contract_creation():
    mem = MemoryContract(
        memory_type=MemoryType.SEMANTIC_FACT,
        scope=MemoryScope.USER,
        user_id="user_123",
        content="User deploys backend microservices on Railway.",
        importance_score=0.8,
        tags=["railway", "deployment", "backend"],
    )
    assert mem.memory_id.startswith("mem_")
    assert mem.memory_type == MemoryType.SEMANTIC_FACT
    assert mem.importance_score == 0.8
    assert "railway" in mem.tags


def test_memory_importance_score_bounds():
    with pytest.raises(ValidationError):
        MemoryContract(
            memory_type=MemoryType.USER_PREFERENCE,
            user_id="user_123",
            content="Prefer Tanglish tone",
            importance_score=1.5,  # must be <= 1.0
        )


def test_memory_query_contract():
    query = MemoryQueryContract(
        query_text="Where does Mukil deploy backend projects?",
        user_id="user_123",
        top_k=3,
    )
    assert query.user_id == "user_123"
    assert query.top_k == 3
    assert MemoryType.SEMANTIC_FACT in query.memory_types
