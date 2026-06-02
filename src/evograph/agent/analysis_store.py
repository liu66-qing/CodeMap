"""Analysis task store: Redis-backed with in-process dict fallback.

Stores task records keyed by task_id. Each record:
  {
    "task_id": str,
    "repo_url": str,
    "status": "running" | "done" | "failed",
    "progress": {stage: {"status": str, "ts": float}},
    "started_at": float,
    "finished_at": float | None,
    "result": dict | None,
    "error": str | None,
  }

Redis is preferred for multi-worker deployments. Falls back to a process-local
dict if Redis is not reachable. The fallback is purely additive — once Redis
becomes available again, new writes go there; existing in-memory records are
not migrated.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from evograph.storage.redis_cache import redis_client

logger = structlog.get_logger()

_KEY_PREFIX = "evograph:analysis:"
_TTL_SECONDS = 7 * 24 * 3600  # 7 days


class AnalysisStore:
    """Hybrid Redis/dict store. Redis first, dict fallback on failure."""

    def __init__(self) -> None:
        self._fallback: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(task_id: str) -> str:
        return f"{_KEY_PREFIX}{task_id}"

    async def get(self, task_id: str) -> dict[str, Any] | None:
        try:
            raw = await redis_client.get(self._key(task_id))
            if raw is not None:
                return raw
        except Exception as e:
            logger.debug("analysis_store_redis_get_failed", error=str(e))
        return self._fallback.get(task_id)

    async def set(self, task_id: str, record: dict[str, Any]) -> None:
        try:
            await redis_client.set(self._key(task_id), record, ttl=_TTL_SECONDS)
            return
        except Exception as e:
            logger.debug("analysis_store_redis_set_failed", error=str(e))
        self._fallback[task_id] = record

    async def update(self, task_id: str, **patch: Any) -> dict[str, Any] | None:
        record = await self.get(task_id)
        if record is None:
            return None
        record.update(patch)
        await self.set(task_id, record)
        return record


analysis_store = AnalysisStore()
