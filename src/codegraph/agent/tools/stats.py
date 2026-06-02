"""Tool execution statistics and dependency tracking.

Enhances tool registry with:
- Call frequency and latency tracking
- Tool dependency graph (which tools call which tools)
- Reuse statistics across agents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict
import time

import structlog

logger = structlog.get_logger()


@dataclass
class ToolStats:
    """Execution statistics for a single tool."""

    tool_name: str
    call_count: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    dependencies: set[str] = field(default_factory=set)  # Tools this tool calls

    def record_call(self, duration_ms: float, success: bool = True):
        """Record a single tool execution."""
        self.call_count += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.call_count
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def add_dependency(self, tool_name: str):
        """Record that this tool depends on another tool."""
        self.dependencies.add(tool_name)

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "call_count": self.call_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float('inf') else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "error_rate": round(self.error_count / self.call_count, 3) if self.call_count > 0 else 0,
            "dependencies": list(self.dependencies),
        }


class ToolStatsCollector:
    """Global tool statistics collector."""

    def __init__(self):
        self._stats: dict[str, ToolStats] = defaultdict(lambda: ToolStats(tool_name=""))
        self._agent_tool_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        agent_name: str | None = None,
    ):
        """Record a tool execution."""
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolStats(tool_name=tool_name)

        self._stats[tool_name].record_call(duration_ms, success)

        if agent_name:
            self._agent_tool_usage[agent_name][tool_name] += 1

    def record_dependency(self, caller_tool: str, callee_tool: str):
        """Record that one tool calls another."""
        if caller_tool not in self._stats:
            self._stats[caller_tool] = ToolStats(tool_name=caller_tool)
        self._stats[caller_tool].add_dependency(callee_tool)

    def get_tool_stats(self, tool_name: str) -> ToolStats | None:
        """Get stats for a specific tool."""
        return self._stats.get(tool_name)

    def get_all_stats(self) -> dict[str, dict]:
        """Get all tool statistics."""
        return {name: stats.to_dict() for name, stats in self._stats.items()}

    def get_top_tools(self, limit: int = 10) -> list[dict]:
        """Get most frequently used tools."""
        sorted_tools = sorted(
            self._stats.values(),
            key=lambda s: s.call_count,
            reverse=True
        )
        return [tool.to_dict() for tool in sorted_tools[:limit]]

    def get_agent_tool_usage(self, agent_name: str) -> dict[str, int]:
        """Get tool usage breakdown for a specific agent."""
        return dict(self._agent_tool_usage.get(agent_name, {}))

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Get tool dependency graph as adjacency list."""
        return {
            name: list(stats.dependencies)
            for name, stats in self._stats.items()
            if stats.dependencies
        }

    def reset(self):
        """Reset all statistics."""
        self._stats.clear()
        self._agent_tool_usage.clear()


# Global collector instance
tool_stats_collector = ToolStatsCollector()
