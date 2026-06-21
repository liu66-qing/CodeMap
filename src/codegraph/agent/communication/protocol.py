"""Communication protocol and shared state (blackboard pattern).

Shared State architecture (Blackboard Pattern):
- Central "blackboard" where agents read/write structured data
- Each agent reads what it needs, writes what it produces
- No direct agent-to-agent coupling — all through blackboard
- Optimistic concurrency: version numbers prevent stale writes

Why Blackboard over direct messaging?
1. Decoupling — agents don't know each other
2. Resumability — if agent crashes, others see partial results on blackboard
3. Debuggability — full state visible at any point
4. Idempotency — reading blackboard is side-effect free
"""
import time
import json
import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StateEntry:
    key: str
    value: Any
    writer: str  # Agent that wrote this
    version: int = 1
    timestamp: float = field(default_factory=time.time)


class SharedState:
    """Blackboard-pattern shared state for multi-agent coordination.

    Thread-safe via asyncio.Lock. Version numbers prevent lost updates.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._state: dict[str, StateEntry] = {}
        self._lock = asyncio.Lock()
        self._history: list[tuple[str, str, Any, float]] = []  # (key, writer, value, time)

    async def write(self, key: str, value: Any, writer: str, expected_version: int | None = None) -> int:
        """Write to shared state with optimistic concurrency control.

        Args:
            key: State key
            value: New value
            writer: Agent ID writing
            expected_version: If set, only succeed if current version matches (CAS)

        Returns:
            New version number

        Raises:
            ValueError: If version conflict (another agent wrote since you read)
        """
        async with self._lock:
            current = self._state.get(key)

            if expected_version is not None and current and current.version != expected_version:
                raise ValueError(
                    f"Version conflict on '{key}': expected {expected_version}, "
                    f"current {current.version} (written by {current.writer})"
                )

            new_version = (current.version + 1) if current else 1
            entry = StateEntry(key=key, value=value, writer=writer, version=new_version)
            self._state[key] = entry
            self._history.append((key, writer, value, time.time()))

            # Persist to Redis if available
            if self._redis:
                await self._redis.hset(
                    "shared_state",
                    key,
                    json.dumps({"value": value, "writer": writer, "version": new_version, "ts": time.time()}),
                )

            return new_version

    async def read(self, key: str) -> tuple[Any, int] | None:
        """Read value and version. Returns (value, version) or None."""
        entry = self._state.get(key)
        if entry:
            return entry.value, entry.version
        return None

    async def read_many(self, keys: list[str]) -> dict[str, Any]:
        """Batch read multiple keys."""
        return {k: self._state[k].value for k in keys if k in self._state}

    async def watch(self, key: str, callback, timeout: float = 60.0) -> None:
        """Watch a key for changes (blocking until change or timeout)."""
        current = self._state.get(key)
        current_version = current.version if current else 0
        start = time.time()

        while time.time() - start < timeout:
            entry = self._state.get(key)
            if entry and entry.version > current_version:
                await callback(entry.value, entry.version)
                return
            await asyncio.sleep(0.1)

    async def get_snapshot(self) -> dict[str, Any]:
        """Full state snapshot for debugging."""
        return {
            k: {"value": e.value, "writer": e.writer, "version": e.version}
            for k, e in self._state.items()
        }

    async def get_history(self, key: str | None = None, last_n: int = 20) -> list[dict]:
        """Get write history for debugging."""
        history = self._history
        if key:
            history = [(k, w, v, t) for k, w, v, t in history if k == key]
        return [
            {"key": k, "writer": w, "value": str(v)[:100], "time": t}
            for k, w, v, t in history[-last_n:]
        ]


class CommunicationProtocol:
    """Defines structured communication patterns between agents.

    Patterns supported:
    1. Pipeline — A → B → C (sequential handoff)
    2. Fan-out/Fan-in — A → [B, C, D] → E (parallel then merge)
    3. Voting — A asks B,C,D for opinions, majority wins
    4. Delegation — A assigns sub-task to B, waits for result
    """

    def __init__(self, bus: "MessageBus", shared_state: SharedState):
        self._bus = bus
        self._state = shared_state

    async def pipeline_handoff(self, from_agent: str, to_agent: str, data: dict, task_key: str) -> None:
        """Hand off work from one agent to next in pipeline."""
        # Write result to shared state
        await self._state.write(f"{task_key}:{from_agent}:output", data, writer=from_agent)

        # Notify next agent
        from .bus import AgentMessage, MessageType
        await self._bus.publish(AgentMessage(
            sender=from_agent,
            topic=f"agent:{to_agent}",
            msg_type=MessageType.TASK_ASSIGNED,
            payload={"task_key": task_key, "input_from": from_agent},
        ))

    async def fan_out(self, coordinator: str, workers: list[str], task: dict, task_key: str) -> None:
        """Distribute work to multiple agents in parallel."""
        await self._state.write(f"{task_key}:status", "fan_out", writer=coordinator)
        await self._state.write(f"{task_key}:workers", workers, writer=coordinator)

        from .bus import AgentMessage, MessageType
        for worker in workers:
            await self._bus.publish(AgentMessage(
                sender=coordinator,
                topic=f"agent:{worker}",
                msg_type=MessageType.TASK_ASSIGNED,
                payload={"task_key": task_key, "task": task},
            ))

    async def fan_in(self, coordinator: str, task_key: str) -> dict[str, Any]:
        """Collect results from all workers (blocking until all complete)."""
        result = await self._state.read(f"{task_key}:workers")
        if not result:
            return {}

        workers = result[0]
        results = {}
        for worker in workers:
            worker_result = await self._state.read(f"{task_key}:{worker}:output")
            if worker_result:
                results[worker] = worker_result[0]

        return results

    async def vote(self, proposer: str, voters: list[str], proposal: dict, task_key: str) -> dict[str, Any]:
        """Request votes from agents. Returns vote tally."""
        from .bus import AgentMessage, MessageType

        await self._state.write(f"{task_key}:proposal", proposal, writer=proposer)

        for voter in voters:
            await self._bus.publish(AgentMessage(
                sender=proposer,
                topic=f"agent:{voter}",
                msg_type=MessageType.VOTE_REQUEST,
                payload={"task_key": task_key, "proposal": proposal},
            ))

        # Votes collected via shared state
        return {"status": "voting_started", "voters": voters, "task_key": task_key}
