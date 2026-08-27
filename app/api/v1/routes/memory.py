"""Persistent Memory REST API Routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.database.repositories.memory_repo import MemoryRepository
from app.database.session import get_db
from app.memory.manager import MemoryManager

router = APIRouter(prefix="/memory", tags=["Memory Subsystem"])


@router.post("/store", response_model=MemoryContract, status_code=status.HTTP_201_CREATED)
async def store_memory(
    memory: MemoryContract,
    db: AsyncSession = Depends(get_db),
):
    """
    Store or update a memory contract (Working, Episodic, Semantic, User Preference).
    Enforces automatic deduplication and provenance metadata.
    """
    manager = MemoryManager(db)
    memory_id = await manager.store(memory)
    saved = await manager.retrieve(memory_id)
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to retrieve stored memory.")
    return saved


@router.post("/query", response_model=List[MemoryContract])
async def query_memories(
    query_spec: MemoryQueryContract,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic and relevance-ranked memory retrieval strictly scoped to the requesting user.
    """
    manager = MemoryManager(db)
    return await manager.query(query_spec)


@router.get("/{memory_id}", response_model=MemoryContract)
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch specific memory by memory_id."""
    manager = MemoryManager(db)
    mem = await manager.retrieve(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
    return mem


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a memory entry by ID."""
    manager = MemoryManager(db)
    deleted = await manager.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")


@router.get("/user/{user_id}", response_model=List[MemoryContract])
async def list_user_memories(
    user_id: str,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """List all stored memories for a user."""
    repo = MemoryRepository(db)
    return await repo.list_memories(user_id=user_id, min_importance=min_importance)
