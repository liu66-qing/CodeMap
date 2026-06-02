"""Ask-codebase: answer a natural-language question about a repo, grounded in
real source code + graph structure, with traceable citations.

This closes the loop from "I have a specific question" to "here's the answer,
and here's exactly where in the code it comes from". The flow:

    1. Semantic retrieval: use the question to find relevant symbols (by name
       match, docstring/signature similarity, and graph neighborhood).
    2. Source grounding: read the real code bodies of the top-K relevant symbols.
    3. LLM synthesis: answer the question using ONLY the provided code as evidence,
       citing which symbols support each claim.
    4. Return: answer + sources (each with symbol, file_path, line range).

Without an LLM, returns the retrieved symbols + their code snippets (still useful
as a "find relevant code" tool). Without source (no on-disk clone), falls back to
signature/docstring-based retrieval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView
from evograph.ingestion.source_reader import get_repo_location, read_snippet_from_disk

logger = structlog.get_logger()

MAX_SOURCES = 6
MAX_LINES_PER_SOURCE = 50


@dataclass
class SourceCitation:
    symbol: str
    file_path: str
    line_start: int
    line_end: int
    snippet: str  # first few lines for display


async def _retrieve_relevant_symbols(
    view: CodeGraphView, question: str, top_k: int = MAX_SOURCES
) -> list:
    """Find symbols whose names/signatures/docstrings are most relevant to the
    question. Simple keyword overlap for now; can be upgraded to embedding search."""
    q_lower = question.lower()
    keywords = [w for w in q_lower.replace("?", " ").replace("？", " ").split() if len(w) > 1]

    scored: list[tuple[float, any]] = []
    for n in view.nodes:
        if n.kind == "module":
            continue
        score = 0.0
        text = f"{n.name} {n.signature} {n.docstring}".lower()
        for kw in keywords:
            if kw in text:
                score += 1.0
            if kw in n.name.lower():
                score += 2.0  # name match is stronger
        # Boost high-fan-in symbols (they're more likely to be architecturally relevant).
        score += min(len(view.callers(n.name)) * 0.3, 2.0)
        if score > 0:
            scored.append((score, n))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]


async def _gather_code_bodies(
    repo_id: str, symbols: list, local_path: str
) -> list[dict]:
    """Read the real code bodies of the retrieved symbols."""
    results: list[dict] = []
    for n in symbols:
        if not n.file_path or not n.line_start:
            continue
        snip = read_snippet_from_disk(local_path, n.file_path, n.line_start, n.line_end)
        if not snip:
            continue
        code = "\n".join(snip.code.splitlines()[:MAX_LINES_PER_SOURCE])
        results.append({
            "symbol": n.name,
            "kind": n.kind,
            "file_path": n.file_path,
            "line_start": snip.line_start,
            "line_end": snip.line_end,
            "code": code,
        })
    return results


_PROMPT = """你是一个代码库问答助手。用户问了一个关于代码库的问题,下面是从代码库中检索到的相关源码片段。请**仅基于这些源码**回答问题,并在回答中标注每个论断来自哪个符号。

用户问题:{question}

检索到的源码:
{sources}

请输出 JSON:
{{
  "answer": "你的回答(中文,2-6 句,讲清机制)",
  "sources": [
    {{"symbol": "引用的符号全名", "relevance": "这个符号为什么相关(一句话)"}}
  ]
}}
只输出 JSON。如果源码不足以回答,在 answer 中说明并建议用户查看哪些模块。"""


async def ask_codebase(repo_id: str, view: CodeGraphView, question: str) -> dict:
    """Public entry: answer a question about a codebase, grounded in real source.

    Returns:
        {
          "answer": str,
          "sources": [{symbol, file_path, line_start, line_end, snippet}],
          "generated_by": "llm" | "retrieval_only"
        }
    """
    if view.is_empty:
        return {"answer": "图谱为空,无法回答。", "sources": [], "generated_by": "empty"}

    # 1. Retrieve relevant symbols.
    symbols = await _retrieve_relevant_symbols(view, question)
    if not symbols:
        return {"answer": "未找到与问题相关的代码符号。", "sources": [], "generated_by": "retrieval_only"}

    # 2. Read their code bodies.
    loc = await get_repo_location(repo_id)
    if loc:
        code_bodies = await _gather_code_bodies(repo_id, symbols, loc.local_path)
    else:
        code_bodies = []

    # Build citation list (always returned, even without LLM).
    citations = [
        {
            "symbol": cb["symbol"],
            "file_path": cb["file_path"],
            "line_start": cb["line_start"],
            "line_end": cb["line_end"],
            "snippet": "\n".join(cb["code"].splitlines()[:5]),
        }
        for cb in code_bodies
    ]

    # 3. LLM synthesis.
    from evograph.config import settings
    if not settings.llm_api_key or not code_bodies:
        # No LLM or no source: return the retrieved symbols as-is.
        fallback_answer = (
            f"找到 {len(symbols)} 个相关符号"
            + (f"(含 {len(code_bodies)} 个源码片段)" if code_bodies else "")
            + "。以下是检索结果,请查看源码了解详情。"
        )
        return {"answer": fallback_answer, "sources": citations, "generated_by": "retrieval_only"}

    from evograph.llm.client import llm_client
    blocks = []
    for cb in code_bodies:
        blocks.append(f"### {cb['symbol']}  ({cb['kind']}, {cb['file_path']}:{cb['line_start']})\n```\n{cb['code']}\n```")

    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            question=question, sources="\n\n".join(blocks),
        )}])
        data = json.loads(raw)
        answer = data.get("answer", "")
        # Merge LLM's source annotations with our precise citations.
        llm_sources = data.get("sources", [])
        # Enrich LLM sources with file/line info from our citations.
        enriched = []
        for ls in llm_sources:
            sym = ls.get("symbol", "")
            match = next((c for c in citations if c["symbol"] == sym or sym in c["symbol"]), None)
            if match:
                enriched.append({**match, "relevance": ls.get("relevance", "")})
            else:
                enriched.append({"symbol": sym, "relevance": ls.get("relevance", ""),
                                 "file_path": "", "line_start": 0, "line_end": 0, "snippet": ""})
        return {"answer": answer, "sources": enriched or citations, "generated_by": "llm"}
    except Exception as exc:
        logger.warning("ask_codebase_llm_failed", error=str(exc))
        return {"answer": "LLM 调用失败,以下是检索到的相关源码。", "sources": citations,
                "generated_by": "retrieval_only"}
