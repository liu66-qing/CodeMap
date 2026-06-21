"""Inter-agent message bus — pub/sub communication backbone.

Architecture:
┌──────────┐    ┌──────────────┐    ┌──────────┐
│ Agent A  │───▶│  MessageBus  │───▶│ Agent B  │
│(producer)│    │  (pub/sub)   │    │(consumer)│
└──────────┘    └──────┬───────┘    └──────────┘
                       │
                       ▼
              ┌────────────────┐
              │  SharedState   │
              │  (blackboard)  │
              └────────────────┘

Design decisions:
- Async pub/sub with topic routing — agents subscribe to relevant topics only
- Redis Streams as transport (when available) — persistence + consumer groups
- In-memory fallback via asyncio.Queue — zero-dependency local dev
- Message ordering guaranteed within topic (Redis Stream ID = timestamp)
- Dead letter queue for failed deliveries — debug without data loss

Why pub/sub over direct RPC?
1. Decoupling — agents don't need to know each other's existence
2. Fan-out — one message can trigger multiple agents (e.g., "new_entity_found")
3. Replay — Redis Streams support reading from any point (debugging)
4. Backpressure — consumers read at own pace
"""
import asyncio
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum


class MessageType(str, Enum):
    # Control messages
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Data messages
    CONTEXT_UPDATE = "context_update"
    ENTITY_DISCOVERED = "entity_discovered"
    TOOL_RESULT = "tool_result"

    # Coordination
    REQUEST_HELP = "request_help"
    OFFER_RESULT = "offer_result"
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"

    # Health
    HEARTBEAT = "heartbeat"
    ERROR_REPORT = "error_report"

@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:10]}")
    sender: str = ""
    topic: str = ""
    msg_type: MessageType = MessageType.CONTEXT_UPDATE
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    reply_to: str | None = None  # For request-response patterns
    ttl: int = 300  # Seconds until message expires

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "topic": self.topic,
            "msg_type": self.msg_type.value,
            "payload": json.dumps(self.payload),
            "timestamp": str(self.timestamp),
            "reply_to": self.reply_to or "",
            "ttl": str(self.ttl),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload)
        return cls(
            id=data.get("id", ""),
            sender=data.get("sender", ""),
            topic=data.get("topic", ""),
            msg_type=MessageType(data.get("msg_type", "context_update")),
            payload=payload,
            timestamp=float(data.get("timestamp", time.time())),
            reply_to=data.get("reply_to") or None,
            ttl=int(data.get("ttl", 300)),
        )


MessageHandler = Callable[[AgentMessage], Awaitable[None]]


class MessageBus:
    """Async message bus with topic-based routing."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._subscribers: dict[str, list[MessageHandler]] = {}
        self._queues: dict[str, asyncio.Queue] = {}  # In-memory fallback
        self._message_log: list[AgentMessage] = []  # For debugging
        self._running = False

    async def publish(self, message: AgentMessage) -> None:
        """Publish message to topic."""
        self._message_log.append(message)

        if self._redis:
            stream_key = f"agent_bus:{message.topic}"
            await self._redis.xadd(stream_key, message.to_dict(), maxlen=1000)
        else:
            # In-memory: deliver to subscribers directly
            handlers = self._subscribers.get(message.topic, [])
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    # Dead letter: log failed delivery
                    self._message_log.append(AgentMessage(
                        sender="bus",
                        topic="dead_letter",
                        msg_type=MessageType.ERROR_REPORT,
                        payload={"original_id": message.id, "error": str(e)},
                    ))

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to topic with handler callback."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    async def request_reply(self, message: AgentMessage, timeout: float = 30.0) -> AgentMessage | None:
        """Send message and wait for reply (request-response pattern)."""
        reply_event = asyncio.Event()
        reply_holder: list[AgentMessage] = []

        async def reply_handler(msg: AgentMessage):
            if msg.reply_to == message.id:
                reply_holder.append(msg)
                reply_event.set()

        reply_topic = f"reply:{message.sender}"
        await self.subscribe(reply_topic, reply_handler)
        await self.publish(message)

        try:
            await asyncio.wait_for(reply_event.wait(), timeout=timeout)
            return reply_holder[0] if reply_holder else None
        except asyncio.TimeoutError:
            return None

    def get_message_log(self, topic: str | None = None, last_n: int = 50) -> list[AgentMessage]:
        """Get recent messages for debugging."""
        msgs = self._message_log
        if topic:
            msgs = [m for m in msgs if m.topic == topic]
        return msgs[-last_n:]

    async def get_stats(self) -> dict[str, Any]:
        return {
            "total_messages": len(self._message_log),
            "topics": list(self._subscribers.keys()),
            "subscriber_counts": {t: len(h) for t, h in self._subscribers.items()},
        }
