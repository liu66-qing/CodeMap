"""ShowcaseAgent — Stage 3: 拆它绝活 (identify design highlights).

Detects design patterns and surfaces 3 highlights with problem/solution/tradeoff
analysis grounded in actual code evidence.
"""

from __future__ import annotations

from typing import Any

import structlog

from evograph.agent.base import BaseAgent

logger = structlog.get_logger()


SHOWCASE_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["highlights"],
    "properties": {
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "problem", "solution", "tradeoff", "evidence"],
                "properties": {
                    "title": {"type": "string"},
                    "problem": {"type": "string"},
                    "solution": {"type": "string"},
                    "tradeoff": {"type": "string"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "snippet": {"type": "string"},
                            "githubUrl": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
}


_SYSTEM = (
    "You are a senior software engineer extracting design highlights from a codebase. "
    "Given detected patterns and code snippets, you pick the 3 most interesting design "
    "decisions and explain each as: the problem it solves, the solution chosen, the "
    "tradeoff accepted, and concrete code evidence. Be specific and grounded — quote "
    "real symbols, not abstract claims."
)


class ShowcaseAgent(BaseAgent):
    """Stage 3 agent: identify design highlights with tradeoff analysis."""

    def __init__(self, tools: dict, llm_client: Any | None = None) -> None:
        super().__init__("showcase", tools, llm_client)

    async def analyze(self, context: dict) -> dict:
        repo_url = context["repo_url"]

        tree = await self.call_tool("fetch_repo_tree", repo_url=repo_url)
        code_files = [
            f
            for f in tree.get("files", [])
            if any(f.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".go", ".java"))
        ][:30]

        # Fetch sample file contents
        file_contents: dict[str, str] = {}
        for f in code_files[:15]:
            try:
                data = await self.call_tool(
                    "fetch_file_content", repo_url=repo_url, file_path=f
                )
                file_contents[f] = data.get("content", "")[:3000]
            except Exception:
                pass

        # Detect patterns
        patterns_data = await self.call_tool(
            "match_patterns", file_contents=file_contents
        )

        prompt = self._build_prompt(context, patterns_data, file_contents)

        try:
            result = await self.call_llm(
                prompt=prompt, system=_SYSTEM, json_schema=SHOWCASE_OUTPUT_SCHEMA
            )
        except Exception as e:
            logger.warning("showcase_llm_failed", error=str(e))
            result = self._fallback(patterns_data, repo_url)

        if isinstance(result, dict) and result.get("_parse_error"):
            result = self._fallback(patterns_data, repo_url)

        self._enrich_urls(result, repo_url)
        return result

    def _build_prompt(
        self, context: dict, patterns_data: dict, file_contents: dict[str, str]
    ) -> str:
        arch_summary = context.get("architectureSummary", "")
        flow_nodes = context.get("flowNodes", [])
        patterns = patterns_data.get("patterns", [])[:5]

        snippets_text = ""
        for path, content in list(file_contents.items())[:6]:
            snippets_text += f"\n--- {path} ---\n{content[:1200]}\n"

        return (
            f"ARCHITECTURE: {arch_summary}\n\n"
            f"MAIN FLOW (from previous stage): "
            f"{[n.get('title', '') for n in flow_nodes[:6]]}\n\n"
            f"DETECTED PATTERNS:\n"
            + "\n".join(
                f"- {p['name']} (confidence={p['confidence']}, files={p['files_involved']}): "
                f"{p['description']}\n  Examples: {[m['file'] + ':' + str(m['line']) for m in p['matches'][:2]]}"
                for p in patterns
            )
            + f"\n\nFILE SNIPPETS:\n{snippets_text}\n\n"
            "Pick the 3 most interesting design highlights. For each, provide problem, "
            "solution, tradeoff, and concrete evidence (file path + snippet)."
        )

    def _fallback(self, patterns_data: dict, repo_url: str) -> dict:
        highlights = []
        for p in patterns_data.get("patterns", [])[:3]:
            ev_match = p["matches"][0] if p["matches"] else {}
            highlights.append({
                "title": f"{p['name'].title()} pattern",
                "problem": "See pattern description",
                "solution": p["description"],
                "tradeoff": "Standard pattern tradeoffs apply",
                "evidence": {
                    "file": ev_match.get("file", ""),
                    "snippet": ev_match.get("snippet", ""),
                    "githubUrl": _gh_url(repo_url, ev_match.get("file", "")),
                },
            })
        return {"highlights": highlights}

    def _enrich_urls(self, result: dict, repo_url: str) -> None:
        for h in result.get("highlights", []):
            ev = h.get("evidence", {})
            if ev.get("file") and not ev.get("githubUrl", "").startswith("http"):
                ev["githubUrl"] = _gh_url(repo_url, ev["file"])


def _gh_url(repo_url: str, path: str) -> str:
    base = repo_url.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/blob/HEAD/{path}"
