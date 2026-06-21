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

from codegraph.agent.analysis_orchestrator import AnalysisOrchestrator
from codegraph.agent.analysis_store import analysis_store

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


@router.get("/repos/{task_id}/traces/debug")
async def get_debug_traces(task_id: str):
    """Enhanced trace view: real execution debugging data.

    Returns structured breakdown of every tool call, LLM invocation,
    timing, and failure recovery — the kind of data you'd look at
    when debugging why an agent produced a bad result.
    """
    record = await analysis_store.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.get("status") not in ("done", "failed"):
        raise HTTPException(status_code=409, detail="Analysis still running")

    traces = record.get("result", {}).get("_traces", {})

    debug_view = {
        "task_id": task_id,
        "summary": {
            "total_stages": len(traces),
            "total_tool_calls": sum(
                len(t.get("tool_calls", [])) for t in traces.values()
            ),
            "total_llm_calls": sum(
                t.get("llm_calls", 0) for t in traces.values()
            ),
            "total_tokens": sum(
                t.get("total_tokens", 0) for t in traces.values()
            ),
            "total_duration_ms": sum(
                (t.get("finished_at", 0) - t.get("started_at", 0)) * 1000
                for t in traces.values()
                if t.get("finished_at") and t.get("started_at")
            ),
        },
        "stages": {},
    }

    for stage_name, trace in traces.items():
        stage_debug = {
            "started_at": trace.get("started_at"),
            "finished_at": trace.get("finished_at"),
            "duration_ms": (
                (trace.get("finished_at", 0) - trace.get("started_at", 0)) * 1000
                if trace.get("finished_at") and trace.get("started_at")
                else None
            ),
            "status": "failed" if trace.get("error") else "success",
            "error": trace.get("error"),
            "tool_calls": [
                {
                    "tool": tc.get("tool_name"),
                    "args_preview": str(tc.get("args", {}))[:200],
                    "result_preview": str(tc.get("result", ""))[:300],
                    "duration_ms": tc.get("duration_ms", 0),
                    "error": tc.get("error"),
                    "success": tc.get("error") is None,
                }
                for tc in trace.get("tool_calls", [])
            ],
            "llm_calls": [
                {
                    "prompt_chars": lc.get("prompt_chars", 0),
                    "response_chars": lc.get("response_chars", 0),
                    "tokens_in": lc.get("tokens_in", 0),
                    "tokens_out": lc.get("tokens_out", 0),
                    "duration_ms": lc.get("duration_ms", 0),
                    "model": lc.get("model", "unknown"),
                }
                for lc in trace.get("llm_calls_detail", [])
            ],
            "token_breakdown": {
                "total": trace.get("total_tokens", 0),
                "by_tool": {},
            },
        }

        for tc in trace.get("tool_calls", []):
            tool_name = tc.get("tool_name", "unknown")
            stage_debug["token_breakdown"]["by_tool"][tool_name] = (
                stage_debug["token_breakdown"]["by_tool"].get(tool_name, 0)
                + tc.get("token_cost", 0)
            )

        debug_view["stages"][stage_name] = stage_debug

    if debug_view["stages"]:
        earliest = min(
            s.get("started_at", float("inf"))
            for s in debug_view["stages"].values()
            if s.get("started_at")
        )
        debug_view["waterfall"] = [
            {
                "stage": name,
                "offset_ms": (s.get("started_at", earliest) - earliest) * 1000,
                "duration_ms": s.get("duration_ms", 0),
                "status": s.get("status"),
            }
            for name, s in debug_view["stages"].items()
            if s.get("started_at")
        ]

    return debug_view


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
