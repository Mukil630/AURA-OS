"""Persistent Multi-Tier Memory Manager and Semantic Retrieval Engine."""
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.enums import EventSeverity, EventType, MemoryScope, MemoryType
from app.core.interfaces.memory import IContextBuilder, IMemoryStore
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository


STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "of", "to", "for", "with", "at", "by", "from",
    "is", "are", "was", "were", "be", "been", "my", "me", "i", "you", "your", "our",
    "and", "or", "but", "so", "if", "that", "this", "it", "as", "he", "she", "they"
}


def _tokenize(text: str) -> List[str]:
    """Extract alphanumeric keywords lowercased and stripped of stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


class MemoryManager(IMemoryStore, IContextBuilder):
    """
    Multi-tier persistent memory manager supporting Working, Episodic, and Semantic memory.
    Provides semantic/lexical similarity search, tenant isolation, threshold filtering,
    multi-turn continuity context synthesis, and audit tracking.
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    # ── IMemoryStore Implementations ──────────────────────────────────────────────────

    async def store(self, memory: MemoryContract) -> str:
        """Persist a memory contract and emit an audit event."""
        if not self.session:
            raise RuntimeError("Database session required for MemoryManager.")

        repo = MemoryRepository(self.session)
        event_repo = EventRepository(self.session)

        saved = await repo.create_or_update_memory(memory)
        mem_type_val = saved.memory_type.value if hasattr(saved.memory_type, "value") else str(saved.memory_type)

        # Audit event
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_mem_{saved.memory_id}",
                task_id=saved.source_task_id or f"mem_{saved.memory_id}",
                event_type=EventType.MEMORY_SAVED,
                severity=EventSeverity.INFO,
                source_component="MemoryManager",
                message=f"Memory '{saved.memory_id}' ({mem_type_val}) saved for user '{saved.user_id}'.",
                payload={"memory_id": saved.memory_id, "type": mem_type_val, "importance": saved.importance_score},
            )
        )
        await self.session.commit()
        return saved.memory_id

    async def retrieve(self, memory_id: str) -> Optional[MemoryContract]:
        """Fetch memory by unique ID."""
        if not self.session:
            return None
        repo = MemoryRepository(self.session)
        return await repo.get_memory(memory_id)

    async def query(self, query_spec: MemoryQueryContract) -> List[MemoryContract]:
        """
        Retrieve relevant memories matching query text and scope, ranked by relevance score.
        Enforces user/tenant isolation and relevance thresholding.
        """
        if not self.session:
            return []

        repo = MemoryRepository(self.session)
        event_repo = EventRepository(self.session)

        # 1. Fetch candidate pool strictly scoped to this user
        candidates = await repo.list_memories(
            user_id=query_spec.user_id,
            memory_types=query_spec.memory_types,
            min_importance=query_spec.min_importance,
            project_id=query_spec.project_id,
        )

        query_tokens = set(_tokenize(query_spec.query_text))
        if not query_tokens:
            # Empty / whitespace query -> Return top importance items
            results = candidates[: query_spec.top_k]
        else:
            # 2. Score candidates using Semantic/Lexical Relevance + Importance Boost
            scored_memories: List[Tuple[float, MemoryContract]] = []
            for mem in candidates:
                score = self._compute_relevance_score(query_tokens, mem)
                if score >= 0.15:  # Minimum relevance cutoff threshold
                    scored_memories.append((score, mem))

            # 3. Sort by computed relevance score descending
            scored_memories.sort(key=lambda x: x[0], reverse=True)
            results = [m for _, m in scored_memories[: query_spec.top_k]]

        # 4. Audit retrieval
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_query_{uuid4().hex[:8]}",
                task_id=f"query_{query_spec.user_id}",
                event_type=EventType.MEMORY_RETRIEVED,
                severity=EventSeverity.INFO,
                source_component="MemoryManager",
                message=f"Retrieved {len(results)} memories for user '{query_spec.user_id}' matching query.",
                payload={"query": query_spec.query_text, "result_count": len(results)},
            )
        )
        await self.session.commit()
        return results

    async def delete(self, memory_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a memory entry."""
        if not self.session:
            return False
        repo = MemoryRepository(self.session)
        ok = await repo.delete_memory(memory_id, user_id=user_id)
        if ok:
            await self.session.commit()
        return ok

    # ── IContextBuilder Implementations ───────────────────────────────────────────────

    async def build_context(
        self,
        user_id: str,
        raw_input: str,
        project_id: Optional[str] = None,
    ) -> List[MemoryContract]:
        """
        Synthesize relevant user preferences, project facts, and recent episodic memories
        to inject into Master Agent / Planner context. Supports multi-turn continuity.
        """
        query_spec = MemoryQueryContract(
            query_text=raw_input,
            user_id=user_id,
            project_id=project_id,
            memory_types=[
                MemoryType.USER_PREFERENCE,
                MemoryType.SEMANTIC_FACT,
                MemoryType.PROJECT_CONTEXT,
                MemoryType.EPISODIC_TASK,
            ],
            top_k=5,
            min_importance=0.2,
        )
        results = await self.query(query_spec)

        # Multi-turn referential continuity: If results are empty/sparse and input has pronoun/reference cues
        referential_cues = ["it", "its", "this", "that", "the repo", "my repo", "the project", "the issue", "fix it", "check it"]
        raw_lower = raw_input.lower()
        if len(results) < 2 and any(cue in raw_lower for cue in referential_cues):
            repo = MemoryRepository(self.session)
            continuity_prefs = await repo.list_memories(
                user_id=user_id,
                memory_types=[MemoryType.USER_PREFERENCE, MemoryType.SEMANTIC_FACT, MemoryType.EPISODIC_TASK],
                min_importance=0.5,
            )
            existing_ids = {m.memory_id for m in results}
            for pref in continuity_prefs[:3]:
                if pref.memory_id not in existing_ids:
                    results.append(pref)

        return results

    # ── Internal Scoring Algorithm ───────────────────────────────────────────────────

    def _compute_relevance_score(self, query_tokens: Set[str], mem: MemoryContract) -> float:
        """
        Compute hybrid similarity score combining:
        - Lexical keyword overlap in content
        - Exact tag matching bonus
        - Summary match bonus
        - Memory intrinsic importance score
        """
        content_tokens = set(_tokenize(mem.content))
        summary_tokens = set(_tokenize(mem.summary or ""))
        tag_tokens = {t.lower() for t in mem.tags}

        # Content match overlap
        content_overlap = len(query_tokens.intersection(content_tokens))
        content_score = content_overlap / max(1, len(query_tokens))

        # Tag match bonus (high signal)
        tag_overlap = len(query_tokens.intersection(tag_tokens))
        tag_score = 1.0 if tag_overlap > 0 else 0.0

        # Summary match bonus
        summary_overlap = len(query_tokens.intersection(summary_tokens))
        summary_score = summary_overlap / max(1, len(query_tokens))

        # Weighting: 45% Content, 30% Tags, 10% Summary, 15% Intrinsic Importance
        composite_score = (
            (0.45 * content_score)
            + (0.30 * tag_score)
            + (0.10 * summary_score)
            + (0.15 * mem.importance_score)
        )
        return round(composite_score, 4)
