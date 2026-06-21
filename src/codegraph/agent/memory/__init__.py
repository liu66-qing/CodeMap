"""Three-tier memory architecture for multi-agent codebase analysis.

Architecture:
- ShortTermMemory: Bounded working memory (OrderedDict, token-budget LRU)
- LongTermMemory: Persistent semantic store (Qdrant + Redis)
- MemoryManager: Unified facade coordinating all tiers

Usage:
    from codegraph.agent.memory import MemoryManager, MemoryType, MemoryPriority

    manager = MemoryManager(short_term_tokens=4000)
    await manager.remember("user asked about auth flow", memory_type=MemoryType.EPISODIC)
    results = await manager.recall("authentication")
"""

from .base import MemoryBackend, MemoryEntry, MemoryPriority, MemoryType
from .long_term import LongTermMemory, MemoryConsolidator
from .manager import MemoryManager
from .short_term import ShortTermMemory

__all__ = [
    "MemoryBackend",
    "MemoryConsolidator",
    "MemoryEntry",
    "MemoryManager",
    "MemoryPriority",
    "MemoryType",
    "LongTermMemory",
    "ShortTermMemory",
]
