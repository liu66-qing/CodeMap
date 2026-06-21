"""Base abstractions for the memory subsystem.

Defines the core data model (MemoryEntry) and abstract backend interface
that all storage tiers implement. The importance scoring formula balances
priority weight, temporal recency, and access frequency — tuned for
agent workloads where recent context matters most but critical decisions
must never be lost.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class MemoryType(str, Enum):
    """Classification of memory content by cognitive function."""

    EPISODIC = "episodic"  # Conversation turns, tool results
    SEMANTIC = "semantic"  # Extracted facts, entity knowledge
    PROCEDURAL = "procedural"  # Learned patterns, successful strategies


class MemoryPriority(str, Enum):
    """Eviction priority levels — maps to importance weights."""

    CRITICAL = "critical"  # Never evict (user corrections, key decisions)
    HIGH = "high"  # Evict last (important context)
    NORMAL = "normal"  # Standard eviction rules
    LOW = "low"  # Evict first (verbose tool outputs)


@dataclass
class MemoryEntry:
    """Single unit of memory with metadata for retrieval and eviction."""

    id: str
    content: str
    memory_type: MemoryType
    priority: MemoryPriority = MemoryPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    session_id: str | None = None
    decay_rate: float = 0.1  # For importance decay over time

    @property
    def importance_score(self) -> float:
        """Compute importance: priority weight * recency * access frequency.

        Formula breakdown:
        - Base (50%): priority weight ensures critical memories always surface
        - Recency (30%): exponential decay rewards recent access
        - Frequency (20%): capped at 10 accesses to prevent runaway scores
        """
        priority_weights = {
            "critical": 1.0,
            "high": 0.8,
            "normal": 0.5,
            "low": 0.2,
        }
        base = priority_weights.get(self.priority, 0.5)
        recency = 1.0 / (
            1.0 + self.decay_rate * (time.time() - self.last_accessed) / 3600
        )
        frequency = min(1.0, self.access_count / 10)
        return base * 0.5 + recency * 0.3 + frequency * 0.2


class MemoryBackend(ABC):
    """Abstract memory storage backend.

    All memory tiers (short-term, long-term) implement this interface,
    enabling uniform access patterns and easy testing with in-memory fakes.
    """

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Persist a memory entry. Returns the entry ID."""
        ...

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5, memory_type: MemoryType | None = None
    ) -> list[MemoryEntry]:
        """Retrieve entries relevant to query, optionally filtered by type."""
        ...

    @abstractmethod
    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Fetch a single entry by its ID."""
        ...

    @abstractmethod
    async def update(self, memory_id: str, **kwargs) -> bool:
        """Update fields on an existing entry. Returns True if found."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete an entry. Returns True if it existed."""
        ...

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Return backend-specific health/usage statistics."""
        ...
