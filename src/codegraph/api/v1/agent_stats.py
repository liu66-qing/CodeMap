"""Agent trace and tool statistics API endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Any

from codegraph.agent.tools.stats import tool_stats_collector

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/tools/stats")
async def get_tool_stats() -> dict[str, Any]:
    """Get execution statistics for all tools.

    Returns:
        - all_tools: dict of tool_name -> stats
        - top_tools: list of most frequently used tools
        - dependency_graph: tool dependency adjacency list
    """
    return {
        "all_tools": tool_stats_collector.get_all_stats(),
        "top_tools": tool_stats_collector.get_top_tools(limit=10),
        "dependency_graph": tool_stats_collector.get_dependency_graph(),
    }


@router.get("/tools/stats/{tool_name}")
async def get_tool_stat(tool_name: str) -> dict[str, Any]:
    """Get execution statistics for a specific tool."""
    stats = tool_stats_collector.get_tool_stats(tool_name)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return stats.to_dict()


@router.get("/agents/{agent_name}/tools")
async def get_agent_tool_usage(agent_name: str) -> dict[str, int]:
    """Get tool usage breakdown for a specific agent."""
    usage = tool_stats_collector.get_agent_tool_usage(agent_name)
    if not usage:
        raise HTTPException(
            status_code=404,
            detail=f"No tool usage found for agent '{agent_name}'"
        )
    return usage


@router.post("/tools/stats/reset")
async def reset_tool_stats() -> dict[str, str]:
    """Reset all tool statistics (admin only)."""
    tool_stats_collector.reset()
    return {"message": "Tool statistics reset successfully"}
