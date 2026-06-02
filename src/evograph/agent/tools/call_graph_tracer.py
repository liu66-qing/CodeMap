"""Call graph tracer — traces request flow from entry points through call relations.

Used by MainFlowAgent to build the "main flow" of a repo.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import structlog

from evograph.agent.tools.code_parser import parse_code_structure
from evograph.agent.tools.github_fetcher import fetch_repo_tree

logger = structlog.get_logger()


async def trace_call_graph(
    repo_url: str,
    entry_hint: list[str] | None = None,
    max_depth: int = 4,
    max_nodes: int = 30,
) -> dict[str, Any]:
    """Trace call graph from likely entry points.

    Args:
        repo_url: repo URL or local path
        entry_hint: optional list of entry-point file paths
        max_depth: max BFS depth
        max_nodes: max nodes to visit

    Returns: {
        "entry_points": [...],
        "call_chain": [...],
        "key_files": [...],
        "depth_visited": int
    }
    """
    tree = await fetch_repo_tree(repo_url)
    files = tree.get("files", [])

    # Pick code files
    code_files = [
        f for f in files
        if any(f.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java"))
    ]

    if not code_files:
        return {"entry_points": [], "call_chain": [], "key_files": [], "depth_visited": 0}

    # Parse all code
    parsed = await parse_code_structure(repo_url, code_files[:200])

    detected_entries = parsed.get("entry_points", [])
    entry_points = entry_hint or detected_entries
    if not entry_points and code_files:
        entry_points = code_files[:1]

    # Build adjacency: caller -> [callees]
    adj: dict[str, list[dict]] = defaultdict(list)
    for c in parsed.get("call_relations", []):
        adj[c["caller"]].append(c)

    # Map function -> file
    fn_to_file = {f["name"]: f["file"] for f in parsed.get("functions", [])}

    # BFS from entry points
    chain: list[dict] = []
    visited: set[str] = set()
    key_files: list[str] = []

    queue: deque = deque()
    for ep in entry_points:
        # Find functions in entry-point file
        for fn in parsed.get("functions", []):
            if fn["file"] == ep:
                queue.append((fn["name"], 0, ep))
                if ep not in key_files:
                    key_files.append(ep)
                break

    depth_visited = 0
    while queue and len(chain) < max_nodes:
        name, depth, file = queue.popleft()
        if name in visited or depth > max_depth:
            continue
        visited.add(name)
        depth_visited = max(depth_visited, depth)

        chain.append({"function": name, "file": file, "depth": depth})

        for call in adj.get(name, []):
            callee = call["callee"]
            if callee not in visited:
                callee_file = fn_to_file.get(callee, file)
                if callee_file not in key_files and len(key_files) < 20:
                    key_files.append(callee_file)
                queue.append((callee, depth + 1, callee_file))

    return {
        "entry_points": entry_points,
        "call_chain": chain,
        "key_files": key_files[:10],
        "depth_visited": depth_visited,
    }
