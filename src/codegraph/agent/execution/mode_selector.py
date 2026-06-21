"""Automatic execution mode selection based on query complexity analysis.

Selection heuristics:
- ReAct: single-hop, factual lookup, <=2 entities, clear tool match
- Plan-Execute: multi-hop, analysis, comparison, 3+ entities, no single tool fits

This avoids overhead of planning for simple queries while ensuring complex ones
get proper decomposition. The selector itself is cheap (~100 tokens LLM call
only for ambiguous cases; most queries resolved by heuristics alone).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class ExecutionMode(str, Enum):
    REACT = "react"
    PLAN_EXECUTE = "plan_execute"


@dataclass
class ModeDecision:
    mode: ExecutionMode
    confidence: float
    reasoning: str
    complexity_signals: dict[str, Any]


class ExecutionModeSelector:
    """Selects execution mode based on query complexity signals.

    Fast heuristic path handles ~80% of queries without an LLM call.
    Only ambiguous cases (score 0.3-0.7) fall through to optional LLM tiebreaker.
    """

    # Heuristic thresholds (no LLM call needed for clear cases)
    PLAN_KEYWORDS = frozenset({
        "compare", "analyze", "how does", "trace", "relationship",
        "between", "all", "every", "architecture", "dependencies",
    })
    REACT_KEYWORDS = frozenset({
        "what is", "where is", "find", "show", "get", "which file",
    })

    def __init__(self, llm_client: Any = None):
        self._llm = llm_client

    async def select(
        self, query: str, available_tools: list[str] | None = None
    ) -> ModeDecision:
        """Determine best execution mode for query."""
        signals = self._analyze_complexity(query)

        # Fast path: clear heuristic match
        if signals["complexity_score"] <= 0.3:
            return ModeDecision(
                mode=ExecutionMode.REACT,
                confidence=0.9,
                reasoning="Simple query, single-hop retrieval sufficient",
                complexity_signals=signals,
            )

        if signals["complexity_score"] >= 0.7:
            return ModeDecision(
                mode=ExecutionMode.PLAN_EXECUTE,
                confidence=0.9,
                reasoning="Complex multi-hop query requires decomposition",
                complexity_signals=signals,
            )

        # Ambiguous: use LLM to decide (if available)
        if self._llm:
            return await self._llm_decide(query, signals)

        # Default: Plan-Execute for ambiguous (safer -- over-planning is cheaper than under-planning)
        return ModeDecision(
            mode=ExecutionMode.PLAN_EXECUTE,
            confidence=0.6,
            reasoning="Ambiguous complexity, defaulting to Plan-Execute",
            complexity_signals=signals,
        )

    def _analyze_complexity(self, query: str) -> dict[str, Any]:
        """Compute complexity signals from query text.

        Returns a dict of normalized signals (0-1) plus a weighted composite score.
        """
        query_lower = query.lower()
        words = query_lower.split()

        # Signal 1: query length (longer queries tend to be more complex)
        length_signal = min(1.0, len(words) / 30)

        # Signal 2: keyword matching (plan vs react indicators)
        plan_matches = sum(1 for kw in self.PLAN_KEYWORDS if kw in query_lower)
        react_matches = sum(1 for kw in self.REACT_KEYWORDS if kw in query_lower)
        keyword_signal = (plan_matches - react_matches) / max(plan_matches + react_matches, 1)

        # Signal 3: entity count (quoted strings, CamelCase, dotted paths, backtick refs)
        entities = re.findall(
            r'[A-Z][a-z]+[A-Z]|"[^"]+"|\b\w+\.\w+\b|`[^`]+`', query
        )
        entity_signal = min(1.0, len(entities) / 5)

        # Signal 4: question complexity (sub-questions, conjunctions)
        conjunctions = sum(
            1 for w in ["and", "or", "then", "also", "both"] if w in words
        )
        conjunction_signal = min(1.0, conjunctions / 3)

        # Weighted composite
        complexity_score = (
            length_signal * 0.2
            + (keyword_signal + 1) / 2 * 0.3  # Normalize keyword_signal to 0-1
            + entity_signal * 0.3
            + conjunction_signal * 0.2
        )

        return {
            "complexity_score": round(complexity_score, 3),
            "length_signal": round(length_signal, 3),
            "keyword_signal": round(keyword_signal, 3),
            "entity_signal": round(entity_signal, 3),
            "conjunction_signal": round(conjunction_signal, 3),
            "entity_count": len(entities),
        }

    async def _llm_decide(self, query: str, signals: dict) -> ModeDecision:
        """Use LLM for ambiguous cases (~20% of queries reach here)."""
        prompt = f"""Classify this query's execution complexity:
Query: {query}
Signals: {signals}

Reply with ONLY "react" or "plan_execute" and one sentence why."""

        response = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        # Handle both string and dict response formats
        if isinstance(response, dict):
            content = response.get("content", "").lower()
        else:
            content = str(response).lower()

        mode = ExecutionMode.PLAN_EXECUTE if "plan" in content else ExecutionMode.REACT

        logger.info(
            "mode_selected_by_llm",
            mode=mode.value,
            reasoning=content[:100],
        )

        return ModeDecision(
            mode=mode,
            confidence=0.75,
            reasoning=content,
            complexity_signals=signals,
        )
