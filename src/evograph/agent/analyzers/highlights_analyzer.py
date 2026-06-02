"""Highlights analyzer: identifies non-trivial design decisions in a codebase.

This is the core differentiator — most tools describe WHAT code does, but
developers want to know WHERE it's clever and WHY. This agent reads the
mechanism analyses and identifies design highlights: context management,
fault tolerance, abstraction boundaries, performance tradeoffs, extensibility.

Each highlight answers: what problem → how solved → why better than naive approach.
"""

from __future__ import annotations

import json

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()


_PROMPT = """你是一位资深架构评审员。下面是一个项目各模块的机制剖析(基于真实源码)。请识别其中**非平凡的设计决策**(不是"用了 FastAPI"这种显而易见的,而是作者做了什么聪明/有意思的设计选择)。

各模块机制:
{mechanisms}

架构概要:
{architecture}

请输出 JSON:
{{
  "highlights": [
    {{
      "title": "亮点标题(简短)",
      "category": "分类(context_management|fault_tolerance|abstraction|performance|extensibility|pattern|other)",
      "problem": "它解决了什么问题(一句话)",
      "solution": "它怎么解决的(2-3句,讲清设计思路)",
      "tradeoff": "为什么这个方案比朴素做法好?朴素做法会遇到什么问题?(2-3句)",
      "modules": ["涉及的模块"],
      "symbols": ["关键符号名"]
    }}
  ]
}}
识别 3-6 个亮点,按重要性排序。只输出 JSON。"""


async def analyze_highlights(
    view: CodeGraphView,
    architecture: dict | None,
    mechanisms: list[dict],
) -> dict:
    """Public entry: identify design highlights. Never raises."""
    if view.is_empty or not mechanisms:
        return {"highlights": [], "generated_by": "empty"}

    arch_brief = ""
    if architecture:
        arch_brief = architecture.get("summary", "") + "\n" + json.dumps(
            [{"name": l.get("name"), "modules": l.get("modules", [])[:6]}
             for l in architecture.get("layers", [])], ensure_ascii=False
        )

    mech_brief = "\n\n".join(
        f"### {m.get('module','?')}\n"
        f"概述: {m.get('overview','')[:150]}\n"
        f"分工: {json.dumps([p.get('role','')[:60] for p in m.get('parts',[])[:4]], ensure_ascii=False)}\n"
        f"连接: {(m.get('connections') or '')[:150]}\n"
        f"数据流: {(m.get('data_flow') or '')[:150]}\n"
        f"状态/记忆: {(m.get('state_memory') or '无')[:100]}"
        for m in mechanisms[:8]
    )

    from evograph.config import settings
    if not settings.llm_api_key:
        return _structural_highlights(view, mechanisms)

    from evograph.llm.client import llm_client
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            mechanisms=mech_brief, architecture=arch_brief,
        )}])
        data = json.loads(raw)
        if not isinstance(data, dict) or "highlights" not in data:
            return _structural_highlights(view, mechanisms)
        data["generated_by"] = "llm"
        return data
    except Exception as exc:
        logger.warning("highlights_llm_failed", error=str(exc))
        return _structural_highlights(view, mechanisms)


def _structural_highlights(view: CodeGraphView, mechanisms: list[dict]) -> dict:
    """Heuristic fallback: flag structurally interesting points."""
    highlights = []
    for m in mechanisms:
        if m.get("state_memory"):
            highlights.append({
                "title": f"{m['module']} 的状态管理",
                "category": "context_management",
                "problem": "需要在调用间保持状态",
                "solution": m["state_memory"][:200],
                "tradeoff": "(启发式检测,未经 LLM 精化)",
                "modules": [m["module"]],
                "symbols": [p["symbol"] for p in m.get("parts", [])[:3]],
            })
        parts = m.get("parts", [])
        if len(parts) >= 4:
            highlights.append({
                "title": f"{m['module']} 的职责分解",
                "category": "abstraction",
                "problem": f"模块含 {len(parts)} 个协作部件",
                "solution": m.get("connections", "")[:200] or m.get("overview", "")[:200],
                "tradeoff": "(启发式检测)",
                "modules": [m["module"]],
                "symbols": [p["symbol"] for p in parts[:4]],
            })
    return {"highlights": highlights[:6], "generated_by": "structural"}
