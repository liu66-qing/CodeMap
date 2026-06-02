"""AnalysisOrchestrator — chains the 4 stage agents.

Stage flow:
  Overview (must run first)
    │
    ├─ MainFlow ┐ (parallel)
    └─ Showcase ┘
              │
              └─ Takeaway (depends on Showcase)

Failures in any stage do not abort the others; the failed stage's output is
replaced by an error stub so downstream stages can still run with whatever
context they have.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import structlog

from evograph.agent.stages import (
    OverviewAgent,
    MainFlowAgent,
    ShowcaseAgent,
    TakeawayAgent,
)
from evograph.agent.tools import STAGE_TOOLS

logger = structlog.get_logger()

ProgressCallback = Callable[[str, str], None] | None


class AnalysisOrchestrator:
    """Coordinates the 4 stage agents with explicit context handoff."""

    def __init__(
        self,
        tools: dict | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.tools = tools or STAGE_TOOLS
        self.llm_client = llm_client
        self.overview_agent = OverviewAgent(self.tools, self.llm_client)
        self.mainflow_agent = MainFlowAgent(self.tools, self.llm_client)
        self.showcase_agent = ShowcaseAgent(self.tools, self.llm_client)
        self.takeaway_agent = TakeawayAgent(self.tools, self.llm_client)

    async def analyze_repo(
        self,
        repo_url: str,
        on_progress: ProgressCallback = None,
    ) -> dict:
        """Run the full 4-stage analysis. Returns all stage outputs and traces."""
        results: dict[str, Any] = {}
        context: dict[str, Any] = {"repo_url": repo_url}

        # === Stage 1: Overview (must run first) ===
        _emit(on_progress, "overview", "running")
        overview = await self._safe_run(self.overview_agent, context, "overview")
        results["overview"] = overview
        if isinstance(overview, dict):
            context["architectureSummary"] = overview.get("architectureSummary", "")
            context["_signals"] = overview.get("_signals", {})
        _emit(on_progress, "overview", "done" if overview else "failed")

        # === Stage 2 & 3: MainFlow + Showcase in parallel ===
        _emit(on_progress, "mainflow", "running")
        _emit(on_progress, "showcase", "running")

        mainflow_task = asyncio.create_task(
            self._safe_run(self.mainflow_agent, dict(context), "mainflow")
        )
        showcase_task = asyncio.create_task(
            self._safe_run(self.showcase_agent, dict(context), "showcase")
        )

        mainflow, showcase = await asyncio.gather(mainflow_task, showcase_task)
        results["mainflow"] = mainflow
        results["showcase"] = showcase
        _emit(on_progress, "mainflow", "done" if mainflow else "failed")
        _emit(on_progress, "showcase", "done" if showcase else "failed")

        # Update context for takeaway
        if isinstance(mainflow, dict):
            context["flowNodes"] = mainflow.get("flowNodes", [])
        if isinstance(showcase, dict):
            context["highlights"] = showcase.get("highlights", [])

        # === Stage 4: Takeaway ===
        _emit(on_progress, "takeaway", "running")
        takeaway = await self._safe_run(self.takeaway_agent, context, "takeaway")
        results["takeaway"] = takeaway
        _emit(on_progress, "takeaway", "done" if takeaway else "failed")

        results["_traces"] = {
            "overview": self.overview_agent.trace.to_dict(),
            "mainflow": self.mainflow_agent.trace.to_dict(),
            "showcase": self.showcase_agent.trace.to_dict(),
            "takeaway": self.takeaway_agent.trace.to_dict(),
        }
        return results

    async def _safe_run(self, agent, context: dict, stage_name: str) -> dict:
        try:
            return await agent.run(context)
        except Exception as e:
            logger.error("stage_failed", stage=stage_name, error=str(e))
            return {"_error": f"{type(e).__name__}: {e}", "_stage": stage_name}


def _emit(cb: ProgressCallback, stage: str, status: str) -> None:
    if cb is None:
        return
    try:
        cb(stage, status)
    except Exception as e:
        logger.warning("progress_callback_failed", stage=stage, error=str(e))
