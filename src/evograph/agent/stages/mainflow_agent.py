"""MainFlowAgent — Stage 2: 跑通主线 (trace the main request flow).

Traces the primary execution path from entry points through the call graph,
then uses LLM to narrate each step in human-friendly language.
"""

from __future__ import annotations

from typing import Any

import structlog

from evograph.agent.base import BaseAgent

logger = structlog.get_logger()


MAINFLOW_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["flowNodes", "evidenceLinks"],
    "properties": {
        "flowNodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "note", "detail"],
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "note": {"type": "string"},
                    "detail": {
                        "type": "object",
                        "properties": {
                            "explanation": {"type": "string"},
                            "whatToLook": {"type": "string"},
                            "whyFirst": {"type": "string"},
                            "outcome": {"type": "string"},
                        },
                    },
                },
            },
        },
        "evidenceLinks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "githubUrl"],
                "properties": {
                    "label": {"type": "string"},
                    "githubUrl": {"type": "string"},
                },
            },
        },
    },
}


_SYSTEM = (
    "You are a code-flow analyst. Given a call chain and key file snippets, "
    "produce a step-by-step execution flow that a new reader can follow. "
    "Each node should explain WHAT happens, WHY it matters, and WHAT to look at. "
    "Keep it concrete — reference actual function names and files."
)


class MainFlowAgent(BaseAgent):
    """Stage 2 agent: trace and narrate the main request flow."""

    def __init__(self, tools: dict, llm_client: Any | None = None) -> None:
        super().__init__("mainflow", tools, llm_client)

    async def analyze(self, context: dict) -> dict:
        repo_url = context["repo_url"]
        entry_hints = context.get("_signals", {}).get("entry_points", [])

        call_graph = await self.call_tool(
            "trace_call_graph",
            repo_url=repo_url,
            entry_hint=entry_hints or None,
            max_depth=4,
            max_nodes=30,
        )

        key_files = call_graph.get("key_files", [])[:5]
        file_snippets: dict[str, str] = {}
        for f in key_files:
            try:
                data = await self.call_tool(
                    "fetch_file_content", repo_url=repo_url, file_path=f
                )
                file_snippets[f] = data.get("content", "")[:2000]
            except Exception:
                pass

        prompt = self._build_prompt(context, call_graph, file_snippets)

        try:
            result = await self.call_llm(
                prompt=prompt, system=_SYSTEM, json_schema=MAINFLOW_OUTPUT_SCHEMA
            )
        except Exception as e:
            logger.warning("mainflow_llm_failed", error=str(e))
            result = self._fallback(call_graph, repo_url)

        if isinstance(result, dict) and result.get("_parse_error"):
            result = self._fallback(call_graph, repo_url)

        self._enrich_urls(result, repo_url)
        return result

    def _build_prompt(
        self, context: dict, call_graph: dict, file_snippets: dict[str, str]
    ) -> str:
        arch_summary = context.get("architectureSummary", "")
        chain = call_graph.get("call_chain", [])
        entries = call_graph.get("entry_points", [])

        snippets_text = ""
        for path, content in file_snippets.items():
            snippets_text += f"\n--- {path} ---\n{content[:1500]}\n"

        return (
            f"ARCHITECTURE CONTEXT:\n{arch_summary}\n\n"
            f"ENTRY POINTS: {entries}\n\n"
            f"CALL CHAIN ({len(chain)} nodes):\n"
            + "\n".join(
                f"  depth={n['depth']} {n['function']} ({n['file']})"
                for n in chain[:20]
            )
            + f"\n\nKEY FILE SNIPPETS:\n{snippets_text}\n\n"
            "Produce 5-8 flowNodes that narrate the main request path. "
            "Each node should map to a real function/file from the call chain. "
            "Also produce evidenceLinks pointing to the key files."
        )

    def _fallback(self, call_graph: dict, repo_url: str) -> dict:
        chain = call_graph.get("call_chain", [])
        nodes = []
        for i, node in enumerate(chain[:8]):
            nodes.append({
                "id": i + 1,
                "title": node["function"],
                "note": f"Depth {node['depth']} in {node['file']}",
                "detail": {
                    "explanation": f"Calls {node['function']} at depth {node['depth']}",
                    "whatToLook": node["file"],
                    "whyFirst": "Part of main execution path",
                    "outcome": "Continues to next step",
                },
            })
        links = [
            {"label": f, "githubUrl": _gh_url(repo_url, f)}
            for f in call_graph.get("key_files", [])[:5]
        ]
        return {"flowNodes": nodes, "evidenceLinks": links}

    def _enrich_urls(self, result: dict, repo_url: str) -> None:
        for link in result.get("evidenceLinks", []):
            if not link.get("githubUrl", "").startswith("http"):
                link["githubUrl"] = _gh_url(repo_url, link.get("label", ""))


def _gh_url(repo_url: str, path: str) -> str:
    base = repo_url.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/blob/HEAD/{path}"
