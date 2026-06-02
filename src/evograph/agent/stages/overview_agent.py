"""OverviewAgent — Stage 1: 先看门道 (positioning + mental model + reading order).

Generates a one-sentence positioning, core problem, mental model triplet, and
a recommended reading order. Output feeds downstream agents via `architectureSummary`.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from evograph.agent.base import BaseAgent

logger = structlog.get_logger()


OVERVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "positioning",
        "coreProblem",
        "mentalModel",
        "readingOrder",
        "architectureSummary",
    ],
    "properties": {
        "positioning": {"type": "string", "description": "One-sentence positioning"},
        "coreProblem": {"type": "string", "description": "The core problem the repo solves"},
        "mentalModel": {
            "type": "object",
            "required": ["whatIsIt", "whoIsItFor", "howItWorks"],
            "properties": {
                "whatIsIt": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
                "whoIsItFor": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
                "howItWorks": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        },
        "readingOrder": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["step", "title", "description", "githubUrl"],
                "properties": {
                    "step": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "githubUrl": {"type": "string"},
                },
            },
        },
        "architectureSummary": {
            "type": "string",
            "description": "Compact architecture summary passed to downstream agents",
        },
    },
}


_SYSTEM = (
    "You are a senior code-comprehension expert. Given raw signals about a repository "
    "(README, file tree, parsed code structure, detected architecture), you produce a "
    "structured overview that helps a new reader form an accurate mental model fast. "
    "Be concrete and specific to THIS repo. No generic platitudes. Keep prose tight."
)


class OverviewAgent(BaseAgent):
    """Stage 1 agent: positioning + mental model + reading order."""

    def __init__(self, tools: dict, llm_client: Any | None = None) -> None:
        super().__init__("overview", tools, llm_client)

    async def analyze(self, context: dict) -> dict:
        repo_url = context["repo_url"]

        tree = await self.call_tool("fetch_repo_tree", repo_url=repo_url)
        readme = await self.call_tool("fetch_readme", repo_url=repo_url)
        readme_summary = await self.call_tool(
            "readme_summarizer", content=readme.get("content", "")
        )

        # Parse a sample of code files
        code_files = [
            f
            for f in tree.get("files", [])
            if any(f.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".go", ".java"))
        ][:25]
        structure = await self.call_tool(
            "parse_code_structure", repo_url=repo_url, files=code_files
        )

        # Detect architecture
        arch = await self.call_tool(
            "detect_architecture",
            files=tree.get("files", []),
            directories=tree.get("directories", []),
            imports=structure.get("imports", []),
        )

        prompt = self._build_prompt(repo_url, tree, readme_summary, structure, arch)

        try:
            llm_out = await self.call_llm(
                prompt=prompt, system=_SYSTEM, json_schema=OVERVIEW_OUTPUT_SCHEMA
            )
        except Exception as e:
            logger.warning("overview_llm_failed", error=str(e))
            llm_out = self._fallback(repo_url, tree, readme_summary, arch)

        if isinstance(llm_out, dict) and llm_out.get("_parse_error"):
            llm_out = self._fallback(repo_url, tree, readme_summary, arch)

        result = self._normalize(llm_out, repo_url, arch, structure)
        return result

    def _build_prompt(
        self,
        repo_url: str,
        tree: dict,
        readme_summary: dict,
        structure: dict,
        arch: dict,
    ) -> str:
        readme_excerpt = readme_summary.get("title", "") + "\n" + readme_summary.get("tagline", "")
        features = readme_summary.get("features", [])
        sections = readme_summary.get("sections", [])
        languages = tree.get("languages", [])
        layers = arch.get("layers", [])
        patterns = arch.get("patterns", [])
        entry_points = structure.get("entry_points", [])
        top_dirs = tree.get("directories", [])[:25]
        top_files = tree.get("files", [])[:60]

        return (
            f"REPO URL: {repo_url}\n"
            f"LANGUAGES: {languages}\n"
            f"TOTAL FILES: {tree.get('total_files', 0)}\n\n"
            f"README TITLE: {readme_summary.get('title', '')}\n"
            f"README TAGLINE: {readme_summary.get('tagline', '')}\n"
            f"README SECTIONS: {sections}\n"
            f"DECLARED FEATURES: {features}\n"
            f"TECH KEYWORDS: {readme_summary.get('tech_keywords', [])}\n\n"
            f"DETECTED ARCHITECTURE STYLE: {arch.get('style', 'unknown')}\n"
            f"LAYERS: {[l['name'] for l in layers]}\n"
            f"PATTERNS: {[p['name'] for p in patterns]}\n"
            f"ENTRY POINTS: {entry_points}\n\n"
            f"TOP DIRECTORIES: {top_dirs}\n"
            f"TOP FILES (sample): {top_files}\n\n"
            "Produce the overview JSON. The `readingOrder` should reference 4-6 actual files "
            "from this repo (use TOP FILES) in the order a new reader should explore them. "
            "Each githubUrl must be the repo URL plus '/blob/HEAD/' plus the file path. "
            "`architectureSummary` should be a single dense paragraph capturing the style, "
            "key layers, and entry points — downstream agents will read it."
        )

    def _fallback(
        self, repo_url: str, tree: dict, readme_summary: dict, arch: dict
    ) -> dict:
        title = readme_summary.get("title", "this repository")
        tagline = readme_summary.get("tagline", "")
        style = arch.get("style", "unknown")
        layer_names = [l["name"] for l in arch.get("layers", [])]
        return {
            "positioning": tagline or f"{title} — a {style} codebase.",
            "coreProblem": "Could not infer core problem from README.",
            "mentalModel": {
                "whatIsIt": {"title": "What is it", "description": tagline or title},
                "whoIsItFor": {"title": "Who is it for", "description": "Inferred from README sections"},
                "howItWorks": {
                    "title": "How it works",
                    "description": f"Architecture style: {style}; layers: {', '.join(layer_names)}",
                },
            },
            "readingOrder": [
                {
                    "step": i + 1,
                    "title": f"Read {f}",
                    "description": "Auto-suggested entry file.",
                    "githubUrl": _gh_url(repo_url, f),
                }
                for i, f in enumerate(tree.get("files", [])[:5])
            ],
            "architectureSummary": arch.get("summary", ""),
        }

    def _normalize(
        self, out: dict, repo_url: str, arch: dict, structure: dict
    ) -> dict:
        # Ensure required keys exist
        out.setdefault("positioning", "")
        out.setdefault("coreProblem", "")
        out.setdefault("mentalModel", {})
        out.setdefault("readingOrder", [])
        out.setdefault(
            "architectureSummary", arch.get("summary", "")
        )
        # Tag githubUrl if LLM omitted them
        for item in out.get("readingOrder", []):
            if not item.get("githubUrl") and item.get("title"):
                item["githubUrl"] = _gh_url(repo_url, item["title"])
        # Enrich for downstream agents (not in schema, but useful)
        out["_signals"] = {
            "entry_points": structure.get("entry_points", []),
            "architecture_style": arch.get("style", ""),
            "layers": [l["name"] for l in arch.get("layers", [])],
        }
        return out


def _gh_url(repo_url: str, path: str) -> str:
    base = repo_url.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/blob/HEAD/{path}"
