"""Panorama analyzer: synthesizes a high-level "how it works" view of a codebase.

After the user knows WHAT the project is (Orient/定向), they want to understand
HOW it operates at a conceptual level — not code-level call chains, but a
"task journey map" showing what happens from input to output.

Produces:
- capabilities: user-facing feature list (what can this project DO)
- journey: conceptual data-flow stages (input → stage1 → stage2 → output)
- collaboration: how modules/agents coordinate (who calls whom, message format)
- abstractions: the core types/interfaces the author defined and their relationships

Grounded in: architecture summary + module mechanisms + module card summaries.
"""

from __future__ import annotations

import json

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()


_PROMPT = """你正在为一位想理解"这个系统怎么运转"的开发者写全景概述。下面是该项目的架构分析和各模块的机制剖析。请综合这些信息,输出一份概念级的全景图。

项目架构:
{architecture}

各模块机制:
{mechanisms}

模块依赖关系:
{edges}

请输出 JSON,字段:
- capabilities: 数组,每项 {{"name": "能力名(用户视角)", "description": "一句话描述这个能力做什么"}}。列出该项目对外提供的 3-8 个核心能力。
- journey: 数组,每项 {{"stage": "阶段名", "description": "这个阶段做什么", "modules": ["涉及的模块"]}}。描述一个典型任务从输入到输出经过的概念阶段(不是代码调用链,是业务流程)。
- collaboration: 字符串,用 2-4 句中文描述模块/agent 之间的协作模式(谁是调度者、谁是执行者、信息怎么传递)。
- abstractions: 数组,每项 {{"name": "核心类型/接口名", "purpose": "它代表什么概念", "relationships": "它跟其他抽象的关系"}}。列出作者定义的 3-6 个最重要的抽象。
只输出 JSON。"""


async def analyze_panorama(
    view: CodeGraphView,
    architecture: dict | None,
    mechanisms: list[dict],
    module_edges: list[dict],
) -> dict:
    """Public entry: produce a panorama overview. Never raises."""
    if view.is_empty:
        return _empty()

    arch_brief = ""
    if architecture:
        arch_brief = json.dumps({
            "summary": architecture.get("summary", ""),
            "layers": [{"name": l.get("name"), "modules": l.get("modules", [])[:8]}
                       for l in architecture.get("layers", [])],
        }, ensure_ascii=False)

    mech_brief = "\n".join(
        f"- {m.get('module','?')}: {m.get('overview','')[:120]}"
        for m in mechanisms[:10]
    ) or "(无机制分析)"

    edges_brief = "\n".join(
        f"  {e.get('source','')} -[{e.get('type','')} x{e.get('weight',1)}]-> {e.get('target','')}"
        for e in module_edges[:15]
    ) or "(无)"

    from evograph.config import settings
    if not settings.llm_api_key:
        return _structural_panorama(architecture, mechanisms, module_edges)

    from evograph.llm.client import llm_client
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            architecture=arch_brief, mechanisms=mech_brief, edges=edges_brief,
        )}])
        data = json.loads(raw)
        if not isinstance(data, dict) or "capabilities" not in data:
            return _structural_panorama(architecture, mechanisms, module_edges)
        data.setdefault("journey", [])
        data.setdefault("collaboration", "")
        data.setdefault("abstractions", [])
        data["generated_by"] = "llm"
        return data
    except Exception as exc:
        logger.warning("panorama_llm_failed", error=str(exc))
        return _structural_panorama(architecture, mechanisms, module_edges)


def _structural_panorama(architecture: dict | None, mechanisms: list[dict], edges: list[dict]) -> dict:
    capabilities = []
    if mechanisms:
        for m in mechanisms[:6]:
            capabilities.append({"name": m.get("module", "?").split(".")[-1],
                                 "description": (m.get("overview") or "")[:100]})
    journey = []
    if architecture:
        for layer in architecture.get("layers", []):
            journey.append({"stage": layer.get("name", ""),
                            "description": f"包含 {len(layer.get('modules',[]))} 个模块",
                            "modules": layer.get("modules", [])[:5]})
    collaboration = "模块间通过函数调用协作。" + (
        f"共 {len(edges)} 条跨模块依赖。" if edges else ""
    )
    return {
        "capabilities": capabilities,
        "journey": journey,
        "collaboration": collaboration,
        "abstractions": [],
        "generated_by": "structural",
    }


def _empty() -> dict:
    return {"capabilities": [], "journey": [], "collaboration": "", "abstractions": [],
            "generated_by": "empty"}
