"""Three-tier memory architecture for multi-agent codebase analysis.

Architecture:
- ShortTermMemory: Bounded working memory (OrderedDict, token-budget LRU)
- LongTermMemory: Persistent semantic store (Qdrant + Redis)
- MemoryManager: Unified facade coordinating all tiers
- SessionMemory: Legacy session store (backward-compatible)

Usage:
    from codegraph.agent.memory import MemoryManager, MemoryType, MemoryPriority
    from codegraph.agent.memory import SessionMemory, get_session  # legacy compat
"""

from .base import MemoryBackend, MemoryEntry, MemoryPriority, MemoryType
from .long_term import LongTermMemory, MemoryConsolidator
from .manager import MemoryManager
from .short_term import ShortTermMemory
from .session_memory import SessionMemory, get_session

__all__ = [
    "MemoryBackend",
    "MemoryConsolidator",
    "MemoryEntry",
    "MemoryManager",
    "MemoryPriority",
    "MemoryType",
    "LongTermMemory",
    "ShortTermMemory",
    "SessionMemory",
    "get_session",
]
