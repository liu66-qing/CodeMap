"""Architecture analyzer: turns a raw code graph into a human-readable picture of
the system's *shape* — its layers, recurring design patterns, and module
boundaries.

Strategy (deterministic features first, LLM for judgment):
    1. Compute cheap, reproducible signals per module: file grouping, fan-in /
       fan-out over CALLS edges, naming hints (controller/service/repo/model…),
       inheritance clusters.
    2. Hand those compact signals to the LLM, which assigns each module to a
       layer and names the patterns it recognizes. The LLM never sees raw source
       — only the distilled structure — so the prompt stays small and the output
       stays grounded.
    3. If the LLM is unavailable or returns garbage, fall back to a purely
       heuristic layering so the pipeline still produces a usable summary.

Output (`architecture_summary`) is a JSON-able dict:
    {
      "layers":     [{"name", "description", "modules": [...]}],
      "patterns":   [{"name", "evidence", "modules": [...]}],
      "boundaries": [{"module", "role", "fan_in", "fan_out", "files"}],
      "summary":    "one-paragraph natural-language overview",
      "generated_by": "llm" | "heuristic"
    }
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()

# Naming hints -> architectural role. Matched against the LAST dotted segment of
# a module's qualified name, case-insensitively. Deliberately broad; the LLM
# refines, this only seeds.
_ROLE_HINTS: list[tuple[str, str]] = [
    (r"controller|handler|route|endpoint|api|view|rest|http", "interface"),
    (r"service|usecase|use_case|application|manager|orchestrat", "service"),
    (r"repo|repository|dao|store|storage|persistence|db|database|model|entity|schema", "data"),
    (r"client|gateway|adapter|connector|provider|integration", "infrastructure"),
    (r"util|helper|common|shared|core|lib", "shared"),
    (r"task|worker|job|celery|queue", "background"),
]


def _module_of(qname: str, module_names: set[str]) -> str | None:
    """Longest module qname that prefixes `qname` (its enclosing module)."""
    best = None
    for m in module_names:
        if qname == m or qname.startswith(m + "."):
            if best is None or len(m) > len(best):
                best = m
    return best


def compute_module_features(view: CodeGraphView) -> list[dict]:
    """Per-module structural signals — pure, deterministic, LLM-free."""
    module_names = {n.name for n in view.nodes_of_kind("module")}
    # If the parser produced no explicit module nodes, synthesize from file paths.
    if not module_names:
        module_names = {n.file_path for n in view.nodes if n.file_path}

    symbols_in: dict[str, list[str]] = defaultdict(list)
    for n in view.nodes:
        owner = _module_of(n.name, module_names) or n.file_path
        if owner:
            symbols_in[owner].append(n.name)

    # Cross-module fan-in / fan-out over CALLS edges.
    fan_out: dict[str, int] = defaultdict(int)
    fan_in: dict[str, int] = defaultdict(int)
    for e in view.edges_of_type("CALLS"):
        sm = _module_of(e.source, module_names)
        tm = _module_of(e.target, module_names)
        if sm and tm and sm != tm:
            fan_out[sm] += 1
            fan_in[tm] += 1

    features: list[dict] = []
    for mod in sorted(module_names):
        last = mod.rsplit(".", 1)[-1].lower()
        role_hint = "unknown"
        for pattern, role in _ROLE_HINTS:
            if re.search(pattern, last):
                role_hint = role
                break
        files = sorted({view.file_of(s) for s in symbols_in.get(mod, []) if view.file_of(s)})
        features.append({
            "module": mod,
            "role_hint": role_hint,
            "fan_in": fan_in.get(mod, 0),
            "fan_out": fan_out.get(mod, 0),
            "symbol_count": len(symbols_in.get(mod, [])),
            "files": files[:5],
        })
    return features


def _inheritance_clusters(view: CodeGraphView) -> list[dict]:
    """Base class -> subclasses, a strong signal of a deliberate abstraction."""
    children: dict[str, list[str]] = defaultdict(list)
    for e in view.edges_of_type("INHERITS"):
        children[e.target].append(e.source)
    return [
        {"base": base, "subclasses": subs}
        for base, subs in children.items()
        if len(subs) >= 2
    ]


_LAYER_ORDER = ["interface", "service", "data", "infrastructure", "background", "shared", "unknown"]
_LAYER_LABELS = {
    "interface": "接口层 / Interface (controllers, API, handlers)",
    "service": "业务层 / Service (use-cases, orchestration)",
    "data": "数据层 / Data (repositories, models, persistence)",
    "infrastructure": "基础设施 / Infrastructure (clients, adapters, gateways)",
    "background": "后台任务 / Background (workers, queues, schedulers)",
    "shared": "公共层 / Shared (utils, common, core)",
    "unknown": "未分类 / Uncategorized",
}

_PROMPT = """你是一名资深软件架构师。下面是一个代码仓库的结构信号(已从代码图谱中提炼,不含源码)。

模块信号(module / 命名角色提示 role_hint / 跨模块被调用次数 fan_in / 跨模块调用次数 fan_out / 符号数 / 代表文件):
{modules}

继承簇(共享基类的类群,设计模式的强信号):
{inheritance}

请基于这些信号判断该系统的架构。要求:
1. layers: 把模块归入分层(接口层/业务层/数据层/基础设施/后台/公共等)。每层给 name、description、modules(模块全名数组)。
2. patterns: 识别设计模式(如分层架构、仓储模式、适配器、策略、工厂、发布订阅等)。每个给 name、evidence(为什么)、modules。
3. boundaries: 列出最关键的模块边界(高 fan_in 的核心模块、高 fan_out 的协调模块),每个给 module、role、reason。
4. summary: 一段中文自然语言总览(2-4 句),说明这个系统是做什么的、怎么组织的。

只输出 JSON,键为 layers, patterns, boundaries, summary。"""


async def _classify_with_llm(features: list[dict], inheritance: list[dict]) -> dict | None:
    """Ask the LLM to turn structural signals into a layered architecture.
    Returns None on any failure so the caller can fall back."""
    from evograph.config import settings
    if not settings.llm_api_key:
        return None
    from evograph.llm.client import llm_client

    # Keep the prompt compact: top modules by structural importance.
    ranked = sorted(features, key=lambda f: f["fan_in"] + f["fan_out"], reverse=True)[:40]
    modules_str = "\n".join(
        f"- {f['module']} | role_hint={f['role_hint']} | fan_in={f['fan_in']} "
        f"fan_out={f['fan_out']} | symbols={f['symbol_count']} | files={f['files']}"
        for f in ranked
    )
    inh_str = "\n".join(
        f"- {c['base']} <- {', '.join(c['subclasses'][:6])}" for c in inheritance[:15]
    ) or "(无)"

    try:
        raw = await llm_client.chat_json(
            messages=[{"role": "user", "content": _PROMPT.format(
                modules=modules_str, inheritance=inh_str
            )}],
        )
        data = json.loads(raw)
        if not isinstance(data, dict) or "layers" not in data:
            return None
        data.setdefault("patterns", [])
        data.setdefault("boundaries", [])
        data.setdefault("summary", "")
        return data
    except Exception as exc:  # network / JSON / API errors -> heuristic fallback
        logger.warning("architecture_llm_failed", error=str(exc))
        return None


def _heuristic_summary(features: list[dict], inheritance: list[dict]) -> dict:
    """LLM-free architecture summary from naming + fan-in/out alone."""
    by_role: dict[str, list[str]] = defaultdict(list)
    for f in features:
        by_role[f["role_hint"]].append(f["module"])

    layers = [
        {"name": _LAYER_LABELS[role], "description": _LAYER_LABELS[role],
         "modules": sorted(by_role[role])}
        for role in _LAYER_ORDER
        if by_role.get(role) and role != "unknown"
    ]
    if by_role.get("unknown"):
        layers.append({"name": _LAYER_LABELS["unknown"], "description": _LAYER_LABELS["unknown"],
                       "modules": sorted(by_role["unknown"])})

    patterns = []
    if any(f["role_hint"] == "interface" for f in features) and \
       any(f["role_hint"] == "data" for f in features):
        patterns.append({
            "name": "分层架构 / Layered architecture",
            "evidence": "命名上同时存在接口层与数据层模块,调用方向自上而下。",
            "modules": [],
        })
    for c in inheritance[:10]:
        patterns.append({
            "name": f"多态/策略族 (基类 {c['base'].rsplit('.', 1)[-1]})",
            "evidence": f"{len(c['subclasses'])} 个子类共享同一基类。",
            "modules": c["subclasses"][:6],
        })

    top = sorted(features, key=lambda f: f["fan_in"], reverse=True)[:8]
    boundaries = [
        {"module": f["module"], "role": f["role_hint"],
         "fan_in": f["fan_in"], "fan_out": f["fan_out"], "files": f["files"]}
        for f in top if f["fan_in"] or f["fan_out"]
    ]
    mod_count = len(features)
    summary = (
        f"该仓库包含约 {mod_count} 个模块,按命名与调用结构可粗分为 {len(layers)} 层。"
        f"核心被依赖模块为 {top[0]['module'] if top else '(无)'}。"
        "(启发式推断,未经 LLM 精化)"
    )
    return {"layers": layers, "patterns": patterns, "boundaries": boundaries, "summary": summary}


async def analyze_architecture(view: CodeGraphView) -> dict:
    """Public entry: produce an `architecture_summary` for a code graph view.

    Always returns a dict (never raises). Uses the LLM when configured, else a
    deterministic heuristic. `generated_by` records which path was taken.
    """
    if view.is_empty:
        return {"layers": [], "patterns": [], "boundaries": [], "summary": "(空图谱,无可分析结构)",
                "generated_by": "empty", "module_count": 0}

    features = compute_module_features(view)
    inheritance = _inheritance_clusters(view)

    llm_result = await _classify_with_llm(features, inheritance)
    if llm_result is not None:
        llm_result["generated_by"] = "llm"
        # Always attach the deterministic boundary metrics — they're ground truth.
        if not llm_result.get("boundaries"):
            top = sorted(features, key=lambda f: f["fan_in"], reverse=True)[:8]
            llm_result["boundaries"] = [
                {"module": f["module"], "role": f["role_hint"],
                 "fan_in": f["fan_in"], "fan_out": f["fan_out"], "files": f["files"]}
                for f in top if f["fan_in"] or f["fan_out"]
            ]
        llm_result["module_count"] = len(features)
        return llm_result

    result = _heuristic_summary(features, inheritance)
    result["generated_by"] = "heuristic"
    result["module_count"] = len(features)
    return result
