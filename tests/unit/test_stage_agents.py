"""Tests for the multi-stage agent layer.

Covers:
- BaseAgent: tool dispatch, trace recording, LLM JSON parsing, error capture
- Tool layer: pure-function tools on a synthetic local repo
- Stage agents: full analyze() with mock LLM
- Orchestrator: 4-stage pipeline + parallel + failure isolation + traces
- AnalysisStore: dict fallback when Redis unavailable
"""

from __future__ import annotations

import asyncio
import json
import os
import textwrap
from pathlib import Path

import pytest


# ---------- Fixtures ----------


@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    """Synthetic repo with a layered structure and a real call chain."""
    (tmp_path / "README.md").write_text(
        "# TinyApp\n\nA small layered demo.\n\n## Features\n- Plugin system\n- REST API\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api").mkdir()
    (tmp_path / "src" / "service").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        textwrap.dedent(
            """
            from .api.handler import handle
            def main():
                handle()
            if __name__ == '__main__':
                main()
            """
        ).strip()
    )
    (tmp_path / "src" / "api" / "__init__.py").write_text("")
    (tmp_path / "src" / "api" / "handler.py").write_text(
        textwrap.dedent(
            """
            from ..service.compute import process
            class HandlerFactory:
                def create(self):
                    return Handler()
            class Handler:
                def run(self):
                    return process(1, 2)
            def handle():
                return Handler().run()
            """
        ).strip()
    )
    (tmp_path / "src" / "service" / "__init__.py").write_text("")
    (tmp_path / "src" / "service" / "compute.py").write_text(
        textwrap.dedent(
            """
            def process(a, b):
                return a + b
            """
        ).strip()
    )
    return tmp_path


class MockLLM:
    """Stage-aware mock LLM. Returns valid JSON for each agent's schema."""

    _model = "mock-llm"

    async def chat_json(self, messages, temperature=0.0):
        sys_msg = messages[0]["content"].lower()
        if "mental model" in sys_msg or "positioning" in sys_msg:
            stage = "overview"
        elif "distill" in sys_msg or "reusable patterns" in sys_msg:
            stage = "takeaway"
        elif "execution flow" in sys_msg or "code-flow" in sys_msg:
            stage = "mainflow"
        else:
            stage = "showcase"
        return json.dumps(self._payload(stage))

    async def chat(self, messages, temperature=0.0):
        return await self.chat_json(messages, temperature)

    @staticmethod
    def _payload(stage: str) -> dict:
        if stage == "overview":
            return {
                "positioning": "TinyApp is a layered demo.",
                "coreProblem": "Show a clean layered architecture.",
                "mentalModel": {
                    "whatIsIt": {"title": "What", "description": "Demo"},
                    "whoIsItFor": {"title": "Who", "description": "Devs"},
                    "howItWorks": {"title": "How", "description": "API → service"},
                },
                "readingOrder": [
                    {
                        "step": 1,
                        "title": "src/main.py",
                        "description": "Entry",
                        "githubUrl": "",
                    }
                ],
                "architectureSummary": "Layered: api → service.",
            }
        if stage == "mainflow":
            return {
                "flowNodes": [
                    {
                        "id": 1,
                        "title": "main",
                        "note": "entry",
                        "detail": {
                            "explanation": "calls handle",
                            "whatToLook": "main.py",
                            "whyFirst": "entry",
                            "outcome": "kicks off",
                        },
                    },
                    {
                        "id": 2,
                        "title": "handle",
                        "note": "delegates",
                        "detail": {
                            "explanation": "Handler().run()",
                            "whatToLook": "handler.py",
                            "whyFirst": "core",
                            "outcome": "returns sum",
                        },
                    },
                ],
                "evidenceLinks": [{"label": "src/main.py", "githubUrl": ""}],
            }
        if stage == "showcase":
            return {
                "highlights": [
                    {
                        "title": "Factory pattern",
                        "problem": "Decouple creation",
                        "solution": "HandlerFactory",
                        "tradeoff": "extra indirection",
                        "evidence": {
                            "file": "src/api/handler.py",
                            "snippet": "class HandlerFactory",
                            "githubUrl": "",
                        },
                    }
                ]
            }
        return {
            "patterns": [
                {
                    "name": "Factory",
                    "scenario": "Object creation",
                    "coreIdea": "Encapsulate construction",
                    "minimalCode": {
                        "language": "python",
                        "code": "class F:\n    def create(self): return Obj()",
                    },
                    "limitations": "Adds a class",
                    "sourceHighlight": "Factory pattern",
                }
            ]
        }


# ---------- Tool layer ----------


@pytest.mark.asyncio
async def test_fetch_repo_tree_local(tiny_repo: Path):
    from evograph.agent.tools import fetch_repo_tree

    tree = await fetch_repo_tree(str(tiny_repo))
    files = tree["files"]
    assert any(f.endswith("main.py") for f in files)
    assert any(f.endswith("README.md") for f in files)
    assert "python" in tree["languages"]


@pytest.mark.asyncio
async def test_fetch_readme_local(tiny_repo: Path):
    from evograph.agent.tools import fetch_readme, summarize_readme

    readme = await fetch_readme(str(tiny_repo))
    assert "TinyApp" in readme["content"]
    summary = await summarize_readme(readme["content"])
    assert summary["title"].startswith("TinyApp")
    assert "Plugin system" in summary["features"]


@pytest.mark.asyncio
async def test_parse_code_structure(tiny_repo: Path):
    from evograph.agent.tools import parse_code_structure

    py_files = ["src/main.py", "src/api/handler.py", "src/service/compute.py"]
    parsed = await parse_code_structure(str(tiny_repo), py_files)
    fn_names = {f["name"] for f in parsed["functions"]}
    assert "main" in fn_names
    assert "process" in fn_names
    cls_names = {c["name"] for c in parsed["classes"]}
    assert "HandlerFactory" in cls_names
    assert "src/main.py" in parsed["entry_points"]


@pytest.mark.asyncio
async def test_detect_architecture(tiny_repo: Path):
    from evograph.agent.tools import (
        detect_architecture,
        fetch_repo_tree,
        parse_code_structure,
    )

    tree = await fetch_repo_tree(str(tiny_repo))
    parsed = await parse_code_structure(
        str(tiny_repo), [f for f in tree["files"] if f.endswith(".py")]
    )
    arch = await detect_architecture(
        tree["files"], tree["directories"], parsed["imports"]
    )
    layer_names = [l["name"] for l in arch["layers"]]
    assert "api" in layer_names
    assert "service" in layer_names


@pytest.mark.asyncio
async def test_pattern_matcher_factory(tiny_repo: Path):
    from evograph.agent.tools import match_patterns

    handler = (tiny_repo / "src" / "api" / "handler.py").read_text()
    out = await match_patterns(file_contents={"handler.py": handler})
    pattern_names = {p["name"] for p in out["patterns"]}
    assert "factory" in pattern_names


@pytest.mark.asyncio
async def test_call_graph_tracer(tiny_repo: Path):
    from evograph.agent.tools import trace_call_graph

    cg = await trace_call_graph(str(tiny_repo), max_depth=4, max_nodes=20)
    assert cg["entry_points"]
    # Chain should at least include the entry function.
    fn_names = {n["function"] for n in cg["call_chain"]}
    assert fn_names  # non-empty


# ---------- BaseAgent ----------


@pytest.mark.asyncio
async def test_base_agent_records_tool_call_trace():
    from evograph.agent.base import BaseAgent

    async def echo(value):
        return {"echoed": value}

    class Dummy(BaseAgent):
        async def analyze(self, context):
            r = await self.call_tool("echo", value=context["x"])
            return {"r": r}

    agent = Dummy("dummy", {"echo": echo}, llm_client=MockLLM())
    out = await agent.run({"x": 42})
    assert out == {"r": {"echoed": 42}}
    assert agent.trace.agent_name == "dummy"
    assert len(agent.trace.tool_calls) == 1
    assert agent.trace.tool_calls[0].tool_name == "echo"
    assert agent.trace.error is None
    assert agent.trace.finished_at >= agent.trace.started_at


@pytest.mark.asyncio
async def test_base_agent_records_tool_failure_and_reraises():
    from evograph.agent.base import BaseAgent

    async def boom():
        raise RuntimeError("nope")

    class Dummy(BaseAgent):
        async def analyze(self, context):
            await self.call_tool("boom")

    agent = Dummy("dummy", {"boom": boom}, llm_client=MockLLM())
    with pytest.raises(RuntimeError):
        await agent.run({})
    assert agent.trace.error and "RuntimeError" in agent.trace.error
    assert agent.trace.tool_calls[0].error and "nope" in agent.trace.tool_calls[0].error


@pytest.mark.asyncio
async def test_base_agent_call_llm_json_schema():
    from evograph.agent.base import BaseAgent

    class Dummy(BaseAgent):
        async def analyze(self, context):
            return await self.call_llm(
                prompt="hi",
                system="positioning mental model",  # routes mock to overview
                json_schema={"type": "object"},
            )

    agent = Dummy("dummy", {}, llm_client=MockLLM())
    out = await agent.run({})
    assert isinstance(out, dict)
    assert "positioning" in out
    assert agent.trace.llm_calls == 1
    assert agent.trace.total_tokens > 0


# ---------- Stage agents ----------


@pytest.mark.asyncio
async def test_overview_agent_against_tiny_repo(tiny_repo: Path):
    from evograph.agent.stages import OverviewAgent
    from evograph.agent.tools import STAGE_TOOLS

    agent = OverviewAgent(STAGE_TOOLS, llm_client=MockLLM())
    out = await agent.run({"repo_url": str(tiny_repo)})
    assert out["positioning"]
    assert out["mentalModel"]["whatIsIt"]
    assert out["readingOrder"]
    assert "_signals" in out
    # All required tools should have been called.
    tool_names = [t.tool_name for t in agent.trace.tool_calls]
    assert "fetch_repo_tree" in tool_names
    assert "fetch_readme" in tool_names
    assert any(n in tool_names for n in ("parse_code_structure", "code_parser"))
    assert any(n in tool_names for n in ("detect_architecture", "architecture_detector"))


@pytest.mark.asyncio
async def test_mainflow_agent_against_tiny_repo(tiny_repo: Path):
    from evograph.agent.stages import MainFlowAgent
    from evograph.agent.tools import STAGE_TOOLS

    agent = MainFlowAgent(STAGE_TOOLS, llm_client=MockLLM())
    out = await agent.run(
        {
            "repo_url": str(tiny_repo),
            "architectureSummary": "Layered",
            "_signals": {"entry_points": ["src/main.py"]},
        }
    )
    assert out["flowNodes"]
    assert out["evidenceLinks"]


@pytest.mark.asyncio
async def test_showcase_agent_against_tiny_repo(tiny_repo: Path):
    from evograph.agent.stages import ShowcaseAgent
    from evograph.agent.tools import STAGE_TOOLS

    agent = ShowcaseAgent(STAGE_TOOLS, llm_client=MockLLM())
    out = await agent.run(
        {"repo_url": str(tiny_repo), "architectureSummary": "Layered", "flowNodes": []}
    )
    assert out["highlights"]


@pytest.mark.asyncio
async def test_takeaway_agent_with_highlights():
    from evograph.agent.stages import TakeawayAgent
    from evograph.agent.tools import STAGE_TOOLS

    agent = TakeawayAgent(STAGE_TOOLS, llm_client=MockLLM())
    out = await agent.run(
        {
            "highlights": [
                {
                    "title": "Factory",
                    "problem": "p",
                    "solution": "s",
                    "tradeoff": "t",
                    "evidence": {"file": "x", "snippet": "y", "githubUrl": ""},
                }
            ]
        }
    )
    assert out["patterns"]


@pytest.mark.asyncio
async def test_takeaway_empty_highlights_returns_empty():
    from evograph.agent.stages import TakeawayAgent
    from evograph.agent.tools import STAGE_TOOLS

    agent = TakeawayAgent(STAGE_TOOLS, llm_client=MockLLM())
    out = await agent.run({"highlights": []})
    assert out == {"patterns": []}


# ---------- Orchestrator ----------


@pytest.mark.asyncio
async def test_orchestrator_full_pipeline(tiny_repo: Path):
    from evograph.agent.analysis_orchestrator import AnalysisOrchestrator

    orch = AnalysisOrchestrator(llm_client=MockLLM())
    progress: list = []
    result = await orch.analyze_repo(
        str(tiny_repo), on_progress=lambda s, st: progress.append((s, st))
    )

    # Each of the 4 stages emitted both running and done.
    stages = ("overview", "mainflow", "showcase", "takeaway")
    for s in stages:
        assert (s, "running") in progress
        assert (s, "done") in progress

    assert result["overview"]["positioning"]
    assert result["mainflow"]["flowNodes"]
    assert result["showcase"]["highlights"]
    assert result["takeaway"]["patterns"]

    traces = result["_traces"]
    for s in stages:
        t = traces[s]
        assert t["agent_name"] == s
        assert t["error"] is None
        assert t["duration_ms"] >= 0
        assert isinstance(t["tool_calls"], list)


@pytest.mark.asyncio
async def test_orchestrator_isolates_stage_failure(tiny_repo: Path):
    """A failing stage must not abort the others."""
    from evograph.agent.analysis_orchestrator import AnalysisOrchestrator
    from evograph.agent.stages import ShowcaseAgent

    class BoomShowcase(ShowcaseAgent):
        async def analyze(self, context):
            raise RuntimeError("explode")

    orch = AnalysisOrchestrator(llm_client=MockLLM())
    orch.showcase_agent = BoomShowcase(orch.tools, llm_client=MockLLM())

    result = await orch.analyze_repo(str(tiny_repo))
    assert result["overview"]["positioning"]
    assert result["mainflow"]["flowNodes"]
    # Showcase should be a stub with _error.
    assert "_error" in result["showcase"]
    # Takeaway runs on empty highlights → empty patterns; pipeline still completes.
    assert "patterns" in result["takeaway"]


# ---------- Store ----------


@pytest.mark.asyncio
async def test_analysis_store_falls_back_to_dict(monkeypatch):
    """When Redis is unreachable, store should silently fall back to the dict."""
    from evograph.agent.analysis_store import AnalysisStore
    from evograph.storage import redis_cache

    async def boom_get(key):
        raise RuntimeError("redis down")

    async def boom_set(key, value, ttl=0):
        raise RuntimeError("redis down")

    monkeypatch.setattr(redis_cache.redis_client, "get", boom_get)
    monkeypatch.setattr(redis_cache.redis_client, "set", boom_set)

    store = AnalysisStore()
    await store.set("abc", {"x": 1})
    got = await store.get("abc")
    assert got == {"x": 1}

    updated = await store.update("abc", x=2, y=3)
    assert updated == {"x": 2, "y": 3}
    again = await store.get("abc")
    assert again == {"x": 2, "y": 3}
