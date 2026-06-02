"""Tour builder: traces how a request flows through the codebase, from an entry
point down through the call graph, and narrates each step.

This answers the developer's "where do I even start reading?" question. Given an
entry point (auto-detected `main` / `app` / `create_app` / CLI handlers, or one
the user names), it walks outgoing CALLS edges breadth-first to produce an
ordered path — entry symbol, then what it calls, then what those call — and asks
the LLM to explain what each step does in one sentence.

The walk is deterministic and bounded (so it terminates on cyclic graphs and
never explodes); only the per-step narration uses the LLM, and that degrades to
the symbol's own signature/docstring when the LLM is unavailable.

Output (`tour`) is JSON-able:
    {
      "entry_point": "<qualified name>",
      "auto_detected": true|false,
      "steps": [
        {"order", "symbol", "kind", "signature", "file_path",
         "depth", "calls", "explanation"}
      ],
      "generated_by": "llm" | "structural"
    }
"""

from __future__ import annotations

import json
import re
from collections import deque

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView, GraphNode

logger = structlog.get_logger()

# Names that conventionally mark an application entry point. Matched against the
# simple (last-segment) name of function/method symbols.
_ENTRY_PATTERNS = [
    r"^main$", r"^create_app$", r"^create_application$", r"^run$",
    r"^app$", r"^cli$", r"^serve$", r"^start$", r"^bootstrap$", r"^handler$",
    r"^lifespan$",
]


def detect_entry_point(view: CodeGraphView) -> tuple[str | None, bool]:
    """Pick the most plausible entry symbol. Returns (qualified_name, auto).

    Preference order:
      1. A callable whose simple name matches a known entry convention,
         ranked by how many other symbols it (transitively) reaches.
      2. Otherwise the callable with the highest outgoing fan-out (the symbol
         that drives the most behavior), as a reasonable "top of the system".
    """
    callables = view.nodes_of_kind("function", "method")
    if not callables:
        return (None, False)

    def reach(name: str) -> int:
        return len(view.callees(name))

    candidates: list[GraphNode] = []
    for n in callables:
        simple = n.name.rsplit(".", 1)[-1]
        if any(re.search(p, simple) for p in _ENTRY_PATTERNS):
            candidates.append(n)
    if candidates:
        best = max(candidates, key=lambda n: reach(n.name))
        return (best.name, True)

    # No conventional entry — fall back to the biggest driver.
    best = max(callables, key=lambda n: reach(n.name))
    return (best.name, True) if reach(best.name) > 0 else (best.name, True)


def build_call_path(view: CodeGraphView, entry: str, max_steps: int = 12,
                    max_depth: int = 4) -> list[dict]:
    """BFS over outgoing CALLS from `entry`, bounded by step/depth budgets.

    Returns ordered step dicts (entry first). Visited tracking keeps cyclic call
    graphs finite. Each step records the immediate callees so the UI can draw the
    "this leads to…" links.
    """
    if view.get(entry) is None:
        return []

    steps: list[dict] = []
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(entry, 0)])

    while queue and len(steps) < max_steps:
        name, depth = queue.popleft()
        if name in seen or depth > max_depth:
            continue
        seen.add(name)

        node = view.get(name)
        if node is None:
            continue
        callees = [c for c in view.callees(name) if view.get(c) is not None]
        steps.append({
            "order": len(steps) + 1,
            "symbol": name,
            "kind": node.kind,
            "signature": node.signature,
            "file_path": node.file_path,
            "docstring": node.docstring,
            "depth": depth,
            "calls": callees[:8],
            "explanation": "",
        })
        for c in callees:
            if c not in seen:
                queue.append((c, depth + 1))

    return steps


_PROMPT = """你正在为开发者生成一段"代码导览"。下面是一个请求从入口出发,沿调用关系展开的有序步骤(已含每步的签名与它接着调用了谁)。请为**每一步**写一句简洁中文说明,讲清这一步在整个流程里干什么。

入口:{entry}

步骤:
{steps}

只输出 JSON:{{"explanations": ["第1步说明", "第2步说明", ...]}},数组长度必须等于步骤数,顺序一一对应。"""


async def _narrate_with_llm(entry: str, steps: list[dict]) -> list[str] | None:
    from evograph.config import settings
    if not settings.llm_api_key or not steps:
        return None
    from evograph.llm.client import llm_client

    steps_str = "\n".join(
        f"{s['order']}. {s['symbol']}  签名={s['signature'] or '(无)'}  "
        f"-> 调用: {', '.join(c.rsplit('.', 1)[-1] for c in s['calls']) or '(叶子)'}"
        for s in steps
    )
    try:
        raw = await llm_client.chat_json(
            messages=[{"role": "user", "content": _PROMPT.format(entry=entry, steps=steps_str)}],
        )
        data = json.loads(raw)
        explanations = data.get("explanations", [])
        if isinstance(explanations, list) and len(explanations) >= len(steps):
            return [str(e) for e in explanations[:len(steps)]]
        return None
    except Exception as exc:
        logger.warning("tour_llm_failed", error=str(exc))
        return None


def _structural_explanation(step: dict) -> str:
    """LLM-free narration: lean on the docstring, else describe the call shape."""
    doc = (step.get("docstring") or "").strip()
    if doc:
        return doc.split("\n")[0][:160]
    calls = step.get("calls") or []
    if calls:
        targets = ", ".join(c.rsplit(".", 1)[-1] for c in calls[:4])
        return f"{step['kind']} {step['symbol'].rsplit('.', 1)[-1]} —— 调用 {targets}。"
    return f"{step['kind']} {step['symbol'].rsplit('.', 1)[-1]} —— 调用链的叶子节点。"


async def build_tour(view: CodeGraphView, entry_point: str | None = None,
                     max_steps: int = 12) -> dict:
    """Public entry: build a narrated code tour for a graph view.

    Always returns a dict (never raises). `entry_point` may be a qualified name
    or a simple name (we resolve it); if omitted/unmatched we auto-detect.
    """
    if view.is_empty:
        return {"entry_point": None, "auto_detected": False, "steps": [],
                "generated_by": "empty"}

    resolved, auto = _resolve_entry(view, entry_point)
    if resolved is None:
        return {"entry_point": None, "auto_detected": False, "steps": [],
                "generated_by": "none"}

    steps = build_call_path(view, resolved, max_steps=max_steps)

    explanations = await _narrate_with_llm(resolved, steps)
    if explanations is not None:
        for s, text in zip(steps, explanations):
            s["explanation"] = text
        generated_by = "llm"
    else:
        for s in steps:
            s["explanation"] = _structural_explanation(s)
        generated_by = "structural"

    # Drop the bulky docstring from the wire payload — explanation captures it.
    for s in steps:
        s.pop("docstring", None)

    return {
        "entry_point": resolved,
        "auto_detected": auto,
        "steps": steps,
        "generated_by": generated_by,
    }


def _resolve_entry(view: CodeGraphView, entry_point: str | None) -> tuple[str | None, bool]:
    if entry_point:
        if view.get(entry_point) is not None:
            return (entry_point, False)
        # Try matching by simple name (user typed "main", not the full qname).
        matches = [n for n in view.nodes_of_kind("function", "method")
                   if n.name.rsplit(".", 1)[-1] == entry_point]
        if matches:
            best = max(matches, key=lambda n: len(view.callees(n.name)))
            return (best.name, False)
    return detect_entry_point(view)
