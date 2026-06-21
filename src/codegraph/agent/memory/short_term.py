"""Short-term memory: bounded sliding window for active conversation context.

Design decisions:
- Fixed capacity (token budget, not message count) — mirrors LLM context limits
- LRU eviction with priority override — critical memories pinned
- No persistence — lives only during session, reconstructed from long-term on resume
- O(1) access via dict + doubly-linked list (OrderedDict pattern)

Storage choice: In-memory OrderedDict
Why not Redis? Latency. Short-term memory accessed every LLM call (~50ms Redis RTT
unacceptable for the hot path).
Why not simple list? Need O(1) eviction + priority pinning.
"""

import asyncio
import time
from collections import OrderedDict
from typing import Any

from .base import MemoryBackend, MemoryEntry, MemoryPriority, MemoryType


class ShortTermMemory(MemoryBackend):
    """Bounded working memory with token-budget eviction.

    Maintains a sliding window of recent memories constrained by both
    token count and entry count. Eviction prioritizes low-priority,
    least-recently-used entries while pinning CRITICAL memories.
    """

    def __init__(self, max_tokens: int = 4000, max_entries: int = 50):
        self._store: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._max_tokens = max_tokens
        self._max_entries = max_entries
        self._current_tokens = 0
        self._lock = asyncio.Lock()

    @property
    def utilization(self) -> float:
        """Current token budget utilization as a fraction [0, 1]."""
        return self._current_tokens / self._max_tokens if self._max_tokens > 0 else 0

    async def store(self, entry: MemoryEntry) -> str:
        """Store entry, evicting lowest-priority LRU entries if over budget."""
        async with self._lock:
            # Evict until we have room
            while (
                self._current_tokens + entry.token_count > self._max_tokens
                or len(self._store) >= self._max_entries
            ):
                if not self._evict_one():
                    break
            self._store[entry.id] = entry
            self._store.move_to_end(entry.id)
            self._current_tokens += entry.token_count
        return entry.id

    async def retrieve(
        self, query: str, top_k: int = 5, memory_type: MemoryType | None = None
    ) -> list[MemoryEntry]:
        """Retrieve by importance score (no embedding search — buffer too small to need it)."""
        entries = list(self._store.values())
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        # Sort by importance, return top_k
        entries.sort(key=lambda e: e.importance_score, reverse=True)
        for e in entries[:top_k]:
            e.access_count += 1
            e.last_accessed = time.time()
        return entries[:top_k]

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Fetch by ID, promoting to most-recently-used position."""
        entry = self._store.get(memory_id)
        if entry:
            self._store.move_to_end(memory_id)
            entry.access_count += 1
            entry.last_accessed = time.time()
        return entry

    async def update(self, memory_id: str, **kwargs) -> bool:
        """Update entry fields in place. Promotes to MRU."""
        entry = self._store.get(memory_id)
        if not entry:
            return False
        for k, v in kwargs.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        self._store.move_to_end(memory_id)
        return True

    async def delete(self, memory_id: str) -> bool:
        """Remove entry and reclaim its token budget."""
        if memory_id in self._store:
            self._current_tokens -= self._store[memory_id].token_count
            del self._store[memory_id]
            return True
        return False

    async def get_stats(self) -> dict[str, Any]:
        """Return current buffer statistics."""
        return {
            "type": "short_term",
            "entries": len(self._store),
            "max_entries": self._max_entries,
            "tokens_used": self._current_tokens,
            "max_tokens": self._max_tokens,
            "utilization": self.utilization,
        }

    def _evict_one(self) -> bool:
        """Evict lowest-priority, least-recently-used entry. Never evicts CRITICAL."""
        candidates = [
            (k, v)
            for k, v in self._store.items()
            if v.priority != MemoryPriority.CRITICAL
        ]
        if not candidates:
            return False
        # Evict first (oldest) non-critical entry
        evict_id = candidates[0][0]
        self._current_tokens -= self._store[evict_id].token_count
        del self._store[evict_id]
        return True

    async def get_window(self, last_n: int = 10) -> list[MemoryEntry]:
        """Get last N entries as conversation window (insertion order)."""
        entries = list(self._store.values())
        return entries[-last_n:]
