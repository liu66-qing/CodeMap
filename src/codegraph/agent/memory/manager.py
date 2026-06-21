"""Unified memory manager — single interface over 3-tier memory hierarchy.

Architecture:
+---------------------------------------------------+
|              MemoryManager (Facade)                |
+--------------+-----------------+------------------+
| ShortTerm    |   LongTerm      |  Episodic        |
| (working)    |   (persistent)  |  (session log)   |
| OrderedDict  |   Qdrant+Redis  |  Redis Stream    |
| ~4K tokens   |   unlimited     |  per-session     |
+--------------+-----------------+------------------+

Read path:  query -> short-term (exact) -> long-term (semantic) -> merge + rank
Write path: entry -> short-term buffer -> [consolidation] -> long-term
"""

import uuid
from typing import Any

from .base import MemoryEntry, MemoryPriority, MemoryType
from .long_term import LongTermMemory, MemoryConsolidator
from .short_term import ShortTermMemory


class MemoryManager:
    """Unified memory interface for agent reasoning loops.

    Coordinates short-term working memory and long-term persistent storage,
    providing a single API surface for remember/recall operations. Handles
    automatic consolidation of important short-term memories into long-term.
    """

    def __init__(
        self,
        short_term_tokens: int = 4000,
        max_entries: int = 50,
        vector_store=None,
        redis_client=None,
        embedding_client=None,
    ):
        self.short_term = ShortTermMemory(
            max_tokens=short_term_tokens, max_entries=max_entries
        )
        self.long_term = LongTermMemory(
            vector_store=vector_store,
            redis_client=redis_client,
            embedding_client=embedding_client,
        )
        self._consolidator = MemoryConsolidator(self.short_term, self.long_term)
        self._session_id: str | None = None

    def set_session(self, session_id: str):
        """Bind this manager to a session for tracking provenance."""
        self._session_id = session_id

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        priority: MemoryPriority = MemoryPriority.NORMAL,
        token_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a memory. Always goes to short-term first.

        Returns the memory ID for later retrieval or deletion.
        Token count is estimated from content length if not provided.
        """
        entry = MemoryEntry(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            memory_type=memory_type,
            priority=priority,
            token_count=token_count or len(content) // 4,  # rough token estimate
            metadata=metadata or {},
            session_id=self._session_id,
        )
        await self.short_term.store(entry)
        return entry.id

    async def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_type: MemoryType | None = None,
        include_long_term: bool = True,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories from all tiers.

        Merges short-term (recency-based) and long-term (semantic) results,
        deduplicates by ID, and ranks by importance score.
        """
        # Short-term: fast, recent
        stm_results = await self.short_term.retrieve(
            query, top_k=top_k, memory_type=memory_type
        )

        if not include_long_term:
            return stm_results

        # Long-term: semantic search
        ltm_results = await self.long_term.retrieve(
            query, top_k=top_k, memory_type=memory_type
        )

        # Merge and deduplicate
        seen_ids = {e.id for e in stm_results}
        merged = list(stm_results)
        for entry in ltm_results:
            if entry.id not in seen_ids:
                merged.append(entry)
                seen_ids.add(entry.id)

        # Rank by importance
        merged.sort(key=lambda e: e.importance_score, reverse=True)
        return merged[:top_k]

    async def consolidate(self) -> list[str]:
        """Run memory consolidation (short-term -> long-term promotion).

        Should be called periodically (e.g., between agent turns or on idle).
        Returns list of promoted memory IDs.
        """
        return await self._consolidator.consolidate()

    async def get_context_window(self, max_tokens: int = 2000) -> str:
        """Build context string from memory for LLM prompt injection.

        Returns a formatted string of recent memories within token budget,
        ordered chronologically (most recent last) for natural reading.
        """
        entries = await self.short_term.get_window(last_n=20)
        context_parts: list[str] = []
        token_budget = max_tokens

        for entry in reversed(entries):  # Most recent last
            if entry.token_count > token_budget:
                break
            context_parts.append(f"[{entry.memory_type.value}] {entry.content}")
            token_budget -= entry.token_count

        return "\n".join(context_parts)

    async def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics from all memory tiers."""
        stm_stats = await self.short_term.get_stats()
        ltm_stats = await self.long_term.get_stats()
        return {
            "short_term": stm_stats,
            "long_term": ltm_stats,
            "session_id": self._session_id,
        }
