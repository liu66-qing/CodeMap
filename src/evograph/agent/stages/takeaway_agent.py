"""TakeawayAgent — Stage 4: 抄走一招 (extract reusable patterns).

Distills design highlights into 2-3 reusable patterns with applicable scenarios,
core ideas, minimal example code, and limitations.
"""

from __future__ import annotations

from typing import Any

import structlog

from evograph.agent.base import BaseAgent

logger = structlog.get_logger()


TAKEAWAY_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["patterns"],
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "scenario", "coreIdea", "minimalCode", "limitations"],
                "properties": {
                    "name": {"type": "string"},
                    "scenario": {"type": "string", "description": "When to apply"},
                    "coreIdea": {"type": "string"},
                    "minimalCode": {
                        "type": "object",
                        "properties": {
                            "language": {"type": "string"},
                            "code": {"type": "string"},
                        },
                    },
                    "limitations": {"type": "string"},
                    "sourceHighlight": {
                        "type": "string",
                        "description": "Title of the highlight this pattern came from",
                    },
                },
            },
        }
    },
}


_SYSTEM = (
    "You are a pragmatic engineer who teaches by example. Given design highlights "
    "from a codebase, you distill 2-3 reusable patterns. For each, you state the "
    "scenario where it applies, the core idea in plain language, a minimal "
    "stand-alone code snippet (10-30 lines, runnable), and the honest limitations. "
    "The minimal code must be self-contained — no external dependencies on the "
    "source project."
)


class TakeawayAgent(BaseAgent):
    """Stage 4 agent: extract reusable patterns from highlights."""

    def __init__(self, tools: dict, llm_client: Any | None = None) -> None:
        super().__init__("takeaway", tools, llm_client)

    async def analyze(self, context: dict) -> dict:
        highlights = context.get("highlights", [])
        if not highlights:
            return {"patterns": []}

        prompt = self._build_prompt(context, highlights)

        try:
            result = await self.call_llm(
                prompt=prompt, system=_SYSTEM, json_schema=TAKEAWAY_OUTPUT_SCHEMA
            )
        except Exception as e:
            logger.warning("takeaway_llm_failed", error=str(e))
            result = self._fallback(highlights)

        if isinstance(result, dict) and result.get("_parse_error"):
            result = self._fallback(highlights)

        return result

    def _build_prompt(self, context: dict, highlights: list[dict]) -> str:
        arch_summary = context.get("architectureSummary", "")
        languages = context.get("_signals", {}).get("languages", []) or ["python"]
        primary_lang = languages[0] if languages else "python"

        h_text = ""
        for i, h in enumerate(highlights[:3]):
            ev = h.get("evidence", {})
            h_text += (
                f"\n[Highlight {i+1}: {h.get('title', '')}]\n"
                f"  Problem: {h.get('problem', '')}\n"
                f"  Solution: {h.get('solution', '')}\n"
                f"  Tradeoff: {h.get('tradeoff', '')}\n"
                f"  Evidence: {ev.get('file', '')}\n"
                f"  Snippet: {ev.get('snippet', '')[:400]}\n"
            )

        return (
            f"ARCHITECTURE CONTEXT: {arch_summary}\n"
            f"PRIMARY LANGUAGE: {primary_lang}\n\n"
            f"DESIGN HIGHLIGHTS:\n{h_text}\n\n"
            "Distill 2-3 reusable patterns. For each, prefer minimal code in "
            f"{primary_lang} (or pseudocode if no clear language fits). Each "
            "minimalCode.code should be 10-30 lines, self-contained, and copy-pastable. "
            "Limitations should be honest — when NOT to use this pattern."
        )

    def _fallback(self, highlights: list[dict]) -> dict:
        patterns = []
        for h in highlights[:2]:
            patterns.append({
                "name": h.get("title", "Pattern"),
                "scenario": h.get("problem", ""),
                "coreIdea": h.get("solution", ""),
                "minimalCode": {
                    "language": "python",
                    "code": "# Minimal example unavailable (LLM fallback)\n# See evidence in source repo.",
                },
                "limitations": h.get("tradeoff", ""),
                "sourceHighlight": h.get("title", ""),
            })
        return {"patterns": patterns}
