"""Learning Map API routes.

Endpoints:
  POST /api/v1/learning/events              — record a learning event
  GET  /api/v1/learning/progress/{user_id}  — get progress summary
  GET  /api/v1/learning/achievements/{user_id} — get badges
  GET  /api/v1/learning/path/{user_id}      — get recommended path
  GET  /api/v1/learning/stats/{user_id}     — overview stats for map page
  GET  /api/v1/learning/hint/{user_id}      — mentor hint (next action)
"""

from __future__ import annotations

from dataclasses import asdict

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from evograph.agent.learning.progress_tracker import progress_tracker
from evograph.agent.learning.achievement_engine import achievement_engine
from evograph.agent.learning.learning_path_planner import path_planner

logger = structlog.get_logger()

router = APIRouter()


class EventRequest(BaseModel):
    user_id: str = Field(default="default")
    task_id: str = Field(default="")
    repo_url: str = Field(default="")
    stage: str = Field(..., description="overview | mainflow | showcase | takeaway")
    type: str = Field(..., description="visit | complete | time_spent | highlight_read | pattern_copied")
    value: float = Field(default=0, description="e.g. seconds for time_spent")
    meta: dict = Field(default_factory=dict)


@router.post("/events")
async def record_event(body: EventRequest) -> dict:
    event = await progress_tracker.record_event(
        user_id=body.user_id,
        task_id=body.task_id,
        repo_url=body.repo_url,
        stage=body.stage,
        event_type=body.type,
        value=body.value,
        meta=body.meta,
    )
    return {"ok": True, "event": event}


@router.get("/progress/{user_id}")
async def get_progress(user_id: str, task_id: str | None = None) -> dict:
    return await progress_tracker.get_progress(user_id, task_id)


@router.get("/achievements/{user_id}")
async def get_achievements(user_id: str) -> dict:
    events = await progress_tracker.get_events(user_id)
    progress = await progress_tracker.get_progress(user_id)
    badges = achievement_engine.compute(events, progress)
    return {
        "user_id": user_id,
        "badges": [asdict(b) for b in badges],
        "unlocked_count": sum(1 for b in badges if b.unlocked),
        "total_count": len(badges),
    }


@router.get("/path/{user_id}")
async def get_path(user_id: str, level: str = "standard") -> dict:
    progress = await progress_tracker.get_progress(user_id)
    return path_planner.plan(level=level, progress=progress)


@router.get("/stats/{user_id}")
async def get_stats(user_id: str) -> dict:
    """Aggregate stats for the learning map page."""
    progress = await progress_tracker.get_progress(user_id)
    events = await progress_tracker.get_events(user_id)
    badges = achievement_engine.compute(events, progress)
    path = path_planner.plan(level="standard", progress=progress)

    return {
        "progress": progress,
        "badges": [asdict(b) for b in badges],
        "path": path,
    }


@router.get("/hint/{user_id}")
async def get_hint(user_id: str) -> dict:
    progress = await progress_tracker.get_progress(user_id)
    path = path_planner.plan(level="standard", progress=progress)
    return {
        "user_id": user_id,
        "hint": path["mentor_hint"],
        "next_action": path["next_action"],
        "overall_percent": progress["overall_percent"],
    }
