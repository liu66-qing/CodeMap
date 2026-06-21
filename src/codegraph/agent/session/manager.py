"""Session management with lifecycle, persistence, and state machine.

Session lifecycle:
    CREATED -> ACTIVE -> (PAUSED <-> ACTIVE) -> COMPLETED
                  |
              EXPIRED (auto, after TTL)

Design decisions:
- Redis for session state -- survives server restarts, supports TTL natively
- Session state machine -- explicit transitions prevent invalid states
- Lazy loading -- session context loaded from Redis only when needed
- Session isolation -- each session has own memory, context, and tool state
- Fork support -- create child sessions for parallel exploration

Why not PostgreSQL? Sessions are ephemeral (hours-days), high write frequency,
natural TTL expiry. Redis fits perfectly. PostgreSQL for audit log only.
"""
import time
import uuid
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"


# Valid state transitions
VALID_TRANSITIONS = {
    SessionState.CREATED: {SessionState.ACTIVE},
    SessionState.ACTIVE: {SessionState.PAUSED, SessionState.COMPLETED, SessionState.EXPIRED},
    SessionState.PAUSED: {SessionState.ACTIVE, SessionState.EXPIRED},
    SessionState.COMPLETED: set(),  # Terminal
    SessionState.EXPIRED: set(),    # Terminal
}


@dataclass
class Session:
    id: str
    state: SessionState = SessionState.CREATED
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    user_id: str | None = None
    repo_url: str | None = None
    parent_session_id: str | None = None  # For forked sessions
    metadata: dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "user_id": self.user_id,
            "repo_url": self.repo_url,
            "parent_session_id": self.parent_session_id,
            "metadata": json.dumps(self.metadata),
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        metadata = data.get("metadata", "{}")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return cls(
            id=data["id"],
            state=SessionState(data.get("state", "created")),
            created_at=float(data.get("created_at", time.time())),
            last_active=float(data.get("last_active", time.time())),
            user_id=data.get("user_id"),
            repo_url=data.get("repo_url"),
            parent_session_id=data.get("parent_session_id"),
            metadata=metadata,
            message_count=int(data.get("message_count", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )


class SessionManager:
    """Manages session lifecycle with Redis persistence."""

    REDIS_PREFIX = "session:"
    DEFAULT_TTL = 86400 * 7  # 7 days

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local: dict[str, Session] = {}  # Fallback when Redis unavailable

    async def create(self, user_id: str | None = None, repo_url: str | None = None, parent_id: str | None = None) -> Session:
        """Create new session."""
        session = Session(
            id=f"sess_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            repo_url=repo_url,
            parent_session_id=parent_id,
        )
        await self._persist(session)
        return session

    async def get(self, session_id: str) -> Session | None:
        """Load session by ID."""
        if self._redis:
            data = await self._redis.hgetall(f"{self.REDIS_PREFIX}{session_id}")
            if data:
                return Session.from_dict(data)
        return self._local.get(session_id)

    async def transition(self, session_id: str, new_state: SessionState) -> bool:
        """Transition session state (validates against state machine)."""
        session = await self.get(session_id)
        if not session:
            return False

        if new_state not in VALID_TRANSITIONS.get(session.state, set()):
            raise ValueError(
                f"Invalid transition: {session.state.value} -> {new_state.value}. "
                f"Valid: {[s.value for s in VALID_TRANSITIONS[session.state]]}"
            )

        session.state = new_state
        session.last_active = time.time()
        await self._persist(session)
        return True

    async def touch(self, session_id: str) -> None:
        """Update last_active timestamp."""
        session = await self.get(session_id)
        if session:
            session.last_active = time.time()
            await self._persist(session)

    async def fork(self, session_id: str) -> Session:
        """Create child session inheriting parent context."""
        parent = await self.get(session_id)
        if not parent:
            raise ValueError(f"Session {session_id} not found")

        child = await self.create(
            user_id=parent.user_id,
            repo_url=parent.repo_url,
            parent_id=session_id,
        )
        child.metadata["forked_from"] = session_id
        child.metadata["fork_time"] = time.time()
        await self._persist(child)
        return child

    async def list_active(self, user_id: str | None = None) -> list[Session]:
        """List active sessions, optionally filtered by user."""
        sessions = []
        if self._redis:
            # Scan for session keys
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=f"{self.REDIS_PREFIX}*", count=100)
                for key in keys:
                    data = await self._redis.hgetall(key)
                    if data:
                        session = Session.from_dict(data)
                        if session.state in (SessionState.ACTIVE, SessionState.PAUSED):
                            if user_id is None or session.user_id == user_id:
                                sessions.append(session)
                if cursor == 0:
                    break
        else:
            sessions = [
                s for s in self._local.values()
                if s.state in (SessionState.ACTIVE, SessionState.PAUSED)
                and (user_id is None or s.user_id == user_id)
            ]

        return sorted(sessions, key=lambda s: s.last_active, reverse=True)

    async def cleanup_expired(self, max_age: float | None = None) -> int:
        """Expire sessions older than max_age. Returns count expired."""
        max_age = max_age or self.DEFAULT_TTL
        cutoff = time.time() - max_age
        expired = 0

        sessions = list(self._local.values()) if not self._redis else []
        for session in sessions:
            if session.last_active < cutoff and session.state not in (SessionState.COMPLETED, SessionState.EXPIRED):
                session.state = SessionState.EXPIRED
                await self._persist(session)
                expired += 1

        return expired

    async def _persist(self, session: Session) -> None:
        """Persist session to storage."""
        if self._redis:
            key = f"{self.REDIS_PREFIX}{session.id}"
            await self._redis.hset(key, mapping=session.to_dict())
            await self._redis.expire(key, self.DEFAULT_TTL)
        self._local[session.id] = session
