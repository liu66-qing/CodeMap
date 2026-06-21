"""Long-term memory: persistent semantic store with vector similarity retrieval.

Design decisions:
- Qdrant for vector storage — already in stack, handles ANN efficiently
- Redis as metadata index — fast filtering by type/session/time
- Embedding on write — amortize cost, not on read path
- Importance-based consolidation — promote frequently accessed short-term -> long-term

Storage choice: Qdrant (vectors) + Redis (metadata index)
Why Qdrant over FAISS? Persistence, filtering, horizontal scaling.
Why Redis index? Qdrant metadata filtering limited; Redis sorted sets give
O(log N) range queries on time and type.
"""

import json
import time
import uuid
from typing import Any

from .base import MemoryBackend, MemoryEntry, MemoryPriority, MemoryType


class LongTermMemory(MemoryBackend):
    """Persistent memory with semantic retrieval via vector similarity.

    Gracefully degrades to keyword matching when vector/Redis backends
    are unavailable, enabling local development without infrastructure.
    """

    COLLECTION_NAME = "agent_long_term_memory"
    REDIS_PREFIX = "ltm:"

    def __init__(self, vector_store=None, redis_client=None, embedding_client=None):
        self._vector_store = vector_store
        self._redis = redis_client
        self._embedding_client = embedding_client
        # Fallback in-memory store when backends unavailable
        self._fallback: dict[str, MemoryEntry] = {}

    async def store(self, entry: MemoryEntry) -> str:
        """Store entry in vector DB + Redis index, with in-memory fallback."""
        if not entry.id:
            entry.id = f"ltm_{uuid.uuid4().hex[:12]}"

        # Generate embedding if not provided
        if not entry.embedding and self._embedding_client:
            entry.embedding = await self._embedding_client.embed(entry.content)

        # Store in vector DB
        if self._vector_store and entry.embedding:
            await self._vector_store.upsert(
                collection=self.COLLECTION_NAME,
                id=entry.id,
                vector=entry.embedding,
                payload={
                    "content": entry.content,
                    "memory_type": entry.memory_type.value,
                    "priority": entry.priority.value,
                    "created_at": entry.created_at,
                    "session_id": entry.session_id,
                    "metadata": json.dumps(entry.metadata),
                },
            )

        # Store metadata in Redis for fast filtering
        if self._redis:
            key = f"{self.REDIS_PREFIX}{entry.id}"
            await self._redis.hset(
                key,
                mapping={
                    "content": entry.content,
                    "memory_type": entry.memory_type.value,
                    "priority": entry.priority.value,
                    "created_at": str(entry.created_at),
                    "access_count": str(entry.access_count),
                    "session_id": entry.session_id or "",
                    "token_count": str(entry.token_count),
                },
            )
            # Add to time-sorted index
            await self._redis.zadd(
                f"{self.REDIS_PREFIX}timeline",
                {entry.id: entry.created_at},
            )
            # Add to type index
            await self._redis.sadd(
                f"{self.REDIS_PREFIX}type:{entry.memory_type.value}",
                entry.id,
            )

        # Always keep in fallback for local access
        self._fallback[entry.id] = entry
        return entry.id

    async def retrieve(
        self, query: str, top_k: int = 5, memory_type: MemoryType | None = None
    ) -> list[MemoryEntry]:
        """Semantic retrieval via vector similarity search."""
        if self._vector_store and self._embedding_client:
            query_embedding = await self._embedding_client.embed(query)
            filters = {}
            if memory_type:
                filters["memory_type"] = memory_type.value

            results = await self._vector_store.search(
                collection=self.COLLECTION_NAME,
                vector=query_embedding,
                top_k=top_k,
                filters=filters,
            )
            entries = []
            for r in results:
                entry = MemoryEntry(
                    id=r["id"],
                    content=r["payload"]["content"],
                    memory_type=MemoryType(r["payload"]["memory_type"]),
                    priority=MemoryPriority(r["payload"]["priority"]),
                    created_at=r["payload"]["created_at"],
                    session_id=r["payload"].get("session_id"),
                    metadata=json.loads(r["payload"].get("metadata", "{}")),
                )
                entries.append(entry)
            return entries

        # Fallback: keyword overlap scoring
        entries = list(self._fallback.values())
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        query_words = query.lower().split()
        scored = [
            (e, sum(1 for w in query_words if w in e.content.lower()))
            for e in entries
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:top_k]]

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Fetch by ID from local cache."""
        return self._fallback.get(memory_id)

    async def update(self, memory_id: str, **kwargs) -> bool:
        """Update entry fields in local cache."""
        entry = self._fallback.get(memory_id)
        if not entry:
            return False
        for k, v in kwargs.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        return True

    async def delete(self, memory_id: str) -> bool:
        """Remove from all stores."""
        if memory_id in self._fallback:
            del self._fallback[memory_id]
            if self._redis:
                await self._redis.delete(f"{self.REDIS_PREFIX}{memory_id}")
            if self._vector_store:
                await self._vector_store.delete(
                    collection=self.COLLECTION_NAME, id=memory_id
                )
            return True
        return False

    async def get_stats(self) -> dict[str, Any]:
        """Return backend availability and entry count."""
        return {
            "type": "long_term",
            "entries": len(self._fallback),
            "has_vector_store": self._vector_store is not None,
            "has_redis": self._redis is not None,
            "has_embedding_client": self._embedding_client is not None,
        }


class MemoryConsolidator:
    """Promotes important short-term memories to long-term storage.

    Consolidation strategy (inspired by human memory):
    1. Access frequency threshold — memories accessed 3+ times likely important
    2. Priority escalation — HIGH/CRITICAL always consolidate
    3. Semantic type — extracted facts always worth persisting
    4. Decay filter — memories still "alive" after N minutes worth keeping
    """

    def __init__(
        self,
        short_term: "ShortTermMemory",  # noqa: F821
        long_term: LongTermMemory,
        consolidation_threshold: int = 3,
        min_age_seconds: float = 300,
    ):
        self._stm = short_term
        self._ltm = long_term
        self._consolidation_threshold = consolidation_threshold
        self._min_age_seconds = min_age_seconds  # 5 min minimum age

    async def consolidate(self) -> list[str]:
        """Run consolidation pass. Returns IDs of promoted memories."""
        promoted: list[str] = []
        window = await self._stm.get_window(last_n=50)

        for entry in window:
            if self._should_consolidate(entry):
                entry.metadata["consolidated_from"] = "short_term"
                entry.metadata["consolidated_at"] = time.time()
                await self._ltm.store(entry)
                promoted.append(entry.id)

        return promoted

    def _should_consolidate(self, entry: MemoryEntry) -> bool:
        """Determine if a short-term memory deserves long-term persistence."""
        age = time.time() - entry.created_at
        if age < self._min_age_seconds:
            return False
        if entry.priority in (MemoryPriority.CRITICAL, MemoryPriority.HIGH):
            return True
        if entry.access_count >= self._consolidation_threshold:
            return True
        if entry.memory_type == MemoryType.SEMANTIC:
            return True
        return False
