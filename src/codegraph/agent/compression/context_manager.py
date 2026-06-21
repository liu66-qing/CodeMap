"""Context window manager -- monitors token usage and triggers compression.

Responsibilities:
1. Track token count of current context
2. Trigger compression when approaching limit (80% threshold)
3. Select appropriate strategy based on content type
4. Maintain compressed context cache to avoid recompression
"""
from typing import Any
from .strategies import (
    Message,
    CompressedContext,
    CompressionStrategy,
    HybridCompression,
    SlidingWindowStrategy,
)


class ContextWindowManager:
    """Manages LLM context window with automatic compression."""

    def __init__(
        self,
        max_tokens: int = 16000,
        compression_threshold: float = 0.8,  # Compress at 80% capacity
        strategy: CompressionStrategy | None = None,
        llm_client=None,
    ):
        self._max_tokens = max_tokens
        self._threshold = compression_threshold
        self._strategy = strategy or HybridCompression(llm_client)
        self._fallback_strategy = SlidingWindowStrategy()
        self._messages: list[Message] = []
        self._compression_count = 0

    @property
    def current_tokens(self) -> int:
        return sum(m.token_count for m in self._messages)

    @property
    def utilization(self) -> float:
        return self.current_tokens / self._max_tokens

    @property
    def needs_compression(self) -> bool:
        return self.utilization >= self._threshold

    async def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add message and compress if needed."""
        import time

        msg = Message(
            role=role,
            content=content,
            token_count=len(content) // 4,  # Rough estimate; production would use tiktoken
            metadata=metadata or {},
            timestamp=time.time(),
        )
        self._messages.append(msg)

        if self.needs_compression:
            await self._compress()

    async def get_context(self) -> list[dict[str, str]]:
        """Get current context as message dicts for LLM API."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    async def _compress(self) -> None:
        """Run compression strategy."""
        target = int(self._max_tokens * 0.6)  # Compress to 60% to give headroom

        try:
            result = await self._strategy.compress(self._messages, target)
            self._messages = result.messages
            self._compression_count += 1
        except Exception:
            # Fallback to simple sliding window
            result = await self._fallback_strategy.compress(self._messages, target)
            self._messages = result.messages
            self._compression_count += 1

    async def get_stats(self) -> dict[str, Any]:
        return {
            "message_count": len(self._messages),
            "current_tokens": self.current_tokens,
            "max_tokens": self._max_tokens,
            "utilization": round(self.utilization, 3),
            "compression_count": self._compression_count,
            "strategy": self._strategy.name,
        }
