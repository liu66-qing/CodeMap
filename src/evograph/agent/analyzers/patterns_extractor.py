"""Patterns extractor: distills reusable design patterns from a codebase.

The final layer of understanding — not just "I read this project" but "I can
take something away and use it in my own work". Extracts transferable patterns
with minimal reproducible examples and applicability notes.
"""

from __future__ import annotations

import json

import structlog

logger = structlog.get_logger()


_PROMPT = """你是一位擅长提炼设计模式的架构师。下面是一个项目的设计亮点和模块机制。请从中提炼出**可迁移到其他项目**的通用设计模式。

设计亮点:
{highlights}

模块机制(精选):
{mechanisms}

请输出 JSON:
{{
  "patterns": [
    {{
      "name": "模式名称(通用的,不绑定具体业务)",
      "description": "这个模式解决什么通用问题(2-3句)",
      "example": "最小可复现的伪代码/精简代码(10-20行,展示核心思路,不依赖具体业务)",
      "applicability": "适合什么场景",
      "limitations": "不适合什么场景 / 使用时要注意什么",
      "source_modules": ["从哪个模块提炼出来的"]
    }}
  ]
}}
提炼 2-5 个模式,按通用性排序。只输出 JSON。"""


async def extract_patterns(highlights: dict, mechanisms: list[dict]) -> dict:
    """Public entry: extract transferable patterns. Never raises."""
    if not highlights.get("highlights") and not mechanisms:
        return {"patterns": [], "generated_by": "empty"}

    hl_brief = "\n".join(
        f"- {h.get('title','')}: {h.get('solution','')[:100]}"
        for h in highlights.get("highlights", [])[:6]
    ) or "(无亮点)"

    mech_brief = "\n".join(
        f"- {m.get('module','')}: {m.get('overview','')[:80]} | 连接: {(m.get('connections') or '')[:80]}"
        for m in mechanisms[:6]
    ) or "(无机制)"

    from evograph.config import settings
    if not settings.llm_api_key:
        return _structural_patterns(highlights, mechanisms)

    from evograph.llm.client import llm_client
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            highlights=hl_brief, mechanisms=mech_brief,
        )}])
        data = json.loads(raw)
        if not isinstance(data, dict) or "patterns" not in data:
            return _structural_patterns(highlights, mechanisms)
        data["generated_by"] = "llm"
        return data
    except Exception as exc:
        logger.warning("patterns_llm_failed", error=str(exc))
        return _structural_patterns(highlights, mechanisms)


def _structural_patterns(highlights: dict, mechanisms: list[dict]) -> dict:
    patterns = []
    for h in highlights.get("highlights", [])[:4]:
        patterns.append({
            "name": h.get("title", "未命名模式"),
            "description": h.get("solution", "")[:200],
            "example": "(需要 LLM 生成精简示例)",
            "applicability": h.get("problem", ""),
            "limitations": h.get("tradeoff", ""),
            "source_modules": h.get("modules", []),
        })
    return {"patterns": patterns, "generated_by": "structural"}
