"""Progress tracker: records learning events and computes completion stats.

Events stored in Redis list (key: evograph:learning:{user_id}:events) with
dict fallback when Redis is unavailable.

Event schema:
  {ts, task_id, repo_url, stage, type, value, meta}

Completion model:
  - Each stage has weight (overview=15, mainflow=25, showcase=30, takeaway=30)
  - A stage is "complete" when user visits it + spends >= threshold_seconds
  - Overall progress = weighted sum of stage completions (0-100)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

from evograph.storage.redis_cache import redis_client

logger = structlog.get_logger()

_REDIS_PREFIX = "evograph:learning:"
_EVENT_TTL = 30 * 24 * 3600  # 30 days

STAGE_WEIGHTS = {
    "overview": 15,
    "mainflow": 25,
    "showcase": 30,
    "takeaway": 30,
}

STAGE_COMPLETION_THRESHOLD_SECONDS = {
    "overview": 30,
    "mainflow": 60,
    "showcase": 90,
    "takeaway": 60,
}


class ProgressTracker:
    def __init__(self) -> None:
        self._fallback: dict[str, list[dict]] = defaultdict(list)

    def _key(self, user_id: str) -> str:
        return f"{_REDIS_PREFIX}{user_id}:events"

    async def record_event(
        self,
        user_id: str,
        task_id: str,
        repo_url: str,
        stage: str,
        event_type: str,
        value: float = 0,
        meta: dict | None = None,
    ) -> dict:
        event = {
            "ts": time.time(),
            "task_id": task_id,
            "repo_url": repo_url,
            "stage": stage,
            "type": event_type,
            "value": value,
            "meta": meta or {},
        }
        try:
            import json
            client = await redis_client._get_client()
            await client.rpush(self._key(user_id), json.dumps(event, default=str))
            await client.expire(self._key(user_id), _EVENT_TTL)
        except Exception:
            self._fallback[user_id].append(event)
        return event

    async def get_events(self, user_id: str) -> list[dict]:
        try:
            import json
            client = await redis_client._get_client()
            raw_list = await client.lrange(self._key(user_id), 0, -1)
            return [json.loads(r) for r in raw_list]
        except Exception:
            return list(self._fallback.get(user_id, []))

    async def get_progress(self, user_id: str, task_id: str | None = None) -> dict:
        """Compute progress for a user (optionally scoped to a task_id)."""
        events = await self.get_events(user_id)
        if task_id:
            events = [e for e in events if e.get("task_id") == task_id]

        stage_stats: dict[str, dict] = {}
        for stage in STAGE_WEIGHTS:
            stage_events = [e for e in events if e.get("stage") == stage]
            visited = any(e["type"] == "visit" for e in stage_events)
            time_spent = sum(e["value"] for e in stage_events if e["type"] == "time_spent")
            highlights_read = sum(1 for e in stage_events if e["type"] == "highlight_read")
            patterns_copied = sum(1 for e in stage_events if e["type"] == "pattern_copied")
            threshold = STAGE_COMPLETION_THRESHOLD_SECONDS.get(stage, 60)
            complete = visited and time_spent >= threshold
            stage_stats[stage] = {
                "visited": visited,
                "time_spent_seconds": round(time_spent, 1),
                "highlights_read": highlights_read,
                "patterns_copied": patterns_copied,
                "complete": complete,
            }

        # Weighted overall progress
        total_progress = 0.0
        for stage, weight in STAGE_WEIGHTS.items():
            if stage_stats[stage]["complete"]:
                total_progress += weight
            elif stage_stats[stage]["visited"]:
                # Partial: time ratio capped at stage weight
                ratio = min(
                    1.0,
                    stage_stats[stage]["time_spent_seconds"]
                    / STAGE_COMPLETION_THRESHOLD_SECONDS.get(stage, 60),
                )
                total_progress += weight * ratio

        # Distinct repos analyzed
        repos = {e.get("repo_url") for e in events if e.get("repo_url")}
        total_events = len(events)

        return {
            "user_id": user_id,
            "task_id": task_id,
            "overall_percent": round(total_progress, 1),
            "stages": stage_stats,
            "total_events": total_events,
            "distinct_repos": len(repos),
            "total_time_seconds": round(
                sum(e["value"] for e in events if e["type"] == "time_spent"), 1
            ),
            "days_active": len(
                {int(e["ts"] // 86400) for e in events}
            ),
        }


progress_tracker = ProgressTracker()
