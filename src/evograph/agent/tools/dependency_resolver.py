"""Dependency resolver — builds a module dependency graph from import relations."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


async def resolve_dependencies(imports: list[dict]) -> dict[str, Any]:
    """Build module dependency graph.

    Args:
        imports: list of {"file": str, "from_module": str, "names": str}

    Returns: {
        "modules": [...],
        "edges": [...],  # {from, to, weight}
        "fan_in": {module: int},
        "fan_out": {module: int},
        "central_modules": [...],
        "leaf_modules": [...]
    }
    """
    edges: dict[tuple[str, str], int] = Counter()
    modules: set[str] = set()

    for imp in imports:
        src = _module_of(imp.get("file", ""))
        tgt = imp.get("from_module", "")
        if not src or not tgt or tgt.startswith("."):
            continue
        tgt_mod = tgt.split(".")[0]
        if src == tgt_mod:
            continue
        edges[(src, tgt_mod)] += 1
        modules.add(src)
        modules.add(tgt_mod)

    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    edge_list = []
    for (src, tgt), weight in edges.items():
        edge_list.append({"from": src, "to": tgt, "weight": weight})
        fan_out[src] += weight
        fan_in[tgt] += weight

    centrality = {m: fan_in[m] + fan_out[m] for m in modules}
    central_modules = sorted(centrality.items(), key=lambda x: -x[1])[:5]
    leaf_modules = [m for m in modules if fan_out.get(m, 0) <= 1 and fan_in.get(m, 0) > 0]

    return {
        "modules": sorted(modules),
        "edges": edge_list,
        "fan_in": dict(fan_in),
        "fan_out": dict(fan_out),
        "central_modules": [{"name": m, "centrality": c} for m, c in central_modules],
        "leaf_modules": leaf_modules[:10],
    }


def _module_of(file_path: str) -> str:
    parts = file_path.replace("\\", "/").split("/")
    if not parts:
        return ""
    if parts[0] == "src" and len(parts) > 1:
        return parts[1]
    return parts[0]
