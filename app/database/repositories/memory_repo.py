"""Repository for Persistent Memory storage and retrieval."""
import re
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import and_, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.enums import MemoryScope, MemoryType
from app.database.base import dump_json, load_json
from app.database.models.memory import MemoryModel
from app.security.sanitizer import SecretSanitizer


def _normalize_text(text: str) -> str:
    """Normalize string for deduplication comparison."""
    return re.sub(r"\s+", " ", text.strip().lower())


class MemoryRepository:
    """Async repository for managing working, episodic, semantic, and preference memories."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update_memory(self, memory: MemoryContract) -> MemoryContract:
        """
        Persist a memory contract. If an equivalent memory exists for the same user,
        updates importance and metadata instead of creating duplicates.
        Guarantees zero raw secrets enter memory persistence.
        """
        clean_content = SecretSanitizer.sanitize_text(memory.content)
        clean_summary = SecretSanitizer.sanitize_text(memory.summary) if memory.summary else None
        clean_memory = memory.model_copy(
            update={
                "content": clean_content,
                "summary": clean_summary,
            }
        )

        # Check for duplicate candidate
        norm_content = _normalize_text(clean_memory.content)
        stmt = (
            select(MemoryModel)
            .where(
                and_(
                    MemoryModel.user_id == clean_memory.user_id,
                    MemoryModel.memory_type == (clean_memory.memory_type.value if hasattr(clean_memory.memory_type, "value") else str(clean_memory.memory_type)),
                )
            )
        )
        res = await self.session.execute(stmt)
        existing_models = res.scalars().all()

        for model in existing_models:
            if _normalize_text(model.content) == norm_content:
                # Update existing memory with highest importance and merge tags
                model.importance_score = max(model.importance_score, memory.importance_score)
                existing_tags = set(load_json(model.tags_json) if isinstance(load_json(model.tags_json), list) else [])
                new_tags = set(memory.tags or [])
                model.tags_json = dump_json(list(existing_tags.union(new_tags)))
                model.updated_at = datetime.now(timezone.utc)
                if clean_memory.summary:
                    model.summary = clean_memory.summary
                await self.session.flush()
                return model.to_contract()

        # Insert new memory
        model = MemoryModel.from_contract(clean_memory)
        self.session.add(model)
        await self.session.flush()
        return model.to_contract()

    async def get_memory(self, memory_id: str) -> Optional[MemoryContract]:
        """Fetch a specific memory record by ID."""
        stmt = select(MemoryModel).where(MemoryModel.memory_id == memory_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return model.to_contract() if model else None

    async def list_memories(
        self,
        user_id: str,
        memory_types: Optional[List[MemoryType]] = None,
        min_importance: float = 0.0,
        project_id: Optional[str] = None,
    ) -> List[MemoryContract]:
        """List memories strictly scoped by user_id and optional filters."""
        filters = [
            MemoryModel.user_id == user_id,
            MemoryModel.importance_score >= min_importance,
        ]
        if memory_types:
            type_vals = [t.value if hasattr(t, "value") else str(t) for t in memory_types]
            filters.append(MemoryModel.memory_type.in_(type_vals))
        if project_id:
            filters.append(MemoryModel.project_id == project_id)

        stmt = (
            select(MemoryModel)
            .where(and_(*filters))
            .order_by(desc(MemoryModel.importance_score), desc(MemoryModel.created_at))
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [m.to_contract() for m in models]

    async def update_memory(self, memory: MemoryContract) -> Optional[MemoryContract]:
        """Update an existing memory entry."""
        stmt = select(MemoryModel).where(MemoryModel.memory_id == memory.memory_id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None

        model.content = memory.content
        model.summary = memory.summary
        model.importance_score = memory.importance_score
        model.tags_json = dump_json(memory.tags)
        model.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return model.to_contract()

    async def delete_memory(self, memory_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a memory entry with optional user ownership check."""
        filters = [MemoryModel.memory_id == memory_id]
        if user_id:
            filters.append(MemoryModel.user_id == user_id)

        stmt = delete(MemoryModel).where(and_(*filters))
        res = await self.session.execute(stmt)
        await self.session.flush()
        return (res.rowcount or 0) > 0

    async def clear_user_memories(self, user_id: str) -> int:
        """Remove all memories belonging to a user."""
        stmt = delete(MemoryModel).where(MemoryModel.user_id == user_id)
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount or 0
