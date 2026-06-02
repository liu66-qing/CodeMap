"""Learning path builder: a recommended reading order for a new contributor.

"Where do I start, and what next?" — this produces an ordered curriculum over the
codebase's most important symbols, so a newcomer reads them in an order that
builds understanding instead of jumping around.

Ordering strategy (deterministic, then LLM rationale):
    1. Score each symbol by structural importance = fan-in (how many call it) +
       a bonus for being an entry point or a class/module hub.
    2. Walk the architecture layers TOP-DOWN (interface → service → data → …),
       and within each layer take the highest-scoring symbols. This mirrors how
       you'd actually onboard: see the entry surface, then the logic it drives,
       then the data it rests on.
    3. Ask the LLM for a one-line "why read this now" per step (optional; falls
       back to a structural reason).

Output (`learning_path`) is JSON-able:
    {
      "steps": [
        {"order", "symbol", "kind", "layer", "signature",
         "file_path", "importance", "reason"}
      ],
      "generated_by": "llm" | "structural"
    }
"""

from __future__ import annotations

import json

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()

# Layer reading order (top-down onboarding). Matches architecture_analyzer keys
# plus the free-text the LLM may emit; we canonicalize loosely.
_LAYER_ORDER = ["interface", "service", "data", "infrastructure", "background", "shared", "other"]


def _canonical_layer(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("接口", "interface", "controller", "api", "route", "handler", "endpoint", "http")):
        return "interface"
    if any(k in n for k in ("业务", "service", "use", "application", "orchestrat", "agent", "manager", "logic")):
        return "service"
    if any(k in n for k in ("数据", "data", "repository", "repo", "model", "schema", "persistence", "entity", "dao")):
        return "data"
    if any(k in n for k in ("基础设施", "infra", "client", "adapter", "gateway", "connector", "provider")):
        return "infrastructure"
    if any(k in n for k in ("后台", "background", "worker", "task", "job", "queue", "schedul")):
        return "background"
    if any(k in n for k in ("公共", "shared", "util", "common", "core", "lib", "helper", "config")):
        return "shared"
    return "other"


def _symbol_layer(symbol: str, module_layer: dict[str, str]) -> str:
    """Layer of a symbol via its longest enclosing-module prefix."""
    best, best_len = "other", -1
    for mod, layer in module_layer.items():
        if (symbol == mod or symbol.startswith(mod + ".")) and len(mod) > best_len:
            best, best_len = layer, len(mod)
    return best


def _module_layer_map(architecture: dict | None) -> dict[str, str]:
    m: dict[str, str] = {}
    if not architecture:
        return m
    for layer in architecture.get("layers", []):
        key = _canonical_layer(layer.get("name", ""))
        for mod in layer.get("modules", []):
            m[mod] = key
    return m


def build_learning_path(
    view: CodeGraphView, architecture: dict | None = None, max_steps: int = 10
) -> list[dict]:
    """Deterministic, layer-ordered list of the most important symbols to read.

    Picks callables and classes (skips bare modules), scores by fan-in + hubs,
    then emits them layer-by-layer top-down. Pure — no LLM, no DB."""
    if view.is_empty:
        return []

    module_layer = _module_layer_map(architecture)
    candidates = view.nodes_of_kind("function", "method", "class")

    def score(n) -> int:
        s = len(view.callers(n.name)) * 2 + len(view.callees(n.name))
        if n.kind == "class":
            s += 2
        simple = n.name.rsplit(".", 1)[-1]
        if simple in ("main", "create_app", "run", "app", "plan_trip", "handler"):
            s += 5
        return s

    scored = sorted(candidates, key=score, reverse=True)

    # Bucket by layer, preserving score order within each bucket.
    by_layer: dict[str, list] = {}
    for n in scored:
        layer = _symbol_layer(n.name, module_layer) if module_layer else _canonical_layer(n.name)
        by_layer.setdefault(layer, []).append(n)

    # Round: take the top symbol(s) from each layer in reading order until full.
    steps: list[dict] = []
    per_layer_quota = max(1, max_steps // max(1, len([l for l in _LAYER_ORDER if by_layer.get(l)])))
    for layer in _LAYER_ORDER:
        bucket = by_layer.get(layer, [])
        for n in bucket[: per_layer_quota + 1]:
            if len(steps) >= max_steps:
                break
            steps.append({
                "order": len(steps) + 1,
                "symbol": n.name,
                "kind": n.kind,
                "layer": layer,
                "signature": n.signature,
                "file_path": n.file_path,
                "docstring": (n.docstring or "")[:200],
                "importance": score(n),
                "reason": "",
            })
        if len(steps) >= max_steps:
            break

    # If layers were sparse, top up with the global highest scorers not yet added.
    if len(steps) < max_steps:
        chosen = {s["symbol"] for s in steps}
        for n in scored:
            if len(steps) >= max_steps:
                break
            if n.name in chosen:
                continue
            steps.append({
                "order": len(steps) + 1, "symbol": n.name, "kind": n.kind,
                "layer": _symbol_layer(n.name, module_layer) if module_layer else _canonical_layer(n.name),
                "signature": n.signature, "file_path": n.file_path,
                "docstring": (n.docstring or "")[:200],
                "importance": score(n), "reason": "",
            })
    return steps


_PROMPT = """你在为新加入项目的开发者设计一条"按依赖顺序阅读代码"的学习路径。下面是已按架构层(从接口层到底层)和重要度排好序的符号。请为**每一步**写一句中文说明:为什么现在读它、它能帮你理解什么。

步骤:
{steps}

只输出 JSON:{{"reasons": ["第1步理由", ...]}},数组长度等于步骤数,一一对应。"""


async def _annotate_with_llm(steps: list[dict]) -> list[str] | None:
    from evograph.config import settings
    if not settings.llm_api_key or not steps:
        return None
    from evograph.llm.client import llm_client

    steps_str = "\n".join(
        f"{s['order']}. [{s['layer']}] {s['symbol']}  {s['signature'] or ''}  "
        f"{('— ' + s['docstring']) if s['docstring'] else ''}"
        for s in steps
    )
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(steps=steps_str)}])
        data = json.loads(raw)
        reasons = data.get("reasons", [])
        if isinstance(reasons, list) and len(reasons) >= len(steps):
            return [str(r) for r in reasons[: len(steps)]]
        return None
    except Exception as exc:
        logger.warning("learning_path_llm_failed", error=str(exc))
        return None


def _structural_reason(step: dict) -> str:
    doc = (step.get("docstring") or "").strip().split("\n")[0]
    if doc:
        return doc[:140]
    layer_label = {
        "interface": "接口层入口,先看它了解系统对外暴露什么",
        "service": "业务逻辑核心,理解主要流程",
        "data": "数据结构/模型,理解系统操作的数据形态",
        "infrastructure": "外部依赖封装",
        "shared": "公共工具",
    }.get(step["layer"], "关键符号")
    return f"{layer_label}(被调用 {step['importance']} 权重)。"


async def build_learning_path_annotated(
    view: CodeGraphView, architecture: dict | None = None, max_steps: int = 10
) -> dict:
    """Public entry: ordered learning path + per-step rationale. Never raises."""
    steps = build_learning_path(view, architecture, max_steps=max_steps)
    if not steps:
        return {"steps": [], "generated_by": "empty"}

    reasons = await _annotate_with_llm(steps)
    if reasons is not None:
        for s, r in zip(steps, reasons):
            s["reason"] = r
        generated_by = "llm"
    else:
        for s in steps:
            s["reason"] = _structural_reason(s)
        generated_by = "structural"

    for s in steps:
        s.pop("docstring", None)
    return {"steps": steps, "generated_by": generated_by}
