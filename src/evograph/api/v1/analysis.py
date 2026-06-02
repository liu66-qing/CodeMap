"""Multi-agent analysis API.

Endpoints:
  POST /api/v1/analysis/repos/analyze         — submit a repo for analysis
  GET  /api/v1/analysis/repos/{task_id}/status   — check progress
  GET  /api/v1/analysis/repos/{task_id}/overview — Stage 1 result
  GET  /api/v1/analysis/repos/{task_id}/mainflow — Stage 2 result
  GET  /api/v1/analysis/repos/{task_id}/showcase — Stage 3 result
  GET  /api/v1/analysis/repos/{task_id}/takeaway — Stage 4 result
  GET  /api/v1/analysis/repos/{task_id}/traces   — Agent execution traces
  GET  /api/v1/analysis/repos/{task_id}          — Full bundle (all stages)

Storage: Redis-backed via AnalysisStore (with in-process dict fallback).
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from evograph.agent.analysis_orchestrator import AnalysisOrchestrator
from evograph.agent.analysis_store import analysis_store

logger = structlog.get_logger()

router = APIRouter()


class AnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repo URL or local path")


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str = "running"


@router.post("/repos/analyze", response_model=AnalyzeResponse)
async def start_analysis(
    body: AnalyzeRequest, background_tasks: BackgroundTasks
) -> AnalyzeResponse:
    """Submit a repo for multi-agent analysis. Returns a task_id immediately."""
    task_id = uuid.uuid4().hex[:12]
    record = {
        "task_id": task_id,
        "repo_url": body.repo_url,
        "status": "running",
        "progress": {},
        "started_at": time.time(),
        "finished_at": None,
        "result": None,
        "error": None,
    }
    await analysis_store.set(task_id, record)

    async def _run() -> None:
        # Local progress accumulator; flushed to store after each stage.
        progress: dict[str, dict] = {}

        def on_progress(stage: str, status: str) -> None:
            progress[stage] = {"status": status, "ts": time.time()}
            # Fire-and-forget patch (do not await; FastAPI background tasks
            # do not love nested awaits in sync callbacks).
            # The final result write below will overwrite this anyway.

        try:
            orch = AnalysisOrchestrator()
            result = await orch.analyze_repo(body.repo_url, on_progress)
            await analysis_store.update(
                task_id,
                status="done",
                progress=progress,
                result=result,
                finished_at=time.time(),
            )
        except Exception as e:
            logger.error("analysis_failed", task_id=task_id, error=str(e))
            await analysis_store.update(
                task_id,
                status="failed",
                progress=progress,
                error=f"{type(e).__name__}: {e}",
                finished_at=time.time(),
            )

    background_tasks.add_task(_run)
    return AnalyzeResponse(task_id=task_id, status="running")


@router.get("/repos/{task_id}/status")
async def get_status(task_id: str) -> dict:
    record = await _require_record(task_id)
    return {
        "task_id": task_id,
        "status": record["status"],
        "progress": record.get("progress", {}),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "error": record.get("error"),
    }


@router.get("/repos/{task_id}")
async def get_full_result(task_id: str) -> dict:
    record = await _require_record(task_id)
    return {
        "task_id": task_id,
        "status": record["status"],
        "result": record.get("result") or {},
    }


@router.get("/repos/{task_id}/overview")
async def get_overview(task_id: str) -> dict:
    return await _stage(task_id, "overview")


@router.get("/repos/{task_id}/mainflow")
async def get_mainflow(task_id: str) -> dict:
    return await _stage(task_id, "mainflow")


@router.get("/repos/{task_id}/showcase")
async def get_showcase(task_id: str) -> dict:
    return await _stage(task_id, "showcase")


@router.get("/repos/{task_id}/takeaway")
async def get_takeaway(task_id: str) -> dict:
    return await _stage(task_id, "takeaway")


@router.get("/repos/{task_id}/traces")
async def get_traces(task_id: str) -> dict:
    record = await _require_record(task_id)
    result = record.get("result") or {}
    return {"task_id": task_id, "traces": result.get("_traces", {})}


# --- helpers ---


async def _require_record(task_id: str) -> dict:
    record = await analysis_store.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    return record


async def _stage(task_id: str, stage_name: str) -> dict:
    record = await _require_record(task_id)
    if record["status"] == "running":
        return {
            "task_id": task_id,
            "stage": stage_name,
            "status": "pending",
            "data": None,
        }
    if record["status"] == "failed":
        return {
            "task_id": task_id,
            "stage": stage_name,
            "status": "failed",
            "data": None,
            "error": record.get("error"),
        }
    result = record.get("result") or {}
    return {
        "task_id": task_id,
        "stage": stage_name,
        "status": "done",
        "data": result.get(stage_name) or {},
    }
