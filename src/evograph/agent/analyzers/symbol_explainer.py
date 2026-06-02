"""Symbol explainer: a plain-language, persona-tuned summary of one code symbol.

Answers the developer's "what does this thing actually do?" — and adapts the
answer to who's asking. A junior dev wants the mechanics spelled out; a PM wants
the business purpose with no jargon; a senior wants a terse architectural note.

The explanation is grounded in hard facts pulled from the graph (signature,
docstring, who calls it, what it calls, which layer it sits in) so the LLM
describes the real symbol rather than hallucinating. With no LLM available it
degrades to a structured summary built from those same facts.

Output (`explanation`) is JSON-able:
    {
      "symbol": "<qualified name>",
      "persona": "junior" | "pm" | "senior",
      "summary": "natural-language explanation tuned to the persona",
      "role": "<layer / role hint>",
      "generated_by": "llm" | "structural"
    }
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Persona -> how the LLM should pitch the explanation. Keys are stable; the UI
# sends one of these.
PERSONAS = {
    "junior": (
        "初级开发者:把它的职责、输入输出、和它怎么与上下游协作讲清楚,"
        "可以点出用到的编程概念,语言通俗但具体到机制。3-5 句。"
    ),
    "pm": (
        "产品经理/非工程背景:只讲它在业务上承担什么角色、对用户/产品意味着什么,"
        "不要出现函数签名、参数、技术术语。2-3 句。"
    ),
    "senior": (
        "资深工程师:一句到两句的高密度说明,点明它在架构中的位置、关键依赖与潜在风险,"
        "假设读者已熟悉代码库,省略基础解释。"
    ),
}
DEFAULT_PERSONA = "junior"


async def _gather_grounding(repo_id: str, symbol: str) -> dict | None:
    """Pull the symbol's node + immediate call neighborhood from Neo4j."""
    from evograph.graph.neo4j_client import neo4j_client

    node_rows = await neo4j_client.execute_query(
        """
        MATCH (e:Entity {repo_id: $repo_id})
        WHERE e.name = $symbol OR e.name ENDS WITH '.' + $symbol
        RETURN e.name AS name, e.code_kind AS kind, e.signature AS signature,
               e.file_path AS file_path, e.description AS description
        LIMIT 1
        """,
        {"repo_id": repo_id, "symbol": symbol},
    )
    if not node_rows:
        return None
    node = node_rows[0]
    full = node["name"]

    callers = await neo4j_client.execute_query(
        """
        MATCH (c:Entity {repo_id: $repo_id})-[r:RELATION {type: 'CALLS'}]->(t:Entity {name: $name})
        WHERE r.is_active = true
        RETURN c.name AS caller LIMIT 20
        """,
        {"repo_id": repo_id, "name": full},
    )
    callees = await neo4j_client.execute_query(
        """
        MATCH (s:Entity {name: $name})-[r:RELATION {type: 'CALLS'}]->(d:Entity {repo_id: $repo_id})
        WHERE r.is_active = true
        RETURN d.name AS callee LIMIT 20
        """,
        {"repo_id": repo_id, "name": full},
    )
    return {
        "node": node,
        "callers": [c["caller"] for c in callers],
        "callees": [c["callee"] for c in callees],
    }


def _layer_for(symbol: str, architecture: dict | None) -> str:
    if not architecture:
        return ""
    for layer in architecture.get("layers", []):
        for mod in layer.get("modules", []):
            if symbol == mod or symbol.startswith(mod + "."):
                return layer.get("name", "")
    return ""


_PROMPT = """你在向一位{persona_label}解释一段代码里的某个符号。请只依据下面提供的事实,不要编造。

符号: {symbol}
类型: {kind}
签名: {signature}
文档字符串: {docstring}
所属架构层: {layer}
调用它的(上游): {callers}
它调用的(下游): {callees}

讲解对象与风格要求: {persona_style}

只输出 JSON: {{"summary": "你的讲解"}}。"""


async def explain_symbol(
    repo_id: str, symbol: str, persona: str = DEFAULT_PERSONA,
    architecture: dict | None = None,
) -> dict | None:
    """Public entry. Returns an explanation dict, or None if the symbol is unknown.

    Never raises; on LLM failure it returns a structural fallback summary.
    """
    persona = persona if persona in PERSONAS else DEFAULT_PERSONA
    grounding = await _gather_grounding(repo_id, symbol)
    if grounding is None:
        return None

    node = grounding["node"]
    full = node["name"]
    layer = _layer_for(full, architecture)

    summary = await _summarize_with_llm(full, node, grounding, layer, persona)
    if summary is not None:
        return {"symbol": full, "persona": persona, "summary": summary,
                "role": layer, "generated_by": "llm"}

    return {
        "symbol": full, "persona": persona,
        "summary": _structural_summary(full, node, grounding, layer),
        "role": layer, "generated_by": "structural",
    }


async def _summarize_with_llm(full, node, grounding, layer, persona) -> str | None:
    from evograph.config import settings
    if not settings.llm_api_key:
        return None
    from evograph.llm.client import llm_client
    import json

    persona_labels = {"junior": "初级开发者", "pm": "产品经理", "senior": "资深工程师"}
    prompt = _PROMPT.format(
        persona_label=persona_labels.get(persona, "开发者"),
        symbol=full,
        kind=node.get("kind") or "?",
        signature=node.get("signature") or "(无)",
        docstring=(node.get("description") or "(无)")[:300],
        layer=layer or "(未分类)",
        callers=", ".join(c.rsplit(".", 1)[-1] for c in grounding["callers"][:12]) or "(无)",
        callees=", ".join(c.rsplit(".", 1)[-1] for c in grounding["callees"][:12]) or "(无)",
        persona_style=PERSONAS[persona],
    )
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": prompt}])
        data = json.loads(raw)
        s = data.get("summary")
        return str(s).strip() if s else None
    except Exception as exc:
        logger.warning("explain_symbol_llm_failed", symbol=full, error=str(exc))
        return None


def _structural_summary(full, node, grounding, layer) -> str:
    """LLM-free fallback: assemble facts into a readable sentence."""
    doc = (node.get("description") or "").strip().split("\n")[0]
    kind = node.get("kind") or "符号"
    name = full.rsplit(".", 1)[-1]
    parts = [f"{kind} `{name}`"]
    if layer:
        parts.append(f"属于{layer}")
    if doc:
        parts.append(f"—— {doc[:160]}")
    nc, ne = len(grounding["callers"]), len(grounding["callees"])
    if nc or ne:
        parts.append(f"(被 {nc} 处调用,自身调用 {ne} 个符号)")
    return "".join(parts) if len(parts) > 1 else f"{kind} `{name}`(暂无更多说明)。"
