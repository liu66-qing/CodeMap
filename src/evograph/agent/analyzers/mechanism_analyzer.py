"""Mechanism analyzer: explains HOW a module works, by reading its real code.

This is the piece that closes the gap from "skeleton" to "flesh". The card map
and architecture views tell you a module *exists* and *what symbols it has*; this
agent reads the actual code bodies of a module's core symbols and asks the LLM to
synthesize a design narrative — division of labor, how the parts connect, how
state/context/memory flows. For a multi-agent module it answers "the coordinator
splits work into N sub-agents, passes context via X, persists memory in Y", which
no amount of call-graph structure alone can reveal.

Input grounding is REAL SOURCE, not signatures: we pull each core symbol's code
body via the source reader and put it in the prompt. Without source (no on-disk
clone) or without an LLM, it degrades to a signature/docstring-based summary.

Output (`mechanism`) is JSON-able:
    {
      "module": "...",
      "overview": "what this module is & does (paragraph)",
      "parts": [{"symbol", "role"}],          # division of labor
      "connections": "how the parts call/coordinate each other",
      "data_flow": "how data/context moves through it",
      "state_memory": "how state/memory/context is held & mutated (or null)",
      "grounded_in": ["symbol names whose code was read"],
      "generated_by": "llm" | "structural"
    }
"""

from __future__ import annotations

import json

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView
from evograph.ingestion.source_reader import get_repo_location, read_snippet_from_disk

logger = structlog.get_logger()

# How many core symbols' bodies to read into the prompt, and a per-symbol line cap
# so one giant function can't crowd out the rest (and the prompt stays fast).
MAX_CORE_SYMBOLS = 6
MAX_LINES_PER_SYMBOL = 45


def _module_members(view: CodeGraphView, module_id: str) -> list:
    """Symbols belonging to a module card (by qualified-name prefix), excluding
    bare module nodes, ranked by importance (fan-in, classes first)."""
    members = [
        n for n in view.nodes
        if n.kind != "module" and (n.name == module_id or n.name.startswith(module_id + "."))
    ]
    members.sort(key=lambda n: (n.kind == "class", len(view.callers(n.name))), reverse=True)
    return members


async def _gather_sources(repo_id: str, view: CodeGraphView, module_id: str) -> list[dict]:
    """Read the real code bodies of a module's core symbols."""
    loc = await get_repo_location(repo_id)
    if not loc:
        return []
    members = _module_members(view, module_id)[:MAX_CORE_SYMBOLS]
    out: list[dict] = []
    for n in members:
        if not n.file_path:
            continue
        ls = getattr(n, "line_start", 0) or 0
        le = getattr(n, "line_end", 0) or 0
        snip = read_snippet_from_disk(loc.local_path, n.file_path, ls or None, le or None)
        if not snip:
            continue
        code = "\n".join(snip.code.splitlines()[:MAX_LINES_PER_SYMBOL])
        out.append({"symbol": n.name, "kind": n.kind, "signature": n.signature, "code": code})
    return out


_PROMPT = """你在向一位想读懂这个模块的开发者解释它的**设计与机制**(不是罗列有哪些函数)。下面是该模块核心符号的**真实源码**。请基于源码,讲清这个模块到底怎么运作的。

模块:{module}

核心符号源码:
{sources}

请输出 JSON,字段:
- overview: 这个模块是什么、负责什么(2-4 句,中文)
- parts: 数组,每项 {{"symbol": 符号名, "role": 它在模块里承担的具体职责}}
- connections: 这些部分之间怎么协作/调用/传递控制(中文,讲清调用关系与协议)
- data_flow: 数据/参数/结果如何在模块内流动(中文)
- state_memory: 状态/上下文/记忆怎么保存与改写;如果该模块不涉及就填 null
只输出 JSON。"""


async def _analyze_with_llm(module_id: str, sources: list[dict]) -> dict | None:
    from evograph.config import settings
    if not settings.llm_api_key or not sources:
        return None
    from evograph.llm.client import llm_client

    blocks = []
    for s in sources:
        blocks.append(f"### {s['symbol']}  ({s['kind']})\n```\n{s['code']}\n```")
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            module=module_id, sources="\n\n".join(blocks),
        )}])
        data = json.loads(raw)
        if not isinstance(data, dict) or "overview" not in data:
            return None
        data.setdefault("parts", [])
        data.setdefault("connections", "")
        data.setdefault("data_flow", "")
        data.setdefault("state_memory", None)
        return data
    except Exception as exc:
        logger.warning("mechanism_llm_failed", module=module_id, error=str(exc))
        return None


def _structural_mechanism(view: CodeGraphView, module_id: str, sources: list[dict]) -> dict:
    """LLM-free fallback: lean on docstrings + signatures + call structure."""
    members = _module_members(view, module_id)[:MAX_CORE_SYMBOLS]
    parts = []
    for n in members:
        doc = (n.docstring or "").strip().split("\n")[0][:120]
        parts.append({"symbol": n.name, "role": doc or (n.signature or n.kind)})
    return {
        "overview": f"模块 {module_id} 含 {len(members)} 个核心符号(基于签名/文档推断,未读取源码精化)。",
        "parts": parts,
        "connections": "(无 LLM,未生成连接叙事)",
        "data_flow": "",
        "state_memory": None,
    }


async def analyze_mechanism(repo_id: str, view: CodeGraphView, module_id: str) -> dict:
    """Public entry: explain how `module_id` works, grounded in real source.
    Always returns a dict (never raises)."""
    sources = await _gather_sources(repo_id, view, module_id)

    llm = await _analyze_with_llm(module_id, sources)
    if llm is not None:
        llm["module"] = module_id
        llm["grounded_in"] = [s["symbol"] for s in sources]
        llm["generated_by"] = "llm"
        return llm

    result = _structural_mechanism(view, module_id, sources)
    result["module"] = module_id
    result["grounded_in"] = [s["symbol"] for s in sources]
    result["generated_by"] = "structural"
    return result
