"""Agent tool layer.

Each tool is a pure async function with structured input/output. Agents call them
via BaseAgent.call_tool(name, **kwargs) which records traces.

Two tool registries coexist:
- ToolRegistry (registry.py): legacy tools used by the older AgentOrchestrator/Engine
  for graph/vector retrieval and code-assistant queries.
- STAGE_TOOLS (this file): new tools used by the multi-stage analysis pipeline
  (OverviewAgent / MainFlowAgent / ShowcaseAgent / TakeawayAgent).
"""

from __future__ import annotations

from typing import Callable, Awaitable, Any

from evograph.agent.tools.github_fetcher import (
    fetch_repo_tree,
    fetch_file_content,
    fetch_readme,
)
from evograph.agent.tools.code_parser import parse_code_structure
from evograph.agent.tools.call_graph_tracer import trace_call_graph
from evograph.agent.tools.architecture_detector import detect_architecture
from evograph.agent.tools.readme_summarizer import summarize_readme
from evograph.agent.tools.dependency_resolver import resolve_dependencies
from evograph.agent.tools.pattern_matcher import match_patterns


STAGE_TOOLS: dict[str, Callable[..., Awaitable[Any]]] = {
    "fetch_repo_tree": fetch_repo_tree,
    "fetch_file_content": fetch_file_content,
    "fetch_readme": fetch_readme,
    "code_parser": parse_code_structure,
    "parse_code_structure": parse_code_structure,
    "call_graph_tracer": trace_call_graph,
    "trace_call_graph": trace_call_graph,
    "architecture_detector": detect_architecture,
    "detect_architecture": detect_architecture,
    "readme_summarizer": summarize_readme,
    "summarize_readme": summarize_readme,
    "dependency_resolver": resolve_dependencies,
    "resolve_dependencies": resolve_dependencies,
    "pattern_matcher": match_patterns,
    "match_patterns": match_patterns,
}


__all__ = [
    "STAGE_TOOLS",
    "fetch_repo_tree",
    "fetch_file_content",
    "fetch_readme",
    "parse_code_structure",
    "trace_call_graph",
    "detect_architecture",
    "summarize_readme",
    "resolve_dependencies",
    "match_patterns",
]
