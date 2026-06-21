"""Long-context compression strategies.

Problem: LLM context windows are finite. As conversations grow, we must compress
without losing critical information. Different strategies trade off differently:

+--------------------+----------------+---------------+--------------+
| Strategy           | Info Loss      | Compute Cost  | Best For     |
+--------------------+----------------+---------------+--------------+
| Sliding Window     | High (drops)   | O(1)          | Chat history |
| Summary            | Medium (lossy) | O(n) LLM call | Long convos  |
| Entity Extraction  | Low (focused)  | O(n) parse    | Code analysis|
| Hybrid             | Lowest         | O(n) mixed    | Production   |
+--------------------+----------------+---------------+--------------+

Design decision: Hybrid as default -- uses sliding window for recent, summary for
middle, entity extraction for oldest. This mirrors human memory (vivid recent,
gist of middle, key facts from past).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0


@dataclass
class CompressedContext:
    messages: list[Message]
    total_tokens: int
    compression_ratio: float  # original_tokens / compressed_tokens
    strategy_used: str
    dropped_count: int = 0  # Messages that were dropped entirely
    summary_sections: list[str] = field(default_factory=list)


class CompressionStrategy(ABC):
    """Base class for context compression strategies."""

    @abstractmethod
    async def compress(self, messages: list[Message], target_tokens: int) -> CompressedContext: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class SlidingWindowStrategy(CompressionStrategy):
    """Keep last N messages that fit within token budget.

    Pros: Zero compute cost, preserves exact recent context.
    Cons: Complete information loss beyond window edge.
    Use: Real-time chat where speed > memory.
    """

    @property
    def name(self) -> str:
        return "sliding_window"

    async def compress(self, messages: list[Message], target_tokens: int) -> CompressedContext:
        kept: list[Message] = []
        tokens = 0
        original_tokens = sum(m.token_count for m in messages)

        # Always keep system messages
        system_msgs = [m for m in messages if m.role == "system"]
        for m in system_msgs:
            tokens += m.token_count
            kept.append(m)

        # Fill from most recent
        non_system = [m for m in messages if m.role != "system"]
        for msg in reversed(non_system):
            if tokens + msg.token_count > target_tokens:
                break
            kept.insert(len(system_msgs), msg)  # Insert after system msgs
            tokens += msg.token_count

        dropped = len(messages) - len(kept)
        ratio = original_tokens / max(tokens, 1)

        return CompressedContext(
            messages=kept,
            total_tokens=tokens,
            compression_ratio=ratio,
            strategy_used=self.name,
            dropped_count=dropped,
        )


class SummaryCompression(CompressionStrategy):
    """Summarize older messages, keep recent verbatim.

    Approach: Split into [old | recent]. Summarize old into single message.
    The summary preserves: key decisions, tool results, entity mentions, user preferences.

    Pros: Retains semantic content from entire conversation.
    Cons: Lossy (details lost), requires LLM call (latency + cost).
    Use: Long multi-turn sessions where context matters.
    """

    def __init__(self, llm_client=None, recent_keep: int = 6):
        self._llm = llm_client
        self._recent_keep = recent_keep

    @property
    def name(self) -> str:
        return "summary"

    async def compress(self, messages: list[Message], target_tokens: int) -> CompressedContext:
        original_tokens = sum(m.token_count for m in messages)

        if original_tokens <= target_tokens:
            return CompressedContext(
                messages=messages,
                total_tokens=original_tokens,
                compression_ratio=1.0,
                strategy_used=self.name,
            )

        # Split: older messages get summarized, recent kept verbatim
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        recent = non_system[-self._recent_keep:]
        older = non_system[:-self._recent_keep]

        if not older:
            # Nothing to summarize, fall back to sliding window
            return await SlidingWindowStrategy().compress(messages, target_tokens)

        # Generate summary of older messages
        summary_text = await self._summarize(older)
        summary_msg = Message(
            role="system",
            content=f"[Conversation summary]\n{summary_text}",
            token_count=len(summary_text) // 4,
            metadata={"is_summary": True, "covers_messages": len(older)},
        )

        kept = system_msgs + [summary_msg] + recent
        tokens = sum(m.token_count for m in kept)
        ratio = original_tokens / max(tokens, 1)

        return CompressedContext(
            messages=kept,
            total_tokens=tokens,
            compression_ratio=ratio,
            strategy_used=self.name,
            dropped_count=len(older),
            summary_sections=[summary_text],
        )

    async def _summarize(self, messages: list[Message]) -> str:
        """Summarize a batch of messages preserving key information."""
        if not self._llm:
            # Fallback: extract first line of each message
            lines = []
            for m in messages:
                first_line = m.content.split("\n")[0][:100]
                lines.append(f"[{m.role}] {first_line}")
            return "\n".join(lines[-10:])

        conversation_text = "\n".join(f"[{m.role}]: {m.content[:500]}" for m in messages)

        prompt = f"""Summarize this conversation segment. Preserve:
1. Key decisions made
2. Important tool results and findings
3. Entity names and relationships discovered
4. User preferences or corrections

Conversation:
{conversation_text}

Summary (concise, bullet points):"""

        response = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.get("content", "")


class EntityExtractionCompression(CompressionStrategy):
    """Extract and retain only entities + relationships, discard prose.

    Approach: Parse messages for code entities (functions, classes, files),
    relationships (calls, imports, inherits), and facts. Store as structured triples.

    Pros: Minimal token usage, preserves factual content.
    Cons: Loses conversational nuance, reasoning chains.
    Use: Code analysis tasks where entities matter more than dialogue.
    """

    @property
    def name(self) -> str:
        return "entity_extraction"

    async def compress(self, messages: list[Message], target_tokens: int) -> CompressedContext:
        import re

        original_tokens = sum(m.token_count for m in messages)

        # Extract entities from all messages
        entities: set[str] = set()
        facts: list[str] = []

        for msg in messages:
            # Code entities: file paths, function names, class names
            paths = re.findall(r'[\w/]+\.\w{1,4}', msg.content)
            funcs = re.findall(r'\b(?:def|function|fn|func)\s+(\w+)', msg.content)
            classes = re.findall(r'\b(?:class|struct|interface)\s+(\w+)', msg.content)
            entities.update(paths)
            entities.update(funcs)
            entities.update(classes)

            # Key facts (lines with "is", "uses", "calls", "returns")
            for line in msg.content.split("\n"):
                if any(kw in line.lower() for kw in ["is a", "uses", "calls", "returns", "depends"]):
                    facts.append(line.strip()[:150])

        # Build compressed representation
        entity_str = "Entities: " + ", ".join(sorted(entities)[:50])
        facts_str = "Facts:\n" + "\n".join(f"- {f}" for f in facts[:20])
        compressed_content = f"{entity_str}\n\n{facts_str}"

        system_msgs = [m for m in messages if m.role == "system"]
        recent = [m for m in messages if m.role != "system"][-3:]

        entity_msg = Message(
            role="system",
            content=f"[Extracted knowledge]\n{compressed_content}",
            token_count=len(compressed_content) // 4,
            metadata={"is_extraction": True},
        )

        kept = system_msgs + [entity_msg] + recent
        tokens = sum(m.token_count for m in kept)

        return CompressedContext(
            messages=kept,
            total_tokens=tokens,
            compression_ratio=original_tokens / max(tokens, 1),
            strategy_used=self.name,
            dropped_count=len(messages) - len(kept),
        )


class HybridCompression(CompressionStrategy):
    """Multi-tier compression mimicking human memory architecture.

    Architecture:
    +---------------------------------------------------+
    | Zone 1: RECENT (keep verbatim)   | last 4 msgs    |
    | Zone 2: MIDDLE (summarize)       | next 10 msgs   |
    | Zone 3: DISTANT (entity extract) | oldest msgs    |
    +---------------------------------------------------+

    Token budget allocation:
    - Recent: 50% (full fidelity where it matters most)
    - Summary: 30% (semantic gist of middle history)
    - Entities: 20% (factual anchors from distant past)

    This is the DEFAULT strategy -- best trade-off for production use.
    """

    def __init__(self, llm_client=None):
        self._llm = llm_client
        self._summary = SummaryCompression(llm_client, recent_keep=4)
        self._entity = EntityExtractionCompression()

    @property
    def name(self) -> str:
        return "hybrid"

    async def compress(self, messages: list[Message], target_tokens: int) -> CompressedContext:
        original_tokens = sum(m.token_count for m in messages)

        if original_tokens <= target_tokens:
            return CompressedContext(
                messages=messages,
                total_tokens=original_tokens,
                compression_ratio=1.0,
                strategy_used=self.name,
            )

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # Zone allocation
        total_non_system = len(non_system)
        recent_count = min(4, total_non_system)
        middle_count = min(10, total_non_system - recent_count)
        distant_count = total_non_system - recent_count - middle_count

        recent = non_system[-recent_count:] if recent_count > 0 else []
        middle = non_system[distant_count:distant_count + middle_count] if middle_count > 0 else []
        distant = non_system[:distant_count] if distant_count > 0 else []

        # Budget allocation
        system_tokens = sum(m.token_count for m in system_msgs)
        available = target_tokens - system_tokens
        recent_budget = int(available * 0.5)
        summary_budget = int(available * 0.3)
        entity_budget = int(available * 0.2)

        # Compress each zone
        compressed_parts: list[Message] = list(system_msgs)

        # Zone 3: Entity extraction for distant
        if distant:
            entity_result = await self._entity.compress(distant, entity_budget)
            for m in entity_result.messages:
                if m.role == "system" and m.metadata.get("is_extraction"):
                    compressed_parts.append(m)

        # Zone 2: Summary for middle
        if middle:
            summary_result = await self._summary.compress(middle, summary_budget)
            for m in summary_result.messages:
                if m.metadata.get("is_summary"):
                    compressed_parts.append(m)

        # Zone 1: Recent verbatim
        compressed_parts.extend(recent)

        tokens = sum(m.token_count for m in compressed_parts)
        return CompressedContext(
            messages=compressed_parts,
            total_tokens=tokens,
            compression_ratio=original_tokens / max(tokens, 1),
            strategy_used=self.name,
            dropped_count=len(messages) - len(compressed_parts),
        )
