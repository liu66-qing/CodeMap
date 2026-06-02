"""Module-card aggregation: collapse the symbol-level graph into a small set of
module CARDS, so the frontend can show a clean "system map" (à la a project
overview) instead of a hairball of hundreds of function nodes.

Each card is one logical module (a depth-bounded package prefix). It carries the
counts and a layer/complexity classification computed deterministically, plus a
one-line summary (batched LLM call, structural fallback). Edges between cards are
the aggregated, weighted CALLS/IMPORTS between their member symbols — so the map
reads as "this subsystem depends on that one", not "this function calls that".

Output (`module_map`) is JSON-able:
    {
      "cards": [
        {"id", "title", "module", "layer", "complexity",
         "symbol_count", "file_count", "kinds": {...},
         "files": [...], "symbols": [...], "summary"}
      ],
      "edges": [{"source", "target", "type", "weight"}],
      "generated_by": "llm" | "structural"
    }
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()

# How many dotted segments define a "module card". 2 keeps cards coarse enough to
# be a system map (e.g. app.api, app.services) rather than per-file.
_CARD_DEPTH = 2

_COMPLEXITY = [(0, "simple"), (15, "moderate"), (40, "complex")]


def _canonical_layer(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("接口", "interface", "controller", "api", "route", "handler", "endpoint", "http", "web")):
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


def _card_key(qname: str) -> str:
    """The module-card a symbol belongs to: its first _CARD_DEPTH dotted segments."""
    parts = qname.split(".")
    if len(parts) <= _CARD_DEPTH:
        # A short name: drop the trailing symbol segment if it looks like one.
        return ".".join(parts[:-1]) if len(parts) > 1 else qname
    return ".".join(parts[:_CARD_DEPTH])


def _complexity(symbol_count: int) -> str:
    label = "simple"
    for threshold, name in _COMPLEXITY:
        if symbol_count >= threshold:
            label = name
    return label


def _module_layer_map(architecture: dict | None) -> dict[str, str]:
    m: dict[str, str] = {}
    if not architecture:
        return m
    for layer in architecture.get("layers", []):
        key = _canonical_layer(layer.get("name", ""))
        for mod in layer.get("modules", []):
            m[mod] = key
    return m


def _layer_for(card_key: str, member_modules: set[str], module_layer: dict[str, str]) -> str:
    """Layer of a card: prefer an architecture assignment for the card or any of
    its member modules; else fall back to naming heuristics on the card key."""
    if card_key in module_layer:
        return module_layer[card_key]
    # Longest matching architecture module prefix among members.
    best, best_len = "", -1
    for mod, layer in module_layer.items():
        if (mod == card_key or mod.startswith(card_key + ".") or card_key.startswith(mod + ".")):
            if len(mod) > best_len:
                best, best_len = layer, len(mod)
    if best:
        return best
    return _canonical_layer(card_key)


def build_cards(view: CodeGraphView, architecture: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Deterministic part: cards + aggregated inter-card edges. Pure, no LLM."""
    module_layer = _module_layer_map(architecture)

    # Map every symbol to its card key.
    sym_card: dict[str, str] = {}
    members: dict[str, list] = defaultdict(list)
    for n in view.nodes:
        key = _card_key(n.name)
        sym_card[n.name] = key
        members[key].append(n)

    cards: list[dict] = []
    card_modules: dict[str, set] = defaultdict(set)
    for key, nodes in members.items():
        kinds: dict[str, int] = defaultdict(int)
        files: set[str] = set()
        symbols: list[dict] = []
        for n in nodes:
            kinds[n.kind] += 1
            if n.file_path:
                files.add(n.file_path)
            card_modules[key].add(_card_key(n.name))
            if n.kind != "module":
                symbols.append({"name": n.name, "kind": n.kind,
                                "signature": n.signature, "file_path": n.file_path})
        # Sort member symbols by fan-in so the most important show first.
        symbols.sort(key=lambda s: len(view.callers(s["name"])), reverse=True)
        non_module = sum(v for k, v in kinds.items() if k != "module")
        # "entities": the most important symbol simple-names (classes first, then
        # high-fan-in callables) — shown as small chips on the card, à la a
        # domain card's entity tags.
        entity_syms = sorted(
            [n for n in nodes if n.kind in ("class", "function", "method")],
            key=lambda n: (n.kind == "class", len(view.callers(n.name))),
            reverse=True,
        )
        entities = []
        for n in entity_syms:
            simple = n.name.rsplit(".", 1)[-1]
            if simple not in entities:
                entities.append(simple)
            if len(entities) >= 6:
                break
        cards.append({
            "id": key,
            "title": key.rsplit(".", 1)[-1] if "." in key else key,
            "module": key,
            "layer": _layer_for(key, card_modules[key], module_layer),
            "complexity": _complexity(non_module),
            "symbol_count": non_module,
            "file_count": len(files),
            "kinds": dict(kinds),
            "files": sorted(files)[:8],
            "entities": entities,
            "symbols": symbols[:40],
            "summary": "",
        })

    # Aggregate inter-card edges (CALLS + IMPORTS), skipping self-loops.
    weights: dict[tuple[str, str, str], int] = defaultdict(int)
    for e in view.edges:
        if e.type not in ("CALLS", "IMPORTS"):
            continue
        sc, tc = sym_card.get(e.source), sym_card.get(e.target)
        if not sc or not tc or sc == tc:
            continue
        weights[(sc, tc, e.type)] += 1
    edges = [
        {"source": s, "target": t, "type": ty, "weight": w}
        for (s, t, ty), w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Rank cards by importance (incoming edge weight + size) for stable ordering.
    incoming: dict[str, int] = defaultdict(int)
    for ed in edges:
        incoming[ed["target"]] += ed["weight"]
    # Drop empty shell cards (a bare package node with no own symbols AND no edges)
    # so the map shows real subsystems, not container packages.
    connected = {e["source"] for e in edges} | {e["target"] for e in edges}
    cards = [c for c in cards if c["symbol_count"] > 0 or c["id"] in connected]
    cards.sort(key=lambda c: (incoming[c["id"]] + c["symbol_count"]), reverse=True)
    return cards, edges


_PROMPT = """下面是一个代码仓库按模块聚合出的若干"卡片",每张卡片含模块名、所属架构层、文件数、主要符号。请为**每张卡片**写一句中文摘要,讲清这个模块在系统里承担什么职责(像项目总览里对子系统的一句话介绍)。

卡片:
{cards}

只输出 JSON:{{"summaries": {{"<模块名>": "一句话摘要", ...}}}},键必须是上面给出的模块名。"""


async def _summarize_with_llm(cards: list[dict]) -> dict[str, str] | None:
    from evograph.config import settings
    if not settings.llm_api_key or not cards:
        return None
    from evograph.llm.client import llm_client

    lines = []
    for c in cards[:30]:
        top_syms = ", ".join(s["name"].rsplit(".", 1)[-1] for s in c["symbols"][:6]) or "(无)"
        lines.append(
            f"- {c['module']} | 层={c['layer']} | 文件={c['file_count']} 符号={c['symbol_count']} | 主要符号: {top_syms}"
        )
    try:
        raw = await llm_client.chat_json(
            messages=[{"role": "user", "content": _PROMPT.format(cards="\n".join(lines))}]
        )
        data = json.loads(raw)
        summaries = data.get("summaries", {})
        return summaries if isinstance(summaries, dict) else None
    except Exception as exc:
        logger.warning("module_cards_llm_failed", error=str(exc))
        return None


def _structural_summary(card: dict) -> str:
    layer_label = {
        "interface": "对外接口层", "service": "业务逻辑", "data": "数据模型",
        "infrastructure": "基础设施/外部依赖", "background": "后台任务", "shared": "公共工具",
    }.get(card["layer"], "模块")
    kinds = card["kinds"]
    bits = []
    if kinds.get("class"):
        bits.append(f"{kinds['class']} 个类")
    if kinds.get("function") or kinds.get("method"):
        bits.append(f"{kinds.get('function',0)+kinds.get('method',0)} 个函数/方法")
    detail = "、".join(bits) or f"{card['symbol_count']} 个符号"
    return f"{layer_label}模块,含 {detail},分布在 {card['file_count']} 个文件。"


async def build_module_map(view: CodeGraphView, architecture: dict | None = None) -> dict:
    """Public entry: module cards + aggregated edges + per-card summaries + project
    meta (the stats the overview sidebar shows).

    Always returns a dict (never raises). Uses one batched LLM call for summaries
    when configured, else a structural fallback per card.
    """
    if view.is_empty:
        return {"cards": [], "edges": [], "meta": _empty_meta(), "generated_by": "empty"}

    cards, edges = build_cards(view, architecture)

    summaries = await _summarize_with_llm(cards)
    if summaries is not None:
        for c in cards:
            c["summary"] = summaries.get(c["module"]) or _structural_summary(c)
        generated_by = "llm"
    else:
        for c in cards:
            c["summary"] = _structural_summary(c)
        generated_by = "structural"

    return {"cards": cards, "edges": edges, "meta": _project_meta(view, cards, edges),
            "generated_by": generated_by}


def _empty_meta() -> dict:
    return {"nodes": 0, "edges": 0, "layers": 0, "cards": 0,
            "kinds": {}, "file_types": {}, "layer_counts": {}}


def _project_meta(view: CodeGraphView, cards: list[dict], edges: list[dict]) -> dict:
    """Overview stats: total nodes/edges, per-kind and per-file-extension counts,
    and how many cards sit in each layer."""
    kinds: dict[str, int] = defaultdict(int)
    for n in view.nodes:
        kinds[n.kind] += 1
    file_types: dict[str, int] = defaultdict(int)
    seen_files: set[str] = set()
    for n in view.nodes:
        if n.file_path and n.file_path not in seen_files:
            seen_files.add(n.file_path)
            ext = n.file_path.rsplit(".", 1)[-1].lower() if "." in n.file_path else "other"
            file_types[ext] += 1
    layer_counts: dict[str, int] = defaultdict(int)
    for c in cards:
        layer_counts[c["layer"]] += 1
    return {
        "nodes": len(view.nodes),
        "edges": len(view.edges),
        "cards": len(cards),
        "layers": len(layer_counts),
        "kinds": dict(kinds),
        "file_types": dict(sorted(file_types.items(), key=lambda kv: kv[1], reverse=True)[:10]),
        "layer_counts": dict(layer_counts),
    }
